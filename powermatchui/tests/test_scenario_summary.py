# powermatchui/tests/test_scenario_summary.py
"""Scenario summary: the statistics module, and the read-only page."""
import calendar
from datetime import date, datetime

import numpy as np
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from powermatchui.utils.scenario_summary import (
    LoadTraceError,
    compare_stats,
    describe_provenance,
    infer_resolution,
    sum_traces,
    summarise_load_trace,
)
from siren_web.models import Scenarios, ScenariosFacilities, Technologies, facilities
from siren_web.services.supply_matrix import set_facility_trace


def _year_trace(year, per_day, fn):
    """A full-year trace where fn(day_index, interval_of_day) gives the value."""
    days = 366 if calendar.isleap(year) else 365
    return np.array([[fn(d, i) for i in range(per_day)] for d in range(days)], dtype=float).ravel()


class InferResolutionTests(SimpleTestCase):
    def test_hourly_and_half_hourly(self):
        self.assertEqual(infer_resolution(np.ones(8760), 2035), (8760, 24))
        self.assertEqual(infer_resolution(np.ones(17520), 2035), (17520, 48))
        self.assertEqual(infer_resolution(np.ones(8784), 2028), (8784, 24))  # leap year

    def test_trailing_nan_padding_is_ignored(self):
        padded = np.concatenate([np.ones(8760), np.full(8760, np.nan)])  # hourly row in a half-hourly matrix
        self.assertEqual(infer_resolution(padded, 2035), (8760, 24))

    def test_partial_year_is_rejected(self):
        with self.assertRaises(LoadTraceError):
            infer_resolution(np.ones(5000), 2035)

    def test_all_nan_is_rejected(self):
        with self.assertRaises(LoadTraceError):
            infer_resolution(np.full(8760, np.nan), 2035)


class SummariseLoadTraceTests(SimpleTestCase):
    def test_flat_half_hourly_year(self):
        s = summarise_load_trace(np.full(17520, 1000.0), 2035)
        self.assertAlmostEqual(s.annual_energy_gwh, 1000.0 * 8760 / 1000)  # 8,760 GWh
        self.assertAlmostEqual(s.average_mw, 1000.0)
        self.assertAlmostEqual(s.load_factor, 1.0)
        self.assertEqual(s.intervals_per_day, 48)
        self.assertEqual(s.time_labels[:3], ['00:00', '00:30', '01:00'])
        self.assertAlmostEqual(s.hours_within_10pct_of_peak, 8760.0)
        self.assertEqual(len(s.duration_curve_mw), 101)

    def test_peak_and_minimum_with_their_times(self):
        trace = _year_trace(2035, 48, lambda d, i: 2000.0)
        trace[14 * 48 + 37] = 6000.0   # 15 Jan, 18:30
        trace[300 * 48 + 22] = -90.0   # day 300, 11:00
        s = summarise_load_trace(trace, 2035)
        self.assertEqual(s.peak_mw, 6000.0)
        self.assertEqual(s.peak_time, datetime(2035, 1, 15, 18, 30))
        self.assertEqual(s.peak_day, date(2035, 1, 15))
        self.assertEqual(s.minimum_mw, -90.0)
        self.assertEqual(s.minimum_time, datetime(2035, 1, 1, 11, 0) + (datetime(2035, 10, 28) - datetime(2035, 1, 1)))
        self.assertEqual(len(s.peak_day_profile_mw), 48)
        self.assertEqual(s.peak_day_profile_mw[37], 6000.0)

    def test_hourly_year_uses_hour_energy(self):
        s = summarise_load_trace(np.full(8760, 500.0), 2035)
        self.assertEqual(s.intervals_per_day, 24)
        self.assertAlmostEqual(s.annual_energy_gwh, 500.0 * 8760 / 1000)

    def test_monthly_energy_sums_to_the_annual_total(self):
        s = summarise_load_trace(_year_trace(2035, 48, lambda d, i: 1000 + d), 2035)
        self.assertEqual(len(s.monthly_energy_gwh), 12)
        self.assertAlmostEqual(sum(s.monthly_energy_gwh), s.annual_energy_gwh)
        self.assertAlmostEqual(s.monthly_energy_gwh[1] / s.monthly_energy_gwh[0], 28 / 31, delta=0.2)  # Feb shorter than Jan

    def test_mean_daily_profile(self):
        s = summarise_load_trace(_year_trace(2035, 48, lambda d, i: 100.0 + i), 2035)
        self.assertEqual(s.mean_daily_profile_mw, [100.0 + i for i in range(48)])

    def test_duration_curve_is_descending_from_peak_to_minimum(self):
        s = summarise_load_trace(_year_trace(2035, 48, lambda d, i: float(d * 48 + i)), 2035)
        curve = s.duration_curve_mw
        self.assertEqual(curve[0], s.peak_mw)
        self.assertEqual(curve[-1], s.minimum_mw)
        self.assertTrue(all(x >= y for x, y in zip(curve, curve[1:])))

    def test_missing_values_are_counted_and_excluded(self):
        trace = np.full(17520, 1000.0)
        trace[100:110] = np.nan
        s = summarise_load_trace(trace, 2035)
        self.assertEqual(s.n_missing, 10)
        self.assertAlmostEqual(s.average_mw, 1000.0)

    def test_negative_only_peak_gives_zero_load_factor(self):
        s = summarise_load_trace(np.full(8760, -5.0), 2035)
        self.assertEqual(s.load_factor, 0.0)


class SumAndCompareTests(SimpleTestCase):
    def test_sum_traces_treats_nan_as_zero_only_where_another_has_data(self):
        a = np.array([1.0, np.nan, np.nan])
        b = np.array([2.0, 3.0, np.nan])
        total = sum_traces([a, b])
        self.assertEqual(total[0], 3.0)
        self.assertEqual(total[1], 3.0)
        self.assertTrue(np.isnan(total[2]))

    def test_compare_rows_show_signed_differences(self):
        a = summarise_load_trace(np.full(17520, 1000.0), 2035)
        b = summarise_load_trace(np.full(17520, 900.0), 2035)
        rows = {r['label']: r for r in compare_stats(a, b)}
        self.assertEqual(rows['Peak (MW)']['delta'], '-100')
        self.assertAlmostEqual(rows['Peak (MW)']['delta_pct'], -10.0)
        self.assertEqual(rows['Average load (MW)']['a'], '1,000')
        self.assertEqual(rows['Annual energy (GWh)']['delta'], '-876.0')
        self.assertIn('Peak time', rows)


class ProvenanceTests(SimpleTestCase):
    def test_esoo_built(self):
        p = dict(describe_provenance(
            'Auto-built from WEM ESOO 2026 (expected, POE10) demand forecast for 2035 (FR-G1-01; AWST clock, target-year weekdays).',
            30, 2025))
        self.assertEqual(p['Built by'], 'ESOO Demand Scenario (FR-G1-01)')
        self.assertEqual(p['ESOO forecast'], 'WEM ESOO 2026, expected scenario, POE10, 2035')
        self.assertEqual(p['Shape prior (SCADA year)'], '2025')
        self.assertEqual(p['Dispatch interval'], '30 minutes')

    def test_ev_built_net(self):
        p = dict(describe_provenance(
            "Auto-built: ESOO 2026 expected POE10 2035 base demand, less the 1,994 GWh of EV load already in it, "
            "plus CSIRO medium EV load (unmanaged) for 2035 (FR-11, net of ESOO's EV; source).", 30, None))
        self.assertEqual(p['Built by'], 'EV Load Scenario (FR-11)')
        self.assertEqual(p['Base demand scenario'], 'ESOO 2026 expected POE10 2035')
        self.assertEqual(p['EV scenario'], 'medium (unmanaged charging), 2035')
        self.assertIn('net of the 1,994 GWh', p['EV treatment'])

    def test_ev_built_gross(self):
        p = dict(describe_provenance(
            'Auto-built: Base demand base demand + CSIRO high EV load (managed) for 2030 (FR-11).', 30, None))
        self.assertEqual(p['EV treatment'], 'EV load added on top of the base')

    def test_hand_made_scenario_shows_its_description(self):
        p = dict(describe_provenance('My baseline', 60, None))
        self.assertEqual(p['Description'], 'My baseline')
        self.assertEqual(p['Dispatch interval'], '60 minutes')


class ScenarioSummaryPageTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user('summary_user', password='pw'))
        self.load_tech = Technologies.objects.create(
            technology_name='Load', technology_signature='LOAD', category='Load', renewable=0, dispatchable=0)
        self.wind_tech = Technologies.objects.create(
            technology_name='Wind', technology_signature='WIND', category='Wind', renewable=1, dispatchable=0)

    def _scenario(self, title, mw, year=2035, description=''):
        scenario = Scenarios.objects.create(title=title, interval_minutes=30, description=description)
        fac = facilities.objects.create(
            facility_name=f'{title} load', facility_code=title[:20], idtechnologies=self.load_tech,
            active=True, existing=True, capacity=0)
        ScenariosFacilities.objects.create(idscenarios=scenario, idfacilities=fac)
        set_facility_trace(year, fac.idfacilities, _year_trace(year, 48, lambda d, i: mw + (500 if i == 37 else 0)))
        return scenario

    def test_lists_only_scenarios_with_a_load_facility(self):
        a = self._scenario('With load', 2000.0)
        gen = Scenarios.objects.create(title='Generation only', interval_minutes=30)
        wind = facilities.objects.create(
            facility_name='Some wind', facility_code='WIND1', idtechnologies=self.wind_tech, active=True, existing=True, capacity=10)
        ScenariosFacilities.objects.create(idscenarios=gen, idfacilities=wind)
        r = self.client.get(reverse('powermatchui:scenario_summary'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'With load')
        self.assertNotContains(r, 'Generation only')

    def test_summary_shows_key_statistics_and_provenance(self):
        s = self._scenario(
            'ESOO test', 2000.0,
            description='Auto-built from WEM ESOO 2026 (expected, POE10) demand forecast for 2035 (FR-G1-01).')
        r = self.client.get(reverse('powermatchui:scenario_summary'), {'scenario': s.pk, 'year': 2035})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Annual energy')
        self.assertContains(r, '2,500')                       # peak 2000 + 500 at 18:30
        self.assertContains(r, '18:30')
        self.assertContains(r, 'WEM ESOO 2026, expected scenario, POE10, 2035')
        self.assertContains(r, 'summary_profile')             # charts rendered
        self.assertContains(r, 'has not been run through Powermatch dispatch')

    def test_year_defaults_to_the_latest_available(self):
        s = self._scenario('Two years', 2000.0, year=2030)
        fac = facilities.objects.get(facility_name='Two years load')
        set_facility_trace(2035, fac.idfacilities, np.full(17520, 3000.0))
        r = self.client.get(reverse('powermatchui:scenario_summary'), {'scenario': s.pk, 'year': '1999'})
        self.assertEqual(r.context['selected_year'], 2035)
        self.assertEqual(r.context['years'], [2030, 2035])

    def test_comparison_table_and_overlay(self):
        a = self._scenario('Base', 2000.0)
        b = self._scenario('Higher', 2200.0)
        r = self.client.get(reverse('powermatchui:scenario_summary'), {'scenario': a.pk, 'compare': b.pk, 'year': 2035})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Comparison with Higher')
        rows = {row['label']: row for row in r.context['comparison']}
        self.assertEqual(rows['Peak (MW)']['delta'], '+200')

    def test_comparison_missing_the_year_is_reported_not_fatal(self):
        a = self._scenario('Base', 2000.0, year=2035)
        b = self._scenario('Other year', 2200.0, year=2030)
        r = self.client.get(reverse('powermatchui:scenario_summary'), {'scenario': a.pk, 'compare': b.pk, 'year': 2035})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'has no Load trace for 2035')
        self.assertContains(r, 'Annual energy')      # the main summary still shows

    def test_scenario_without_a_trace_gets_a_message(self):
        scenario = Scenarios.objects.create(title='Empty', interval_minutes=30)
        fac = facilities.objects.create(
            facility_name='Empty load', facility_code='EMPTY', idtechnologies=self.load_tech, active=True, existing=True, capacity=0)
        ScenariosFacilities.objects.create(idscenarios=scenario, idfacilities=fac)
        r = self.client.get(reverse('powermatchui:scenario_summary'), {'scenario': scenario.pk})
        self.assertContains(r, 'no stored Load trace')

    def test_unknown_scenario_and_garbage_params(self):
        r = self.client.get(reverse('powermatchui:scenario_summary'), {'scenario': '9999', 'year': 'abc', 'compare': 'x'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "exist or has no Load facility")

    def test_multiple_load_facilities_are_summed(self):
        s = self._scenario('Two loads', 1000.0)
        extra = facilities.objects.create(
            facility_name='Second load', facility_code='LOAD2', idtechnologies=self.load_tech, active=True, existing=True, capacity=0)
        ScenariosFacilities.objects.create(idscenarios=s, idfacilities=extra)
        set_facility_trace(2035, extra.idfacilities, np.full(17520, 250.0))
        r = self.client.get(reverse('powermatchui:scenario_summary'), {'scenario': s.pk, 'year': 2035})
        self.assertEqual(len(r.context['facility_rows']), 2)
        self.assertAlmostEqual(r.context['stats'].peak_mw, 1500.0 + 250.0)   # 1000 + 500 spike + 250

    def test_requires_login(self):
        self.client.logout()
        r = self.client.get(reverse('powermatchui:scenario_summary'))
        self.assertEqual(r.status_code, 302)
