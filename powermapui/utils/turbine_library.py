"""
CSV wind-turbine library.

Layout under settings.TURBINE_LIBRARY_DIR::

    index.csv             one row per turbine (see INDEX_COLUMNS)
    curves/<slug>.csv     wind_speed_ms,power_kw on a regular grid
    SOURCES.md            attribution / licences

The library is the run-time source of power curves for the SAM wind path. It is
plain files: reading it needs no database and no network. It is built by
`manage.py import_turbine_library`.

This module also holds the pieces the importer shares with the run path: curve
normalisation/validation and a parser for the legacy SIREN `.pow` files.
"""

import csv
import hashlib
import logging
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

INDEX_FILE = 'index.csv'
CURVES_SUBDIR = 'curves'
INDEX_COLUMNS = [
    'slug', 'name', 'manufacturer', 'application', 'rated_kw',
    'rotor_diameter_m', 'hub_height_m', 'iec_class', 'vintage_year',
    'is_reference', 'source', 'licence', 'curve_file',
]
CURVE_COLUMNS = ['wind_speed_ms', 'power_kw']

CURVE_STEP = 0.5          # m/s grid the library stores curves on
CURVE_MAX_SPEED = 30.0
DEFAULT_CUT_OUT = 25.0    # m/s, assumed when a source doesn't say
RATED_TOLERANCE = 0.98    # a point this close to rated counts as "at rated"

_SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9._-]*$')


class TurbineLibraryError(Exception):
    """The turbine library is missing, malformed or lacks the requested turbine."""


@dataclass(frozen=True)
class LibraryTurbine:
    slug: str
    name: str
    manufacturer: str
    application: str              # onshore | offshore | floating
    rated_kw: float
    rotor_diameter_m: float
    hub_height_m: Optional[float]
    iec_class: str
    vintage_year: Optional[int]
    is_reference: bool
    source: str
    licence: str
    curve_file: str

    @property
    def specific_power(self) -> float:
        """Rated power per swept area, W/m2."""
        return self.rated_kw * 1000.0 / (math.pi * (self.rotor_diameter_m / 2.0) ** 2)


@dataclass(frozen=True)
class Curve:
    wind_speeds: Tuple[float, ...]
    power_kw: Tuple[float, ...]

    @property
    def max_power(self) -> float:
        return max(self.power_kw) if self.power_kw else 0.0

    def scaled(self, factor: float) -> 'Curve':
        """Same wind-speed axis, power multiplied by `factor`."""
        return Curve(self.wind_speeds, tuple(p * factor for p in self.power_kw))


# ---------------------------------------------------------------------------
# Locating and reading the library
# ---------------------------------------------------------------------------

def library_dir() -> Path:
    from django.conf import settings
    return Path(getattr(settings, 'TURBINE_LIBRARY_DIR'))


def slugify(text: str) -> str:
    slug = re.sub(r'[^a-z0-9.]+', '-', (text or '').lower()).strip('-.')
    return slug or 'turbine'


def _to_float(value) -> Optional[float]:
    try:
        f = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


_index_cache: Dict[str, Tuple[Tuple[int, int], List[LibraryTurbine]]] = {}


def load_index(directory: Optional[Path] = None) -> List[LibraryTurbine]:
    """All turbines in index.csv. Cached until the file changes."""
    directory = Path(directory) if directory else library_dir()
    path = directory / INDEX_FILE
    try:
        st = path.stat()
    except FileNotFoundError:
        raise TurbineLibraryError(
            f"Turbine library index not found at {path}. "
            f"Run `manage.py import_turbine_library`."
        )
    # mtime alone is too coarse: two writes inside the filesystem's timestamp
    # granularity (~16 ms on Windows) look identical, so include the size too
    stamp = (st.st_mtime_ns, st.st_size)
    cached = _index_cache.get(str(path))
    if cached and cached[0] == stamp:
        return cached[1]

    turbines: List[LibraryTurbine] = []
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            rated = _to_float(row.get('rated_kw'))
            diameter = _to_float(row.get('rotor_diameter_m'))
            if not row.get('slug') or not rated or not diameter:
                logger.warning(f"Skipping malformed turbine library row: {row}")
                continue
            vintage = _to_float(row.get('vintage_year'))
            turbines.append(LibraryTurbine(
                slug=row['slug'],
                name=row.get('name') or row['slug'],
                manufacturer=row.get('manufacturer') or '',
                application=(row.get('application') or 'onshore').lower(),
                rated_kw=rated,
                rotor_diameter_m=diameter,
                hub_height_m=_to_float(row.get('hub_height_m')),
                iec_class=row.get('iec_class') or '',
                vintage_year=int(vintage) if vintage else None,
                is_reference=(row.get('is_reference') or '').strip().lower() in ('1', 'true', 'yes'),
                source=row.get('source') or '',
                licence=row.get('licence') or '',
                curve_file=row.get('curve_file') or f"{CURVES_SUBDIR}/{row['slug']}.csv",
            ))
    _index_cache[str(path)] = (stamp, turbines)
    return turbines


def get_turbine(slug: str, directory: Optional[Path] = None) -> Optional[LibraryTurbine]:
    for turbine in load_index(directory):
        if turbine.slug == slug:
            return turbine
    return None


def index_hash(directory: Optional[Path] = None) -> str:
    """Short digest of index.csv, stored with an assumed turbine so a rebuilt
    library invalidates earlier selections."""
    path = (Path(directory) if directory else library_dir()) / INDEX_FILE
    try:
        return hashlib.sha1(path.read_bytes()).hexdigest()[:12]
    except FileNotFoundError:
        return ''


def load_curve(slug: str, directory: Optional[Path] = None) -> Curve:
    """Read curves/<slug>.csv. Raises TurbineLibraryError if it is absent."""
    if not _SLUG_RE.match(slug or ''):
        raise TurbineLibraryError(f"Invalid turbine slug: {slug!r}")
    path = (Path(directory) if directory else library_dir()) / CURVES_SUBDIR / f"{slug}.csv"
    if not path.exists():
        raise TurbineLibraryError(f"No power curve for '{slug}' at {path}")
    speeds: List[float] = []
    powers: List[float] = []
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            ws, pw = _to_float(row.get('wind_speed_ms')), _to_float(row.get('power_kw'))
            if ws is not None and pw is not None:
                speeds.append(ws)
                powers.append(pw)
    if len(speeds) < 5:
        raise TurbineLibraryError(f"Power curve '{slug}' has too few points ({len(speeds)})")
    return Curve(tuple(speeds), tuple(powers))


# ---------------------------------------------------------------------------
# Curve normalisation / validation (shared with the importer)
# ---------------------------------------------------------------------------

def normalise_curve(wind_speeds: Sequence[float], powers: Sequence[float],
                    rated_kw: float, step: float = CURVE_STEP,
                    max_speed: float = CURVE_MAX_SPEED,
                    default_cut_out: float = DEFAULT_CUT_OUT
                    ) -> Tuple[List[float], List[float]]:
    """
    Resample a power curve onto a regular 0..max_speed grid.

    - Linear interpolation between points, except a drop from rated to zero is
      treated as a hard cut-out (rated is held until the zero point).
    - Below the first point there is no generation.
    - Past the last point the curve holds rated power until `default_cut_out`
      if the last point is at rated, otherwise it is zero.
    """
    points: Dict[float, float] = {}
    for ws, pw in zip(wind_speeds, powers):
        if ws is None or pw is None or not (math.isfinite(ws) and math.isfinite(pw)):
            continue
        points[float(ws)] = max(0.0, float(pw))
    pts = sorted(points.items())
    if not pts:
        raise ValueError("Power curve has no valid points")

    at_rated = RATED_TOLERANCE * rated_kw
    first_ws, last_ws = pts[0][0], pts[-1][0]
    grid = [round(i * step, 6) for i in range(int(round(max_speed / step)) + 1)]
    out: List[float] = []
    j = 0
    for x in grid:
        if x < first_ws:
            out.append(0.0)
        elif x >= last_ws:
            last_p = pts[-1][1]
            if x == last_ws:
                out.append(last_p)
            elif last_p >= at_rated and x < default_cut_out:
                out.append(last_p)
            else:
                out.append(0.0)
        else:
            while pts[j + 1][0] <= x:
                j += 1
            (w0, p0), (w1, p1) = pts[j], pts[j + 1]
            if x == w0:
                out.append(p0)
            elif p0 >= at_rated and p1 == 0.0:
                out.append(p0)                       # hard cut-out
            else:
                out.append(p0 + (p1 - p0) * (x - w0) / (w1 - w0))
    return grid, [round(p, 3) for p in out]


def validate_curve(wind_speeds: Sequence[float], powers: Sequence[float],
                   rated_kw: float) -> Tuple[List[str], List[str]]:
    """Return (fatal problems, warnings) for a curve about to enter the library."""
    fatal: List[str] = []
    warnings: List[str] = []
    if len(wind_speeds) != len(powers) or len(wind_speeds) < 5:
        return ["too few points"], warnings
    if any(b <= a for a, b in zip(wind_speeds, wind_speeds[1:])):
        fatal.append("wind speeds not strictly increasing")
    if any(p < 0 for p in powers):
        warnings.append("negative power (parasitic load) clipped to zero")
    peak = max(powers)
    if peak <= 0:
        fatal.append("no generation")
    elif rated_kw:
        deviation = abs(peak / rated_kw - 1.0)
        if deviation > 0.10:
            fatal.append(f"peak power {peak:.0f} kW is {deviation:.0%} from rated {rated_kw:.0f} kW")
        elif deviation > 0.03:
            warnings.append(f"peak power {peak:.0f} kW differs {deviation:.1%} from rated {rated_kw:.0f} kW")
    if wind_speeds[0] < 2.0 and powers[0] > 0:
        warnings.append("non-zero power at the lowest wind speed")
    return fatal, warnings


# ---------------------------------------------------------------------------
# Legacy SIREN .pow files
# ---------------------------------------------------------------------------

@dataclass
class PowFile:
    name: str
    rotor_diameter: float
    cut_out: float
    cut_in: float
    wind_speeds: List[float]
    power_kw: List[float]
    notes: List[str] = field(default_factory=list)

    @property
    def rated_kw(self) -> float:
        return max(self.power_kw) if self.power_kw else 0.0


def parse_pow_file(path) -> PowFile:
    """
    Parse a SIREN `.pow` file.

    One double-quoted value per line::

        name
        rotor diameter, whole metres
        rotor diameter, tenths of a metre
        cut-out speed (m/s)
        cut-in speed (m/s)
        power in kW at 1, 2, 3 ... m/s
        [free-text notes]

    Power at 0 m/s is not stored (it is zero) so it is added here.
    """
    path = Path(path)
    raw = path.read_text(encoding='latin-1').splitlines()
    lines = [ln.strip().strip('"').strip() for ln in raw]
    lines = [ln for ln in lines if ln]
    if len(lines) < 7:
        raise ValueError(f"{path.name}: too short to be a .pow file")

    name, numbers, notes = lines[0], [], []
    for i, ln in enumerate(lines[1:], start=1):
        value = _to_float(ln)
        if value is None:
            notes = lines[i:]
            break
        numbers.append(value)
    if len(numbers) < 5:
        raise ValueError(f"{path.name}: no power values found")

    whole, tenths, cut_out, cut_in, *power = numbers
    rotor = whole + (tenths / 10.0 if 0 <= tenths < 10 else tenths / 100.0)
    speeds = [0.0] + [float(i) for i in range(1, len(power) + 1)]
    return PowFile(name=name, rotor_diameter=rotor, cut_out=cut_out, cut_in=cut_in,
                   wind_speeds=speeds, power_kw=[0.0] + power, notes=notes)


def _name_key(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', (text or '').lower())


def find_pow_file(turbine_model: str, pow_dir) -> Optional[Path]:
    """
    Find the `.pow` file for a turbine model name, tolerating the manufacturer
    prefix and punctuation differences ('V150-4.2Mw' vs 'Vestas V150-4.2Mw.pow').
    Returns None unless exactly one file matches.
    """
    key = _name_key(turbine_model)
    if len(key) < 4:
        return None
    files = list(Path(pow_dir).glob('*.pow'))
    exact = [f for f in files if _name_key(f.stem) == key]
    if len(exact) == 1:
        return exact[0]
    loose = [f for f in files
             if _name_key(f.stem).endswith(key) or (len(_name_key(f.stem)) >= 6 and key.endswith(_name_key(f.stem)))]
    if len(loose) == 1:
        return loose[0]
    if len(exact) > 1 or len(loose) > 1:
        logger.warning(f"Ambiguous .pow match for '{turbine_model}': "
                       f"{[f.name for f in (exact or loose)]}")
    return None
