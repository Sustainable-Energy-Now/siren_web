"""
Geospatial derivation of SwisBoundaryMembership + PostcodeBoundary from a
SWIS boundary polygon and ABS Postal Area (POA 2021) boundaries.

Shared by the ``derive_swis_boundary_membership`` management command and the
"Recompute all from geometry" button on the SWIS boundary map.

Classification: fraction of each postcode polygon's AREA inside the SWIS
polygon (a pure centroid test can never yield 'partial').
  - fraction >= IN_THRESHOLD   -> 'in'
  - fraction <= OUT_THRESHOLD  -> 'out'
  - otherwise                  -> 'partial'
The thresholds absorb GIS noise from the SWIS coastline and the ABS POA
coastline being two independently-drawn vectors (coastal postcodes come
back ~99.9% inside, not exactly 100%).

Only pip-installable, no-GDAL libraries are used (shapely + pyshp).
"""
import json
import math

IN_THRESHOLD = 0.99
OUT_THRESHOLD = 0.01

# ABS POA 2021 field name, and the WGS84 mean-earth radius for the rough
# planar-degrees -> km^2 area conversion (postcode-scale, good to a few %).
POA_CODE_FIELD = 'POA_CODE21'
_DEG_KM = math.pi * 6371.0088 / 180.0  # km per degree of latitude


def _area_sqkm(geom) -> float:
    """Rough area in km^2 from a lon/lat shapely geometry."""
    if geom.is_empty:
        return 0.0
    lat = geom.centroid.y
    return geom.area * _DEG_KM * (_DEG_KM * math.cos(math.radians(lat)))


def derive_membership(swis_polygon, poa_shapefile_path, state_prefix='6',
                      simplify_tolerance=0.001, dry_run=False, log=None):
    """Walk the POA shapefile, classify each postcode, and (unless dry_run)
    upsert SwisBoundaryMembership + PostcodeBoundary.

    Returns a summary dict:
        {'in': n, 'out': n, 'partial': n,
         'created': n, 'updated': n,
         'skipped_invalid': n, 'skipped_non_numeric': n,
         'rows': [ {postcode, status, frac_in}, ... ]}   # rows only on dry_run
    """
    import shapefile
    from shapely.geometry import shape as shapely_shape, mapping as shapely_mapping

    from siren_web.models import SwisBoundaryMembership, PostcodeBoundary

    if not swis_polygon.is_valid:
        swis_polygon = swis_polygon.buffer(0)

    sf = shapefile.Reader(str(poa_shapefile_path))

    counts = {'in': 0, 'out': 0, 'partial': 0}
    created = updated = skipped_invalid = skipped_non_numeric = 0
    rows = []

    for i, rec in enumerate(sf.records()):
        postcode = str(rec[POA_CODE_FIELD])
        if not postcode.startswith(state_prefix):
            continue
        # ABS uses sentinel POA codes (e.g. 'ZZZZ') for no-postcode areas.
        if not postcode.isdigit():
            skipped_non_numeric += 1
            continue

        postcode_geom = shapely_shape(sf.shape(i).__geo_interface__)
        if not postcode_geom.is_valid:
            postcode_geom = postcode_geom.buffer(0)
        if not postcode_geom.is_valid or postcode_geom.is_empty:
            skipped_invalid += 1
            continue

        centroid = postcode_geom.centroid
        frac_in = (postcode_geom.intersection(swis_polygon).area / postcode_geom.area
                   if postcode_geom.area else 0.0)
        # The ratio is two independent GEOS area computations, so a fully-in /
        # fully-out postcode lands a rounding epsilon off 1.0 / 0.0 (e.g.
        # 1.0000000000000002). Snap that noise away and clamp to [0, 1] —
        # anything genuinely on the boundary is percent-level, not 1e-9.
        if frac_in > 1.0 - 1e-9:
            frac_in = 1.0
        elif frac_in < 1e-9:
            frac_in = 0.0
        else:
            frac_in = min(1.0, max(0.0, frac_in))
        if frac_in >= IN_THRESHOLD:
            status = 'in'
        elif frac_in <= OUT_THRESHOLD:
            status = 'out'
        else:
            status = 'partial'
        counts[status] += 1

        if log:
            log(f"  {postcode}: {status} ({frac_in * 100:.2f}% in-SWIS area)")
        if dry_run:
            rows.append({'postcode': postcode, 'status': status, 'frac_in': frac_in})
            continue

        note = (
            f'Derived from SWIS boundary + ABS POA 2021 (area-fraction test, '
            f'{frac_in * 100:.2f}% in-SWIS).'
            if status != 'partial' else
            f'Derived: postcode polygon straddles the SWIS boundary — '
            f'{frac_in * 100:.2f}% of its area falls inside SWIS.'
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

        simplified = postcode_geom.simplify(simplify_tolerance, preserve_topology=True)
        if simplified.is_empty:
            simplified = postcode_geom
        PostcodeBoundary.objects.update_or_create(
            postcode=postcode,
            defaults={
                'geojson': json.dumps(shapely_mapping(simplified)),
                'centroid_lat': centroid.y,
                'centroid_lon': centroid.x,
                'area_sqkm': _area_sqkm(postcode_geom),
                'source': 'ABS POA 2021',
            },
        )

    return {
        **counts,
        'created': created,
        'updated': updated,
        'skipped_invalid': skipped_invalid,
        'skipped_non_numeric': skipped_non_numeric,
        'rows': rows,
    }
