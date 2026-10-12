"""
Fetch and cache BARRA-C2 weather for facilities' own grid cells.

SAM runs with WEATHER_SOURCE = 'barra_c2' fetch on first use anyway; this command
does it ahead of time (a wind cell-year takes ~8 minutes, a solar one ~5), so a
baseline run or a comparison does not stall on the network.

Usage:
    python manage.py fetch_barra_c2_weather --facility YANDIN_WF1 --year 2025
    python manage.py fetch_barra_c2_weather --all-with-scada --year 2025
    python manage.py fetch_barra_c2_weather --lat -31.65 --lon 117.30 --technology solar --year 2025
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


def facilities_with_scada(year):
    """Wind/solar facilities with any SCADA in the year."""
    import numpy as np
    from siren_web.models import facilities
    from siren_web.services.facility_scada_matrix import facility_trace
    found = []
    for f in facilities.objects.filter(latitude__isnull=False).select_related('idtechnologies'):
        if not facility_technologies(f):
            continue
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
        parser.add_argument('--all-with-scada', action='store_true',
                            help='Every wind/solar facility with SCADA in --year')
        parser.add_argument('--lat', type=float)
        parser.add_argument('--lon', type=float)
        parser.add_argument('--technology', choices=['wind', 'solar'])

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
        if opts['all_with_scada']:
            chosen.extend(f for f in facilities_with_scada(year) if f not in chosen)
        for f in chosen:
            for tech in facility_technologies(f):
                jobs.append((f.facility_name, tech, float(f.latitude), float(f.longitude)))

        if not jobs:
            raise CommandError('Nothing to fetch: give --facility, --all-with-scada or --lat/--lon')

        failures = 0
        for label, tech, lat, lon in jobs:
            self.stdout.write(f'{label}: {tech} {year}')
            try:
                path = barra_c2.get_or_fetch(
                    tech, lat, lon, year, weather_dir,
                    progress=lambda step: self.stdout.write(f'    {step}'))
                self.stdout.write(self.style.SUCCESS(f'  {path}'))
            except barra_c2.BarraError as e:
                failures += 1
                self.stdout.write(self.style.ERROR(f'  failed: {e}'))
        if failures:
            raise CommandError(f'{failures} of {len(jobs)} fetches failed')
