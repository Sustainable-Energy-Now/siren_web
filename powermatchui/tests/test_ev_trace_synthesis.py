# powermatchui/tests/test_ev_trace_synthesis.py
"""
Unit tests for the FR-09/FR-10 half-hourly EV load trace synthesis module
(powermatchui.utils.ev_trace_synthesis).

Follows powerplotui/test_dot_wa_ev_parser.py: the pure construction
helpers (shape combination, tiling/scaling, the managed-charging kernel)
are exercised directly with hand-built shapes; no database or fixture
file is needed.
"""
import calendar
from datetime import date, timedelta

import numpy as np
from django.test import SimpleTestCase

from powermatchui.utils.ev_trace_synthesis import (
    ENERGY_CONSERVATION_TOLERANCE_PCT,
    INTERVALS_PER_DAY,
    AnnualTraceResult,
    ChargingTypeProfile,
    TraceSynthesisError,
    apply_managed_charging_lever,
    combine_charging_type_shapes,
    require_energy_conserved,
    shape_annual_energy_to_halfhourly,
)


def _spike(interval):
    """A 48-value shape with all of the day's charging in one interval."""
    s = [0.0] * INTERVALS_PER_DAY
    s[interval] = 7.0  # unnormalised on purpose — the module normalises
    return s


FLAT = [1.0] * INTERVALS_PER_DAY


class CombineChargingTypeShapesTests(SimpleTestCase):
    def test_single_profile_composite_is_the_normalised_shape(self):
        prof = ChargingTypeProfile('Convenience', 'unmanaged', 0.4, _spike(10), _spike(40))
        weekday, weekend = combine_charging_type_shapes([prof], 'unmanaged')
        self.assertAlmostEqual(weekday.sum(), 1.0)
        self.assertAlmostEqual(weekend.sum(), 1.0)
        self.assertAlmostEqual(weekday[10], 1.0)
        self.assertAlmostEqual(weekend[40], 1.0)

    def test_shares_weight_the_composite(self):
        a = ChargingTypeProfile('A', 'unmanaged', 1.0, _spike(0), _spike(0))
        b = ChargingTypeProfile('B', 'unmanaged', 3.0, _spike(47), _spike(47))
        weekday, _ = combine_charging_type_shapes([a, b], 'unmanaged')
        self.assertAlmostEqual(weekday[0], 0.25)
        self.assertAlmostEqual(weekday[47], 0.75)

    def test_shares_are_renormalised_across_supplied_profiles(self):
        # Same 1:3 ratio, absolute shares 10x larger — result is identical
        # because shares are renormalised over the profiles actually passed.
        a = ChargingTypeProfile('A', 'unmanaged', 10.0, _spike(0), _spike(0))
        b = ChargingTypeProfile('B', 'unmanaged', 30.0, _spike(47), _spike(47))
        weekday, _ = combine_charging_type_shapes([a, b], 'unmanaged')
        self.assertAlmostEqual(weekday[0], 0.25)
        self.assertAlmostEqual(weekday[47], 0.75)

    def test_only_matching_charging_mode_is_used(self):
        unmanaged = ChargingTypeProfile('U', 'unmanaged', 1.0, _spike(5), _spike(5))
        managed = ChargingTypeProfile('M', 'managed', 1.0, _spike(30), _spike(30))
        weekday, _ = combine_charging_type_shapes([unmanaged, managed], 'unmanaged')
        self.assertAlmostEqual(weekday[5], 1.0)
        self.assertAlmostEqual(weekday[30], 0.0)

    def test_no_matching_profiles_raises(self):
        managed = ChargingTypeProfile('M', 'managed', 1.0, _spike(30), _spike(30))
        with self.assertRaises(TraceSynthesisError):
            combine_charging_type_shapes([managed], 'unmanaged')

    def test_wrong_length_shape_raises(self):
        bad = ChargingTypeProfile('bad', 'unmanaged', 1.0, [1.0] * 47, FLAT)
        with self.assertRaises(TraceSynthesisError):
            combine_charging_type_shapes([bad], 'unmanaged')

    def test_non_positive_shape_raises(self):
        bad = ChargingTypeProfile('bad', 'unmanaged', 1.0, [0.0] * INTERVALS_PER_DAY, FLAT)
        with self.assertRaises(TraceSynthesisError):
            combine_charging_type_shapes([bad], 'unmanaged')

    def test_non_positive_total_share_raises(self):
        a = ChargingTypeProfile('A', 'unmanaged', 0.0, FLAT, FLAT)
        with self.assertRaises(TraceSynthesisError):
            combine_charging_type_shapes([a], 'unmanaged')


class ShapeAnnualEnergyToHalfhourlyTests(SimpleTestCase):
    def _flat_shape(self):
        return np.full(INTERVALS_PER_DAY, 1.0 / INTERVALS_PER_DAY)

    def test_non_leap_year_interval_count(self):
        result = shape_annual_energy_to_halfhourly(1000.0, self._flat_shape(), self._flat_shape(), 2025)
        self.assertEqual(result.n_intervals, 365 * INTERVALS_PER_DAY)

    def test_leap_year_interval_count(self):
        result = shape_annual_energy_to_halfhourly(1000.0, self._flat_shape(), self._flat_shape(), 2024)
        self.assertEqual(result.n_intervals, 366 * INTERVALS_PER_DAY)
        self.assertTrue(calendar.isleap(2024))

    def test_energy_is_conserved_within_tolerance(self):
        result = shape_annual_energy_to_halfhourly(12345.678, self._flat_shape(), self._flat_shape(), 2025)
        self.assertAlmostEqual(result.achieved_energy_mwh, 12345.678, places=3)
        self.assertLessEqual(result.integral_check_pct, ENERGY_CONSERVATION_TOLERANCE_PCT)
        self.assertEqual(result.notes, [])

    def test_flat_shape_gives_a_constant_trace(self):
        result = shape_annual_energy_to_halfhourly(1000.0, self._flat_shape(), self._flat_shape(), 2025)
        expected_mw = (1000.0 / 365) / INTERVALS_PER_DAY / 0.5
        self.assertTrue(np.allclose(result.trace, expected_mw))

    def test_weekday_and_weekend_shapes_are_placed_by_real_calendar(self):
        weekday = np.zeros(INTERVALS_PER_DAY)
        weekday[0] = 1.0
        weekend = np.zeros(INTERVALS_PER_DAY)
        weekend[47] = 1.0

        result = shape_annual_energy_to_halfhourly(365.0, weekday, weekend, 2025)
        daily = result.trace.reshape(-1, INTERVALS_PER_DAY)

        first_day = date(2025, 1, 1)
        n_weekend = sum((first_day + timedelta(days=i)).weekday() >= 5 for i in range(365))
        n_weekday = 365 - n_weekend

        self.assertEqual(int((daily[:, 0] > 0).sum()), n_weekday)
        self.assertEqual(int((daily[:, 47] > 0).sum()), n_weekend)
        # 2025-01-01 is a Wednesday → weekday shape (spike at interval 0).
        self.assertGreater(daily[0, 0], 0.0)
        self.assertEqual(daily[0, 47], 0.0)
        self.assertAlmostEqual(result.achieved_energy_mwh, 365.0, places=6)


class RequireEnergyConservedTests(SimpleTestCase):
    def _result(self, pct):
        return AnnualTraceResult(
            trace=np.zeros(INTERVALS_PER_DAY), year=2025, n_intervals=INTERVALS_PER_DAY,
            target_energy_mwh=100.0, achieved_energy_mwh=100.0, integral_check_pct=pct,
        )

    def test_passes_through_a_conserved_result(self):
        ok = self._result(ENERGY_CONSERVATION_TOLERANCE_PCT / 2)
        self.assertIs(require_energy_conserved(ok), ok)

    def test_raises_on_a_result_that_failed_the_integral_check(self):
        with self.assertRaises(TraceSynthesisError):
            require_energy_conserved(self._result(ENERGY_CONSERVATION_TOLERANCE_PCT * 10))


class ApplyManagedChargingLeverTests(SimpleTestCase):
    def test_conserves_each_days_total_energy(self):
        rng = np.random.default_rng(0)
        trace = rng.uniform(1.0, 5.0, size=3 * INTERVALS_PER_DAY)
        shifted = apply_managed_charging_lever(trace)
        before = trace.reshape(-1, INTERVALS_PER_DAY).sum(axis=1)
        after = shifted.reshape(-1, INTERVALS_PER_DAY).sum(axis=1)
        self.assertTrue(np.allclose(before, after))

    def test_moves_energy_from_on_peak_into_the_off_peak_window(self):
        trace = np.full(INTERVALS_PER_DAY, 1.0)  # one flat day
        shifted = apply_managed_charging_lever(trace, offpeak_start_interval=0, offpeak_end_interval=14, shift_fraction=0.5)
        # 34 on-peak intervals halved to 0.5; 17 units spread over 14 off-peak intervals.
        self.assertTrue(np.allclose(shifted[14:], 0.5))
        self.assertTrue(np.allclose(shifted[:14], 1.0 + 17.0 / 14.0))
        self.assertAlmostEqual(shifted.sum(), INTERVALS_PER_DAY)

    def test_shift_fraction_zero_is_a_no_op(self):
        trace = np.linspace(1.0, 10.0, 2 * INTERVALS_PER_DAY)
        self.assertTrue(np.allclose(apply_managed_charging_lever(trace, shift_fraction=0.0), trace))

    def test_rejects_non_whole_day_trace(self):
        with self.assertRaises(TraceSynthesisError):
            apply_managed_charging_lever(np.ones(INTERVALS_PER_DAY + 3))

    def test_rejects_invalid_window_bounds(self):
        day = np.ones(INTERVALS_PER_DAY)
        with self.assertRaises(TraceSynthesisError):
            apply_managed_charging_lever(day, offpeak_start_interval=14, offpeak_end_interval=14)
        with self.assertRaises(TraceSynthesisError):
            apply_managed_charging_lever(day, offpeak_start_interval=0, offpeak_end_interval=INTERVALS_PER_DAY + 1)

    def test_rejects_out_of_range_shift_fraction(self):
        day = np.ones(INTERVALS_PER_DAY)
        with self.assertRaises(TraceSynthesisError):
            apply_managed_charging_lever(day, shift_fraction=1.5)
