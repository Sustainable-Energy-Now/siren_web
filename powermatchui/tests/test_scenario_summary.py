# powermatchui/tests/test_scenario_summary.py
"""Scenario summary: the statistics module, and the read-only page."""
import calendar
from datetime import date, datetime
from types import SimpleNamespace

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
from siren_web.models import Demand, EsooVintage
from siren_web.services.demand_matrix import set_demand_trace


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
    """describe_provenance reads a Demand's own structured fields directly
    (no DB access needed -- a plain SimpleNamespace duck-types the handful
    of attributes it reads)."""

    def _demand(self, **overrides):
        defaults = dict(
            parent_demand_id=None, parent_demand=None,
            esoo_vintage_id=None, esoo_vintage=None, esoo_scenario='', poe_level=None,
            csiro_scenario='', charging_mode='', net_of_esoo_ev=False,
            forecast_year=2035, reference_year=None, interval_minutes=30, description='',
        )
        defaults.update(overrides)
        return SimpleNamespace(**defaults)

    def test_esoo_built(self):
        demand = self._demand(
            esoo_vintage_id=1, esoo_vintage=SimpleNamespace(year=2026),
            esoo_scenario='expected', poe_level=10, forecast_year=2035, reference_year=2025,
        )
        p = dict(describe_provenance(demand))
        self.assertEqual(p['Built by'], 'ESOO Demand Scenario (FR-G1-01)')
        self.assertEqual(p['ESOO forecast'], 'WEM ESOO 2026, expected scenario, POE10, 2035')
        self.assertEqual(p['Shape prior (SCADA year)'], '2025')
        self.assertEqual(p['Dispatch interval'], '30 minutes')

    def test_ev_built_net(self):
        base = self._demand()
        base.name = 'ESOO 2026 expected POE10 2035'
        demand = self._demand(
            parent_demand_id=1, parent_demand=base,
            csiro_scenario='medium', charging_mode='unmanaged', forecast_year=2035,
            net_of_esoo_ev=True,
        )
        p = dict(describe_provenance(demand))
        self.assertEqual(p['Built by'], 'EV Load Scenario (FR-11)')
        self.assertEqual(p['Base demand'], 'ESOO 2026 expected POE10 2035')
        self.assertEqual(p['EV scenario'], 'medium (unmanaged charging), 2035')
        self.assertIn("net of ESOO's own EV", p['EV treatment'])

    def test_ev_built_gross(self):
        base = self._demand()
        base.name = 'Base demand'
        demand = self._demand(
            parent_demand_id=1, parent_demand=base,
            csiro_scenario='high', charging_mode='managed', forecast_year=2030,
            net_of_esoo_ev=False,
        )
        p = dict(describe_provenance(demand))
        self.assertEqual(p['EV treatment'], 'EV load added on top of the base')

    def test_hand_made_scenario_shows_its_description(self):
        demand = self._demand(description='My baseline', interval_minutes=60)
        p = dict(describe_provenance(demand))
        self.assertEqual(p['Description'], 'My baseline')
        self.assertEqual(p['Dispatch interval'], '60 minutes')


class ScenarioSummaryPageTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user('summary_user', password='pw'))

    def _demand(self, name, mw, year=2035, description='', **extra):
        demand = Demand.objects.create(
            name=name, interval_minutes=30, forecast_year=year, description=description, **extra
        )
        set_demand_trace(year, demand.iddemand, _year_trace(year, 48, lambda d, i: mw + (500 if i == 37 else 0)))
        return demand

    def test_lists_only_active_demands(self):
        self._demand('Active demand', 2000.0)
        self._demand('Inactive demand', 2000.0, is_active=False)
        r = self.client.get(reverse('powermatchui:scenario_summary'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Active demand')
        self.assertNotContains(r, 'Inactive demand')

    def test_summary_shows_key_statistics_and_provenance(self):
        vintage = EsooVintage.objects.create(year=2026, tier='modern_comparable')
        s = self._demand(
            'ESOO test', 2000.0,
            description='Auto-built from WEM ESOO 2026 (expected, POE10) demand forecast for 2035 (FR-G1-01).',
            esoo_vintage=vintage, esoo_scenario='expected', poe_level=10,
        )
        r = self.client.get(reverse('powermatchui:scenario_summary'), {'scenario': s.pk, 'year': 2035})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Annual energy')
        self.assertContains(r, '2,500')                       # peak 2000 + 500 at 18:30
        self.assertContains(r, '18:30')
        self.assertContains(r, 'WEM ESOO 2026, expected scenario, POE10, 2035')
        self.assertContains(r, 'summary_profile')             # charts rendered
        self.assertContains(r, 'has not been run through Powermatch dispatch')

    def test_year_defaults_to_the_latest_available(self):
        s = self._demand('Two years', 2000.0, year=2030)
        set_demand_trace(2035, s.iddemand, np.full(17520, 3000.0))
        r = self.client.get(reverse('powermatchui:scenario_summary'), {'scenario': s.pk, 'year': '1999'})
        self.assertEqual(r.context['selected_year'], 2035)
        self.assertEqual(r.context['years'], [2030, 2035])

    def test_comparison_table_and_overlay(self):
        a = self._demand('Base', 2000.0)
        b = self._demand('Higher', 2200.0)
        r = self.client.get(reverse('powermatchui:scenario_summary'), {'scenario': a.pk, 'compare': b.pk, 'year': 2035})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Comparison with Higher')
        rows = {row['label']: row for row in r.context['comparison']}
        self.assertEqual(rows['Peak (MW)']['delta'], '+200')

    def test_comparison_missing_the_year_is_reported_not_fatal(self):
        a = self._demand('Base', 2000.0, year=2035)
        b = self._demand('Other year', 2200.0, year=2030)
        r = self.client.get(reverse('powermatchui:scenario_summary'), {'scenario': a.pk, 'compare': b.pk, 'year': 2035})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'has no trace for 2035')
        self.assertContains(r, 'Annual energy')      # the main summary still shows

    def test_scenario_without_a_trace_gets_a_message(self):
        demand = Demand.objects.create(name='Empty', interval_minutes=30, forecast_year=2035)
        r = self.client.get(reverse('powermatchui:scenario_summary'), {'scenario': demand.pk})
        self.assertContains(r, 'has no stored trace')

    def test_unknown_scenario_and_garbage_params(self):
        r = self.client.get(reverse('powermatchui:scenario_summary'), {'scenario': '9999', 'year': 'abc', 'compare': 'x'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "That Demand doesn")  # avoid the apostrophe, which is HTML-escaped in the response

    def test_requires_login(self):
        self.client.logout()
        r = self.client.get(reverse('powermatchui:scenario_summary'))
        self.assertEqual(r.status_code, 302)
