# siren_web/management/commands/generate_facilities_takeup_scenarios.py
"""
Auto-generate/refresh Facilities Take-up Scenarios (Low/Expected/High) for
one or more target years.

A Facilities Take-up scenario is an ordinary `Scenarios` row (`scenario_type`
= "Facilities Take-up", `is_auto_generated=True`) whose `ScenariosFacilities`
membership is computed from each facility's status, commissioning_date,
commissioning_probability/effective_commissioning_probability and
decommissioning_date, rather than curated by hand. Membership changes are
made through ordinary create()/delete() calls on ScenariosFacilities so
powermapui.signals' receivers fire and keep ScenariosTechnologies.capacity
(the per-technology capacity summary) in sync -- see that module for the
mechanism this command deliberately reuses rather than duplicating.

Membership rule per (year, band), retirement checked first:
  - decommissioning_date <= year, or status == 'decommissioned': excluded
    from every band.
  - status in (commissioned, under_construction) and commissioning_date is
    null or <= year: included in every band.
  - status in (proposed, planned) with commissioning_date set and <= year:
      low      -> excluded
      expected -> included only if effective_commissioning_probability
                  >= --probability-threshold
      high     -> included unconditionally
  - status in (proposed, planned) with commissioning_date null: timing
    unknown, excluded from every band (logged).

Idempotent: rerunning for the same (year, band) resyncs membership to
whatever the formula currently produces (facilities newly excluded are
removed, not just left stale) rather than creating a duplicate scenario.
Refuses to touch a same-titled scenario that isn't itself auto-generated,
so a hand-curated scenario that happens to share the generated title is
never silently overwritten.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from siren_web.models import Scenarios, ScenarioType, ScenariosFacilities, ScenariosTechnologies, facilities

BAND_CHOICES = ('low', 'expected', 'high')


class Command(BaseCommand):
    help = (
        "Auto-generate/refresh Facilities Take-up Scenarios (Low/Expected/High) for "
        "one or more target years, from each facility's status, commissioning_date, "
        "commissioning_probability and decommissioning_date."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--years', type=int, nargs='+', required=True,
            help='Target build-out years, e.g. --years 2030 2035 2040',
        )
        parser.add_argument(
            '--bands', type=str, nargs='+', default=list(BAND_CHOICES), choices=BAND_CHOICES,
            help='Which probability bands to (re)generate (default: all three).',
        )
        parser.add_argument(
            '--probability-threshold', type=float, default=0.5,
            help=(
                "Minimum effective_commissioning_probability for a proposed/planned "
                "facility to qualify for the 'expected' band (default: 0.5)."
            ),
        )

    def handle(self, *args, **options):
        years = options['years']
        bands = options['bands']
        threshold = options['probability_threshold']

        scenario_type, _ = ScenarioType.objects.get_or_create(
            name='Facilities Take-up',
            defaults={
                'description': (
                    "Commissioned, grid-connected facilities -- a Scenarios row's "
                    "facility/technology portfolio, either manually curated or "
                    "auto-generated (Low/Expected/High) by this command from each "
                    "facility's commissioning probability, commissioning date and "
                    "retirement date."
                ),
                'is_system_default': True,
            },
        )

        for year in years:
            for band in bands:
                self._generate_one(year, band, threshold, scenario_type)

    def _qualifying_facility_ids(self, year, band, threshold):
        qualifying = []
        skipped_unknown_timing = []

        for facility in facilities.objects.exclude(status='decommissioned'):
            if facility.decommissioning_date and facility.decommissioning_date.year <= year:
                continue  # retirement always wins, checked first

            if facility.status in ('commissioned', 'under_construction'):
                if facility.commissioning_date is None or facility.commissioning_date.year <= year:
                    qualifying.append(facility.idfacilities)
                continue

            if facility.status in ('proposed', 'planned'):
                if facility.commissioning_date is None:
                    skipped_unknown_timing.append(facility.facility_name or str(facility.idfacilities))
                    continue
                if facility.commissioning_date.year > year:
                    continue
                if band == 'low':
                    continue
                if band == 'high':
                    qualifying.append(facility.idfacilities)
                    continue
                # band == 'expected'
                prob = facility.effective_commissioning_probability
                if prob is not None and prob >= threshold:
                    qualifying.append(facility.idfacilities)

        if skipped_unknown_timing:
            self.stdout.write(self.style.WARNING(
                f"{year}/{band}: skipped {len(skipped_unknown_timing)} proposed/planned "
                f"facility(ies) with no commissioning_date (timing unknown): "
                + ', '.join(skipped_unknown_timing[:10])
                + (' ...' if len(skipped_unknown_timing) > 10 else '')
            ))

        return set(qualifying)

    @transaction.atomic
    def _generate_one(self, year, band, threshold, scenario_type):
        title = f"Facilities Take-up - {band.title()} - {year}"
        scenario = Scenarios.objects.filter(title=title).first()

        if scenario is not None and not scenario.is_auto_generated:
            self.stdout.write(self.style.ERROR(
                f"'{title}' already exists and is not marked is_auto_generated -- "
                "refusing to overwrite. Rename or delete it first if you want this "
                "command to manage it."
            ))
            return

        if scenario is None:
            scenario = Scenarios.objects.create(
                title=title,
                description=f"Auto-generated Facilities Take-up scenario ({band} band, {year}).",
                scenario_type=scenario_type,
                forecast_year=year,
                probability_band=band,
                is_auto_generated=True,
            )
        else:
            scenario.scenario_type = scenario_type
            scenario.forecast_year = year
            scenario.probability_band = band
            scenario.is_auto_generated = True
            scenario.save(update_fields=['scenario_type', 'forecast_year', 'probability_band', 'is_auto_generated'])

        target_ids = self._qualifying_facility_ids(year, band, threshold)
        current_ids = set(
            ScenariosFacilities.objects.filter(idscenarios=scenario).values_list('idfacilities_id', flat=True)
        )

        to_add = target_ids - current_ids
        to_remove = current_ids - target_ids

        for facility_id in to_add:
            # One at a time (not bulk_create) so powermapui.signals'
            # post_save/m2m_changed receivers fire and keep
            # ScenariosTechnologies.capacity in sync on every addition.
            ScenariosFacilities.objects.create(idscenarios=scenario, idfacilities_id=facility_id)

        if to_remove:
            ScenariosFacilities.objects.filter(idscenarios=scenario, idfacilities_id__in=to_remove).delete()
            # Removals aren't covered by any signal (see powermapui/signals.py,
            # which only reacts to additions) -- resync capacity explicitly.
            for scenario_tech in ScenariosTechnologies.objects.filter(idscenarios=scenario):
                scenario_tech.update_capacity()

        self.stdout.write(self.style.SUCCESS(
            f"{title}: {len(target_ids)} facilities ({len(to_add)} added, {len(to_remove)} removed)."
        ))
