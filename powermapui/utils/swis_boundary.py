"""
Shared helpers for the editable SWIS boundary polygon.

Used by:
  - siren_web/migrations/0173* (seed the SwisBoundary row)
  - powermapui/views/map_views.py (serve / persist the boundary)
  - powermapui/views/ev_boundary_views.py (read-only reference on the map)
  - siren_web/management/commands/derive_swis_boundary_membership.py
  - powermapui/utils/swis_membership_service.py

The stored source of truth is the ``SwisBoundary`` DB row. A committed
GeoJSON file (``siren_web/static/geojson/swis_boundary.geojson``) seeds that
row on a fresh database and acts as a last-resort fallback. No KML.

Deliberately free of module-level Django-model imports so a migration can
import it. Only shapely is used (no GDAL).
"""
import json
from pathlib import Path

from django.conf import settings


def default_boundary_geojson_path() -> Path:
    return Path(settings.BASE_DIR) / 'siren_web' / 'static' / 'geojson' / 'swis_boundary.geojson'


def boundary_geometry_from_file(path=None) -> dict:
    """Load the committed GeoJSON and return its geometry dict.

    Accepts a bare geometry, a Feature, or a single-feature FeatureCollection.
    """
    path = Path(path) if path else default_boundary_geojson_path()
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('type') == 'FeatureCollection':
        data = data['features'][0]
    if data.get('type') == 'Feature':
        data = data['geometry']
    return data


def geojson_to_shapely(geojson: dict):
    """shapely geometry from a GeoJSON dict, repaired with buffer(0) if invalid."""
    from shapely.geometry import shape

    geom = shape(geojson)
    if not geom.is_valid:
        geom = geom.buffer(0)
    return geom


def polygon_vertex_count(geojson: dict) -> int:
    """Total vertices across all rings of a GeoJSON Polygon/MultiPolygon."""
    gtype = geojson.get('type')
    coords = geojson.get('coordinates', [])
    if gtype == 'Polygon':
        return sum(len(ring) for ring in coords)
    if gtype == 'MultiPolygon':
        return sum(len(ring) for poly in coords for ring in poly)
    return 0


def load_swis_polygon(file_override=None):
    """The current SWIS polygon as a shapely geometry.

    Prefers the editable ``SwisBoundary`` DB row; falls back to the committed
    GeoJSON file (or ``file_override`` when given). ``file_override`` forces
    the file source.
    """
    if file_override:
        return geojson_to_shapely(boundary_geometry_from_file(file_override))

    try:
        from siren_web.models import SwisBoundary
        row = SwisBoundary.get_solo()
    except Exception:
        row = None

    if row and row.geojson:
        try:
            return geojson_to_shapely(json.loads(row.geojson))
        except Exception:
            pass
    return geojson_to_shapely(boundary_geometry_from_file())


def swis_boundary_geojson_str() -> str:
    """GeoJSON geometry string for templates: DB row, else committed file, else 'null'."""
    try:
        from siren_web.models import SwisBoundary
        row = SwisBoundary.get_solo()
        if row and row.geojson:
            return row.geojson
    except Exception:
        pass
    try:
        return json.dumps(boundary_geometry_from_file())
    except Exception:
        return 'null'
