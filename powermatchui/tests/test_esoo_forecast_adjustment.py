# powermatchui/tests/test_esoo_forecast_adjustment.py
"""
Unit tests for powermatchui.utils.esoo_forecast_adjustment.compute_bias_correction
-- the pure function behind the Powermatch-facing bias-correction feature.
No database: same SimpleTestCase style as test_ev_reconciliation.py,
driving compute_bias_correction directly against fixture
ForecastActualPair-shaped dicts via align_forecast_actual_pairs.
"""
from django.test import SimpleTestCase

from powermatchui.utils.esoo_forecast_adjustment import compute_bias_correction
from powerplotui.services.esoo_bias_analysis import align_forecast_actual_pairs


def _figure(vintage_year, forecast_year, metric, scenario, poe_level, value, unit='MW'):
    return {
        'vintage_year': vintage_year, 'forecast_year': forecast_year, 'metric': metric,
        'demand_growth_scenario': scenario, 'poe_level': poe_level,
        'demand_basis': 'operational', 'value': value, 'unit': unit,
    }


def _actual(forecast_year, metric, value):
    return {'forecast_year': forecast_year, 'metric': metric, 'demand_basis': 'operational', 'value': value}


# Six years of POE10 peak_summer forecasts at horizon=2, errors varying
# around a mean of +400 MW (not constant -- assess_systematic_bias
# refuses to t-test a zero-variance sample) but tight enough to be
# significant at n=6.
OVER_FORECAST_ERRORS = [380, 420, 390, 410, 405, 395]  # mean == 400.0
OVER_FORECAST_FIGURES = [
    _figure(2010 + i, 2012 + i, 'peak_summer', 'expected', 10, 4000)
    for i in range(6)
]
OVER_FORECAST_ACTUALS = [
    _actual(2012 + i, 'peak_summer', 4000 - e)
    for i, e in enumerate(OVER_FORECAST_ERRORS)
]


class ComputeBiasCorrectionTests(SimpleTestCase):
    def _pairs(self, figures=OVER_FORECAST_FIGURES, actuals=OVER_FORECAST_ACTUALS):
        pairs, _refused = align_forecast_actual_pairs(figures, actuals)
        return pairs

    def test_sufficient_evidence_applies_negative_correction_for_over_forecast(self):
        pairs = self._pairs()
        result = compute_bias_correction(
            pairs, metric='peak_summer', demand_growth_scenario='expected', poe_level=10,
            horizon=2, original_value=4500.0, unit='MW',
        )
        self.assertEqual(result.verdict, 'forecasts_run_high')
        self.assertEqual(result.adjustment_value, -400.0)
        self.assertEqual(result.adjusted_value, 4100.0)
        self.assertEqual(result.n, 6)
        self.assertLess(result.p_value, 0.05)

    def test_insufficient_evidence_applies_no_correction(self):
        # Only 3 historical pairs -- below assess_systematic_bias's
        # default minimum sample size of 5.
        pairs = self._pairs(figures=OVER_FORECAST_FIGURES[:3], actuals=OVER_FORECAST_ACTUALS[:3])
        result = compute_bias_correction(
            pairs, metric='peak_summer', demand_growth_scenario='expected', poe_level=10,
            horizon=2, original_value=4500.0, unit='MW',
        )
        self.assertEqual(result.verdict, 'insufficient_evidence')
        self.assertEqual(result.adjustment_value, 0.0)
        self.assertEqual(result.adjusted_value, 4500.0)
        self.assertIn('No correction applied', result.notes[0])

    def test_no_historical_pairs_for_group_is_insufficient_evidence(self):
        pairs = self._pairs()
        result = compute_bias_correction(
            pairs, metric='minimum', demand_growth_scenario='expected', poe_level=90,
            horizon=2, original_value=1000.0, unit='MW',
        )
        self.assertEqual(result.verdict, 'insufficient_evidence')
        self.assertEqual(result.n, 0)

    def test_category_label_is_carried_through(self):
        pairs = self._pairs()
        result = compute_bias_correction(
            pairs, metric='peak_summer', demand_growth_scenario='expected', poe_level=10,
            horizon=2, original_value=4500.0, unit='MW', category='growth_assumption',
        )
        self.assertEqual(result.category, 'growth_assumption')
        self.assertEqual(result.metric, 'peak_summer')
        self.assertEqual(result.horizon, 2)

    def test_under_forecast_group_applies_positive_correction(self):
        under_forecast_errors = [-380, -420, -390, -410, -405, -395]  # mean == -400.0
        under_forecast_figures = [
            _figure(2010 + i, 2012 + i, 'peak_summer', 'expected', 10, 4000)
            for i in range(6)
        ]
        under_forecast_actuals = [
            _actual(2012 + i, 'peak_summer', 4000 - e)
            for i, e in enumerate(under_forecast_errors)
        ]
        pairs = self._pairs(figures=under_forecast_figures, actuals=under_forecast_actuals)
        result = compute_bias_correction(
            pairs, metric='peak_summer', demand_growth_scenario='expected', poe_level=10,
            horizon=2, original_value=4000.0, unit='MW',
        )
        self.assertEqual(result.verdict, 'forecasts_run_low')
        self.assertEqual(result.adjustment_value, 400.0)
        self.assertEqual(result.adjusted_value, 4400.0)
