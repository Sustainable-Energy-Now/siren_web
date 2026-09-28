"""
Splits Biomass dispatch behavior: sets the Biomass Technologies row to
non-dispatchable (so dispatch reads the real SCADA-derived traces written by
biomass_trace_from_scada.py) and moves any facility with zero qualifying
trace years onto a new dispatchable "twin" technology, so it keeps the old
nameplate-capacity-optimized dispatch behavior instead of silently
contributing zero generation.

Technologies.dispatchable is technology-level (no per-facility override
exists), so a facility that needs different dispatch behavior from its
siblings has to live on a different Technologies row -- this module creates
and maintains that twin technology and everything a facility needs to move
onto it cleanly: FacilityGenerators overrides, ScenariosTechnologies rows
(so it isn't silently dropped from scenarios it belongs to), and
TechnologyYears costs.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Max

from siren_web.models import (
    FacilityGenerators,
    Generatorattributes,
    ScenariosFacilities,
    ScenariosTechnologies,
    Technologies,
    TechnologyYears,
    facilities,
)
from siren_web.services import supply_matrix
from siren_web.services.biomass_trace_from_scada import (
    MIN_COVERAGE_DEFAULT,
    TRACE_YEARS,
    analyze,
    get_biomass_technology,
)

TWIN_NAME_SUFFIX = ' (dispatchable)'
TWIN_SIGNATURE_SUFFIX = 'D'


@dataclass
class DispatchSplitPlan:
    source_technology: Technologies
    facilities_to_repoint: list
    facilities_staying: list


def build_plan(min_coverage: float = MIN_COVERAGE_DEFAULT, years=TRACE_YEARS) -> DispatchSplitPlan:
    """Re-derives the current qualifying/non-qualifying split from the DB
    (pure function of current state, not of a prior command run) and checks
    that every 'staying' facility already has a real trace for at least one
    of its qualifying years."""
    source = get_biomass_technology()
    results = analyze(min_coverage=min_coverage, years=years)

    to_repoint = [r for r in results if r.moves_to_twin]
    staying = [r for r in results if not r.moves_to_twin]

    for result in staying:
        if not any(supply_matrix.facility_has_trace(y, result.facility_id) for y in result.qualifying_years):
            raise ValueError(
                f"Facility {result.facility_id} ({result.facility_name}) has qualifying "
                f"years {result.qualifying_years} but no SupplyFactorMatrix trace yet -- "
                "run build_biomass_supply_traces first with the same --min-coverage."
            )

    return DispatchSplitPlan(source_technology=source, facilities_to_repoint=to_repoint, facilities_staying=staying)


def _twin_signature(source: Technologies) -> str:
    return f'{source.technology_signature}{TWIN_SIGNATURE_SUFFIX}'[:20]


def get_or_create_twin(source: Technologies, dry_run: bool = False):
    """
    Returns (twin, created). If the twin already exists, returns it
    untouched regardless of dry_run. If it doesn't exist yet and dry_run is
    True, returns an unsaved (pk=None) placeholder instance rather than
    persisting one early -- every downstream write is itself gated on
    dry_run, so this placeholder is only ever used to report "would create"
    counts, never to build a real foreign key.
    """
    twin_name = f'{source.technology_name}{TWIN_NAME_SUFFIX}'
    existing = Technologies.objects.filter(technology_name=twin_name).first()
    if existing is not None:
        return existing, False
    if dry_run:
        return Technologies(technology_name=twin_name), True
    twin = Technologies.objects.create(
        technology_name=twin_name,
        technology_signature=_twin_signature(source),
        category=source.category,
        renewable=source.renewable,
        fuel_type=source.fuel_type,
        dispatchable=1,
        lifetime=source.lifetime,
        discount_rate=source.discount_rate,
        emissions=source.emissions,
        area=source.area,
        water_usage=source.water_usage,
        description=(
            f'Dispatchable twin of {source.technology_name} for facilities without '
            'sufficient SCADA coverage to build a real generation trace.'
        ),
    )
    return twin, True


def sync_generator_attributes(source: Technologies, twin: Technologies, dry_run: bool) -> None:
    source_attrs = Generatorattributes.objects.filter(idtechnologies=source).first()
    if source_attrs is None or dry_run:
        return
    Generatorattributes.objects.update_or_create(
        idtechnologies=twin,
        defaults=dict(
            capacity_max=source_attrs.capacity_max,
            capacity_min=source_attrs.capacity_min,
            rampdown_max=source_attrs.rampdown_max,
            rampup_max=source_attrs.rampup_max,
        ),
    )


def sync_technology_years(source: Technologies, twin: Technologies, dry_run: bool) -> int:
    rows = list(TechnologyYears.objects.filter(idtechnologies=source))
    if not dry_run:
        for row in rows:
            TechnologyYears.objects.update_or_create(
                idtechnologies=twin, year=row.year,
                defaults=dict(
                    capex=row.capex, fom=row.fom, vom=row.vom, fuel=row.fuel,
                    capex_premium_pct=row.capex_premium_pct,
                ),
            )
    return len(rows)


def repoint_facility(facility, source: Technologies, twin: Technologies, dry_run: bool) -> dict:
    changes = {'facility_id': facility.idfacilities, 'facility_name': facility.facility_name}

    generator_rows_count = FacilityGenerators.objects.filter(idfacilities=facility, idtechnologies=source).count()
    changes['facility_generators_moved'] = generator_rows_count
    if not dry_run:
        FacilityGenerators.objects.filter(idfacilities=facility, idtechnologies=source).update(idtechnologies=twin)

    scenario_ids = list(
        ScenariosFacilities.objects.filter(idfacilities=facility).values_list('idscenarios', flat=True)
    )
    scenarios_technologies_created = 0
    for scenario_id in scenario_ids:
        already_on_twin = ScenariosTechnologies.objects.filter(
            idscenarios_id=scenario_id, idtechnologies=twin
        ).exists()
        if already_on_twin:
            continue
        if dry_run:
            scenarios_technologies_created += 1
            continue
        source_st = ScenariosTechnologies.objects.filter(idscenarios_id=scenario_id, idtechnologies=source).first()
        # merit_order must be unique per scenario -- load_and_supply (in
        # fetch_supplyfactors_data) is a flat dict keyed by merit_order, so
        # copying the source's merit_order onto the twin would make one of
        # the two technologies silently overwrite the other's dispatch
        # column. Append the twin after every existing merit_order in this
        # scenario instead; if a different dispatch priority is wanted for
        # the twin, it can be edited afterwards like any other
        # ScenariosTechnologies row.
        max_merit_order = ScenariosTechnologies.objects.filter(
            idscenarios_id=scenario_id
        ).aggregate(Max('merit_order'))['merit_order__max'] or 0
        ScenariosTechnologies.objects.create(
            idscenarios_id=scenario_id, idtechnologies=twin,
            merit_order=max_merit_order + 1,
            mult=source_st.mult if source_st else None,
            col=source_st.col if source_st else None,
            capacity=0,
        )
        scenarios_technologies_created += 1
    changes['scenarios_technologies_created'] = scenarios_technologies_created

    if not dry_run:
        facility.idtechnologies = twin
        facility.save(update_fields=['idtechnologies'])

    return changes


def resync_scenario_technology_capacities(source: Technologies, twin: Technologies, dry_run: bool) -> None:
    if dry_run:
        return
    for st in ScenariosTechnologies.objects.filter(idtechnologies__in=[source, twin]):
        st.update_capacity()


def apply_plan(plan: DispatchSplitPlan, dry_run: bool = False) -> dict:
    summary = {
        'twin_created': False,
        'twin_technology_name': None,
        'facilities_repointed': [],
        'source_set_non_dispatchable': False,
    }

    if plan.facilities_to_repoint:
        twin, created = get_or_create_twin(plan.source_technology, dry_run=dry_run)
        summary['twin_created'] = created
        summary['twin_technology_name'] = twin.technology_name
        sync_generator_attributes(plan.source_technology, twin, dry_run)
        sync_technology_years(plan.source_technology, twin, dry_run)
        for result in plan.facilities_to_repoint:
            facility = facilities.objects.get(pk=result.facility_id)
            summary['facilities_repointed'].append(
                repoint_facility(facility, plan.source_technology, twin, dry_run)
            )
        resync_scenario_technology_capacities(plan.source_technology, twin, dry_run)

    if plan.facilities_staying:
        summary['source_set_non_dispatchable'] = True
        if not dry_run:
            plan.source_technology.dispatchable = 0
            plan.source_technology.save(update_fields=['dispatchable'])

    return summary
