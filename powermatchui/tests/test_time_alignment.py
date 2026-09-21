# powermatchui/tests/test_time_alignment.py
"""UTC -> AWST and reference-year -> target-year alignment of half-hourly traces."""
import calendar

import numpy as np
from django.test import SimpleTestCase

from powermatchui.utils.time_alignment import (
    align_reference_to_target,
    align_weekdays,
    utc_to_awst,
)


def _weekday_coded_year(year):
    """Each day filled with its own weekday number (Mon=0)."""
    days = 366 if calendar.isleap(year) else 365
    return np.repeat([calendar.weekday(year, 1, 1) + d for d in range(days)], 48) % 7


class UtcToAwstTests(SimpleTestCase):
    def test_moves_a_1030_utc_peak_to_1830_awst(self):
        utc = np.zeros(365 * 48)
        utc[10 * 2 + 1::48] = 1.0  # 10:30 UTC every day (index 21 of the day)
        local = utc_to_awst(utc)
        self.assertEqual(set(np.flatnonzero(local[:48])), {37})  # 18:30 local
        self.assertEqual(local.size, utc.size)

    def test_first_local_intervals_wrap_from_the_end_of_the_utc_year(self):
        utc = np.arange(96, dtype=float)
        local = utc_to_awst(utc)
        np.testing.assert_array_equal(local[:16], utc[-16:])
        np.testing.assert_array_equal(local[16:], utc[:-16])


class AlignWeekdaysTests(SimpleTestCase):
    def test_result_has_target_years_weekday_pattern(self):
        ref, target = 2025, 2035  # Wed vs Mon start, both 365 days
        aligned, notes = align_weekdays(_weekday_coded_year(ref), ref, target)
        self.assertEqual(notes, [])
        # Every day matches except the last 5, which wrap round from the start of
        # the reference year (a 365-day year is 52 weeks + 1 day, so the seam is off by a weekday).
        seam = 5 * 48
        np.testing.assert_array_equal(aligned[:-seam], _weekday_coded_year(target)[:-seam])

    def test_same_year_is_unchanged(self):
        trace = np.arange(365 * 48, dtype=float)
        aligned, notes = align_weekdays(trace, 2025, 2025)
        np.testing.assert_array_equal(aligned, trace)
        self.assertEqual(notes, [])

    def test_leap_vs_non_leap_is_left_alone_with_a_note(self):
        trace = np.arange(366 * 48, dtype=float)  # 2024 is a leap year
        aligned, notes = align_weekdays(trace, 2024, 2035)
        np.testing.assert_array_equal(aligned, trace)
        self.assertEqual(len(notes), 1)
        self.assertIn('Weekday alignment skipped', notes[0])

    def test_align_reference_to_target_applies_both_shifts(self):
        ref, target = 2025, 2035
        utc = np.zeros(365 * 48)
        utc[21::48] = 1.0  # 10:30 UTC daily
        aligned, _ = align_reference_to_target(utc, ref, target)
        self.assertEqual(set(np.flatnonzero(aligned[:48])), {37})
