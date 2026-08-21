# powermatchui/views/esoo_scenario_views.py
"""
FR-G1-01 — WEM ESOO demand-forecast scenario selector.

Lets a user pick a WEM ESOO demand-forecast vintage/scenario/POE/year and
turns it into a Powermatch-ready scenario: a half-hourly demand trace,
written into `supplyfactors` for a `Technologies(category='Load')`
facility attached to a `Scenarios(interval_minutes=30)` row, using the
*existing* Powermatch demand-input mechanism (Load facility +
supplyfactors) rather than a parallel path.

Construction chain (Phase 2 modules, already unit-tested against real
data — this view is the first thing that chains them together against a
real ESOO figure and real FacilityScada data, so treat it as unverified
until it's actually run once against the live database):

    EsooFigure anchors (peak, minimum, energy)
        -> powermatchui.utils.esoo_ldc.fit_ldc_to_anchors
        -> powermatchui.utils.esoo_trace_synthesis.synthesize_chronological_trace
        -> powermatchui.utils.esoo_reconciliation.reconcile_trace / require_reconciled
        -> supplyfactors rows

D5 (domain separation): this view also surfaces the vintage's
domain='supply_adequacy' EsooFigure rows (RCT, capacity outlook) as
read-only reference data (FR-G1-06). Those rows are fetched in a
completely separate query from the demand anchors and are never passed
into fit_ldc_to_anchors/synthesize_chronological_trace/supplyfactors — the
template renders them as a plain list alongside the scenario result,
nothing more.
"""
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.db.models.functions import ExtractYear
from django.shortcuts import redirect, render

from siren_web.models import (
    EsooFigure,
    EsooVintage,
    ESOO_POE_LEVEL_CHOICES,
    ESOO_SCENARIO_CHOICES,
    FacilityScada,
    Scenarios,
    ScenariosFacilities,
    ScenariosTechnologies,
    Technologies,
    facilities,
    supplyfactors,
)
from powermatchui.utils.esoo_ldc import LDCConstructionError, fit_ldc_to_anchors
from powermatchui.utils.esoo_reconciliation import (
    TraceRejectedError,
    reconcile_trace,
    require_reconciled,
)
from powermatchui.utils.esoo_trace_synthesis import (
    select_reference_year,
    synthesize_chronological_trace,
)

INTERVAL_HOURS = 0.5  # FR-G1-01 always builds a half-hourly demand trace
LOAD_TECHNOLOGY_NAME = 'Load'
LOAD_TECHNOLOGY_SIGNATURE = 'LOAD'


def _expected_half_hourly_intervals(year: int) -> int:
    """Real half-hourly interval count for one calendar year -- used to
    convert a target year's annual energy anchor into a target average MW
    (fit_ldc_to_anchors' target_n_intervals), independent of however long
    the reference year's own shape array happens to be."""
    import calendar
    return (366 if calendar.isleap(year) else 365) * 48

# A reference year needs to be close to a full half-hourly year of
# FacilityScada data (17520 intervals in a non-leap year, 17568 in a leap
# year) to be trusted as a shape prior; this allows headroom for minor
# real-world data gaps without accepting a mostly-empty year.
MIN_INTERVALS_FOR_REFERENCE_YEAR = 17000


class AnchorNotFoundError(ValueError):
    """Raised when a required ESOO demand anchor isn't published for the
    requested (vintage, scenario, POE, forecast_year) combination."""


class ReferenceShapeError(ValueError):
    """Raised when no usable reference-year shape can be built from
    FacilityScada."""


@dataclass
class EsooScenarioBuildResult:
    """Everything the template needs to report what was built."""
    scenario: Scenarios
    facility: facilities
    title: str
    forecast_year: int
    reference_year: str
    n_rows: int
    gamma: float
    ldc_notes: list = field(default_factory=list)
    synthesis_notes: list = field(default_factory=list)
    reconciliation_notes: list = field(default_factory=list)
    peak_mw: float = 0.0
    minimum_mw: float = 0.0
    energy_mwh: float = 0.0
    achieved_peak_mw: float = 0.0
    achieved_minimum_mw: float = 0.0
    achieved_energy_mwh: float = 0.0


def _energy_to_mwh(figure: EsooFigure) -> float:
    unit = (figure.unit or '').strip().upper()
    if unit == 'GWH':
        return figure.value * 1000.0
    if unit == 'MWH':
        return figure.value
    raise AnchorNotFoundError(
        f"Energy figure (id={figure.idesoofigure}) has unexpected unit '{figure.unit}'; "
        "expected GWh or MWh — refusing to guess a conversion."
    )


def _power_mw(figure: EsooFigure, label: str) -> float:
    unit = (figure.unit or '').strip().upper()
    if unit != 'MW':
        raise AnchorNotFoundError(
            f"{label} figure (id={figure.idesoofigure}) has unexpected unit '{figure.unit}'; "
            "expected MW — refusing to guess a conversion."
        )
    return figure.value


def resolve_esoo_anchors(vintage: EsooVintage, esoo_scenario: str, poe: int, forecast_year: int,
                          demand_basis: str = 'operational'):
    """
    Pull the three FR-G1-02 anchors (peak, minimum, annual energy) from
    EsooFigure for one (vintage, scenario, POE, forecast_year) combination.

    - peak: domain='demand', metric='peak_summer' (WEM's annual system
      peak is a summer, aircon-driven peak), at the user-selected POE.
      No fallback: if this exact combination isn't published, fail.
    - energy: metric='energy' at the user-selected POE if published,
      else at poe_level=NULL (many vintages publish energy forecasts
      without a POE breakdown — the model's own documented convention,
      not a guess). No further fallback.
    - minimum: metric='minimum'. AEMO's minimum-demand POE convention
      isn't settled in this codebase (see validate_esoo_data.py's
      OQ-3 note), so this follows the brief's documented policy: prefer
      POE90 where published, else the closest available POE to 90 for
      this (vintage, scenario, forecast_year).

    Coverage across the ESOO archive is genuinely uneven (not every
    vintage/year/scenario published every figure) — this never guesses
    or defaults a missing anchor, it raises AnchorNotFoundError naming
    exactly what's missing.
    """
    base_qs = EsooFigure.objects.filter(
        vintage=vintage,
        domain='demand',
        demand_growth_scenario=esoo_scenario,
        forecast_year=forecast_year,
        demand_basis=demand_basis,
    )

    missing = []

    peak_fig = base_qs.filter(metric='peak_summer', poe_level=poe).first()
    if peak_fig is None:
        missing.append(f"peak_summer at POE{poe}")

    energy_fig = base_qs.filter(metric='energy', poe_level=poe).first()
    if energy_fig is None:
        energy_fig = base_qs.filter(metric='energy', poe_level__isnull=True).first()
    if energy_fig is None:
        missing.append(f"energy (at POE{poe} or with no POE breakdown)")

    minimum_candidates = list(base_qs.filter(metric='minimum'))
    min_fig = None
    if minimum_candidates:
        min_fig = min(minimum_candidates, key=lambda f: abs((f.poe_level or 0) - 90))
    else:
        missing.append("minimum demand (any POE)")

    if missing:
        raise AnchorNotFoundError(
            f"WEM ESOO {vintage.year} / {esoo_scenario} / POE{poe} / {forecast_year} "
            f"({demand_basis}) is missing required anchor(s): {', '.join(missing)}. "
            "ESOO coverage is uneven across vintages and forecast years — this exact "
            "combination wasn't published; try a different vintage, scenario, POE or year."
        )

    peak_mw = _power_mw(peak_fig, 'peak_summer')
    minimum_mw = _power_mw(min_fig, 'minimum')
    energy_mwh = _energy_to_mwh(energy_fig)

    return peak_mw, minimum_mw, energy_mwh, peak_fig, min_fig, energy_fig


def build_reference_shape():
    """
    Aggregate real FacilityScada data to total system operational demand
    per interval, for one reference year — the D10 "reference-year shape
    prior" fed to fit_ldc_to_anchors / synthesize_chronological_trace.

    FacilityScada.quantity is half-hourly ENERGY (MWh), not power (MW) --
    confirmed 2026-08-19 against live AEMO data (see
    compute_annual_demand_actuals.py's module docstring). Average MW per
    interval = MWh / 0.5h, so the per-interval sum below is doubled. This
    scaling has no effect on fit_ldc_to_anchors' gamma or the synthesised
    trace's shape -- peak_normalise() divides out any uniform constant --
    but keeping it in true MW avoids a mislabelled variable and matters if
    this shape is ever consumed anywhere that isn't normalisation-first.

    "Total system operational demand" is approximated here as the sum of
    all facilities' SCADA generation across the whole interval set, which
    is this codebase's existing definition of operational demand (see
    memory: "RE% operational = RE sources / operational demand
    (grid-connected generation)") — i.e. total scheduled/metered
    generation is used as the demand-shape proxy, since generation and
    consumption are equal in real time (ignoring losses).

    Picks the most recent year with enough FacilityScada intervals to
    count as a complete year (see MIN_INTERVALS_FOR_REFERENCE_YEAR),
    via esoo_trace_synthesis.select_reference_year's default policy
    (most-recent-available). horizon_aware reference-year selection
    (FR-G1-04's optional per-forecast-year cycling) is not wired up here;
    every call uses the single most recent complete year.
    """
    # Count DISTINCT dispatch_interval values per year, not raw
    # FacilityScada rows -- a plain Count('scada_year') counts one row per
    # facility per interval (~76 facilities), so even a partial year
    # trivially clears MIN_INTERVALS_FOR_REFERENCE_YEAR on row volume
    # alone, letting an in-progress current year masquerade as complete.
    year_counts = (
        FacilityScada.objects
        .annotate(scada_year=ExtractYear('dispatch_interval'))
        .values('scada_year')
        .annotate(n=Count('dispatch_interval', distinct=True))
        .order_by('scada_year')
    )
    complete_years = [
        str(row['scada_year']) for row in year_counts
        if row['n'] and row['n'] >= MIN_INTERVALS_FOR_REFERENCE_YEAR
    ]
    if not complete_years:
        raise ReferenceShapeError(
            "No FacilityScada year has enough recorded intervals "
            f"(>= {MIN_INTERVALS_FOR_REFERENCE_YEAR}) to serve as a reference-year shape."
        )

    reference_year = select_reference_year(complete_years, horizon_aware=False)

    rows = (
        FacilityScada.objects
        .filter(dispatch_interval__year=int(reference_year))
        .values('dispatch_interval')
        .annotate(total_mwh=Sum('quantity'))
        .order_by('dispatch_interval')
    )
    reference_shape = np.array([float(r['total_mwh']) * 2 for r in rows], dtype=float)
    if reference_shape.size == 0:
        raise ReferenceShapeError(f"No aggregated FacilityScada data found for reference year {reference_year}.")

    return reference_shape, reference_year


def _get_or_create_load_technology() -> Technologies:
    """Reuse the same 'Load' Technologies row every scenario's
    fetch_technology_attributes/fetch_supplyfactors_data already expects
    (see siren_web/database_operations.py) — not a new parallel path."""
    tech, _ = Technologies.objects.get_or_create(
        technology_name=LOAD_TECHNOLOGY_NAME,
        defaults={
            'technology_signature': LOAD_TECHNOLOGY_SIGNATURE,
            'category': 'Load',
            'renewable': 0,
            'dispatchable': 0,
        },
    )
    return tech


def _scenario_title(vintage: EsooVintage, esoo_scenario: str, poe: int, forecast_year: int) -> str:
    # Scenarios.title / facilities.facility_name / facility_code are all
    # limited to 45/45/30 chars respectively; this format comfortably fits.
    return f"ESOO {vintage.year} {esoo_scenario} POE{poe} {forecast_year}"[:45]


def build_scenario_from_esoo(vintage: EsooVintage, esoo_scenario: str, poe: int, forecast_year: int,
                              demand_basis: str = 'operational') -> EsooScenarioBuildResult:
    """
    FR-G1-01 orchestration: anchors -> LDC -> chronological trace ->
    reconciliation -> persisted supplyfactors, reusing the existing Load
    facility / Scenarios / supplyfactors mechanism.
    """
    peak_mw, minimum_mw, energy_mwh, peak_fig, min_fig, energy_fig = resolve_esoo_anchors(
        vintage, esoo_scenario, poe, forecast_year, demand_basis
    )

    reference_shape, reference_year = build_reference_shape()

    ldc_fit = fit_ldc_to_anchors(
        reference_shape=reference_shape,
        target_peak=peak_mw,
        target_minimum=minimum_mw,
        target_energy_mwh=energy_mwh,
        interval_hours=INTERVAL_HOURS,
        reference_year=reference_year,
        target_n_intervals=_expected_half_hourly_intervals(forecast_year),
    )

    synthesis = synthesize_chronological_trace(
        ldc_fit.absolute, reference_shape, reference_year=reference_year
    )

    report = require_reconciled(reconcile_trace(
        synthesis.trace,
        target_peak=peak_mw,
        target_minimum=minimum_mw,
        target_energy_mwh=energy_mwh,
        interval_hours=INTERVAL_HOURS,
    ))

    title = _scenario_title(vintage, esoo_scenario, poe, forecast_year)
    load_tech = _get_or_create_load_technology()

    scenario_obj, created = Scenarios.objects.get_or_create(
        title=title,
        defaults={
            'interval_minutes': 30,
            'description': (
                f"Auto-built from WEM ESOO {vintage.year} ({esoo_scenario}, POE{poe}) "
                f"demand forecast for {forecast_year} (FR-G1-01)."
            ),
        },
    )
    if not created and scenario_obj.interval_minutes != 30:
        scenario_obj.interval_minutes = 30
        scenario_obj.save(update_fields=['interval_minutes'])

    facility_obj, _ = facilities.objects.get_or_create(
        facility_name=title,
        defaults={
            'facility_code': title[:30],
            'idtechnologies': load_tech,
            'active': True,
            'existing': True,
            'capacity': 0,
        },
    )
    if facility_obj.idtechnologies_id != load_tech.idtechnologies:
        facility_obj.idtechnologies = load_tech
        facility_obj.save(update_fields=['idtechnologies'])

    ScenariosFacilities.objects.get_or_create(idscenarios=scenario_obj, idfacilities=facility_obj)

    scenario_tech, st_created = ScenariosTechnologies.objects.get_or_create(
        idscenarios=scenario_obj,
        idtechnologies=load_tech,
        defaults={'merit_order': 0, 'capacity': 0, 'mult': 1, 'col': None},
    )
    if not st_created and scenario_tech.merit_order != 0:
        scenario_tech.merit_order = 0
        scenario_tech.save(update_fields=['merit_order'])

    # Idempotent regeneration: clear any previous trace for this
    # facility/year before writing the new one.
    supplyfactors.objects.filter(idfacilities=facility_obj, year=forecast_year).delete()
    records = [
        supplyfactors(idfacilities=facility_obj, year=forecast_year, hour=h, supply=0, quantum=float(v))
        for h, v in enumerate(synthesis.trace)
    ]
    supplyfactors.objects.bulk_create(records, batch_size=1000)

    return EsooScenarioBuildResult(
        scenario=scenario_obj,
        facility=facility_obj,
        title=title,
        forecast_year=forecast_year,
        reference_year=reference_year,
        n_rows=len(records),
        gamma=ldc_fit.gamma,
        ldc_notes=ldc_fit.notes,
        synthesis_notes=synthesis.notes,
        reconciliation_notes=report.notes,
        peak_mw=peak_mw,
        minimum_mw=minimum_mw,
        energy_mwh=energy_mwh,
        achieved_peak_mw=report.achieved_peak,
        achieved_minimum_mw=report.achieved_minimum,
        achieved_energy_mwh=report.achieved_energy_mwh,
    )


@login_required
def esoo_scenario_selector(request):
    """
    FR-G1-01 selector view. GET renders the picker; POST builds the
    scenario and re-renders with the result (or an error naming exactly
    what went wrong — missing anchor, inconsistent anchors, no usable
    reference shape, or a trace that failed reconciliation).

    Also renders the selected vintage's domain='supply_adequacy' figures
    (RCT, capacity outlook) as read-only reference data (FR-G1-06) — see
    the module docstring for why that query never touches the demand
    pipeline above.
    """
    vintages = EsooVintage.objects.order_by('-year')
    scenario_choices = [c for c in ESOO_SCENARIO_CHOICES if c[0] != 'not_applicable']
    poe_choices = ESOO_POE_LEVEL_CHOICES

    result: Optional[EsooScenarioBuildResult] = None
    supply_adequacy_figures = None
    selected_vintage_id = request.POST.get('vintage') or request.GET.get('vintage')
    selected_scenario = request.POST.get('esoo_scenario', '')
    selected_poe = request.POST.get('poe_level', '')
    selected_forecast_year = request.POST.get('forecast_year', '')

    if request.method == 'POST':
        vintage = None
        try:
            vintage = EsooVintage.objects.get(pk=selected_vintage_id)
            poe = int(selected_poe)
            forecast_year = int(selected_forecast_year)
        except (EsooVintage.DoesNotExist, TypeError, ValueError):
            messages.error(
                request,
                "Please select a valid ESOO vintage, scenario, POE level and forecast year."
            )
            vintage = None

        if vintage is not None and selected_scenario:
            try:
                result = build_scenario_from_esoo(vintage, selected_scenario, poe, forecast_year)
                messages.success(
                    request,
                    f"Built Powermatch scenario '{result.title}' — {result.n_rows} half-hourly "
                    f"demand rows written for {forecast_year} "
                    f"(reference shape: {result.reference_year}, shape exponent gamma={result.gamma:.3f})."
                )
                for note in result.ldc_notes + result.synthesis_notes:
                    messages.warning(request, note)
            except AnchorNotFoundError as e:
                messages.error(request, str(e))
            except ReferenceShapeError as e:
                messages.error(request, str(e))
            except LDCConstructionError as e:
                messages.error(request, f"Could not construct a load-duration curve from these anchors: {e}")
            except TraceRejectedError as e:
                messages.error(request, f"Synthesised trace failed reconciliation and was rejected: {e}")
        elif vintage is not None and not selected_scenario:
            messages.error(request, "Please select a demand growth scenario (Low/Expected/High).")

    if selected_vintage_id:
        try:
            selected_vintage = EsooVintage.objects.get(pk=selected_vintage_id)
            supply_adequacy_figures = EsooFigure.objects.filter(
                vintage=selected_vintage, domain='supply_adequacy'
            ).order_by('forecast_year', 'metric')
        except (EsooVintage.DoesNotExist, ValueError, TypeError):
            supply_adequacy_figures = None

    context = {
        'vintages': vintages,
        'scenario_choices': scenario_choices,
        'poe_choices': poe_choices,
        'result': result,
        'supply_adequacy_figures': supply_adequacy_figures,
        'selected_vintage_id': selected_vintage_id,
        'selected_scenario': selected_scenario,
        'selected_poe': selected_poe,
        'selected_forecast_year': selected_forecast_year,
    }
    return render(request, 'esoo_scenario_selector.html', context)
