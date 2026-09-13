# powerplotui/tests/test_esoo_bias_analysis.py
"""
Unit tests for the FR-G2 bias-tracking statistics module
(powerplotui.services.esoo_bias_analysis).

Same style as test_ev_uptake_analysis.py -- pure functions over plain
dicts, no database. Covers the pre-existing central-estimate behaviour
(compute_central_estimate_errors/assess_systematic_bias, locked in here
for the first time) plus the compute_mean_error_by_group/
raw_errors_by_group generalisation added for the Powermatch-facing
bias-correction feature, which needs bias stats at POE levels other than
the central estimate's POE50 (in particular POE10, the binding forecast).
"""
from django.test import SimpleTestCase

from powerplotui.services.esoo_bias_analysis import (
    align_forecast_actual_pairs,
    assess_systematic_bias,
    compute_band_calibration,
    compute_central_estimate_errors,
    compute_mean_error_by_group,
    melt_actual_to_metric_dicts,
    raw_errors_by_group,
)


def _figure(vintage_year, forecast_year, metric, scenario, poe_level, value, unit='MW', demand_basis='operational'):
    return {
        'vintage_year': vintage_year, 'forecast_year': forecast_year, 'metric': metric,
        'demand_growth_scenario': scenario, 'poe_level': poe_level,
        'demand_basis': demand_basis, 'value': value, 'unit': unit,
    }


def _actual(forecast_year, metric, value, demand_basis='operational'):
    return {'forecast_year': forecast_year, 'metric': metric, 'demand_basis': demand_basis, 'value': value}


class AlignForecastActualPairsTests(SimpleTestCase):
    def test_matches_on_year_metric_basis_and_computes_signed_error(self):
        figures = [_figure(2018, 2020, 'peak_summer', 'expected', 10, 4000)]
        actuals = [_actual(2020, 'peak_summer', 3800)]
        pairs, refused = align_forecast_actual_pairs(figures, actuals)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(refused, [])
        self.assertEqual(pairs[0].error, 200)  # forecast - actual, positive = over-forecast
        self.assertEqual(pairs[0].horizon, 2)

    def test_demand_basis_mismatch_is_refused_not_dropped(self):
        figures = [_figure(2018, 2020, 'peak_summer', 'expected', 10, 4000, demand_basis='underlying')]
        actuals = [_actual(2020, 'peak_summer', 3800, demand_basis='operational')]
        pairs, refused = align_forecast_actual_pairs(figures, actuals)
        self.assertEqual(pairs, [])
        self.assertEqual(len(refused), 1)
        self.assertIn('demand_basis mismatch', refused[0]['reason'])

    def test_no_actual_yet_is_silently_excluded(self):
        figures = [_figure(2018, 2030, 'peak_summer', 'expected', 10, 4000)]
        pairs, refused = align_forecast_actual_pairs(figures, [])
        self.assertEqual(pairs, [])
        self.assertEqual(refused, [])


class ComputeMeanErrorByGroupTests(SimpleTestCase):
    """Covers the generalisation added alongside compute_central_estimate_errors."""

    def _pairs(self):
        figures = [
            _figure(2016, 2018, 'peak_summer', 'expected', 10, 4200),
            _figure(2016, 2018, 'peak_summer', 'expected', 50, 4000),
            _figure(2017, 2019, 'peak_summer', 'expected', 10, 4300),
            _figure(2017, 2019, 'peak_summer', 'expected', 50, 4050),
        ]
        actuals = [_actual(2018, 'peak_summer', 3800), _actual(2019, 'peak_summer', 3900)]
        pairs, _refused = align_forecast_actual_pairs(figures, actuals)
        return pairs

    def test_poe10_group_is_distinct_from_central_estimate_poe50(self):
        pairs = self._pairs()
        poe10 = compute_mean_error_by_group(pairs, demand_growth_scenario='expected', poe_level=10)
        central = compute_central_estimate_errors(pairs)
        # Both are horizon=2 peak_summer, but drawn from different POE figures.
        self.assertEqual(poe10[('peak_summer', 2)]['me'], 400)   # mean(4200-3800, 4300-3900) = mean(400,400)
        self.assertEqual(central[('peak_summer', 2)]['me'], 175)  # mean(4000-3800, 4050-3900) = mean(200,150)
        self.assertEqual(poe10[('peak_summer', 2)]['n'], 2)

    def test_scenario_filter_excludes_non_matching_scenario(self):
        figures = [_figure(2016, 2018, 'peak_summer', 'high', 10, 5000)]
        actuals = [_actual(2018, 'peak_summer', 3800)]
        pairs, _refused = align_forecast_actual_pairs(figures, actuals)
        result = compute_mean_error_by_group(pairs, demand_growth_scenario='expected', poe_level=10)
        self.assertEqual(result, {})

    def test_raw_errors_by_group_matches_aggregated_mean(self):
        pairs = self._pairs()
        raw = raw_errors_by_group(pairs, demand_growth_scenario='expected', poe_level=10)
        self.assertEqual(raw[('peak_summer', 2)], [400, 400])

    def test_poe_level_50_still_matches_no_poe_axis_energy_figures(self):
        # D12(a): energy has no POE axis, so poe_level=None counts as the
        # central estimate alongside an explicit POE50 -- preserved by
        # the poe_level=50 special case in _matches_group.
        figures = [_figure(2016, 2018, 'energy', 'expected', None, 30000, unit='GWh')]
        actuals = [_actual(2018, 'energy', 28000)]
        pairs, _refused = align_forecast_actual_pairs(figures, actuals)
        result = compute_mean_error_by_group(pairs, demand_growth_scenario='expected', poe_level=50)
        self.assertEqual(result[('energy', 2)]['me'], 2000)

    def test_poe_level_other_than_50_requires_exact_match_no_fallback(self):
        # Unlike poe_level=50, a POE10 request must not silently accept a
        # no-POE-axis figure -- there's no equivalent convention for it.
        figures = [_figure(2016, 2018, 'energy', 'expected', None, 30000, unit='GWh')]
        actuals = [_actual(2018, 'energy', 28000)]
        pairs, _refused = align_forecast_actual_pairs(figures, actuals)
        result = compute_mean_error_by_group(pairs, demand_growth_scenario='expected', poe_level=10)
        self.assertEqual(result, {})


class ComputeBandCalibrationTests(SimpleTestCase):
    def test_realised_frequency_and_nominal_frequency(self):
        figures = [
            _figure(2016, 2018, 'peak_summer', 'expected', 10, 4200),
            _figure(2017, 2019, 'peak_summer', 'expected', 10, 3700),
        ]
        actuals = [_actual(2018, 'peak_summer', 3800), _actual(2019, 'peak_summer', 3900)]  # one exceeds, one doesn't
        pairs, _refused = align_forecast_actual_pairs(figures, actuals)
        result = compute_band_calibration(pairs)
        self.assertEqual(result[('peak_summer', 10)]['realised_frequency'], 0.5)
        self.assertEqual(result[('peak_summer', 10)]['nominal_frequency'], 0.1)

    def test_minimum_metric_requires_explicit_direction(self):
        figures = [_figure(2016, 2018, 'minimum', 'expected', 90, 1000)]
        actuals = [_actual(2018, 'minimum', 950)]
        pairs, _refused = align_forecast_actual_pairs(figures, actuals)
        with self.assertRaises(ValueError):
            compute_band_calibration(pairs)


class AssessSystematicBiasTests(SimpleTestCase):
    def test_below_minimum_sample_size_is_insufficient_evidence(self):
        verdict = assess_systematic_bias([100, 200, 300])
        self.assertEqual(verdict.verdict, 'insufficient_evidence')
        self.assertIsNone(verdict.p_value)

    def test_clear_positive_bias_is_forecasts_run_high(self):
        verdict = assess_systematic_bias([400, 420, 410, 405, 415, 395])
        self.assertEqual(verdict.verdict, 'forecasts_run_high')
        self.assertLess(verdict.p_value, 0.05)

    def test_errors_straddling_zero_are_insufficient_evidence(self):
        verdict = assess_systematic_bias([100, -100, 50, -50, 20, -20])
        self.assertEqual(verdict.verdict, 'insufficient_evidence')


class MeltActualToMetricDictsTests(SimpleTestCase):
    class _FakeActual:
        def __init__(self, year, demand_basis, energy, minimum, peak, peak_month):
            self.year = year
            self.demand_basis = demand_basis
            self.annual_energy_gwh = energy
            self.minimum_demand_mw = minimum
            self.peak_demand_mw = peak
            self.peak_datetime = _FakeDatetime(peak_month) if peak_month else None

    def test_summer_peak_is_tagged_peak_summer(self):
        actual = self._FakeActual(2020, 'operational', 30000, 1200, 3800, peak_month=1)
        out = melt_actual_to_metric_dicts(actual)
        metrics = {d['metric']: d['value'] for d in out}
        self.assertEqual(metrics['peak_summer'], 3800)
        self.assertEqual(metrics['energy'], 30000)
        self.assertEqual(metrics['minimum'], 1200)

    def test_shoulder_month_peak_emits_no_peak_metric(self):
        actual = self._FakeActual(2020, 'operational', 30000, 1200, 3200, peak_month=4)
        out = melt_actual_to_metric_dicts(actual)
        metrics = {d['metric'] for d in out}
        self.assertNotIn('peak_summer', metrics)
        self.assertNotIn('peak_winter', metrics)


class _FakeDatetime:
    def __init__(self, month):
        self.month = month
