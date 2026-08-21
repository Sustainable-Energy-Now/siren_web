# siren_web/management/commands/compute_annual_demand_actuals.py
"""
FR-G2-01 — populate AnnualDemandActual, the SCADA-derived actual-demand side
of every G2 bias comparison (see powerplotui/services/esoo_bias_analysis.py),
from real half-hourly FacilityScada data.

Aggregation window: WEM 'Capacity Year', NOT calendar year. EsooFigure.
forecast_year is a Capacity-Year start-label (e.g. forecast_year=2026 means
the 2026-27 Capacity Year, per esoo_pdf_parser._capacity_year_to_int) --
confirmed against the 2026 WEM ESOO PDF's own "Notes for reading this
report" section (p.30): "A Capacity Year commences in the 08:00 Trading
Interval on 1 October and ends at the completion of the 07:30 Trading
Interval on 1 October of the following calendar year." Table 1 and Table
10's forecast columns are both headed 'Capacity Year' (not calendar year),
and Table 11's own event labels ("Winter maximum 2024-25" for an event
dated 28 July 2025, "Summer maximum 2025-26" for an event dated 2 February
2026) only make sense under this definition -- confirming it applies
uniformly across energy/peak/minimum figures.

If AnnualDemandActual were instead keyed by calendar year, every pair
align_forecast_actual_pairs() builds would silently compare a forecast for
(e.g.) Dec-Mar summer demand against an actual aggregated over a Jan-Dec
window straddling a different summer -- months of systematic misalignment
baked into every downstream bias statistic without any error being raised.
So here, `--year N` means Capacity Year N-(N+1): the half-open window
[1 Oct N 08:00 AWST, 1 Oct N+1 08:00 AWST).

Unit convention -- RESOLVED 2026-08-19 against real live AEMO data:
FacilityScada.quantity is HALF-HOURLY ENERGY (MWh), not power (MW), stored
at half-hourly resolution (`unique_together = ['dispatch_interval',
'facility']` -- one row per facility per half hour).

Verified directly against AEMO's live 5-minute SCADA feed: raw 5-minute
`quantity` readings for a real baseload coal unit (BW1_BLUEWATERS_G2,
217 MW nameplate) sat steady at ~17.9-17.95 across a full hour. Read as MW,
that is an implausible ~8% capacity factor for baseload coal; read as
5-minute MWh, it implies an average power of ~17.9 x 12 = ~215 MW, ~99% of
nameplate -- exactly what a baseload coal unit should show. So the raw
5-minute AEMO field is genuine energy (mWh), confirming
_aggregate_to_half_hourly()'s SUM of six 5-minute values is the CORRECT way
to build a half-hourly *energy* total -- that part was never the bug.

The bug is downstream: every consumer of FacilityScada.quantity (this
command as it stood before this fix, update_ret_dashboard.py, and
powerplotui/views/scada_views.py's FacilityManager) treats that stored
half-hourly MWh value as if it were an instantaneous/average MW power
reading. Concretely, for THIS command:
  - peak/minimum demand: the stored quantity for an interval IS that
    interval's MWh, so the true average MW for the half hour is
    quantity * 2 (MWh / 0.5h), not quantity directly. Using quantity
    directly (as the previous version of this command did) understates
    every peak/minimum by 2x -- this is exactly the ~2,112 MW vs AEMO's
    real ~4,219 MW gap found during Phase 3b for the 2 Feb 2026 event.
  - annual energy: quantity is ALREADY MWh per interval, so the correct
    annual total is just sum(quantity) -- no further * 0.5 is needed (the
    previous version applied an incorrect second * 0.5, understating
    annual energy by 2x as well).

update_ret_dashboard.py and scada_views.py carry the same MW/MWh
misreading (the former's own docstring literally states "SCADA quantity is
in MW"); scada_views.py's FacilityManager compounds it further by also
assuming 5-minute rows (`* (5/60)`) against data that is actually
half-hourly. Both are pre-existing, widely-relied-upon platform code
(RET Dashboard, RE% reporting) -- left untouched here pending the user's
decision on how to proceed, since fixing them has much wider blast radius
(historical MonthlyREPerformance figures, potential backfill) than this
command's own, not-yet-depended-upon output.
"""
from datetime import datetime

import pytz
from django.core.management.base import BaseCommand
from django.db.models import Case, DecimalField, F, Sum, Value, When

from siren_web.models import AnnualDemandActual, FacilityScada

AWST = pytz.timezone('Australia/Perth')


class Command(BaseCommand):
    help = (
        'Populate AnnualDemandActual (FR-G2-01) from real half-hourly FacilityScada data, '
        'one WEM Capacity Year at a time. --year N means Capacity Year N-(N+1) '
        '(1 Oct N 08:00 AWST to 1 Oct N+1 08:00 AWST), matching EsooFigure.forecast_year labelling.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--year', type=int,
            help='Single Capacity Year start-label to compute, e.g. 2024 (= Capacity Year 2024-25)',
        )
        parser.add_argument('--years', type=str, help='Range of Capacity Year start-labels, e.g. 2018-2024')
        parser.add_argument(
            '--demand-basis', type=str, choices=['operational', 'underlying'], default='operational',
            help=(
                "Demand basis to compute (default: operational, the canonical basis for this "
                "project per D3). 'underlying' is not yet implemented -- skipped per Phase 3b scope."
            ),
        )
        parser.add_argument(
            '--force', action='store_true',
            help='Recompute even if a row already exists for this year/basis',
        )
        parser.add_argument(
            '--min-coverage', type=float, default=50.0,
            help=(
                'Minimum %% of expected half-hourly intervals present before a row is written '
                '(default: 50.0). Years below this are reported and skipped, not silently written '
                'as if they were complete.'
            ),
        )

    def handle(self, *args, **options):
        if options['demand_basis'] == 'underlying':
            self.stdout.write(self.style.ERROR(
                "--demand-basis underlying is not implemented yet (FR-G2-01 prioritises the "
                "operational basis; underlying requires joining DPVGeneration per half-hour "
                "interval, deferred per the Phase 3b brief). Omit --demand-basis or pass "
                "'operational'."
            ))
            return

        if options['year']:
            years = [options['year']]
        elif options['years']:
            try:
                start, end = (int(x) for x in options['years'].split('-'))
            except ValueError:
                self.stdout.write(self.style.ERROR("--years must be formatted like 2018-2024"))
                return
            years = list(range(start, end + 1))
        else:
            self.stdout.write(self.style.ERROR('Specify --year or --years (e.g. --years 2018-2024)'))
            return

        for year in years:
            self.compute_year(year, options['force'], options['min_coverage'])

    def compute_year(self, year, force, min_coverage):
        """Compute and store the operational-basis AnnualDemandActual row for
        Capacity Year `year`-`year+1`."""
        existing = AnnualDemandActual.objects.filter(year=year, demand_basis='operational').first()
        if existing and not force:
            self.stdout.write(self.style.WARNING(
                f"  {year} (operational) already computed. Use --force to recompute."
            ))
            return

        start_dt = AWST.localize(datetime(year, 10, 1, 8, 0, 0))
        end_dt = AWST.localize(datetime(year + 1, 10, 1, 8, 0, 0))

        self.stdout.write(
            f"Computing Capacity Year {year}-{str(year + 1)[-2:]} "
            f"({start_dt} -> {end_dt}, exclusive)..."
        )

        scada_qs = FacilityScada.objects.filter(
            dispatch_interval__gte=start_dt,
            dispatch_interval__lt=end_dt,
        )

        if not scada_qs.exists():
            self.stdout.write(self.style.ERROR(f"  No SCADA data found for Capacity Year {year}-{str(year + 1)[-2:]}"))
            return

        # Total positive (generation) MW per half-hourly interval -- matches
        # update_ret_dashboard.py's operational-demand definition (excludes
        # storage/hydro charging, i.e. negative quantities), which in turn
        # matches the 2026 WEM ESOO's own glossary definition of
        # "Operational demand": electricity supplied from market-registered
        # energy producing systems to meet demand in the SWIS.
        interval_totals = scada_qs.values('dispatch_interval').annotate(
            total_demand=Sum(
                Case(
                    When(quantity__gt=0, then=F('quantity')),
                    default=Value(0),
                    output_field=DecimalField(),
                )
            )
        ).order_by('dispatch_interval')

        n_intervals = 0
        energy_mw_sum = 0.0
        peak_mw = None
        peak_dt = None
        min_mw = None
        min_dt = None

        for row in interval_totals:
            # row['total_demand'] is half-hourly ENERGY (MWh) -- see module
            # docstring. Average power for the interval is MWh / 0.5h.
            energy_mwh = float(row['total_demand'] or 0)
            demand_mw = energy_mwh * 2
            dt = row['dispatch_interval']
            n_intervals += 1
            energy_mw_sum += energy_mwh
            if peak_mw is None or demand_mw > peak_mw:
                peak_mw, peak_dt = demand_mw, dt
            if min_mw is None or demand_mw < min_mw:
                min_mw, min_dt = demand_mw, dt

        expected_intervals = round((end_dt - start_dt).total_seconds() / 1800)
        coverage_pct = (n_intervals / expected_intervals * 100) if expected_intervals else 0

        if coverage_pct < min_coverage:
            self.stdout.write(self.style.ERROR(
                f"  Only {n_intervals}/{expected_intervals} half-hourly intervals present "
                f"({coverage_pct:.1f}%) -- below --min-coverage {min_coverage}%. Skipping write "
                f"(pass --min-coverage 0 to force a write anyway)."
            ))
            return
        elif coverage_pct < 95:
            self.stdout.write(self.style.WARNING(
                f"  {n_intervals}/{expected_intervals} half-hourly intervals ({coverage_pct:.1f}%) "
                f"-- incomplete year, treat this record with caution."
            ))

        # energy_mw_sum is already a sum of half-hourly MWh values (see
        # module docstring) -- just convert to GWh, no further * 0.5.
        annual_energy_gwh = energy_mw_sum / 1000.0

        actual, created = AnnualDemandActual.objects.update_or_create(
            year=year, demand_basis='operational',
            defaults={
                'annual_energy_gwh': annual_energy_gwh,
                'peak_demand_mw': peak_mw,
                'peak_datetime': peak_dt,
                'minimum_demand_mw': min_mw,
                'minimum_datetime': min_dt,
            }
        )
        action = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(
            f"  {action}: Capacity Year {year}-{str(year + 1)[-2:]} operational -- "
            f"energy {annual_energy_gwh:,.0f} GWh, peak {peak_mw:,.0f} MW @ {peak_dt}, "
            f"min {min_mw:,.0f} MW @ {min_dt} ({coverage_pct:.1f}% interval coverage)"
        ))
