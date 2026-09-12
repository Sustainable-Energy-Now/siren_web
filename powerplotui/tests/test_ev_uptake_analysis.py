# powerplotui/tests/test_ev_uptake_analysis.py
"""
Unit tests for the FR-13/FR-14 tracking-inversion module
(powerplotui.services.ev_uptake_analysis).

Same style as powerplotui/test_dot_wa_ev_parser.py — the pure functions
over plain dicts are driven directly, no database. O8: every comparison
here is fleet-count vs fleet-count, never against a consumption figure.
"""
from django.test import SimpleTestCase

from powerplotui.services.ev_uptake_analysis import (
    aggregate_wa_fleet_by_scenario_year,
    build_projection_curves,
    build_tracking_report,
    flag_nearest_trajectory,
)


def _figure(scenario, year, fleet):
    return {'csiro_scenario': scenario, 'forecast_year': year, 'fleet_count': fleet}


class AggregateWaFleetTests(SimpleTestCase):
    def test_sums_state_wide_by_scenario_year(self):
        figures = [
            _figure('Step Change', 2025, 100.0),
            _figure('Step Change', 2025, 250.0),  # another postcode, same key
            _figure('Step Change', 2026, 400.0),
            _figure('Slow Change', 2025, 90.0),
        ]
        totals = aggregate_wa_fleet_by_scenario_year(figures)
        self.assertEqual(totals[('Step Change', 2025)], 350.0)
        self.assertEqual(totals[('Step Change', 2026)], 400.0)
        self.assertEqual(totals[('Slow Change', 2025)], 90.0)

    def test_none_fleet_count_is_skipped(self):
        figures = [_figure('Step Change', 2025, None), _figure('Step Change', 2025, 42.0)]
        self.assertEqual(aggregate_wa_fleet_by_scenario_year(figures), {('Step Change', 2025): 42.0})


class BuildProjectionCurvesTests(SimpleTestCase):
    def test_reshapes_into_one_curve_per_scenario(self):
        totals = {
            ('Step Change', 2025): 1000.0,
            ('Step Change', 2030): 5000.0,
            ('Slow Change', 2025): 600.0,
        }
        curves = build_projection_curves(totals)
        self.assertEqual(curves['Step Change'], {2025: 1000.0, 2030: 5000.0})
        self.assertEqual(curves['Slow Change'], {2025: 600.0})


class FlagNearestTrajectoryTests(SimpleTestCase):
    CURVES = {
        'Step Change': {2025: 1000.0, 2026: 1500.0},
        'Slow Change': {2025: 500.0, 2026: 700.0},
    }

    def test_picks_the_nearest_scenario_and_reports_divergence(self):
        flag = flag_nearest_trajectory(2025, 600.0, self.CURVES)
        self.assertEqual(flag.nearest_scenario, 'Slow Change')
        self.assertEqual(flag.divergence_fleet_count, 100.0)  # 600 - 500
        self.assertAlmostEqual(flag.divergence_pct, 20.0)
        self.assertEqual(flag.curves, {'Step Change': 1000.0, 'Slow Change': 500.0})

    def test_negative_divergence_when_actual_is_below_the_nearest_curve(self):
        flag = flag_nearest_trajectory(2025, 450.0, self.CURVES)
        self.assertEqual(flag.nearest_scenario, 'Slow Change')
        self.assertEqual(flag.divergence_fleet_count, -50.0)

    def test_returns_none_when_no_curve_covers_that_year(self):
        self.assertIsNone(flag_nearest_trajectory(2027, 800.0, self.CURVES))

    def test_only_scenarios_with_that_exact_year_are_considered(self):
        curves = {
            'Step Change': {2025: 1000.0},
            'Slow Change': {2026: 400.0},  # no 2025 point
        }
        flag = flag_nearest_trajectory(2025, 350.0, curves)
        self.assertEqual(flag.nearest_scenario, 'Step Change')
        self.assertEqual(set(flag.curves), {'Step Change'})


class BuildTrackingReportTests(SimpleTestCase):
    FIGURES = [
        _figure('Step Change', 2025, 1000.0),
        _figure('Step Change', 2026, 1500.0),
        _figure('Slow Change', 2025, 500.0),
        _figure('Slow Change', 2026, 700.0),
    ]

    def test_flags_the_latest_actuals_year(self):
        actuals = [
            {'year': 2025, 'fleet_count': 520.0},
            {'year': 2026, 'fleet_count': 690.0},
        ]
        report = build_tracking_report(self.FIGURES, actuals)
        self.assertEqual(report['actuals_by_year'], {2025: 520.0, 2026: 690.0})
        self.assertEqual(report['latest_flag'].year, 2026)
        self.assertEqual(report['latest_flag'].nearest_scenario, 'Slow Change')
        self.assertEqual(set(report['curves']), {'Step Change', 'Slow Change'})

    def test_no_actuals_yields_no_flag(self):
        report = build_tracking_report(self.FIGURES, [])
        self.assertEqual(report['actuals_by_year'], {})
        self.assertIsNone(report['latest_flag'])
        self.assertEqual(set(report['curves']), {'Step Change', 'Slow Change'})

    def test_latest_flag_is_none_when_no_curve_covers_the_latest_actuals_year(self):
        report = build_tracking_report(self.FIGURES, [{'year': 2099, 'fleet_count': 10.0}])
        self.assertIsNone(report['latest_flag'])
