# powermatchui/tests/test_ev_net_of_esoo.py
"""
The "net of ESOO's own EV load" option on the EV scenario builder/comparison:
base - EV already in the ESOO base + scenario EV, instead of base + scenario EV.
"""
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
from django.test import SimpleTestCase, TestCase

from powermatchui.utils import iasr_ev_energy
from powermatchui.utils.esoo_embedded_ev import (
    EmbeddedEv,
    EmbeddedEvNotAvailableError,
    parse_esoo_base,
    resolve_embedded_ev,
)
from powermatchui.utils.ev_trace_synthesis import ChargingTypeProfile
from powermatchui.utils.time_alignment import ESOO_TRACE_CLOCK_MARKER
from powermatchui.views import ev_scenario_views
from siren_web.models import Scenarios

ESOO_DESCRIPTION = (
    f"Auto-built from WEM ESOO 2026 (expected, POE10) demand forecast for 2035 (FR-G1-01; {ESOO_TRACE_CLOCK_MARKER})."
)
N = 17520


class ParseEsooBaseTests(SimpleTestCase):
    def test_reads_vintage_scenario_and_year_from_the_builders_description(self):
        self.assertEqual(parse_esoo_base(ESOO_DESCRIPTION), dict(vintage=2026, scenario='expected', forecast_year=2035))

    def test_non_esoo_description_is_none(self):
        self.assertIsNone(parse_esoo_base('Hand-made baseline'))
        self.assertIsNone(parse_esoo_base(''))


class ResolveEmbeddedEvTests(SimpleTestCase):
    def test_override_wins_and_is_not_flagged_as_an_assumption(self):
        emb = resolve_embedded_ev('anything', 2035, override_gwh=1500.0)
        self.assertEqual(emb.energy_mwh, 1_500_000.0)
        self.assertFalse(emb.is_assumption)

    def test_negative_override_is_rejected(self):
        with self.assertRaises(EmbeddedEvNotAvailableError):
            resolve_embedded_ev(ESOO_DESCRIPTION, 2035, override_gwh=-1.0)

    def test_non_esoo_base_without_override_asks_for_a_figure(self):
        with self.assertRaises(EmbeddedEvNotAvailableError) as ctx:
            resolve_embedded_ev('Hand-made baseline', 2035)
        self.assertIn('Enter that figure', str(ctx.exception))

    def _resolve_with_workbook(self, description, year=2035, totals=None):
        doc = SimpleNamespace(local_file_path='2025/wb.xlsx', ev_vintage=SimpleNamespace(version='2025'))
        totals = totals if totals is not None else {2035: 1993.8, 2034: 1588.0}
        seen = []

        def fake_totals(path, mtime, trajectory):
            seen.append(trajectory)
            return totals

        fake_path = mock.Mock(spec=Path)
        fake_path.stat.return_value = SimpleNamespace(st_mtime=1.0)
        fake_path.__str__ = lambda self: 'wb.xlsx'
        with mock.patch.object(iasr_ev_energy, '_iasr_workbooks', return_value=[(doc, fake_path)]), \
                mock.patch.object(iasr_ev_energy, '_iasr_wem_gwh', side_effect=fake_totals):
            return resolve_embedded_ev(description, year), seen

    def test_expected_maps_to_step_change_and_is_flagged_as_an_assumption(self):
        emb, seen = self._resolve_with_workbook(ESOO_DESCRIPTION)
        self.assertEqual(seen, ['Step Change'])
        self.assertAlmostEqual(emb.energy_mwh, 1_993_800.0)
        self.assertTrue(emb.is_assumption)
        self.assertIn('WEM', emb.source)

    def test_low_and_high_map_to_the_other_trajectories(self):
        for scenario, trajectory in (('low', 'Slower Growth'), ('high', 'Accelerated Transition')):
            _, seen = self._resolve_with_workbook(ESOO_DESCRIPTION.replace('expected', scenario))
            self.assertEqual(seen, [trajectory])

    def test_year_missing_from_the_workbook_asks_for_a_figure(self):
        with self.assertRaises(EmbeddedEvNotAvailableError):
            self._resolve_with_workbook(ESOO_DESCRIPTION, year=2060)

    def test_no_registered_workbook_asks_for_a_figure(self):
        with mock.patch.object(iasr_ev_energy, '_iasr_workbooks', return_value=[]):
            with self.assertRaises(EmbeddedEvNotAvailableError):
                resolve_embedded_ev(ESOO_DESCRIPTION, 2035)


def _flat_profile(mode, share, hour_peak):
    shape = np.zeros(48)
    shape[hour_peak * 2] = 1.0
    return ChargingTypeProfile(
        charging_type_label=f'{mode} test', charging_mode=mode, share_of_charging=share,
        weekday_shape=shape.tolist(), weekend_shape=shape.tolist(),
    )


class EmbeddedEvTraceTests(SimpleTestCase):
    def test_mix_is_share_weighted_and_conserves_energy(self):
        profiles = [_flat_profile('unmanaged', 0.7, 18), _flat_profile('managed', 0.3, 2)]
        with mock.patch.object(ev_scenario_views, '_charging_profiles', return_value=profiles):
            trace = ev_scenario_views._embedded_ev_trace(1_000_000.0, 2035)
            unmanaged, _ = ev_scenario_views._synthesise_trace(1_000_000.0, 2035, 'unmanaged', profiles)
            managed, _ = ev_scenario_views._synthesise_trace(1_000_000.0, 2035, 'managed', profiles)
        self.assertEqual(trace.size, N)
        self.assertAlmostEqual(trace.sum() * 0.5, 1_000_000.0, delta=1.0)
        np.testing.assert_allclose(trace, 0.7 * unmanaged + 0.3 * managed)


class NetOfEsooBuildTests(TestCase):
    def _run_build(self, ev_mwh_per_interval, embedded_mwh, base_description, **kwargs):
        base = Scenarios.objects.create(title='ESOO 2026 expected POE10 2035', interval_minutes=30,
                                        description=base_description)
        ev_record = SimpleNamespace(annual_energy_mwh=ev_mwh_per_interval * N * 0.5, integral_check_pct=0.0)
        embedded = EmbeddedEv(energy_mwh=embedded_mwh, source='IASR test source', is_assumption=True)
        with mock.patch.object(ev_scenario_views, '_get_or_build_ev_load_trace', return_value=ev_record), \
                mock.patch.object(ev_scenario_views, 'load_trace', return_value=np.full(N, ev_mwh_per_interval)), \
                mock.patch.object(ev_scenario_views, '_base_trace', return_value=np.full(N, 3000.0)), \
                mock.patch.object(ev_scenario_views, 'resolve_embedded_ev', return_value=embedded), \
                mock.patch.object(ev_scenario_views, '_embedded_ev_trace', return_value=np.full(N, embedded_mwh / (N * 0.5))), \
                mock.patch.object(ev_scenario_views, 'clear_facility_trace'), \
                mock.patch.object(ev_scenario_views, 'set_facility_trace') as set_trace:
            result = ev_scenario_views.build_scenario_from_ev(base, 'medium', 2035, 'unmanaged', **kwargs)
        return result, set_trace

    def test_net_option_removes_embedded_ev_before_adding_the_scenarios(self):
        # scenario EV 400 MW flat, embedded EV 200 MW flat -> net +200 MW on a 3,000 MW base
        embedded_mwh = 200.0 * N * 0.5
        result, set_trace = self._run_build(400.0, embedded_mwh, ESOO_DESCRIPTION, net_of_esoo_ev=True)
        np.testing.assert_allclose(set_trace.call_args.args[2], 3200.0)
        self.assertTrue(result.net_of_esoo_ev)
        self.assertAlmostEqual(result.esoo_ev_energy_mwh, embedded_mwh)
        self.assertEqual(result.esoo_ev_source, 'IASR test source')
        self.assertIn(' + EV net medium 2035', result.title)
        self.assertIn('net of ESOO', result.scenario.description)
        self.assertTrue(any('working hypothesis' in n for n in result.notes))

    def test_without_the_option_the_ev_load_is_simply_added(self):
        result, set_trace = self._run_build(400.0, 200.0 * N * 0.5, ESOO_DESCRIPTION)
        np.testing.assert_allclose(set_trace.call_args.args[2], 3400.0)
        self.assertFalse(result.net_of_esoo_ev)
        self.assertNotIn('net', result.title.split(' + EV ')[-1].split()[0:1])

    def test_scenario_smaller_than_the_embedded_ev_warns_that_demand_falls(self):
        result, set_trace = self._run_build(100.0, 200.0 * N * 0.5, ESOO_DESCRIPTION, net_of_esoo_ev=True)
        np.testing.assert_allclose(set_trace.call_args.args[2], 2900.0)
        self.assertTrue(any('lower than the EV load already' in n for n in result.notes))

    def test_net_and_gross_builds_get_distinct_scenario_titles(self):
        net, _ = self._run_build(400.0, 100.0 * N * 0.5, ESOO_DESCRIPTION, net_of_esoo_ev=True)
        Scenarios.objects.filter(title='ESOO 2026 expected POE10 2035').delete()
        gross, _ = self._run_build(400.0, 100.0 * N * 0.5, ESOO_DESCRIPTION)
        self.assertNotEqual(net.title, gross.title)


class NetOfEsooCompareTests(TestCase):
    def test_comparison_is_against_the_published_base_with_net_ev_energy(self):
        base = Scenarios.objects.create(title='ESOO base', interval_minutes=30, description=ESOO_DESCRIPTION)
        embedded = EmbeddedEv(energy_mwh=100.0 * N * 0.5, source='IASR test source', is_assumption=True)
        ev_by_scenario = {'low': 50.0, 'medium': 100.0, 'high': 300.0}  # MW flat; embedded is 100 MW flat
        records = {s: SimpleNamespace(annual_energy_mwh=mw * N * 0.5, integral_check_pct=0.0) for s, mw in ev_by_scenario.items()}
        current = {}

        def fake_get_or_build(scenario, year, mode):
            current['scenario'] = scenario
            return records[scenario]

        with mock.patch.object(ev_scenario_views, '_base_trace', return_value=np.full(N, 3000.0)), \
                mock.patch.object(ev_scenario_views, '_net_ev_adjustment', return_value=(np.full(N, 100.0), embedded)), \
                mock.patch.object(ev_scenario_views, '_get_or_build_ev_load_trace', side_effect=fake_get_or_build), \
                mock.patch.object(ev_scenario_views, 'load_trace', side_effect=lambda rec: np.full(N, rec.annual_energy_mwh / (N * 0.5))):
            report, meta, unavailable, emb = ev_scenario_views.compare_ev_sensitivity(
                base, 2035, 'unmanaged', net_of_esoo_ev=True)

        self.assertIs(emb, embedded)
        self.assertEqual(unavailable, [])
        by_scenario = {r.csiro_scenario: r for r in report.rows}
        # net = 3000 + (EV - 100): 2950 / 3000 / 3200 against the published 3000 base
        self.assertAlmostEqual(by_scenario['low'].net_peak_mw, 2950.0)
        self.assertAlmostEqual(by_scenario['low'].peak_delta_mw, -50.0)
        self.assertAlmostEqual(by_scenario['medium'].peak_delta_mw, 0.0)
        self.assertAlmostEqual(by_scenario['high'].peak_delta_mw, 200.0)
        self.assertAlmostEqual(by_scenario['high'].ev_annual_energy_mwh, 200.0 * N * 0.5)  # net EV energy

    def test_without_the_option_nothing_is_removed(self):
        base = Scenarios.objects.create(title='ESOO base', interval_minutes=30, description=ESOO_DESCRIPTION)
        rec = SimpleNamespace(annual_energy_mwh=100.0 * N * 0.5, integral_check_pct=0.0)
        with mock.patch.object(ev_scenario_views, '_base_trace', return_value=np.full(N, 3000.0)), \
                mock.patch.object(ev_scenario_views, '_get_or_build_ev_load_trace', return_value=rec), \
                mock.patch.object(ev_scenario_views, 'load_trace', return_value=np.full(N, 100.0)):
            report, _, _, emb = ev_scenario_views.compare_ev_sensitivity(base, 2035, 'unmanaged')
        self.assertIsNone(emb)
        self.assertAlmostEqual(report.rows[0].peak_delta_mw, 100.0)


class NetOfEsooPagesTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        self.client.force_login(get_user_model().objects.create_user('ev_analyst', password='pw'))
        self.base = Scenarios.objects.create(title='ESOO base', interval_minutes=30, description=ESOO_DESCRIPTION)

    def test_selector_shows_the_option_and_keeps_it_ticked_after_a_failed_post(self):
        from django.urls import reverse
        r = self.client.post(reverse('powermatchui:ev_scenario_selector'), {
            'base_scenario': self.base.pk, 'csiro_scenario': 'medium', 'charging_mode': 'unmanaged',
            'forecast_year': '2035', 'net_of_esoo_ev': 'on', 'esoo_ev_gwh': 'abc',
        })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Net of ESOO's own EV load")
        self.assertContains(r, 'name="net_of_esoo_ev"')
        self.assertContains(r, 'checked')
        self.assertContains(r, 'a number for the EV energy')

    def test_selector_reports_a_non_esoo_base_that_needs_a_manual_figure(self):
        from django.urls import reverse
        plain = Scenarios.objects.create(title='Hand-made', interval_minutes=30, description='')
        ev_record = SimpleNamespace(annual_energy_mwh=1.0, integral_check_pct=0.0)
        with mock.patch.object(ev_scenario_views, '_get_or_build_ev_load_trace', return_value=ev_record), \
                mock.patch.object(ev_scenario_views, 'load_trace', return_value=np.zeros(48)), \
                mock.patch.object(ev_scenario_views, '_base_trace', return_value=np.ones(48)):
            r = self.client.post(reverse('powermatchui:ev_scenario_selector'), {
                'base_scenario': plain.pk, 'csiro_scenario': 'medium', 'charging_mode': 'unmanaged',
                'forecast_year': '2035', 'net_of_esoo_ev': 'on',
            })
        self.assertContains(r, 'Enter that figure')

    def test_compare_page_shows_the_net_note_and_signed_deltas(self):
        from django.urls import reverse
        from powermatchui.utils.ev_sensitivity_comparison import compare_scenarios
        base = np.full(N, 3000.0)
        report = compare_scenarios(base, {'low': np.full(N, -50.0), 'high': np.full(N, 200.0)}, 2035, 'unmanaged')
        embedded = EmbeddedEv(energy_mwh=100.0 * N * 0.5, source='IASR test source', is_assumption=True)
        with mock.patch.object(ev_scenario_views, 'compare_ev_sensitivity', return_value=(report, {}, [], embedded)):
            r = self.client.get(reverse('powermatchui:ev_scenario_compare'), {
                'base_scenario': self.base.pk, 'charging_mode': 'unmanaged', 'forecast_year': '2035',
                'net_of_esoo_ev': 'on',
            })
        self.assertContains(r, "Net of ESOO's own EV load.")
        self.assertContains(r, 'IASR test source')
        self.assertContains(r, '-50')      # negative delta shown without a stray '+'
        self.assertNotContains(r, '+-50')
        self.assertContains(r, '+200')
