# powermatchui/tests/test_ev_reconciliation.py
"""
Unit tests for the FR-06/FR-07 reconciliation module
(powermatchui.utils.ev_reconciliation).

Every function here takes plain dicts, so the whole module is covered by
SimpleTestCase with no database — same approach as
powerplotui/test_dot_wa_ev_parser.py, which drives the pure fetch/parse
helpers directly and only reaches for a fixture when an end-to-end path
needs one (there is no such path here).
"""
from django.test import SimpleTestCase

from powermatchui.utils.ev_reconciliation import (
    DEFAULT_TOLERANCE_PCT,
    BackcastNotValidatedError,
    aggregate_statewide_annual_energy,
    aggregate_swis_annual_energy,
    require_backcast_passed,
    run_backcast_gate,
)


def _figure(postcode, year, scenario, kwh):
    return {
        'postcode': postcode,
        'forecast_year': year,
        'csiro_scenario': scenario,
        'consumption_kwh': kwh,
    }


# 6010 fully in SWIS, 6011 half in, 6100 out, 6999 has no membership row.
MEMBERSHIP = {
    '6010': {'membership_status': 'in', 'apportionment_fraction': 1.0},
    '6011': {'membership_status': 'partial', 'apportionment_fraction': 0.5},
    '6100': {'membership_status': 'out', 'apportionment_fraction': 0.0},
}


class SwisAggregationTests(SimpleTestCase):
    def test_in_and_partial_postcodes_aggregate_with_unit_conversion(self):
        figures = [
            _figure('6010', 2025, 'Step Change', 1_000_000),
            _figure('6011', 2025, 'Step Change', 1_000_000),  # partial → 0.5
        ]
        result = aggregate_swis_annual_energy(figures, MEMBERSHIP)
        # (1_000_000 + 0.5 * 1_000_000) kWh / 1000 = 1500 MWh
        self.assertAlmostEqual(result.aggregated_mwh[('Step Change', 2025)], 1500.0)
        self.assertEqual(result.n_figures_used, 2)
        self.assertEqual(result.excluded_postcodes, [])

    def test_out_of_swis_postcode_is_dropped_but_not_reported_as_excluded(self):
        result = aggregate_swis_annual_energy([_figure('6100', 2025, 'Step Change', 5_000_000)], MEMBERSHIP)
        self.assertEqual(result.aggregated_mwh, {})
        self.assertEqual(result.n_figures_used, 0)
        self.assertEqual(result.excluded_postcodes, [])  # 'out' is a known decision, not a gap

    def test_postcode_without_membership_row_is_excluded_and_reported(self):
        figures = [
            _figure('6999', 2025, 'Step Change', 9_000_000),
            _figure('6998', 2025, 'Step Change', 9_000_000),
        ]
        result = aggregate_swis_annual_energy(figures, MEMBERSHIP)
        self.assertEqual(result.aggregated_mwh, {})
        self.assertEqual(result.excluded_postcodes, ['6998', '6999'])  # sorted

    def test_none_consumption_is_skipped(self):
        figures = [
            _figure('6010', 2025, 'Step Change', None),
            _figure('6010', 2025, 'Step Change', 2_000_000),
        ]
        result = aggregate_swis_annual_energy(figures, MEMBERSHIP)
        self.assertAlmostEqual(result.aggregated_mwh[('Step Change', 2025)], 2000.0)
        self.assertEqual(result.n_figures_used, 1)

    def test_keys_split_by_scenario_and_year(self):
        figures = [
            _figure('6010', 2025, 'Step Change', 1_000_000),
            _figure('6010', 2026, 'Step Change', 1_000_000),
            _figure('6010', 2025, 'Slow Change', 1_000_000),
        ]
        result = aggregate_swis_annual_energy(figures, MEMBERSHIP)
        self.assertEqual(
            set(result.aggregated_mwh),
            {('Step Change', 2025), ('Step Change', 2026), ('Slow Change', 2025)},
        )


class StatewideAggregationTests(SimpleTestCase):
    def test_no_boundary_filter_is_applied(self):
        figures = [
            _figure('6010', 2025, 'Step Change', 1_000_000),   # in SWIS
            _figure('6100', 2025, 'Step Change', 1_000_000),   # out of SWIS
            _figure('6999', 2025, 'Step Change', 1_000_000),   # unknown to the boundary
        ]
        totals = aggregate_statewide_annual_energy(figures)
        self.assertAlmostEqual(totals[('Step Change', 2025)], 3000.0)

    def test_none_consumption_is_skipped(self):
        figures = [
            _figure('6010', 2025, 'Step Change', None),
            _figure('6011', 2025, 'Step Change', 4_000_000),
        ]
        self.assertAlmostEqual(aggregate_statewide_annual_energy(figures)[('Step Change', 2025)], 4000.0)


class BackcastGateTests(SimpleTestCase):
    def test_within_tolerance_passes(self):
        aggregated = {('Step Change', 2023): 1000.0}
        published = {('Step Change', 2023): 1000.5}  # 0.05% < 0.1% default
        (check,) = run_backcast_gate(aggregated, published)
        self.assertEqual(check.status, 'passed')
        self.assertLess(check.error_pct, DEFAULT_TOLERANCE_PCT)
        self.assertEqual(check.notes, [])

    def test_outside_tolerance_fails_with_note(self):
        aggregated = {('Step Change', 2023): 1000.0}
        published = {('Step Change', 2023): 1010.0}  # ~0.99%
        (check,) = run_backcast_gate(aggregated, published)
        self.assertEqual(check.status, 'failed')
        self.assertTrue(any('exceeds tolerance' in n for n in check.notes))

    def test_missing_published_reference_is_not_yet_validated(self):
        (check,) = run_backcast_gate({('Step Change', 2023): 1000.0}, {})
        self.assertEqual(check.status, 'not_yet_validated')
        self.assertIsNone(check.published_mwh)

    def test_tolerance_none_never_passes_by_default(self):
        aggregated = {('Step Change', 2023): 1000.0}
        published = {('Step Change', 2023): 1000.0}  # exact match
        (check,) = run_backcast_gate(aggregated, published, tolerance_pct=None)
        self.assertEqual(check.status, 'not_yet_validated')

    def test_checks_are_sorted_by_key(self):
        aggregated = {
            ('Step Change', 2025): 1.0,
            ('Slow Change', 2023): 1.0,
            ('Step Change', 2023): 1.0,
        }
        checks = run_backcast_gate(aggregated, {})
        self.assertEqual(
            [(c.csiro_scenario, c.forecast_year) for c in checks],
            [('Slow Change', 2023), ('Step Change', 2023), ('Step Change', 2025)],
        )


class RequireBackcastPassedTests(SimpleTestCase):
    def test_all_passed_returns_checks_unchanged(self):
        checks = run_backcast_gate({('Step Change', 2023): 1000.0}, {('Step Change', 2023): 1000.0})
        self.assertIs(require_backcast_passed(checks), checks)

    def test_any_unvalidated_or_failed_check_raises(self):
        checks = run_backcast_gate({('Step Change', 2023): 1000.0}, {})
        with self.assertRaises(BackcastNotValidatedError) as ctx:
            require_backcast_passed(checks)
        self.assertIn('Step Change/2023', str(ctx.exception))
        self.assertIn('not_yet_validated', str(ctx.exception))
