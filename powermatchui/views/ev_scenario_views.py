# powermatchui/views/ev_scenario_views.py
"""
FR-11/FR-12 — EV load scenario builder (Outcome A: sensitivity capability).

Mirrors esoo_scenario_views.py's orchestration shape but the construction
chain is genuinely different (no LDC/anchor-fit — see
powermatchui.utils.ev_trace_synthesis's module docstring):

    AEMO 2025 IASR EV workbook, WEM region (CSIRO 2025 trajectories developed for AEMO)
        -> powermatchui.utils.iasr_ev_energy.scenario_energy_mwh                (annual BEV+PHEV energy)
    EvChargingProfile (charging_mode='unmanaged', or 'managed' where real data exists)
        -> powermatchui.utils.ev_trace_synthesis.combine_charging_type_shapes  (FR-09 step 1)
    annual energy + composite shape
        -> powermatchui.utils.ev_trace_synthesis.shape_annual_energy_to_halfhourly (FR-09 steps 2-3)
        -> powermatchui.utils.ev_trace_synthesis.apply_managed_charging_lever (FR-10, if requested)
        -> powermatchui.utils.ev_load_trace_store.save_trace (EvLoadTrace, D12 file-based storage)

FR-11/GR-03 integration (D2: EV layer is fully additional and separable):
this NEVER mutates an existing base Demand's trace. Instead it
creates/updates a *derived* Demand ("<base name> + EV <scenario> <year>",
parent_demand pointing back at the base) carrying base + EV trace,
elementwise. The base Demand is always left untouched, so GR-03's "no EV
layer" acceptance test is satisfied by construction: simply not
building/selecting a derived Demand reproduces the base trace exactly, and
switching which CSIRO scenario is selected only changes which derived
Demand exists — the base Demand's own trace is never touched.

Data source: the annual energy is AEMO's 2025 IASR WEM trajectory (Low / Medium /
High = Slower Growth / Step Change / Accelerated Transition, a working mapping), which
replaced the older 2022 CSIRO postcode files (EvUptakePostcodeFigure). Those remain in
the database for the FR-07 backcast (validate_ev_data) but no longer drive this builder.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import numpy as np

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from siren_web.models import (
    Demand,
    DemandMatrix,
    EV_CHARGING_MODE_CHOICES,
    EvChargingProfile,
    EvLoadTrace,
)
from siren_web.services.demand_matrix import clear_demand_trace, demand_trace, set_demand_trace
from powermatchui.utils.ev_load_trace_store import load_trace, save_trace
from powermatchui.utils.esoo_embedded_ev import EmbeddedEv, EmbeddedEvNotAvailableError, resolve_embedded_ev
from powermatchui.utils.iasr_ev_energy import SCENARIO_LABELS, IasrDataNotAvailableError, scenario_energy_mwh
from powermatchui.utils.time_alignment import ESOO_TRACE_CLOCK_MARKER
from powermatchui.utils.ev_sensitivity_comparison import (
    SCENARIO_ORDER,
    SensitivityComparisonError,
    compare_scenarios,
)
from powermatchui.utils.ev_trace_synthesis import (
    ChargingTypeProfile,
    TraceSynthesisError,
    apply_managed_charging_lever,
    combine_charging_type_shapes,
    require_energy_conserved,
    shape_annual_energy_to_halfhourly,
)


class EvLoadNotAvailableError(ValueError):
    """Raised when there isn't enough validated data to build/find an EV load trace."""


class BaseTraceNotFoundError(ValueError):
    """Raised when the selected base Demand has no usable half-hourly trace."""


@dataclass
class EvScenarioBuildResult:
    demand: Demand
    title: str
    forecast_year: int
    csiro_scenario: str
    charging_mode: str
    n_rows: int
    ev_annual_energy_mwh: float
    integral_check_pct: float
    notes: list = field(default_factory=list)
    net_of_esoo_ev: bool = False
    esoo_ev_energy_mwh: float = 0.0
    esoo_ev_source: str = ''


def _charging_profiles() -> list:
    profiles = [
        ChargingTypeProfile(
            charging_type_label=p.charging_type_label, charging_mode=p.charging_mode,
            share_of_charging=p.share_of_charging,
            weekday_shape=p.weekday_halfhourly_shape, weekend_shape=p.weekend_halfhourly_shape,
        )
        for p in EvChargingProfile.objects.filter(charging_mode__in=('unmanaged', 'managed'))
    ]
    if not profiles:
        raise EvLoadNotAvailableError(
            "No usable EvChargingProfile rows found (charging_mode='unmanaged'/'managed') — ingest the "
            "AEMO ISP Step Change document and load its charging-type shapes before building a trace."
        )
    return profiles


def _synthesise_trace(annual_energy_mwh: float, forecast_year: int, charging_mode: str, profiles: list):
    """FR-09/FR-10: shape annual energy into a half-hourly trace for one charging
    mode. Returns (trace_mw, integral_check_pct)."""
    try:
        weekday_shape, weekend_shape = combine_charging_type_shapes(profiles, 'unmanaged')
    except TraceSynthesisError as e:
        raise EvLoadNotAvailableError(str(e))

    # Prefer AEMO's own real managed/TOU charging-type shapes when this
    # region/vintage has them; fall back to the FR-10 synthetic
    # redistribution lever only when no real managed-mode data exists.
    used_synthetic_lever = False
    if charging_mode == 'managed':
        try:
            weekday_shape, weekend_shape = combine_charging_type_shapes(profiles, 'managed')
        except TraceSynthesisError:
            used_synthetic_lever = True

    try:
        shaped = require_energy_conserved(
            shape_annual_energy_to_halfhourly(annual_energy_mwh, weekday_shape, weekend_shape, forecast_year)
        )
    except TraceSynthesisError as e:
        raise EvLoadNotAvailableError(str(e))

    trace = shaped.trace
    if charging_mode == 'managed' and used_synthetic_lever:
        trace = apply_managed_charging_lever(trace)
    return np.asarray(trace, dtype=float), shaped.integral_check_pct


def _embedded_ev_trace(energy_mwh: float, forecast_year: int) -> np.ndarray:
    """Half-hourly shape of the EV load already inside an ESOO base.

    ESOO doesn't publish its charging-behaviour assumption, so this uses AEMO's
    own IASR charging-type mix: unmanaged and managed composite shapes weighted
    by their total shares (the workbook's 2040 snapshot: ~70% / 30%)."""
    profiles = _charging_profiles()
    shares = {
        mode: sum(p.share_of_charging for p in profiles if p.charging_mode == mode)
        for mode in ('unmanaged', 'managed')
    }
    total = shares['unmanaged'] + shares['managed']
    if total <= 0:
        raise EvLoadNotAvailableError("EvChargingProfile shares sum to zero; can't weight the embedded-EV shape.")
    w_unmanaged = shares['unmanaged'] / total
    unmanaged, _ = _synthesise_trace(energy_mwh, forecast_year, 'unmanaged', profiles)
    if w_unmanaged >= 1.0:
        return unmanaged
    managed, _ = _synthesise_trace(energy_mwh, forecast_year, 'managed', profiles)
    return w_unmanaged * unmanaged + (1.0 - w_unmanaged) * managed


def _net_ev_adjustment(base_demand: Demand, forecast_year: int, override_gwh: Optional[float]):
    """(embedded EV trace MW, EmbeddedEv) for the 'net of ESOO's EV' option."""
    embedded = resolve_embedded_ev(base_demand.esoo_scenario or None, forecast_year, override_gwh)
    return _embedded_ev_trace(embedded.energy_mwh, forecast_year), embedded


def _get_or_build_ev_load_trace(csiro_scenario: str, forecast_year: int, charging_mode: str) -> EvLoadTrace:
    """Reuse an already-built EvLoadTrace if it still matches the current energy
    source; otherwise build it from AEMO's 2025 IASR WEM trajectory energy and the
    IASR charging shapes (FR-09/FR-10; see utils/iasr_ev_energy.py).

    The annual energy comes from the IASR EV workbook's WEM region, not the older
    2022 CSIRO postcode files: it is SWIS-wide already, so there is no postcode
    aggregation. A stored trace built from an older source (different annual
    energy) is rebuilt rather than trusted."""
    try:
        annual_energy_mwh, _source = scenario_energy_mwh(csiro_scenario, forecast_year)
    except IasrDataNotAvailableError as e:
        raise EvLoadNotAvailableError(str(e))

    existing = EvLoadTrace.objects.filter(
        csiro_scenario=csiro_scenario, year=forecast_year, charging_mode=charging_mode
    ).first()
    if (
        existing
        and (Path(settings.EV_TRACE_DIR) / existing.file_path).exists()
        and abs(existing.annual_energy_mwh - annual_energy_mwh) <= 1e-6 * annual_energy_mwh
    ):
        return existing
    # A dangling row (.npy file gone -- EV_TRACE_DIR is not committed) or one built from
    # different annual energy (e.g. the retired 2022 CSIRO data) falls through and is rebuilt.

    profiles = _charging_profiles()
    trace, integral_check_pct = _synthesise_trace(annual_energy_mwh, forecast_year, charging_mode, profiles)

    return save_trace(
        trace, csiro_scenario, forecast_year, charging_mode,
        annual_energy_mwh=annual_energy_mwh, integral_check_pct=integral_check_pct,
    )


def _base_trace(base_demand: Demand, forecast_year: int) -> np.ndarray:
    if base_demand.interval_minutes != 30:
        raise BaseTraceNotFoundError(
            f"Base Demand '{base_demand.name}' has interval_minutes={base_demand.interval_minutes}; "
            "D12 requires a half-hourly (30-minute) base Demand to add the EV layer to directly."
        )

    if 'FR-G1-01' in (base_demand.description or '') and ESOO_TRACE_CLOCK_MARKER not in base_demand.description:
        raise BaseTraceNotFoundError(
            f"Base Demand '{base_demand.name}' was built before the ESOO trace was put on the AWST "
            "clock, so it is 8 hours out from the EV charging shapes. Rebuild it from the ESOO scenario page "
            "(/esoo-scenario/) and try again."
        )

    trace = None
    try:
        trace = demand_trace(forecast_year, base_demand.iddemand)
    except DemandMatrix.DoesNotExist:
        trace = None

    if trace is not None:
        trace = trace[~np.isnan(trace)]
        if trace.size == 0:
            trace = None

    if trace is None:
        raise BaseTraceNotFoundError(
            f"Base Demand '{base_demand.name}' has no trace for {forecast_year}."
        )
    return np.asarray(trace, dtype=float)


def _ev_scenario_description(base_demand, csiro_scenario, charging_mode, forecast_year, embedded) -> str:
    if embedded is None:
        return (
            f"Auto-built: {base_demand.name} base demand + CSIRO {csiro_scenario} EV load "
            f"({charging_mode}) for {forecast_year} (FR-11)."
        )
    return (
        f"Auto-built: {base_demand.name} base demand, less the {embedded.energy_mwh / 1000:,.0f} GWh of EV load "
        f"already in it, plus CSIRO {csiro_scenario} EV load ({charging_mode}) for {forecast_year} "
        f"(FR-11, net of ESOO's EV; {embedded.source})."
    )


def _net_ev_notes(embedded: EmbeddedEv, scenario_energy_mwh: float) -> list:
    notes = [
        f"Net of ESOO's own EV load: removed {embedded.energy_mwh / 1000:,.0f} GWh already in the base "
        f"({embedded.source}); the scenario's {scenario_energy_mwh / 1000:,.0f} GWh replaces it, "
        f"a net change of {(scenario_energy_mwh - embedded.energy_mwh) / 1000:+,.0f} GWh."
    ]
    if embedded.is_assumption:
        notes.append(
            "The ESOO-to-IASR trajectory mapping (Low/Expected/High = Slower Growth/Step Change/Accelerated "
            "Transition) is a working hypothesis, not published by AEMO. Enter the EV energy by hand to override it."
        )
    if scenario_energy_mwh < embedded.energy_mwh:
        notes.append(
            "This scenario's EV energy is lower than the EV load already in the ESOO base, so the result has "
            "less EV load (and lower demand) than the ESOO base as published."
        )
    return notes


def build_scenario_from_ev(base_demand: Demand, csiro_scenario: str, forecast_year: int,
                            charging_mode: str = 'unmanaged', net_of_esoo_ev: bool = False,
                            esoo_ev_gwh: Optional[float] = None) -> EvScenarioBuildResult:
    """
    FR-11 orchestration: resolve/build the EV load trace, add it to the
    base Demand's own trace, and persist the sum into a derived Demand
    (D2/GR-03 — the base Demand itself is never modified).

    `net_of_esoo_ev`: an ESOO demand forecast already includes EV charging, so
    adding a scenario's EV load on top counts EV growth twice. When set, the EV
    load already inside the base (see utils/esoo_embedded_ev.py; `esoo_ev_gwh`
    overrides its estimate) is removed first: base - embedded EV + scenario EV.
    """
    ev_trace_record = _get_or_build_ev_load_trace(csiro_scenario, forecast_year, charging_mode)
    ev_trace = load_trace(ev_trace_record)
    base_trace = _base_trace(base_demand, forecast_year)

    if ev_trace.size != base_trace.size:
        raise BaseTraceNotFoundError(
            f"EV trace has {ev_trace.size} intervals but base Demand has {base_trace.size} for {forecast_year} "
            "— both should be a full half-hourly year; investigate before combining."
        )
    embedded, embedded_trace = None, None
    if net_of_esoo_ev:
        embedded_trace, embedded = _net_ev_adjustment(base_demand, forecast_year, esoo_ev_gwh)
        if embedded_trace.size != base_trace.size:
            raise BaseTraceNotFoundError(
                f"Embedded-EV trace has {embedded_trace.size} intervals but the base Demand has {base_trace.size}."
            )
        net_trace = base_trace - embedded_trace + ev_trace
    else:
        net_trace = base_trace + ev_trace

    # Demand.name is capped at 45 chars (see esoo_scenario_views.py's
    # comment on the same limit). Truncate the base Demand's own name
    # rather than the combined string, so the EV-identifying suffix always
    # survives intact instead of being cut off mid-word/mid-year (a real
    # cosmetic bug hit when this first ran against a real 30-char ESOO
    # base title: "... + EV medium 203" instead of "...2030").
    suffix = f" + EV {'net ' if net_of_esoo_ev else ''}{csiro_scenario} {forecast_year}"
    max_base_len = 45 - len(suffix)
    base_name = base_demand.name if len(base_demand.name) <= max_base_len else base_demand.name[:max_base_len].rstrip()
    title = f"{base_name}{suffix}"

    demand_obj, created = Demand.objects.update_or_create(
        name=title,
        defaults={
            'description': _ev_scenario_description(
                base_demand, csiro_scenario, charging_mode, forecast_year, embedded,
            ),
            'interval_minutes': 30,
            'forecast_year': forecast_year,
            'parent_demand': base_demand,
            'csiro_scenario': csiro_scenario,
            'charging_mode': charging_mode,
            'net_of_esoo_ev': net_of_esoo_ev,
        },
    )

    # Idempotent regeneration: clear any previous trace for this
    # demand/year before writing the new one.
    clear_demand_trace(forecast_year, demand_obj.iddemand)
    set_demand_trace(forecast_year, demand_obj.iddemand, net_trace)

    notes = []
    if ev_trace_record.integral_check_pct and ev_trace_record.integral_check_pct > 0.01:
        notes.append(
            f"EV trace integral check {ev_trace_record.integral_check_pct:.4f}% exceeds FR-09's 0.01% tolerance."
        )
    if embedded is not None:
        notes.extend(_net_ev_notes(embedded, ev_trace_record.annual_energy_mwh))

    return EvScenarioBuildResult(
        demand=demand_obj, title=title, forecast_year=forecast_year,
        csiro_scenario=csiro_scenario, charging_mode=charging_mode, n_rows=len(net_trace),
        ev_annual_energy_mwh=ev_trace_record.annual_energy_mwh,
        integral_check_pct=ev_trace_record.integral_check_pct or 0.0, notes=notes,
        net_of_esoo_ev=embedded is not None,
        esoo_ev_energy_mwh=embedded.energy_mwh if embedded else 0.0,
        esoo_ev_source=embedded.source if embedded else '',
    )


def compare_ev_sensitivity(base_demand: Demand, forecast_year: int, charging_mode: str,
                           net_of_esoo_ev: bool = False, esoo_ev_gwh: Optional[float] = None):
    """
    FR-12 orchestration. Resolve/build the EV load trace for every CSIRO
    uptake scenario (Low/Medium/High), add each to the base Demand's own
    half-hourly trace, and hand the arrays to the pure comparison.

    Never creates derived Demand rows — the comparison is analysis, not
    a build (use build_scenario_from_ev for that). Returns
    (SensitivityReport | None, per_scenario_meta: dict, unavailable: list[(scenario, reason)],
    embedded: EmbeddedEv | None).

    With `net_of_esoo_ev`, each scenario's EV trace has the EV load already in
    the ESOO base subtracted, so the comparison is against the ESOO base *as
    published* and its "EV energy" / deltas are the net change (see
    build_scenario_from_ev).
    """
    base_trace = _base_trace(base_demand, forecast_year)
    embedded, embedded_trace = None, None
    if net_of_esoo_ev:
        embedded_trace, embedded = _net_ev_adjustment(base_demand, forecast_year, esoo_ev_gwh)

    ev_traces, per_scenario_meta, unavailable = {}, {}, []
    for scenario in SCENARIO_ORDER:
        try:
            record = _get_or_build_ev_load_trace(scenario, forecast_year, charging_mode)
            arr = load_trace(record)
        except (EvLoadNotAvailableError, FileNotFoundError) as e:
            unavailable.append((scenario, str(e)))
            continue
        if arr.size != base_trace.size:
            unavailable.append((
                scenario,
                f"EV trace has {arr.size} intervals but the base Demand has {base_trace.size} for {forecast_year}.",
            ))
            continue
        if embedded_trace is not None:
            if embedded_trace.size != arr.size:
                unavailable.append((scenario, "Embedded-EV trace length differs from the EV trace."))
                continue
            arr = arr - embedded_trace
        ev_traces[scenario] = arr
        per_scenario_meta[scenario] = record

    if not ev_traces:
        return None, {}, unavailable, embedded

    report = compare_scenarios(base_trace, ev_traces, forecast_year, charging_mode)
    for row in report.rows:
        meta = per_scenario_meta.get(row.csiro_scenario)
        if meta is not None:
            row.integral_check_pct = meta.integral_check_pct
            if meta.integral_check_pct and meta.integral_check_pct > 0.01:
                row.notes.append(
                    f"integral check {meta.integral_check_pct:.4f}% exceeds FR-09's 0.01% tolerance"
                )
    return report, per_scenario_meta, unavailable, embedded


@login_required
def ev_scenario_compare(request):
    """FR-12 sensitivity comparison. Reads a base Demand / year / charging
    mode from the query string and shows Low/Medium/High side by side."""
    base_scenarios = (
        Demand.objects.filter(interval_minutes=30, parent_demand__isnull=True)
        .order_by('name')
    )
    charging_mode_choices = EV_CHARGING_MODE_CHOICES

    selected_base_id = request.GET.get('base_scenario') or ''
    selected_charging_mode = request.GET.get('charging_mode', 'unmanaged')
    selected_forecast_year = request.GET.get('forecast_year', '')
    net_of_esoo_ev = request.GET.get('net_of_esoo_ev') == 'on'
    selected_esoo_ev_gwh = request.GET.get('esoo_ev_gwh', '').strip()

    report = None
    per_scenario_meta = {}
    unavailable = []
    embedded = None
    error = None

    if selected_base_id and selected_forecast_year:
        try:
            base_demand = Demand.objects.get(pk=selected_base_id)
            forecast_year = int(selected_forecast_year)
            esoo_ev_gwh = _parse_gwh(selected_esoo_ev_gwh)
        except (Demand.DoesNotExist, TypeError, ValueError):
            error = "Select a valid base scenario and forecast year (and a number for the EV energy, if entered)."
        else:
            try:
                report, per_scenario_meta, unavailable, embedded = compare_ev_sensitivity(
                    base_demand, forecast_year, selected_charging_mode,
                    net_of_esoo_ev=net_of_esoo_ev, esoo_ev_gwh=esoo_ev_gwh,
                )
            except (BaseTraceNotFoundError, SensitivityComparisonError,
                    EmbeddedEvNotAvailableError, EvLoadNotAvailableError) as e:
                error = str(e)

    return render(request, 'ev_scenario_compare.html', {
        'base_scenarios': base_scenarios,
        'charging_mode_choices': charging_mode_choices,
        'selected_base_id': selected_base_id,
        'selected_charging_mode': selected_charging_mode,
        'selected_forecast_year': selected_forecast_year,
        'net_of_esoo_ev': net_of_esoo_ev,
        'selected_esoo_ev_gwh': selected_esoo_ev_gwh,
        'embedded': embedded,
        'embedded_gwh': embedded.energy_mwh / 1000.0 if embedded else None,
        'report': report,
        'chart_html': _build_comparison_chart(report, net_of_esoo_ev=embedded is not None) if report else '',
        'unavailable': unavailable,
        'error': error,
    })


def _parse_gwh(raw: str) -> Optional[float]:
    """Optional GWh form field: blank -> None, otherwise a float (ValueError if not a number)."""
    raw = (raw or '').strip().replace(',', '')
    return float(raw) if raw else None


def _build_comparison_chart(report, net_of_esoo_ev: bool = False):
    """Peak-day half-hourly overlay: base demand for the worst-case day,
    plus base+EV for each CSIRO scenario (or, net of ESOO's EV, base - the EV
    already in it + the scenario's EV)."""
    import plotly.graph_objects as go

    colours = {'low': '#3498db', 'medium': '#f39c12', 'high': '#e74c3c'}
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=report.peak_day_times, y=report.peak_day_base_mw, mode='lines',
        name='Base demand', line=dict(color='#2c3e50', width=3),
    ))
    for scenario, series in report.peak_day_net_mw.items():
        fig.add_trace(go.Scatter(
            x=report.peak_day_times, y=series, mode='lines',
            name=f"Base {'net of ESOO EV + EV' if net_of_esoo_ev else '+ EV'} ({scenario})",
            line=dict(color=colours.get(scenario, '#7f8c8d'), dash='dot'),
        ))
    fig.update_layout(
        title=(f"Worst-case day ({report.peak_day_date}): half-hourly demand, base vs base "
               f"{'with the ESOO EV load swapped for each scenario' if net_of_esoo_ev else '+ EV'}"),
        xaxis_title='Time of day', yaxis_title='Demand (MW)',
        height=430, hovermode='x unified',
        xaxis=dict(tickmode='array', tickvals=report.peak_day_times[::4]),
    )
    return fig.to_html(include_plotlyjs='cdn', full_html=False, div_id='ev_sensitivity_chart')


@login_required
def ev_scenario_selector(request):
    """FR-11 selector view. GET renders the picker; POST builds the derived Demand."""
    base_scenarios = Demand.objects.filter(interval_minutes=30, parent_demand__isnull=True).order_by('name')
    scenario_choices = SCENARIO_LABELS
    charging_mode_choices = EV_CHARGING_MODE_CHOICES

    result: Optional[EvScenarioBuildResult] = None
    selected_base_id = request.POST.get('base_scenario') or request.GET.get('base_scenario')
    selected_scenario = request.POST.get('csiro_scenario', '')
    selected_charging_mode = request.POST.get('charging_mode', 'unmanaged')
    selected_forecast_year = request.POST.get('forecast_year', '')
    net_of_esoo_ev = request.POST.get('net_of_esoo_ev') == 'on'
    selected_esoo_ev_gwh = request.POST.get('esoo_ev_gwh', '').strip()

    if request.method == 'POST':
        base_demand = None
        try:
            base_demand = Demand.objects.get(pk=selected_base_id)
            forecast_year = int(selected_forecast_year)
            esoo_ev_gwh = _parse_gwh(selected_esoo_ev_gwh)
        except (Demand.DoesNotExist, TypeError, ValueError):
            messages.error(
                request,
                "Please select a valid base scenario, CSIRO uptake scenario and forecast year "
                "(and a number for the EV energy, if entered).",
            )
            base_demand = None

        if base_demand is not None and selected_scenario:
            try:
                result = build_scenario_from_ev(
                    base_demand, selected_scenario, forecast_year, selected_charging_mode,
                    net_of_esoo_ev=net_of_esoo_ev, esoo_ev_gwh=esoo_ev_gwh,
                )
                messages.success(
                    request,
                    f"Built Demand '{result.title}' — {result.n_rows} half-hourly rows "
                    f"(EV annual energy: {result.ev_annual_energy_mwh:,.1f} MWh, "
                    f"integral check {result.integral_check_pct:.4f}%)."
                )
                for note in result.notes:
                    messages.warning(request, note)
            except (EvLoadNotAvailableError, BaseTraceNotFoundError, EmbeddedEvNotAvailableError) as e:
                messages.error(request, str(e))
        elif base_demand is not None and not selected_scenario:
            messages.error(request, "Please select an EV scenario (Low/Medium/High).")

    context = {
        'base_scenarios': base_scenarios,
        'scenario_choices': scenario_choices,
        'charging_mode_choices': charging_mode_choices,
        'result': result,
        'selected_base_id': selected_base_id,
        'selected_scenario': selected_scenario,
        'selected_charging_mode': selected_charging_mode,
        'selected_forecast_year': selected_forecast_year,
        'net_of_esoo_ev': net_of_esoo_ev,
        'selected_esoo_ev_gwh': selected_esoo_ev_gwh,
    }
    return render(request, 'ev_scenario_selector.html', context)
