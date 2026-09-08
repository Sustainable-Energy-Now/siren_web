# powermatchui/test_ev_sensitivity_comparison.py
"""Unit tests for the FR-12 pure comparison module
(powermatchui.utils.ev_sensitivity_comparison)."""
import numpy as np
from django.test import SimpleTestCase

from powermatchui.utils.ev_sensitivity_comparison import (
    INTERVALS_PER_DAY,
    SensitivityComparisonError,
    compare_scenarios,
)

# 2 days: a flat 900 MW base with a 1400 MW block in the evening of each day.
_EVENING = np.concatenate([np.full(36, 900.0), np.full(12, 1400.0)])
BASE_2D = np.tile(_EVENING, 2)
# EV load: small overnight bump (managed-ish), scaled per scenario.
_EV_DAY = np.concatenate([np.full(14, 20.0), np.full(34, 2.0)])
EV_2D = np.tile(_EV_DAY, 2)


class CompareScenariosTests(SimpleTestCase):
    def test_energy_peak_and_min_metrics(self):
        report = compare_scenarios(
            BASE_2D, {'low': EV_2D, 'high': EV_2D * 5}, 2030, 'managed',
        )
        self.assertEqual([r.csiro_scenario for r in report.rows], ['low', 'high'])
        low, high = report.rows

        # Energy scales linearly with the EV trace.
        self.assertAlmostEqual(high.ev_annual_energy_mwh, low.ev_annual_energy_mwh * 5, places=6)
        self.assertAlmostEqual(low.base_annual_energy_mwh, float(BASE_2D.sum() * 0.5), places=6)

        # Base peak is the evening block; EV there is tiny, so the system
        # peak does not move and the coincident EV load is small.
        self.assertEqual(low.base_peak_mw, 1400.0)
        self.assertFalse(low.peak_shifts)
        self.assertEqual(low.ev_at_base_peak_mw, 2.0)

        # Net minimum lands where base is at its floor AND the EV shape is
        # at its lowest (the 2.0 MW daytime tail here), not the overnight bump.
        self.assertEqual(low.base_min_mw, 900.0)
        self.assertEqual(low.net_min_mw, 902.0)
        self.assertEqual(low.min_delta_mw, 2.0)
        self.assertEqual(high.min_delta_mw, 10.0)

    def test_peak_can_shift_when_ev_is_large_and_daytime(self):
        # EV concentrated in an off-base-peak interval, large enough to
        # overtake the base evening peak.
        ev = np.zeros(INTERVALS_PER_DAY)
        ev[20] = 600.0
        report = compare_scenarios(BASE_2D, {'high': np.tile(ev, 2)}, 2030)
        row = report.rows[0]
        self.assertTrue(row.peak_shifts)
        self.assertEqual(row.net_peak_time, '10:00')  # interval 20 = 10:00
        self.assertEqual(row.net_peak_mw, 1500.0)

    def test_peak_day_slice_is_48_values_per_scenario(self):
        report = compare_scenarios(BASE_2D, {'low': EV_2D, 'high': EV_2D * 3}, 2030)
        self.assertEqual(len(report.peak_day_base_mw), INTERVALS_PER_DAY)
        self.assertEqual(len(report.peak_day_times), INTERVALS_PER_DAY)
        for series in report.peak_day_net_mw.values():
            self.assertEqual(len(series), INTERVALS_PER_DAY)

    def test_rejects_length_mismatch(self):
        with self.assertRaises(SensitivityComparisonError):
            compare_scenarios(BASE_2D, {'low': EV_2D[:-1]}, 2030)

    def test_rejects_non_whole_day_base(self):
        with self.assertRaises(SensitivityComparisonError):
            compare_scenarios(np.ones(100), {'low': np.ones(100)}, 2030)

    def test_rejects_empty_ev_traces(self):
        with self.assertRaises(SensitivityComparisonError):
            compare_scenarios(BASE_2D, {}, 2030)
