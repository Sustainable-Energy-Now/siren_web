"""
Western Power GIS reconciliation for CEL stages.

Western Power publishes its *existing* network monthly on data.wa.gov.au
(SLIP).  Two layers say when CEL works have actually been built:

  WP-051  NCMT High Voltage Overhead Transmission Lines  — route + kV
  WP-049  NCMT Existing Substations/Terminals/Power Stations

A CEL stage's linked GridLines (CELStageGridLine) are "confirmed" when an
in-service line runs along the GridLine's KML route at or above its
voltage_level ('new' lines) or above it with the old-voltage line gone
('upgrade' lines, whose voltage_level is the pre-CEL rating); its 'new' terminals (CELStageTerminal) are confirmed
when an existing substation sits at the terminal's location.  Some
confirmed → the stage is at least under construction; all confirmed → it
is operational.  The layers carry no planned assets, so this can only
evidence completion — funding status and expected dates still come from
documents (cel_source_watcher).

The SLIP services need a (free) SLIP account: set SLIP_USERNAME /
SLIP_PASSWORD (env or [slip] in .django/secrets.toml), or download the
layers' GeoJSON by hand and pass the files.

Also here: reserved_capacity_mw derived from the facilities already aligned
to each stage that are under construction.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field

import requests
from django.conf import settings

from .cel_viability_service import _haversine_km, _point_to_segment_distance_km

SLIP_NCMT = ('https://services.slip.wa.gov.au/arcgis/rest/services/'
             'WP_Public_Secure_Services/NCMT_Public_Secure_Services/MapServer')
DEFAULT_LINES_URL = f'{SLIP_NCMT}/2'          # WP-051
DEFAULT_SUBSTATIONS_URL = f'{SLIP_NCMT}/0'    # WP-049
PAGE_SIZE = 1000
REQUEST_TIMEOUT = 90

LINE_TOLERANCE_KM = 1.0
TERMINAL_TOLERANCE_KM = 1.5
LINE_COVERAGE_REQUIRED = 0.8
ROUTE_SAMPLES = 12


class GisUnavailable(RuntimeError):
    """No credentials or file to read a layer from."""


# ---------------------------------------------------------------------------
# Layer loading
# ---------------------------------------------------------------------------

def slip_auth():
    user = getattr(settings, 'SLIP_USERNAME', '') or ''
    password = getattr(settings, 'SLIP_PASSWORD', '') or ''
    return (user, password) if user and password else None


def fetch_layer(layer_url: str, auth, session=None) -> list[dict]:
    """All features of an ArcGIS REST layer as GeoJSON features (WGS84),
    paging through the server's transfer limit."""
    getter = session or requests
    features, offset = [], 0
    while True:
        resp = getter.get(f'{layer_url}/query', auth=auth, timeout=REQUEST_TIMEOUT, params={
            'where': '1=1', 'outFields': '*', 'returnGeometry': 'true', 'outSR': 4326,
            'f': 'geojson', 'resultOffset': offset, 'resultRecordCount': PAGE_SIZE,
        })
        if resp.status_code == 401:
            raise GisUnavailable(f'SLIP refused the credentials for {layer_url} (HTTP 401).')
        resp.raise_for_status()
        payload = resp.json()
        if 'error' in payload:
            raise GisUnavailable(f"SLIP error for {layer_url}: {payload['error']}")
        page = payload.get('features') or []
        features.extend(page)
        more = payload.get('exceededTransferLimit') or (
            payload.get('properties') or {}).get('exceededTransferLimit')
        if not page or not more:
            return features
        offset += len(page)


def load_geojson_file(path: str) -> list[dict]:
    with open(path, encoding='utf-8') as fh:
        payload = json.load(fh)
    features = payload.get('features') if isinstance(payload, dict) else None
    if features is None:
        raise ValueError(f'{path} is not a GeoJSON FeatureCollection.')
    for f in features[:50]:
        pts = feature_points(f.get('geometry'))
        if pts and (abs(pts[0][0]) > 90 or abs(pts[0][1]) > 180):
            raise ValueError(f'{path} looks projected (e.g. MGA metres) — download it in GDA2020/WGS84 lat/lon.')
    return features


def load_layer(file_path: str | None, layer_url: str, session=None) -> list[dict]:
    if file_path:
        return load_geojson_file(file_path)
    auth = slip_auth()
    if auth is None:
        raise GisUnavailable(
            'No SLIP credentials: set SLIP_USERNAME / SLIP_PASSWORD (or [slip] username/password in '
            '.django/secrets.toml), or pass a downloaded GeoJSON file.')
    return fetch_layer(layer_url, auth, session=session)


# ---------------------------------------------------------------------------
# Feature helpers
# ---------------------------------------------------------------------------

def feature_points(geometry) -> list[tuple[float, float]]:
    """Every vertex of a GeoJSON geometry as (lat, lon)."""
    if not geometry:
        return []
    gtype, coords = geometry.get('type'), geometry.get('coordinates')
    if gtype == 'GeometryCollection':
        return [p for g in geometry.get('geometries') or [] for p in feature_points(g)]
    depth = {'Point': 0, 'MultiPoint': 1, 'LineString': 1, 'MultiLineString': 2,
             'Polygon': 2, 'MultiPolygon': 3}.get(gtype)
    if depth is None or coords is None:
        return []
    flat = [coords]
    for _ in range(depth):
        flat = [c for group in flat for c in group]
    return [(float(c[1]), float(c[0])) for c in flat]


def feature_paths(geometry) -> list[list[tuple[float, float]]]:
    """Polylines (lists of (lat, lon)) of a line geometry."""
    if not geometry:
        return []
    gtype, coords = geometry.get('type'), geometry.get('coordinates') or []
    if gtype == 'LineString':
        coords = [coords]
    elif gtype != 'MultiLineString':
        return []
    return [[(float(c[1]), float(c[0])) for c in path] for path in coords if len(path) >= 2]


_KV_KEY_RE = re.compile(r'volt|kv', re.I)
_NUM_RE = re.compile(r'(\d+(?:\.\d+)?)')


def feature_voltage_kv(props: dict) -> float | None:
    """Voltage from whichever attribute carries it ('VOLTAGE', 'kV_Rating',
    'Operating_Voltage' …) — the layer's field names aren't documented."""
    for key, value in (props or {}).items():
        if value in (None, '') or not _KV_KEY_RE.search(key):
            continue
        m = _NUM_RE.search(str(value))
        if m:
            kv = float(m.group(1))
            return kv / 1000.0 if kv >= 1000 else kv            # volts → kV
    return None


def feature_out_of_service(props: dict) -> bool:
    return any(isinstance(v, str) and 'out of service' in v.lower() for v in (props or {}).values())


@dataclass
class LineFeature:
    kv: float | None
    paths: list
    bbox: tuple                     # (min_lat, min_lon, max_lat, max_lon)


def index_lines(features) -> list[LineFeature]:
    out = []
    for f in features:
        props = f.get('properties') or {}
        if feature_out_of_service(props):
            continue
        paths = feature_paths(f.get('geometry'))
        if not paths:
            continue
        pts = [p for path in paths for p in path]
        bbox = (min(p[0] for p in pts), min(p[1] for p in pts),
                max(p[0] for p in pts), max(p[1] for p in pts))
        out.append(LineFeature(feature_voltage_kv(props), paths, bbox))
    return out


def _near_bbox(lat, lon, bbox, tol_km) -> bool:
    dlat = tol_km / 111.0
    dlon = tol_km / (111.0 * max(0.2, math.cos(math.radians(lat))))
    return bbox[0] - dlat <= lat <= bbox[2] + dlat and bbox[1] - dlon <= lon <= bbox[3] + dlon


def _distance_to_feature_km(lat, lon, feature: LineFeature) -> float:
    best = float('inf')
    for path in feature.paths:
        for (a_lat, a_lon), (b_lat, b_lon) in zip(path, path[1:]):
            best = min(best, _point_to_segment_distance_km(lat, lon, a_lat, a_lon, b_lat, b_lon))
    return best


def sample_route(coords: list, n: int = ROUTE_SAMPLES) -> list[tuple[float, float]]:
    """n points spread evenly by distance along a [[lat, lon], …] route,
    skipping the ends (terminals, where many lines converge)."""
    if len(coords) < 2:
        return []
    seg = [_haversine_km(a[0], a[1], b[0], b[1]) for a, b in zip(coords, coords[1:])]
    total = sum(seg)
    if total == 0:
        return []
    out = []
    for i in range(n):
        target = total * (0.05 + 0.9 * i / max(1, n - 1))
        run = 0.0
        for (a, b), length in zip(zip(coords, coords[1:]), seg):
            if run + length >= target and length > 0:
                t = (target - run) / length
                out.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
                break
            run += length
    return out


def gridline_route(grid_line) -> list:
    """[[lat, lon], …] from the GridLine's KML geometry, or [] if it has none
    (a straight from→to line is too far from any real route to test)."""
    kml = grid_line.get_kml_geometry_data()
    if kml and kml.get('coordinates'):
        return [[c[1], c[0]] for c in kml['coordinates']]
    return []


# ---------------------------------------------------------------------------
# Asset checks
# ---------------------------------------------------------------------------

@dataclass
class AssetCheck:
    kind: str                       # 'line' | 'terminal'
    name: str
    state: str                      # 'confirmed' | 'not_built' | 'unknown'
    detail: str


def check_line(grid_line, line_index, role='new', tol_km=LINE_TOLERANCE_KM) -> AssetCheck:
    """A 'new' line is built when GIS shows a line at ≥ its voltage_level
    along its route.  An 'upgrade' line keeps its pre-CEL voltage_level
    (e.g. CEL-North's 132 kV lines going to 330 kV); it counts as done only
    where GIS shows a *higher* voltage there AND no in-service line at the
    old voltage remains.  Existing higher-voltage circuits share these
    corridors (CEL-North's 132 and 330 kV lines are 0–50 m apart), so
    "a higher-voltage line nearby" alone would confirm upgrades that haven't
    happened.  A thermal-only upgrade, or one that adds a circuit beside a
    retained old one, can't be seen in these layers and stays 'not built'."""
    route = gridline_route(grid_line)
    base = grid_line.voltage_level or 0
    target = base + 1.0 if role == 'upgrade' else base - 0.5
    wanted = (f'>{base:g} kV with no {base:g} kV line remaining' if role == 'upgrade'
              else f'≥{base:g} kV')
    if not route:
        return AssetCheck('line', grid_line.line_name, 'unknown',
                          'no KML route geometry on the GridLine, so it can\'t be matched')
    samples = sample_route(route)
    matched, kvs_seen = 0, Counter()
    for lat, lon in samples:
        near = [(f, _distance_to_feature_km(lat, lon, f)) for f in line_index if _near_bbox(lat, lon, f.bbox, tol_km)]
        near = [(f, d) for f, d in near if d <= tol_km]
        if not near:
            continue
        for f, _ in near:
            if f.kv is not None:
                kvs_seen[f.kv] += 1
        higher = any(f.kv is not None and f.kv >= target for f, _ in near)
        old_remains = role == 'upgrade' and any(
            f.kv is not None and abs(f.kv - base) < 0.5 for f, _ in near)
        if higher and not old_remains:
            matched += 1
    coverage = matched / len(samples) if samples else 0.0
    seen = ', '.join(f'{kv:g} kV' for kv, _ in kvs_seen.most_common(3)) or 'no line'
    detail = (f'{role}: {coverage:.0%} of the route has an in-service line at {wanted} within '
              f'{tol_km:g} km (GIS shows {seen} along it)')
    return AssetCheck('line', grid_line.line_name,
                      'confirmed' if coverage >= LINE_COVERAGE_REQUIRED else 'not_built', detail)


def index_substations(features) -> list[tuple[str, list]]:
    out = []
    for f in features:
        props = f.get('properties') or {}
        if feature_out_of_service(props):
            continue
        pts = feature_points(f.get('geometry'))
        if pts:
            name = next((str(v) for k, v in props.items() if 'name' in k.lower() and v), '')
            out.append((name, pts))
    return out


def check_terminal(terminal, substation_index, tol_km=TERMINAL_TOLERANCE_KM) -> AssetCheck:
    if terminal.latitude is None or terminal.longitude is None:
        return AssetCheck('terminal', terminal.terminal_name, 'unknown', 'terminal has no coordinates')
    best_name, best_d = '', float('inf')
    for name, pts in substation_index:
        d = min(_haversine_km(terminal.latitude, terminal.longitude, lat, lon) for lat, lon in pts)
        if d < best_d:
            best_name, best_d = name, d
    if best_d <= tol_km:
        return AssetCheck('terminal', terminal.terminal_name, 'confirmed',
                          f'existing substation "{best_name or "unnamed"}" {best_d:.2f} km away')
    near = f'nearest existing substation {best_d:.1f} km away' if best_d < float('inf') else 'no substations loaded'
    return AssetCheck('terminal', terminal.terminal_name, 'not_built', near)


@dataclass
class StageAssessment:
    stage: object
    checks: list = field(default_factory=list)

    @property
    def checkable(self):
        return [c for c in self.checks if c.state != 'unknown']

    @property
    def confirmed(self):
        return [c for c in self.checks if c.state == 'confirmed']

    @property
    def all_built(self):
        return bool(self.checks) and len(self.confirmed) == len(self.checks)

    def evidence(self) -> str:
        lines = [f'Western Power GIS (data.wa.gov.au WP-051/WP-049), checked {self._today()}:']
        lines += [f'- {c.kind} {c.name}: {c.state.replace("_", " ")} — {c.detail}' for c in self.checks]
        lines.append('New lines need GIS voltage >= the GridLine voltage_level; upgrade lines need GIS '
                     'voltage above it and no line left at the old voltage (voltage_level holds the '
                     'pre-CEL rating).  Western Power '
                     'refreshes the layers monthly, so a first sighting can lag commissioning by '
                     'about a month.')
        return '\n'.join(lines)

    @staticmethod
    def _today():
        import datetime as dt
        return dt.date.today().isoformat()


def assess_stage(stage, line_index, substation_index) -> StageAssessment:
    a = StageAssessment(stage)
    if line_index is not None:
        for assoc in stage.stage_gridlines.select_related('grid_line'):
            a.checks.append(check_line(assoc.grid_line, line_index, role=assoc.line_role))
    if substation_index is not None:
        for assoc in stage.stage_terminals.filter(terminal_role='new').select_related('terminal'):
            a.checks.append(check_terminal(assoc.terminal, substation_index))
    return a


# ---------------------------------------------------------------------------
# Derived reserved capacity
# ---------------------------------------------------------------------------

def derived_reserved_capacity(stage):
    """(MW, [facility names]) of facilities aligned to the stage that are
    under construction — the capacity already spoken for on it."""
    from siren_web.models import FacilityCELAlignment

    rows = (FacilityCELAlignment.objects
            .filter(cel_stage=stage, is_aligned=True, is_exception=False,
                    facility__status='under_construction')
            .select_related('facility'))
    names = [f'{a.facility.facility_name} ({a.facility.capacity or 0:,.0f} MW)' for a in rows]
    return sum(a.facility.capacity or 0.0 for a in rows), names
