"""
Fetch and cache BARRA-C2 weather for facilities' own grid cells.

SAM runs with WEATHER_SOURCE = 'barra_c2' fetch on first use anyway; this command
does it ahead of time (a new cell-year takes ~3 minutes), so a baseline run or a
comparison does not stall on the network. Cells already cached are skipped, so it is
safe to re-run or schedule. Registered on the Data Pipelines page.

Usage:
    python manage.py fetch_barra_c2_weather --facility YANDIN_WF1 --year 2025
    python manage.py fetch_barra_c2_weather --all --year 2025 --max-new 15
    python manage.py fetch_barra_c2_weather --all-with-scada --year 2025
    python manage.py fetch_barra_c2_weather --lat -31.65 --lon 117.30 --technology solar --year 2025

--max-new caps how many cells are downloaded in one run (cached cells don't count);
re-run to continue. The Data Pipelines runner treats a run still going after an hour
as stopped, so keep a web-started run to about 15 new cells.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from siren_web.services import barra_c2


def facility_technologies(facility):
    """'wind' and/or 'solar', from the facility's active installations or its technology."""
    from siren_web.models import FacilitySolar, FacilityWindTurbines
    techs = []
    if FacilityWindTurbines.objects.filter(idfacilities=facility, is_active=True).exists():
        techs.append('wind')
    if FacilitySolar.objects.filter(idfacilities=facility, is_active=True).exists():
        techs.append('solar')
    if not techs and facility.idtechnologies:
        name = (facility.idtechnologies.technology_name or '').lower()
        if 'wind' in name:
            techs.append('wind')
        elif 'pv' in name or 'solar' in name:
            techs.append('solar')
    return techs


def wind_solar_facilities():
    """Every facility with a location and wind or solar generation (existing or proposed)."""
    from siren_web.models import facilities
    return [f for f in facilities.objects.filter(latitude__isnull=False, longitude__isnull=False)
            .select_related('idtechnologies').order_by('facility_name')
            if facility_technologies(f)]


def wind_solar_facility_codes():
    """Facility codes for the Data Pipelines facility picker."""
    return [f.facility_code for f in wind_solar_facilities() if f.facility_code]


def facilities_with_scada(year):
    """Wind/solar facilities with any SCADA in the year."""
    import numpy as np
    from siren_web.services.facility_scada_matrix import facility_trace
    found = []
    for f in wind_solar_facilities():
        trace = facility_trace(year, f.idfacilities)
        if trace is not None and np.any(~np.isnan(trace)):
            found.append(f)
    return found


class Command(BaseCommand):
    help = "Fetch and cache BARRA-C2 SAM weather files for facilities' own grid cells"

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, required=True)
        parser.add_argument('--facility', action='append', default=[],
                            help='Facility code (repeatable)')
        parser.add_argument('--all', action='store_true',
                            help='Every wind/solar facility with a location, existing or proposed')
        parser.add_argument('--all-with-scada', action='store_true',
                            help='Every wind/solar facility with SCADA in --year')
        parser.add_argument('--lat', type=float)
        parser.add_argument('--lon', type=float)
        parser.add_argument('--technology', choices=['wind', 'solar'])
        parser.add_argument('--max-new', type=int, default=0,
                            help='Download at most this many new cells this run (0 = no limit)')

    def handle(self, *args, **opts):
        from siren_web.models import facilities
        year = opts['year']
        weather_dir = settings.WEATHER_DATA_DIR
        jobs = []  # (label, technology, lat, lon)

        if opts['lat'] is not None or opts['lon'] is not None:
            if opts['lat'] is None or opts['lon'] is None or not opts['technology']:
                raise CommandError('--lat, --lon and --technology go together')
            jobs.append((f"({opts['lat']}, {opts['lon']})", opts['technology'],
                         opts['lat'], opts['lon']))

        chosen = []
        for code in opts['facility']:
            try:
                chosen.append(facilities.objects.get(facility_code=code))
            except facilities.DoesNotExist:
                raise CommandError(f'No facility with code {code}')
        if opts['all']:
            chosen.extend(f for f in wind_solar_facilities() if f not in chosen)
        elif opts['all_with_scada']:
            chosen.extend(f for f in facilities_with_scada(year) if f not in chosen)
        for f in chosen:
            techs = facility_technologies(f)
            if not techs:
                self.stdout.write(self.style.WARNING(f'{f.facility_name}: not a wind or solar facility'))
            for tech in techs:
                jobs.append((f.facility_name, tech, float(f.latitude), float(f.longitude)))

        if not jobs:
            raise CommandError('Nothing to fetch: give --facility, --all, --all-with-scada or --lat/--lon')

        progress = (lambda step: self.stdout.write(f'    {step}')) if opts['verbosity'] > 1 else None
        fetched = cached = deferred = failures = 0
        for label, tech, lat, lon in jobs:
            try:
                if barra_c2.is_cached(tech, lat, lon, year, weather_dir):
                    cached += 1
                    continue
                if opts['max_new'] and fetched >= opts['max_new']:
                    deferred += 1
                    continue
                self.stdout.write(f'{label}: fetching {tech} {year}')
                path = barra_c2.get_or_fetch(tech, lat, lon, year, weather_dir, progress=progress)
                fetched += 1
                self.stdout.write(self.style.SUCCESS(f'  {path}'))
            except barra_c2.BarraError as e:
                failures += 1
                self.stdout.write(self.style.ERROR(f'{label}: {tech} {year} failed: {e}'))

        self.stdout.write(f'{fetched} fetched, {cached} already cached, {deferred} left for a later run, '
                          f'{failures} failed ({len(jobs)} facility-technologies)')
        if failures:
            raise CommandError(f'{failures} of {len(jobs)} fetches failed')
