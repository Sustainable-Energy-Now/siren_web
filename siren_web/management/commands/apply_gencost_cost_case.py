# siren_web/management/commands/apply_gencost_cost_case.py
"""
Applies one GenCost cost case's parsed GencostCostFigure rows onto the
live TechnologyYears table the LCOE engine actually reads
(powermatchui/views/balance_grid_load.py's PowerMatchProcessor via
database_operations.fetch_technology_attributes). Only the `capex` field
is written; any existing fom/vom/fuel on a TechnologyYears row is left
untouched, since GenCost's Appendix Tables don't publish those as a time
series (see the plan doc's Phase-2 notes).

--premium-pct optionally scales capex up (or down, if negative) before
writing -- GenCost's figures are national averages, and WA capital costs
typically run higher (freight, remoteness, a thinner local labour/EPC
market). The premium is applied at write time only: GencostCostFigure
keeps CSIRO's published number untouched, and the percentage used is
recorded on the written TechnologyYears row itself (capex_premium_pct),
so it's visible right next to the resulting capex value, not just in
CommandRun history.

Rows whose raw_technology_label has no GencostTechnologyMapping (or is
explicitly mapped to nothing) are skipped and reported, not silently
dropped.
"""
from django.core.management.base import BaseCommand

from siren_web.models import GENCOST_COST_CASE_CHOICES, GencostCostFigure, GencostTechnologyMapping, GencostVintage, TechnologyYears

VALID_CASES = [key for key, _ in GENCOST_COST_CASE_CHOICES]


class Command(BaseCommand):
    help = "Apply one GenCost case's parsed capex figures onto TechnologyYears"

    def add_arguments(self, parser):
        parser.add_argument('--vintage', type=str, required=True, help="GenCost edition, e.g. '2025-26'")
        parser.add_argument('--case', type=str, required=True, choices=VALID_CASES, help='Cost case to apply')
        parser.add_argument('--premium-pct', type=float, default=0.0,
                             help="Percent to scale capex by, e.g. 15 for +15%% (WA cost premium over GenCost's national average). Default 0.")
        parser.add_argument('--dry-run', action='store_true', help='Report what would change without writing')

    def handle(self, *args, **options):
        edition = options['vintage']
        case = options['case']
        dry_run = options['dry_run']
        premium_pct = options['premium_pct']
        premium_factor = 1 + premium_pct / 100

        try:
            vintage = GencostVintage.objects.get(edition=edition)
        except GencostVintage.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"No GencostVintage '{edition}'."))
            return

        figures = GencostCostFigure.objects.filter(vintage=vintage, cost_case=case, cost_component='capex')
        if not figures.exists():
            self.stdout.write(self.style.ERROR(
                f"No capex figures for GenCost {edition}/{case}; run `extract_gencost_figures --vintage {edition}` first."
            ))
            return

        mapping = {
            m.raw_technology_label: m
            for m in GencostTechnologyMapping.objects.select_related('technology')
        }

        to_write, skipped_pending, skipped_ignored = [], [], []
        for figure in figures:
            m = mapping.get(figure.raw_technology_label)
            if m is None or not m.is_resolved:
                skipped_pending.append(figure.raw_technology_label)
                continue
            if m.technology is None:  # explicitly ignored, not an oversight
                skipped_ignored.append(figure.raw_technology_label)
                continue

            adjusted_capex = figure.value * premium_factor

            if dry_run:
                if premium_pct:
                    self.stdout.write(
                        f"  {figure.raw_technology_label} -> {m.technology.technology_name} "
                        f"{figure.financial_year}: capex = {figure.value} x {premium_factor:.3f} = {adjusted_capex:.1f}"
                    )
                else:
                    self.stdout.write(
                        f"  {figure.raw_technology_label} -> {m.technology.technology_name} "
                        f"{figure.financial_year}: capex = {figure.value}"
                    )
                continue

            to_write.append(TechnologyYears(
                idtechnologies=m.technology, year=figure.financial_year,
                capex=adjusted_capex, capex_premium_pct=premium_pct,
            ))

        if skipped_pending:
            pending_labels = sorted(set(skipped_pending))
            self.stdout.write(self.style.WARNING(
                f"Skipped {len(skipped_pending)} figure(s) with pending (unreviewed) technology label(s): "
                f"{', '.join(pending_labels)} - map or ignore them on the mapping review page and re-run."
            ))
        if skipped_ignored:
            self.stdout.write(f"Skipped {len(skipped_ignored)} figure(s) marked not-applicable (as intended).")

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run - nothing written.'))
            return

        # One (or a few, batched) INSERT ... ON DUPLICATE KEY UPDATE rather
        # than one update_or_create round-trip per row -- see
        # extract_gencost_figures.py's equivalent comment for why (this
        # project's MariaDB host has enough per-query latency that a few
        # hundred individual writes takes minutes).
        TechnologyYears.objects.bulk_create(to_write, update_conflicts=True, update_fields=['capex', 'capex_premium_pct'])
        premium_note = f' (capex x {premium_factor:.3f}, {premium_pct:+g}% premium)' if premium_pct else ''
        self.stdout.write(self.style.SUCCESS(f'TechnologyYears: {len(to_write)} figure(s) applied{premium_note}.'))
