"""
Per-facility bias factors for SAM-simulated generation (FacilityGenerationBias).

A factor is fitted for one (facility, weather source) pair from the facility's SCADA,
by `manage.py compare_weather_sources --set-bias`, and applied inside the SAM simulation
run to the facility's combined hourly output. It is a plain multiplier: the simplest
correction that removes an energy bias while keeping the simulated shape. Hours a factor
above 1 would push past installed capacity are capped at capacity.
"""

from typing import Optional, Sequence

import numpy as np

DEFAULT_METHOD = 'energy_masked'


def get_factor(facility_id: int, weather_source: str) -> Optional[float]:
    """The stored factor for the facility and weather source, or None."""
    from siren_web.models import FacilityGenerationBias
    row = (FacilityGenerationBias.objects
           .filter(idfacilities_id=facility_id, weather_source=weather_source)
           .values_list('factor', flat=True).first())
    return float(row) if row is not None else None


def apply_factor(hourly: Sequence[float], factor: float,
                 capacity_kw: Optional[float] = None) -> np.ndarray:
    """Hourly output times the factor, capped at capacity when one is given."""
    out = np.asarray(hourly, dtype=float) * float(factor)
    if capacity_kw and capacity_kw > 0:
        out = np.minimum(out, capacity_kw)
    return out


def fit_energy_factor(sim: Sequence[float], scada: Sequence[float]) -> Optional[float]:
    """SCADA energy / simulated energy over hours where both exist, or None."""
    s = np.asarray(sim, dtype=float)
    o = np.asarray(scada, dtype=float)
    n = min(len(s), len(o))
    s, o = s[:n], o[:n]
    both = ~(np.isnan(s) | np.isnan(o))
    sim_energy = s[both].sum()
    if not both.any() or sim_energy <= 0:
        return None
    return float(o[both].sum() / sim_energy)


KW_PER_MW = 1000.0
LOCAL_UTC_OFFSET_HOURS = 8           # AWST; the hourly series are UTC-indexed
MASK_SCADA_BELOW = 0.02              # curtailment/outage mask: SCADA below 2% of capacity...
MASK_SIM_ABOVE = 0.30                # ...while the simulation is above 30%
MIN_R_HOUR = 0.6                     # a factor is not stored below this hourly correlation...
FACTOR_RANGE = (0.5, 1.5)            # ...or outside this range...
MIN_WINDOW_ENERGY_SHARE = 0.15       # ...or when the window holds too little of the simulated energy


def scada_hourly_mw(year: int, facility_id: int):
    """Hourly mean MW from the half-hourly SCADA MWh (UTC hours); NaN unless both halves exist."""
    from siren_web.services.facility_scada_matrix import facility_trace
    trace = facility_trace(year, facility_id)
    if trace is None:
        return None
    n = trace.shape[0] // 2
    hourly = trace[:n * 2].reshape(n, 2).sum(axis=1)  # NaN if either half missing; MWh/h == MW
    return np.where(np.isnan(hourly), np.nan, np.clip(hourly, 0.0, None))


def masked(sim_mw, scada_mw, capacity_mw):
    """Copies with likely curtailment/outage hours set to NaN in both, and how many there were."""
    sim = np.array(sim_mw, dtype=float)
    obs = np.array(scada_mw[:len(sim)], dtype=float)
    sim = sim[:len(obs)]
    drop = (obs < MASK_SCADA_BELOW * capacity_mw) & (sim > MASK_SIM_ABOVE * capacity_mw)
    sim[drop] = np.nan
    obs[drop] = np.nan
    return sim, obs, int(drop.sum())


def window_mask(n_hours: int, start: int, end: int) -> np.ndarray:
    """Hours (UTC-indexed from 1 January) whose AWST hour of day is in [start, end), wrapping."""
    local = (np.arange(n_hours) + LOCAL_UTC_OFFSET_HOURS) % 24
    if start == 0 and end == 24:
        return np.ones(n_hours, dtype=bool)
    if start > end:
        return (local >= start) | (local < end)
    return (local >= start) & (local < end)


def _corr(a, b):
    ok = ~(np.isnan(a) | np.isnan(b))
    if ok.sum() < 3 or np.std(a[ok]) == 0 or np.std(b[ok]) == 0:
        return float('nan')
    return float(np.corrcoef(a[ok], b[ok])[0, 1])


def fit_facility(facility, year: int, window=(0, 24), weather_source: Optional[str] = None,
                 window_name: str = 'all') -> dict:
    """
    Fit a facility's bias factor from a fresh SAM run against its SCADA.

    The SAM run uses `weather_source` (default settings.WEATHER_SOURCE) with any stored
    factor left off. Likely curtailment/outage hours are masked, then only hours in the
    AWST `window` (start, end) count. Returns the fit and whether it is sound enough to
    store ('status' == 'ok'); raises ValueError when there is nothing to fit.
    """
    from django.conf import settings
    from powermapui.views.sam_resource_processor import SAMResourceProcessor
    from powermatchui.views.power_views import process_hybrid_facility

    source = weather_source or getattr(settings, 'WEATHER_SOURCE', 'era5')
    capacity = float(facility.capacity or 0)
    if capacity <= 0:
        raise ValueError(f'{facility.facility_name} has no capacity')
    obs = scada_hourly_mw(year, facility.idfacilities)
    if obs is None or not np.any(~np.isnan(obs)):
        raise ValueError(f'No SCADA for {facility.facility_name} in {year}')

    processor = SAMResourceProcessor(weather_data_dir=settings.WEATHER_DATA_DIR, weather_source=source)
    results, reason = process_hybrid_facility(processor, facility, str(year), apply_bias=False)
    if not results or not results.hourly_generation:
        raise ValueError(f'No SAM result for {facility.facility_name}' + (f': {reason}' if reason else ''))

    sim = np.asarray(results.hourly_generation, dtype=float) / KW_PER_MW
    n = min(len(sim), len(obs))
    sim, obs = sim[:n], obs[:n]
    sim_m, obs_m, n_masked = masked(sim, obs, capacity)
    in_window = window_mask(n, *window)
    sim_w = np.where(in_window, sim_m, np.nan)
    obs_w = np.where(in_window, obs_m, np.nan)
    both = ~(np.isnan(sim_w) | np.isnan(obs_w))

    factor = fit_energy_factor(sim_w, obs_w)
    sim_total = float(np.nansum(np.where(np.isnan(obs_m), np.nan, sim_m)))
    window_share = float(sim_w[both].sum() / sim_total) if sim_total > 0 else 0.0
    r_hour = _corr(sim_w, obs_w)
    stored = get_factor(facility.idfacilities, source)

    if factor is None:
        status = 'no fit: no simulated energy in the window'
    elif window_share < MIN_WINDOW_ENERGY_SHARE:
        status = (f'not storable: the window holds only {window_share:.0%} of the simulated '
                  f'energy (minimum {MIN_WINDOW_ENERGY_SHARE:.0%})')
    elif np.isnan(r_hour) or r_hour < MIN_R_HOUR:
        status = f'not storable: hourly correlation {r_hour:.2f} is below {MIN_R_HOUR}'
    elif not FACTOR_RANGE[0] <= factor <= FACTOR_RANGE[1]:
        status = f'not storable: factor outside {FACTOR_RANGE[0]}-{FACTOR_RANGE[1]}'
    else:
        status = 'ok'

    return {
        'facility_id': facility.idfacilities, 'facility_name': facility.facility_name,
        'year': year, 'weather_source': source, 'window': window_name,
        'factor': factor, 'stored_factor': stored, 'status': status,
        'hours': int(both.sum()), 'masked_hours': n_masked, 'window_energy_share': window_share,
        'r_hour': r_hour,
        'scada_energy_mwh': float(obs_w[both].sum()), 'simulated_energy_mwh': float(sim_w[both].sum()),
        'annual_energy_ratio': (float(np.nansum(np.where(np.isnan(obs), np.nan, sim))) /
                                float(np.nansum(np.where(np.isnan(sim), np.nan, obs)))
                                if np.nansum(obs) > 0 else None),
    }


def store_fit(fit: dict):
    """Store a fit from fit_facility (only when its status is 'ok')."""
    if fit['status'] != 'ok':
        raise ValueError(fit['status'])
    return set_factor(
        fit['facility_id'], fit['weather_source'], fit['factor'], fitted_year=fit['year'],
        method=f"energy_masked_{fit['window']}", fitted_hours=fit['hours'], r_hour=fit['r_hour'],
        scada_energy_mwh=fit['scada_energy_mwh'], simulated_energy_mwh=fit['simulated_energy_mwh'],
        notes=f"Fitted on {fit['window']} hours (AWST), curtailment-masked")


def set_factor(facility_id: int, weather_source: str, factor: float, **fit_details):
    """Create or replace the factor for the facility and weather source."""
    from siren_web.models import FacilityGenerationBias
    fields = {'factor': float(factor), 'method': fit_details.pop('method', DEFAULT_METHOD)}
    fields.update(fit_details)
    row, _ = FacilityGenerationBias.objects.update_or_create(
        idfacilities_id=facility_id, weather_source=weather_source, defaults=fields)
    return row


def clear_factor(facility_id: int, weather_source: str) -> bool:
    """Delete the factor; True if there was one."""
    from siren_web.models import FacilityGenerationBias
    deleted, _ = FacilityGenerationBias.objects.filter(
        idfacilities_id=facility_id, weather_source=weather_source).delete()
    return bool(deleted)
