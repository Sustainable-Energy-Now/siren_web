"""
Create/refresh Facilities Take-up Scenarios (Low/Expected/High) for target years.

A Facilities Take-up scenario is an ordinary `Scenarios` row (`scenario_type`
= "Facilities Take-up", `is_auto_generated=True`) whose `ScenariosFacilities`
membership is computed from each facility's status, commissioning_date,
effective_commissioning_probability and decommissioning_date.

Membership rule per (year, band), retirement checked first:
  - decommissioning_date <= year, or status == 'decommissioned': excluded.
  - status in (commissioned, under_construction) and commissioning_date is
    null or <= year: included in every band.
  - status in (proposed, planned) with commissioning_date set and <= year:
      low      -> excluded
      expected -> included only if effective_commissioning_probability >= threshold
      high     -> included
  - status in (proposed, planned) with no commissioning_date: excluded (timing unknown).

Membership changes use create()/delete() on ScenariosFacilities (not bulk) so
powermapui.signals keeps ScenariosTechnologies.capacity in sync. Idempotent;
refuses to touch a same-titled scenario that isn't auto-generated.
"""
from dataclasses import dataclass, field

from django.db import transaction

from siren_web.models import Scenarios, ScenarioType, ScenariosFacilities, ScenariosTechnologies, facilities

BAND_CHOICES = ('low', 'expected', 'high')

FACILITIES_TAKEUP_TYPE_DESCRIPTION = (
    "Commissioned, grid-connected facilities -- a Scenarios row's "
    "facility/technology portfolio, either manually curated or auto-generated "
    "(Low/Expected/High) from each facility's commissioning probability, "
    "commissioning date and retirement date."
)


@dataclass
class TakeupResult:
    title: str
    year: int
    band: str
    ok: bool = True
    n_facilities: int = 0
    n_added: int = 0
    n_removed: int = 0
    created: bool = False
    error: str = ''
    skipped_unknown_timing: list = field(default_factory=list)


def _qualifying_facility_ids(year, band, threshold):
    qualifying, skipped = set(), []

    for facility in facilities.objects.exclude(status='decommissioned'):
        if facility.decommissioning_date and facility.decommissioning_date.year <= year:
            continue

        if facility.status in ('commissioned', 'under_construction'):
            if facility.commissioning_date is None or facility.commissioning_date.year <= year:
                qualifying.add(facility.idfacilities)
            continue

        if facility.status in ('proposed', 'planned'):
            if facility.commissioning_date is None:
                skipped.append(facility.facility_name or str(facility.idfacilities))
                continue
            if facility.commissioning_date.year > year or band == 'low':
                continue
            if band == 'high':
                qualifying.add(facility.idfacilities)
                continue
            prob = facility.effective_commissioning_probability
            if prob is not None and prob >= threshold:
                qualifying.add(facility.idfacilities)

    return qualifying, skipped


@transaction.atomic
def generate_takeup_scenario(year, band, threshold=0.5):
    title = f"Facilities Take-up - {band.title()} - {year}"
    result = TakeupResult(title=title, year=year, band=band)

    scenario_type, _ = ScenarioType.objects.get_or_create(
        name='Facilities Take-up',
        defaults={'description': FACILITIES_TAKEUP_TYPE_DESCRIPTION, 'is_system_default': True},
    )

    scenario = Scenarios.objects.filter(title=title).first()
    if scenario is not None and not scenario.is_auto_generated:
        result.ok = False
        result.error = (
            f"'{title}' already exists and is not auto-generated; rename or delete it first."
        )
        return result

    if scenario is None:
        scenario = Scenarios.objects.create(
            title=title,
            description=f"Auto-generated Facilities Take-up scenario ({band} band, {year}).",
            scenario_type=scenario_type,
            forecast_year=year,
            probability_band=band,
            is_auto_generated=True,
        )
        result.created = True
    else:
        scenario.scenario_type = scenario_type
        scenario.forecast_year = year
        scenario.probability_band = band
        scenario.save(update_fields=['scenario_type', 'forecast_year', 'probability_band'])

    scenario.probability_threshold = threshold if band == 'expected' else None
    scenario.save(update_fields=['probability_threshold'])

    target_ids, result.skipped_unknown_timing = _qualifying_facility_ids(year, band, threshold)
    current_ids = set(
        ScenariosFacilities.objects.filter(idscenarios=scenario).values_list('idfacilities_id', flat=True)
    )
    to_add, to_remove = target_ids - current_ids, current_ids - target_ids

    for facility_id in to_add:
        ScenariosFacilities.objects.create(idscenarios=scenario, idfacilities_id=facility_id)

    if to_remove:
        ScenariosFacilities.objects.filter(idscenarios=scenario, idfacilities_id__in=to_remove).delete()
        # signals only react to additions, so resync capacity after removals
        for scenario_tech in ScenariosTechnologies.objects.filter(idscenarios=scenario):
            scenario_tech.update_capacity()

    result.n_facilities, result.n_added, result.n_removed = len(target_ids), len(to_add), len(to_remove)
    return result


def generate_takeup_scenarios(years, bands=BAND_CHOICES, threshold=0.5):
    return [generate_takeup_scenario(y, b, threshold) for y in years for b in bands]
