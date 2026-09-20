"""
Turbine resolution for the SAM wind simulation.

A wind installation either names a turbine model (use its curve) or is
"Unspecified" -- only a turbine count and a nameplate. For the latter we pick a
representative turbine from the CSV library and scale it so the farm keeps its
nameplate: the implied rating per turbine is known exactly, so the reference
curve's power is scaled to it and its rotor diameter by sqrt(scale), which holds
specific power (and so the wind-speed axis) constant.

`select_representative_turbine` is pure (library in, turbine out).
`resolve_wind_installation` / `resolve_wind_facility` are the DB-facing entry
points used by the SAM path.
"""

import logging
import math
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from powermapui.utils import turbine_library as lib

logger = logging.getLogger(__name__)

DEFAULT_RATED_KW = 6000.0        # per-turbine rating when nothing implies one
MIN_CANDIDATE_KW = 1500.0        # utility scale only
SCALE_MIN, SCALE_MAX = 0.6, 1.6  # preferred range for implied / reference rating
SP_WINDOW = (220.0, 320.0)       # W/m2, typical modern onshore designs
DEFAULT_HUB_HEIGHT_M = 100.0     # the only resource height we hold is 100 m
MAX_ASSUMED_HUB_HEIGHT_M = 140.0 # the 100 m resource is extrapolated to hub height with a
                                 # fixed shear (see sam_resource_processor), so don't let a
                                 # tall reference (the ATB 7 MW is 175 m) inflate an assumed
                                 # turbine's yield
DEFAULT_YEARS_AHEAD = 3          # commissioning year when no date is recorded
VINTAGE_WEIGHT = 0.02            # score per year of vintage mismatch
VINTAGE_CAP_YEARS = 10
UNKNOWN_VINTAGE_PENALTY = 0.06   # commercial models carry no design year


class NoRepresentativeTurbine(Exception):
    """The library has no turbine that can stand in for the request."""


@dataclass(frozen=True)
class ResolvedTurbine:
    """Everything the SAM wind module needs to know about one turbine type."""
    name: str
    rated_kw: float
    rotor_diameter: float
    hub_height: float
    wind_speeds: Tuple[float, ...]
    power_kw: Tuple[float, ...]
    kind: str                       # 'specified' | 'assumed'
    basis: str                      # human-readable provenance
    no_turbines: int = 1
    reference_slug: Optional[str] = None
    scale: float = 1.0

    @property
    def installation_capacity_mw(self) -> float:
        return self.no_turbines * self.rated_kw / 1000.0


# ---------------------------------------------------------------------------
# Pure selection
# ---------------------------------------------------------------------------

def _score(turbine: lib.LibraryTurbine, rated_kw: float, cod_year: int) -> float:
    size = abs(math.log(rated_kw / turbine.rated_kw))
    if turbine.vintage_year:
        vintage = VINTAGE_WEIGHT * min(abs(cod_year - turbine.vintage_year), VINTAGE_CAP_YEARS)
    else:
        vintage = UNKNOWN_VINTAGE_PENALTY
    low, high = SP_WINDOW
    sp = turbine.specific_power
    if sp < low:
        specific = abs(math.log(sp / low))
    elif sp > high:
        specific = abs(math.log(sp / high))
    else:
        specific = 0.0
    return size + vintage + specific


def select_representative_turbine(rated_kw: float, cod_year: int, *,
                                  application: str = 'onshore',
                                  hub_height: Optional[float] = None,
                                  min_kw: float = MIN_CANDIDATE_KW,
                                  index: Optional[List[lib.LibraryTurbine]] = None,
                                  directory=None) -> ResolvedTurbine:
    """
    Choose the reference turbine closest to `rated_kw` (and to `cod_year`'s
    vintage) and scale it to exactly `rated_kw`. Deterministic.

    `min_kw` is the smallest reference considered (utility scale by default).
    """
    if rated_kw <= 0:
        raise NoRepresentativeTurbine(f"Invalid rated power {rated_kw}")
    turbines = index if index is not None else lib.load_index(directory)
    pool = [t for t in turbines
            if t.application == application and t.rated_kw >= min_kw]
    preferred = [t for t in pool if SCALE_MIN <= rated_kw / t.rated_kw <= SCALE_MAX]
    if preferred:
        candidates = preferred
    elif pool:
        candidates = pool
        logger.warning(
            f"No {application} reference turbine within x{SCALE_MIN}-{SCALE_MAX} of "
            f"{rated_kw:.0f} kW; scaling the nearest one further"
        )
    else:
        raise NoRepresentativeTurbine(
            f"Turbine library has no {application} turbines >= {MIN_CANDIDATE_KW:.0f} kW"
        )

    reference = min(candidates, key=lambda t: (_score(t, rated_kw, cod_year), t.slug))
    curve = lib.load_curve(reference.slug, directory)
    factor = rated_kw / curve.max_power            # peak becomes exactly rated_kw
    scale = rated_kw / reference.rated_kw          # rating ratio, sizes the rotor
    scaled = curve.scaled(factor)
    hub = hub_height or min(reference.hub_height_m or DEFAULT_HUB_HEIGHT_M, MAX_ASSUMED_HUB_HEIGHT_M)

    basis = (f"{reference.name} ({reference.rated_kw / 1000:.2f} MW, "
             f"{reference.rotor_diameter_m:.0f} m rotor) scaled x{scale:.2f} "
             f"to {rated_kw / 1000:.2f} MW, hub {hub:.0f} m")
    return ResolvedTurbine(
        name=f"Assumed {rated_kw / 1000:.1f} MW",
        rated_kw=rated_kw,
        rotor_diameter=reference.rotor_diameter_m * math.sqrt(scale),
        hub_height=float(hub),
        wind_speeds=scaled.wind_speeds,
        power_kw=scaled.power_kw,
        kind='assumed',
        basis=basis,
        reference_slug=reference.slug,
        scale=scale,
    )


# ---------------------------------------------------------------------------
# DB-facing resolution
# ---------------------------------------------------------------------------

def _year_of(value) -> Optional[int]:
    if isinstance(value, (date, datetime)):
        return value.year
    return None


def cod_year_for(wind_install=None, facility=None) -> int:
    """Commissioning year: installation date, else facility date, else today + 3."""
    candidates = []
    if wind_install is not None:
        candidates += [wind_install.commissioning_date, wind_install.installation_date]
    if facility is not None:
        candidates.append(facility.commissioning_date)
    for value in candidates:
        year = _year_of(value)
        if year:
            return year
    return date.today().year + DEFAULT_YEARS_AHEAD


def application_for(wind_install=None, facility=None) -> str:
    """'onshore' unless the technology says offshore/floating (both use offshore designs)."""
    technology = None
    if wind_install is not None:
        technology = wind_install.idtechnologies
    if technology is None and facility is not None:
        technology = facility.idtechnologies
    name = (getattr(technology, 'technology_name', '') or '').lower()
    return 'offshore' if 'offshore' in name or 'floating' in name else 'onshore'


def implied_rated_kw(wind_install) -> Tuple[float, str]:
    """
    Rating per turbine implied by the installation's nameplate, else
    DEFAULT_RATED_KW. Returns (kW, where it came from).

    Facility capacity is deliberately not consulted: for wind facilities a
    post_save signal derives it from the installations, so it says nothing
    this installation doesn't.
    """
    n = wind_install.no_turbines or 0
    if n > 0 and wind_install.nameplate_capacity:
        return wind_install.nameplate_capacity * 1000.0 / n, 'installation nameplate'
    return DEFAULT_RATED_KW, 'default rating'


def _resolve_specified(turbine, wind_install) -> Optional[ResolvedTurbine]:
    """Resolve a named turbine from the CSV library, else its legacy .pow file."""
    n = wind_install.no_turbines or 1
    hub_override = wind_install.hub_height

    if turbine.power_curve_csv:
        try:
            entry = lib.get_turbine(turbine.power_curve_csv)
            curve = lib.load_curve(turbine.power_curve_csv)
        except lib.TurbineLibraryError as e:
            logger.warning(f"Library curve for '{turbine.turbine_model}' unavailable: {e}")
        else:
            return ResolvedTurbine(
                name=turbine.turbine_model,
                rated_kw=turbine.rated_power or (entry.rated_kw if entry else curve.max_power),
                rotor_diameter=turbine.rotor_diameter or (entry.rotor_diameter_m if entry else 0.0),
                hub_height=float(hub_override or (entry.hub_height_m if entry else None)
                                 or DEFAULT_HUB_HEIGHT_M),
                wind_speeds=curve.wind_speeds, power_kw=curve.power_kw,
                kind='specified', basis=f"library curve '{turbine.power_curve_csv}'",
                no_turbines=n, reference_slug=turbine.power_curve_csv,
            )

    from django.conf import settings
    pow_path = lib.find_pow_file(turbine.turbine_model, settings.POWER_CURVES_DIR)
    if pow_path is not None:
        try:
            pow_file = lib.parse_pow_file(pow_path)
            rated = turbine.rated_power or pow_file.rated_kw
            speeds, powers = lib.normalise_curve(pow_file.wind_speeds, pow_file.power_kw, rated)
        except (ValueError, OSError) as e:
            logger.warning(f"Could not read {pow_path.name} for '{turbine.turbine_model}': {e}")
        else:
            return ResolvedTurbine(
                name=turbine.turbine_model, rated_kw=rated,
                rotor_diameter=turbine.rotor_diameter or pow_file.rotor_diameter,
                hub_height=float(hub_override or DEFAULT_HUB_HEIGHT_M),
                wind_speeds=tuple(speeds), power_kw=tuple(powers),
                kind='specified', basis=f".pow file '{pow_path.name}'", no_turbines=n,
            )
    return None


def _store_assumption(wind_install, value: Optional[Dict[str, Any]]) -> None:
    """
    Write `assumed_turbine` without going through save(): it is a derived
    cache, and FacilityWindTurbines' post_save signal would needlessly
    recompute facility and scenario capacities on every simulation run.
    """
    type(wind_install).objects.filter(pk=wind_install.pk).update(assumed_turbine=value)
    wind_install.assumed_turbine = value


def _persist_assumption(wind_install, resolved: ResolvedTurbine, inputs: Dict[str, Any]) -> None:
    """Save the selection on the installation when it has changed."""
    payload = {
        'reference_slug': resolved.reference_slug,
        'rated_kw': round(resolved.rated_kw, 2),
        'rotor_diameter': round(resolved.rotor_diameter, 2),
        'hub_height': resolved.hub_height,
        'scale': round(resolved.scale, 4),
        'basis': resolved.basis,
        'inputs': inputs,
        'library_index_hash': lib.index_hash(),
    }
    saved = wind_install.assumed_turbine or {}
    if {k: v for k, v in saved.items() if k != 'selected_at'} == payload:
        return
    try:
        _store_assumption(wind_install, {**payload, 'selected_at': datetime.now(timezone.utc).isoformat()})
    except Exception as e:      # a failed write must not stop the simulation
        logger.error(f"Could not save assumed turbine for installation "
                     f"{wind_install.pk}: {e}")


def _clear_assumption(wind_install) -> None:
    if wind_install.assumed_turbine:
        try:
            _store_assumption(wind_install, None)
        except Exception as e:
            logger.error(f"Could not clear assumed turbine for installation {wind_install.pk}: {e}")


def resolve_wind_installation(wind_install, persist: bool = True) -> ResolvedTurbine:
    """
    Turbine to simulate for a FacilityWindTurbines row.

    A named turbine with a curve is used as given (and any stale assumption is
    cleared). Otherwise -- unspecified, or a named turbine with no curve -- a
    representative turbine is chosen and, for unspecified installations, saved
    on `assumed_turbine`.
    """
    facility = wind_install.facility
    turbine = wind_install.wind_turbine
    n = wind_install.no_turbines or 1

    if turbine is not None:
        resolved = _resolve_specified(turbine, wind_install)
        if resolved is not None:
            if persist:
                _clear_assumption(wind_install)
            return resolved
        rated_kw = turbine.rated_power
        if not rated_kw:
            rated_kw, _ = implied_rated_kw(wind_install)
        logger.warning(
            f"No power curve found for '{turbine.turbine_model}' at {facility.facility_name}; "
            f"simulating a representative {rated_kw / 1000:.1f} MW turbine instead"
        )
        persist = False       # the row names a turbine; don't record an assumption
        source = 'turbine rating'
    else:
        rated_kw, source = implied_rated_kw(wind_install)

    cod_year = cod_year_for(wind_install, facility)
    application = application_for(wind_install, facility)
    resolved = select_representative_turbine(
        rated_kw, cod_year, application=application, hub_height=wind_install.hub_height,
        # a named small turbine (e.g. a 550 kW Enercon) should be stood in for by a
        # comparable one, not scaled down from a multi-MW design
        min_kw=min(MIN_CANDIDATE_KW, 0.5 * rated_kw) if turbine is not None else MIN_CANDIDATE_KW,
    )
    resolved = replace(resolved, no_turbines=n)
    logger.info(f"{facility.facility_name}: no turbine specified; using {resolved.basis} "
                f"(rating from {source}, commissioning {cod_year})")
    if persist:
        _persist_assumption(wind_install, resolved, {
            'no_turbines': n,
            'rated_kw': round(rated_kw, 2),
            'rating_source': source,
            'cod_year': cod_year,
            'application': application,
            'hub_height_override': wind_install.hub_height,
        })
    return resolved


def resolve_wind_facility(facility) -> ResolvedTurbine:
    """
    Turbine for a wind facility that has no installation rows at all: size a
    representative farm from the facility's capacity.
    """
    capacity_kw = (facility.capacity or 0) * 1000.0
    if capacity_kw <= 0:
        raise NoRepresentativeTurbine(
            f"{facility.facility_name} has no wind installation and no capacity to size one from"
        )
    n = max(1, round(capacity_kw / DEFAULT_RATED_KW))
    resolved = select_representative_turbine(
        capacity_kw / n, cod_year_for(None, facility),
        application=application_for(None, facility),
    )
    return replace(resolved, no_turbines=n)
