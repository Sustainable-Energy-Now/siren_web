# siren_web/management/commands/derive_swis_boundary_membership.py
"""
FR-04/05 (D9) — derive SwisBoundaryMembership (and PostcodeBoundary geometry)
from the SWIS boundary polygon and ABS Postal Area (POA 2021) boundaries.

SWIS polygon source (in priority order):
  1. --boundary-file PATH   explicit GeoJSON file (forces the file source)
  2. the editable SwisBoundary DB row (seeded from the committed GeoJSON,
     then hand-edited on the grid map)
  3. siren_web/static/geojson/swis_boundary.geojson

POA boundaries:
  --poa-shapefile PATH   ABS POA_2021_AUST_*.shp; defaults to
                         settings.POA_SHAPEFILE_PATH
                         (siren_web/siren_files/gis/ — see that dir's README).

Classification rule and the shared walk live in
powermapui.utils.swis_membership_service. Only pip-installable, no-GDAL
libraries are used (shapely + pyshp).
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from powermapui.utils.swis_boundary import load_swis_polygon
from powermapui.utils.swis_membership_service import derive_membership


class Command(BaseCommand):
    help = "Derive SwisBoundaryMembership + PostcodeBoundary (FR-04/05, D9) from the SWIS boundary and ABS POA shapefile"

    def add_arguments(self, parser):
        parser.add_argument('--boundary-file', type=str, default=None,
                            help='Force the SWIS polygon from this GeoJSON file instead of the SwisBoundary DB row')
        parser.add_argument('--poa-shapefile', type=str, default=None,
                            help='Path to ABS POA_2021_AUST_*.shp (default: settings.POA_SHAPEFILE_PATH)')
        parser.add_argument('--state-prefix', type=str, default='6',
                            help="Only process POA codes starting with this prefix (default '6' for WA)")
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        try:
            import shapefile  # noqa: F401
            import shapely  # noqa: F401
        except ImportError as e:
            self.stdout.write(self.style.ERROR(f"Missing dependency: {e}. Run: pip install shapely pyshp"))
            return

        poa_path = Path(options['poa_shapefile']) if options['poa_shapefile'] else Path(settings.POA_SHAPEFILE_PATH)
        if not poa_path.exists():
            self.stdout.write(self.style.ERROR(
                f"POA shapefile not found: {poa_path}\n"
                f"Download the ABS POA 2021 boundaries — see {Path(settings.GIS_DATA_DIR) / 'README.md'}"
            ))
            return

        swis_polygon = load_swis_polygon(file_override=options['boundary_file'])
        if not swis_polygon.is_valid:
            swis_polygon = swis_polygon.buffer(0)
        if not swis_polygon.is_valid:
            self.stdout.write(self.style.ERROR('SWIS boundary polygon is invalid even after buffer(0) repair'))
            return

        # Report the source that was actually used.
        if options['boundary_file']:
            src_desc = f"GeoJSON file {options['boundary_file']}"
        else:
            from siren_web.models import SwisBoundary
            row = SwisBoundary.get_solo()
            src_desc = (f"SwisBoundary DB row ({row.source}, {row.vertex_count} vertices, updated {row.updated_at:%Y-%m-%d %H:%M})"
                        if row else "committed swis_boundary.geojson (no DB row)")
        self.stdout.write(f"SWIS polygon: {src_desc}")
        self.stdout.write(f"POA shapefile: {poa_path}")

        dry_run = options['dry_run']
        result = derive_membership(
            swis_polygon, poa_path,
            state_prefix=options['state_prefix'],
            dry_run=dry_run,
            log=(self.stdout.write if dry_run else None),
        )

        self.stdout.write('\n' + '=' * 60)
        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run — nothing written.'))
        else:
            self.stdout.write(self.style.SUCCESS(f"Created: {result['created']}   Updated: {result['updated']}"))
        self.stdout.write(
            f"Status counts: in={result['in']}  out={result['out']}  partial={result['partial']}  "
            f"skipped(invalid geometry)={result['skipped_invalid']}  "
            f"skipped(non-numeric POA code)={result['skipped_non_numeric']}"
        )
        self.stdout.write('=' * 60)
