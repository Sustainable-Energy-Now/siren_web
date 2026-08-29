# powermatchui/views/ev_scenario_views.py
"""
FR-11/FR-12 — EV load scenario builder (Outcome A: sensitivity capability).

Mirrors esoo_scenario_views.py's orchestration shape but the construction
chain is genuinely different (no LDC/anchor-fit — see
powermatchui.utils.ev_trace_synthesis's module docstring):

    EvUptakePostcodeFigure (passed only) + SwisBoundaryMembership
        -> powermatchui.utils.ev_reconciliation.aggregate_swis_annual_energy   (FR-06)
    EvChargingProfile (charging_mode='unmanaged', or 'managed' where real data exists)
        -> powermatchui.utils.ev_trace_synthesis.combine_charging_type_shapes  (FR-09 step 1)
    annual energy + composite shape
        -> powermatchui.utils.ev_trace_synthesis.shape_annual_energy_to_halfhourly (FR-09 steps 2-3)
        -> powermatchui.utils.ev_trace_synthesis.apply_managed_charging_lever (FR-10, if requested)
        -> powermatchui.utils.ev_load_trace_store.save_trace (EvLoadTrace, D12 file-based storage)

FR-11/GR-03 integration (D2: EV layer is fully additional and separable):
this NEVER mutates an existing base Scenario's supplyfactors. Instead it
creates/updates a *derived* Scenario ("<base title> + EV <scenario> <year>")
whose Load facility carries base + EV trace, elementwise. The base
Scenario is always left untouched, so GR-03's "no EV layer" acceptance
test is satisfied by construction: simply not building/selecting a
derived scenario reproduces the base trace exactly, and switching which
CSIRO scenario is selected only changes which derived Scenario exists —
the base Load facility's own supplyfactors are never touched.

FR-07 note: this view does NOT re-run the backcast gate itself (that is
validate_ev_data's job, against a caller-supplied published-aggregates
file) -- it only trusts EvUptakePostcodeFigure rows already marked
validation_status='passed', per the Section 8 standing principle.
"""
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from siren_web.models import (
    EV_CHARGING_MODE_CHOICES,
    EV_CSIRO_SCENARIO_CHOICES,
    EvChargingProfile,
    EvLoadTrace,
    EvUptakePostcodeFigure,
    Scenarios,
    ScenariosFacilities,
    ScenariosTechnologies,
    SwisBoundaryMembership,
    Technologies,
    facilities,
    supplyfactors,
)
from powermatchui.utils.ev_load_trace_store import load_trace, save_trace
from powermatchui.utils.ev_reconciliation import aggregate_swis_annual_energy
from powermatchui.utils.ev_trace_synthesis import (
    ChargingTypeProfile,
    TraceSynthesisError,
    apply_managed_charging_lever,
    combine_charging_type_shapes,
    require_energy_conserved,
    shape_annual_energy_to_halfhourly,
)

LOAD_TECHNOLOGY_NAME = 'Load'
LOAD_TECHNOLOGY_SIGNATURE = 'LOAD'


class EvLoadNotAvailableError(ValueError):
    """Raised when there isn't enough validated data to build/find an EV load trace."""


class BaseTraceNotFoundError(ValueError):
    """Raised when the selected base Scenario has no usable half-hourly Load trace."""


@dataclass
class EvScenarioBuildResult:
    scenario: Scenarios
    facility: facilities
    title: str
    forecast_year: int
    csiro_scenario: str
    charging_mode: str
    n_rows: int
    ev_annual_energy_mwh: float
    integral_check_pct: float
    notes: list = field(default_factory=list)


def _get_or_build_ev_load_trace(csiro_scenario: str, forecast_year: int, charging_mode: str) -> EvLoadTrace:
    """Reuse an already-built EvLoadTrace if one exists; otherwise build it
    from EvUptakePostcodeFigure + EvChargingProfile (FR-06/FR-09/FR-10)."""
    existing = EvLoadTrace.objects.filter(
        csiro_scenario=csiro_scenario, year=forecast_year, charging_mode=charging_mode
    ).first()
    if existing:
        return existing

    figures = list(
        EvUptakePostcodeFigure.objects.filter(
            csiro_scenario=csiro_scenario, forecast_year=forecast_year, validation_status='passed',
        ).values('postcode', 'forecast_year', 'csiro_scenario', 'consumption_kwh')
    )
    if not figures:
        raise EvLoadNotAvailableError(
            f"No validated (validation_status='passed') EvUptakePostcodeFigure rows for "
            f"{csiro_scenario}/{forecast_year} — run extract_ev_figures and validate_ev_data first."
        )

    membership_by_postcode = {
        m.postcode: {'membership_status': m.membership_status, 'apportionment_fraction': m.apportionment_fraction}
        for m in SwisBoundaryMembership.objects.all()
    }
    aggregation = aggregate_swis_annual_energy(figures, membership_by_postcode)
    key = (csiro_scenario, forecast_year)
    annual_energy_mwh = aggregation.aggregated_mwh.get(key)
    if annual_energy_mwh is None:
        raise EvLoadNotAvailableError(
            f"SWIS-wide annual energy could not be aggregated for {csiro_scenario}/{forecast_year} "
            "(no postcode in this figure set has a confirmed SwisBoundaryMembership row)."
        )

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

    return save_trace(
        trace, csiro_scenario, forecast_year, charging_mode,
        annual_energy_mwh=annual_energy_mwh, integral_check_pct=shaped.integral_check_pct,
    )


def _base_trace(base_scenario: Scenarios, forecast_year: int) -> np.ndarray:
    if base_scenario.interval_minutes != 30:
        raise BaseTraceNotFoundError(
            f"Base scenario '{base_scenario.title}' has interval_minutes={base_scenario.interval_minutes}; "
            "D12 requires a half-hourly (30-minute) base scenario to add the EV layer to directly."
        )
    rows = list(
        supplyfactors.objects.filter(
            idfacilities__scenarios=base_scenario,
            idfacilities__idtechnologies__technology_name=LOAD_TECHNOLOGY_NAME,
            year=forecast_year,
        ).order_by('hour').values_list('quantum', flat=True)
    )
    if not rows:
        raise BaseTraceNotFoundError(
            f"Base scenario '{base_scenario.title}' has no Load supplyfactors for {forecast_year}."
        )
    return np.array(rows, dtype=float)


def _get_or_create_load_technology() -> Technologies:
    tech, _ = Technologies.objects.get_or_create(
        technology_name=LOAD_TECHNOLOGY_NAME,
        defaults={'technology_signature': LOAD_TECHNOLOGY_SIGNATURE, 'category': 'Load', 'renewable': 0, 'dispatchable': 0},
    )
    return tech


def build_scenario_from_ev(base_scenario: Scenarios, csiro_scenario: str, forecast_year: int,
                            charging_mode: str = 'unmanaged') -> EvScenarioBuildResult:
    """
    FR-11 orchestration: resolve/build the EV load trace, add it to the
    base scenario's own Load trace, and persist the sum into a derived
    Scenario (D2/GR-03 — the base Scenario itself is never modified).
    """
    ev_trace_record = _get_or_build_ev_load_trace(csiro_scenario, forecast_year, charging_mode)
    ev_trace = load_trace(ev_trace_record)
    base_trace = _base_trace(base_scenario, forecast_year)

    if ev_trace.size != base_trace.size:
        raise BaseTraceNotFoundError(
            f"EV trace has {ev_trace.size} intervals but base scenario has {base_trace.size} for {forecast_year} "
            "— both should be a full half-hourly year; investigate before combining."
        )
    net_trace = base_trace + ev_trace

    # Scenarios.title is capped at 45 chars (see esoo_scenario_views.py's
    # comment on the same limit). Truncate the base scenario's own title
    # rather than the combined string, so the EV-identifying suffix always
    # survives intact instead of being cut off mid-word/mid-year (a real
    # cosmetic bug hit when this first ran against a real 30-char ESOO
    # base title: "... + EV medium 203" instead of "...2030").
    suffix = f" + EV {csiro_scenario} {forecast_year}"
    max_base_len = 45 - len(suffix)
    base_title = base_scenario.title if len(base_scenario.title) <= max_base_len else base_scenario.title[:max_base_len].rstrip()
    title = f"{base_title}{suffix}"
    load_tech = _get_or_create_load_technology()

    scenario_obj, created = Scenarios.objects.get_or_create(
        title=title,
        defaults={
            'interval_minutes': 30,
            'description': (
                f"Auto-built: {base_scenario.title} base demand + CSIRO {csiro_scenario} EV load "
                f"({charging_mode}) for {forecast_year} (FR-11)."
            ),
        },
    )
    if not created and scenario_obj.interval_minutes != 30:
        scenario_obj.interval_minutes = 30
        scenario_obj.save(update_fields=['interval_minutes'])

    # facility_code (max 30 chars, uniquely constrained) is derived from the
    # scenario id rather than truncating `title` -- base ESOO scenario titles
    # are themselves exactly 30 characters, so title[:30] silently dropped
    # the "+ EV ..." suffix entirely and collided with the base scenario's
    # own Load facility (a real bug hit when this was first run against a
    # real ESOO base scenario, 2026-08-26).
    facility_code = f"EV-{csiro_scenario}-{forecast_year}-{scenario_obj.idscenarios}"[:30]
    facility_obj, _ = facilities.objects.get_or_create(
        facility_name=title,
        defaults={'facility_code': facility_code, 'idtechnologies': load_tech, 'active': True, 'existing': True, 'capacity': 0},
    )
    if facility_obj.idtechnologies_id != load_tech.idtechnologies:
        facility_obj.idtechnologies = load_tech
        facility_obj.save(update_fields=['idtechnologies'])

    ScenariosFacilities.objects.get_or_create(idscenarios=scenario_obj, idfacilities=facility_obj)
    scenario_tech, st_created = ScenariosTechnologies.objects.get_or_create(
        idscenarios=scenario_obj, idtechnologies=load_tech,
        defaults={'merit_order': 0, 'capacity': 0, 'mult': 1, 'col': None},
    )
    if not st_created and scenario_tech.merit_order != 0:
        scenario_tech.merit_order = 0
        scenario_tech.save(update_fields=['merit_order'])

    supplyfactors.objects.filter(idfacilities=facility_obj, year=forecast_year).delete()
    records = [
        supplyfactors(idfacilities=facility_obj, year=forecast_year, hour=h, supply=0, quantum=float(v))
        for h, v in enumerate(net_trace)
    ]
    supplyfactors.objects.bulk_create(records, batch_size=1000)

    notes = []
    if ev_trace_record.integral_check_pct and ev_trace_record.integral_check_pct > 0.01:
        notes.append(
            f"EV trace integral check {ev_trace_record.integral_check_pct:.4f}% exceeds FR-09's 0.01% tolerance."
        )

    return EvScenarioBuildResult(
        scenario=scenario_obj, facility=facility_obj, title=title, forecast_year=forecast_year,
        csiro_scenario=csiro_scenario, charging_mode=charging_mode, n_rows=len(records),
        ev_annual_energy_mwh=ev_trace_record.annual_energy_mwh,
        integral_check_pct=ev_trace_record.integral_check_pct or 0.0, notes=notes,
    )


@login_required
def ev_scenario_selector(request):
    """FR-11 selector view. GET renders the picker; POST builds the derived scenario."""
    base_scenarios = Scenarios.objects.filter(interval_minutes=30).order_by('title')
    scenario_choices = EV_CSIRO_SCENARIO_CHOICES
    charging_mode_choices = EV_CHARGING_MODE_CHOICES

    result: Optional[EvScenarioBuildResult] = None
    selected_base_id = request.POST.get('base_scenario') or request.GET.get('base_scenario')
    selected_scenario = request.POST.get('csiro_scenario', '')
    selected_charging_mode = request.POST.get('charging_mode', 'unmanaged')
    selected_forecast_year = request.POST.get('forecast_year', '')

    if request.method == 'POST':
        base_scenario = None
        try:
            base_scenario = Scenarios.objects.get(pk=selected_base_id)
            forecast_year = int(selected_forecast_year)
        except (Scenarios.DoesNotExist, TypeError, ValueError):
            messages.error(request, "Please select a valid base scenario, CSIRO uptake scenario and forecast year.")
            base_scenario = None

        if base_scenario is not None and selected_scenario:
            try:
                result = build_scenario_from_ev(base_scenario, selected_scenario, forecast_year, selected_charging_mode)
                messages.success(
                    request,
                    f"Built Powermatch scenario '{result.title}' — {result.n_rows} half-hourly rows "
                    f"(EV annual energy: {result.ev_annual_energy_mwh:,.1f} MWh, "
                    f"integral check {result.integral_check_pct:.4f}%)."
                )
                for note in result.notes:
                    messages.warning(request, note)
            except EvLoadNotAvailableError as e:
                messages.error(request, str(e))
            except BaseTraceNotFoundError as e:
                messages.error(request, str(e))
        elif base_scenario is not None and not selected_scenario:
            messages.error(request, "Please select a CSIRO uptake scenario (Low/Medium/High).")

    context = {
        'base_scenarios': base_scenarios,
        'scenario_choices': scenario_choices,
        'charging_mode_choices': charging_mode_choices,
        'result': result,
        'selected_base_id': selected_base_id,
        'selected_scenario': selected_scenario,
        'selected_charging_mode': selected_charging_mode,
        'selected_forecast_year': selected_forecast_year,
    }
    return render(request, 'ev_scenario_selector.html', context)
