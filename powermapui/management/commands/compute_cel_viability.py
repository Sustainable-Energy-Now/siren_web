"""
Management command: compute_cel_viability
==========================================
Recomputes CEL transmission viability scores for RE facility pipeline.

For each active CEL stage, the command calculates the geographic alignment
and viability score for every scoreable facility (proposed, planned,
under_construction, commissioned) and persists the results to the
FacilityCELAlignment table.

Usage
-----
    # Full recompute (all stages, all facilities)
    python manage.py compute_cel_viability

    # Single stage
    python manage.py compute_cel_viability --stage <cel_stage_id>

    # Facilities for a specific SIREN scenario
    python manage.py compute_cel_viability --scenario <scenario_title>

    # Verbose output (one line per facility)
    python manage.py compute_cel_viability -v 2

    # Dry-run: compute but do not save to database
    python manage.py compute_cel_viability --dry-run
"""

import logging

from django.core.management.base import BaseCommand, CommandError

from siren_web.models import CELStage, Scenarios
from powermapui.utils.cel_viability_service import CELViabilityService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Recompute CEL transmission viability scores for the RE facility pipeline. "
        "Results are stored in FacilityCELAlignment."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--stage',
            type=int,
            metavar='CEL_STAGE_ID',
            help="Recompute only for this CEL stage (by primary key).",
        )
        parser.add_argument(
            '--scenario',
            type=str,
            metavar='SCENARIO_TITLE',
            help="Restrict to facilities linked to this SIREN scenario title.",
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            help="Compute scores but do not write to the database.",
        )

    def handle(self, *args, **options):
        verbosity = options['verbosity']   # 0, 1, or 2 (set by -v flag)
        dry_run = options['dry_run']
        stage_id = options.get('stage')
        scenario_title = options.get('scenario')

        # ── Resolve optional filters ──────────────────────────────────────

        scenario = None
        if scenario_title:
            try:
                scenario = Scenarios.objects.get(title=scenario_title)
            except Scenarios.DoesNotExist:
                raise CommandError(
                    f"Scenario '{scenario_title}' not found. "
                    "Check the title with: python manage.py shell -c "
                    "\"from siren_web.models import Scenarios; "
                    "[print(s.title) for s in Scenarios.objects.all()]\""
                )
            if verbosity >= 1:
                self.stdout.write(f"Filtering to scenario: {scenario.title}")

        stage = None
        if stage_id:
            try:
                stage = CELStage.objects.select_related('cel_program').get(
                    cel_stage_id=stage_id
                )
            except CELStage.DoesNotExist:
                raise CommandError(
                    f"CEL stage with ID {stage_id} not found. "
                    "List stages with: python manage.py shell -c "
                    "\"from siren_web.models import CELStage; "
                    "[print(s.cel_stage_id, s.name) for s in CELStage.objects.all()]\""
                )
            if verbosity >= 1:
                self.stdout.write(
                    f"Restricting to stage: [{stage.cel_stage_id}] {stage.name} "
                    f"({stage.cel_program.code})"
                )

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN — scores will be computed but not saved.")
            )

        # ── Run the service ───────────────────────────────────────────────

        if dry_run:
            self._run_dry(stage, scenario, verbosity)
        elif stage:
            count = CELViabilityService.score_facilities_for_stage(stage, verbosity)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Updated {count} alignment record(s) for stage '{stage.name}'."
                )
            )
        else:
            stats = CELViabilityService.score_all_facilities(scenario, verbosity)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Complete: {stats['stages_processed']} stage(s), "
                    f"{stats['alignments_created']} created, "
                    f"{stats['alignments_updated']} updated."
                )
            )
            if verbosity >= 1:
                self._print_summary()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _run_dry(self, stage, scenario, verbosity):
        """Compute and print scores without persisting."""
        from siren_web.models import facilities as FacilitiesModel

        stages = (
            [stage] if stage
            else list(CELStage.objects.filter(is_active=True).select_related('cel_program'))
        )
        if not stages:
            self.stdout.write(self.style.WARNING("No active CEL stages found."))
            return

        facility_qs = CELViabilityService._get_facility_queryset(scenario)
        facility_count = facility_qs.count()

        self.stdout.write(
            f"\nDry run: {len(stages)} stage(s), {facility_count} facility/ies\n"
        )

        for s in stages:
            route_coords = s.get_route_coordinates()
            if not route_coords:
                self.stdout.write(
                    self.style.WARNING(f"  [{s.cel_stage_id}] {s.name} — no route coordinates, skipped.")
                )
                continue

            aligned = []
            for f in facility_qs:
                result = CELViabilityService._compute_alignment(f, s, route_coords)
                if result['is_aligned']:
                    aligned.append((f, result))

            self.stdout.write(
                f"\n  Stage: {s.name} ({s.cel_program.code}) "
                f"[{s.funding_status}]  "
                f"Available: {s.available_capacity_mw:,.0f} / {s.total_capacity_mw:,.0f} MW"
            )
            self.stdout.write(f"  Aligned facilities: {len(aligned)}")

            if verbosity >= 2:
                for f, r in sorted(aligned, key=lambda x: -(x[1]['viability_score'] or 0)):
                    label = r['viability_label'].upper()
                    cap = f.capacity or 0
                    self.stdout.write(
                        f"    {label:8s}  {r['viability_score']:.3f}  "
                        f"{cap:6.0f} MW  dist={r['distance_km']:.1f} km  "
                        f"{f.facility_name} [{f.status}]"
                    )

    def _print_summary(self):
        """Print a post-run pipeline summary to stdout."""
        summary = CELViabilityService.get_pipeline_summary()
        totals = summary['totals']

        self.stdout.write("\n── Pipeline Summary ─────────────────────────────────────")
        self.stdout.write(
            f"  CEL total capacity:     {totals['cel_total_capacity_mw']:>8,.0f} MW"
        )
        self.stdout.write(
            f"  CEL available headroom: {totals['cel_available_capacity_mw']:>8,.0f} MW"
        )
        self.stdout.write(
            f"  Total aligned pipeline: {totals['pipeline_mw']:>8,.0f} MW"
        )
        self.stdout.write(
            f"  High-viability pipeline:{totals['high_viability_mw']:>8,.0f} MW"
        )
        self.stdout.write("")

        by_v = summary['by_viability']
        self.stdout.write("  Viability breakdown:")
        for tier in ('high', 'medium', 'low', 'exception', 'unscored'):
            d = by_v[tier]
            if d['count']:
                self.stdout.write(
                    f"    {tier:10s}  {d['count']:3d} facilities  "
                    f"{d['capacity_mw']:,.0f} MW"
                )

        self.stdout.write("")
        self.stdout.write("  By CEL stage:")
        for s in summary['by_stage']:
            self.stdout.write(
                f"    {s['program_code']:<8s} {s['stage_name']:<40s} "
                f"[{s['funding_status']:<21s}]  "
                f"avail {s['available_capacity_mw']:>6,.0f}/{s['total_capacity_mw']:>6,.0f} MW  "
                f"aligned {s['aligned_facility_count']:>3d} fac  "
                f"high-viability {s['high_viability_pipeline_mw']:>6,.0f} MW"
            )
        self.stdout.write("─" * 60)
