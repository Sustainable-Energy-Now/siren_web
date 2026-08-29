# siren_web/management/commands/derive_swis_boundary_membership.py
"""
FR-04/05 (D9) — derive SwisBoundaryMembership from a real SWIS boundary
polygon and ABS Postal Area (POA) boundaries, replacing the manual/CSV
CRUD path in powermapui/views/ev_boundary_views.py with a reproducible
geospatial derivation (FR-04's acceptance criterion: "reproducible
membership table").

Inputs:
  --swis-kml         A KML Polygon of the SWIS boundary (defaults to
                      siren_web/static/kml/SWIS_Boundary.kml).
  --poa-shapefile     ABS POA_2021_AUST_*.shp (ASGS Edition 3 digital
                      boundary files, WGS84/GDA2020 lon-lat — close enough
                      to the KML's WGS84 for this purpose; the GDA2020 vs
                      WGS84 datum difference is centimetre-scale, far
                      below postcode-polygon precision).

Classification rule: D9 specifies a "centroid-in-SWIS flag, with an
apportionment_fraction field reserved (unused this Sprint) for edge
postcodes" -- but FR-04's acceptance criterion requires postcodes to
genuinely land in three buckets (in/out/partial), which a pure centroid
test can never produce (a centroid is always on exactly one side). This
command resolves that by computing the fraction of each postcode
polygon's AREA that falls inside the SWIS polygon:
  - fraction >= IN_THRESHOLD    -> 'in'
  - fraction <= OUT_THRESHOLD   -> 'out'
  - otherwise                   -> 'partial'
A plain exact-containment test (postcode.within(swis)) was tried first
and rejected: coastal postcodes came back 'partial' at a ~99.9% in-SWIS
area fraction purely because the KML coastline and the ABS POA
coastline are two independently-drawn vectors that don't align to the
metre (a real GIS artefact, not a genuine SWIS/NWIS ambiguity) -- e.g.
6011/6015/6019/6020/6025/6518/6614 all sit at 99%+ inside. The threshold
version correctly separates that noise from real boundary-straddling
postcodes like 6612 (14% inside), 6620 (41%), 6630 (9%), out on the
Wheatbelt/Goldfields fringe -- the actual "edge postcode" case D9 cares
about. Since the overlap fraction is computed anyway to make this
distinction, apportionment_fraction is populated with the real value
(not left at the model's placeholder default) -- a bonus beyond D9's
"unused this Sprint" minimum, not a requirement of it.

Only pip-installable, no-GDAL-required libraries are used (shapely +
pyshp), avoiding a GDAL/Fiona/geopandas dependency on Windows.
"""
import xml.etree.ElementTree as ET
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from siren_web.models import SwisBoundaryMembership

KML_NS = {'kml': 'http://www.opengis.net/kml/2.2'}
IN_THRESHOLD = 0.99
OUT_THRESHOLD = 0.01


def _parse_ring(el):
    if el is None or not el.text:
        return None
    coords = []
    for token in el.text.strip().split():
        parts = token.split(',')
        coords.append((float(parts[0]), float(parts[1])))
    return coords


def parse_kml_polygon(kml_path: Path):
    from shapely.geometry import Polygon

    tree = ET.parse(kml_path)
    root = tree.getroot()
    placemark = root.find('.//kml:Placemark', KML_NS)
    if placemark is None:
        raise ValueError(f"No <Placemark> found in {kml_path}")
    polygon_el = placemark.find('.//kml:Polygon', KML_NS)
    if polygon_el is None:
        raise ValueError(f"No <Polygon> found in {kml_path}'s Placemark")

    outer = _parse_ring(polygon_el.find('kml:outerBoundaryIs/kml:LinearRing/kml:coordinates', KML_NS))
    if outer is None:
        raise ValueError(f"No outerBoundaryIs/LinearRing/coordinates found in {kml_path}")

    holes = []
    for inner_el in polygon_el.findall('kml:innerBoundaryIs', KML_NS):
        ring = _parse_ring(inner_el.find('kml:LinearRing/kml:coordinates', KML_NS))
        if ring:
            holes.append(ring)

    polygon = Polygon(outer, holes)
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    return polygon


class Command(BaseCommand):
    help = "Derive SwisBoundaryMembership (FR-04/05, D9) from a SWIS boundary KML and ABS POA shapefile"

    def add_arguments(self, parser):
        default_kml = Path(settings.BASE_DIR) / 'siren_web' / 'static' / 'kml' / 'SWIS_Boundary.kml'
        parser.add_argument('--swis-kml', type=str, default=str(default_kml))
        parser.add_argument('--poa-shapefile', type=str, required=True, help='Path to ABS POA_2021_AUST_*.shp')
        parser.add_argument(
            '--state-prefix', type=str, default='6',
            help="Only process POA codes starting with this prefix (default '6' for WA)",
        )
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        try:
            import shapefile
            from shapely.geometry import shape as shapely_shape
        except ImportError as e:
            self.stdout.write(self.style.ERROR(f"Missing dependency: {e}. Run: pip install shapely pyshp"))
            return

        swis_polygon = parse_kml_polygon(Path(options['swis_kml']))
        if not swis_polygon.is_valid:
            self.stdout.write(self.style.ERROR('SWIS boundary polygon is invalid even after buffer(0) repair'))
            return

        sf = shapefile.Reader(options['poa_shapefile'])
        prefix = options['state_prefix']
        dry_run = options['dry_run']

        created, updated, skipped_invalid, skipped_non_numeric = 0, 0, 0, 0
        counts = {'in': 0, 'out': 0, 'partial': 0}

        for i, rec in enumerate(sf.records()):
            postcode = rec['POA_CODE21']
            if not postcode.startswith(prefix):
                continue
            # ABS uses sentinel POA codes (e.g. 'ZZZZ') for no-postcode /
            # migratory areas; a real Australian postcode is always 4 digits.
            if not postcode.isdigit():
                skipped_non_numeric += 1
                continue

            shp = sf.shape(i)
            postcode_geom = shapely_shape(shp.__geo_interface__)
            if not postcode_geom.is_valid:
                postcode_geom = postcode_geom.buffer(0)
            if not postcode_geom.is_valid or postcode_geom.is_empty:
                skipped_invalid += 1
                continue

            centroid = postcode_geom.centroid
            frac_in = postcode_geom.intersection(swis_polygon).area / postcode_geom.area if postcode_geom.area else 0.0
            if frac_in >= IN_THRESHOLD:
                status = 'in'
            elif frac_in <= OUT_THRESHOLD:
                status = 'out'
            else:
                status = 'partial'
            counts[status] += 1

            if dry_run:
                self.stdout.write(f"  {postcode}: {status} ({frac_in*100:.2f}% in-SWIS area; centroid {centroid.y:.5f},{centroid.x:.5f})")
                continue

            note = (
                f'Derived from SWIS_Boundary.kml + ABS POA 2021 (D9, area-fraction test, {frac_in*100:.2f}% in-SWIS).'
                if status != 'partial' else
                f'Derived: postcode polygon straddles the SWIS boundary — {frac_in*100:.2f}% of its area falls inside SWIS.'
            )
            _, was_created = SwisBoundaryMembership.objects.update_or_create(
                postcode=postcode,
                defaults={
                    'membership_status': status,
                    'apportionment_fraction': frac_in,
                    'centroid_lat': centroid.y,
                    'centroid_lon': centroid.x,
                    'notes': note,
                },
            )
            created += 1 if was_created else 0
            updated += 0 if was_created else 1

        self.stdout.write('\n' + '=' * 60)
        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run — nothing written.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Created: {created}   Updated: {updated}'))
        self.stdout.write(
            f"Status counts: in={counts['in']}  out={counts['out']}  partial={counts['partial']}  "
            f"skipped(invalid geometry)={skipped_invalid}  skipped(non-numeric POA code)={skipped_non_numeric}"
        )
        self.stdout.write('=' * 60)
