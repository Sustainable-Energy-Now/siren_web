# powermatchui/tests/test_ev_scenario_views.py
"""
Regression test for powermatchui.views.ev_scenario_views.build_scenario_from_ev.

The trace read/write helpers are patched out: this exercises the orchestration
(derived Scenario/Load facility creation, summing the base and EV traces,
persisting the sum, and the result object) -- not EV trace synthesis. It exists
because the SupplyFactorMatrix conversion left a stale `len(records)` in the
result construction, which raised NameError after everything had already been
written, and nothing covered this path.
"""
from types import SimpleNamespace
from unittest import mock

import numpy as np
from django.test import TestCase

from powermatchui.utils.time_alignment import ESOO_TRACE_CLOCK_MARKER
from powermatchui.views import ev_scenario_views
from siren_web.models import Scenarios, facilities

N_INTERVALS = 17520


class BuildScenarioFromEvTests(TestCase):
    def test_builds_derived_scenario_and_persists_summed_trace(self):
        base = Scenarios.objects.create(title='Base demand', interval_minutes=30)
        base_trace = np.full(N_INTERVALS, 2000.0)
        ev_trace = np.full(N_INTERVALS, 100.0)
        ev_record = SimpleNamespace(annual_energy_mwh=876000.0, integral_check_pct=0.001)

        with mock.patch.object(ev_scenario_views, '_get_or_build_ev_load_trace', return_value=ev_record), \
                mock.patch.object(ev_scenario_views, 'load_trace', return_value=ev_trace), \
                mock.patch.object(ev_scenario_views, '_base_trace', return_value=base_trace), \
                mock.patch.object(ev_scenario_views, 'clear_facility_trace') as clear_trace, \
                mock.patch.object(ev_scenario_views, 'set_facility_trace') as set_trace:
            result = ev_scenario_views.build_scenario_from_ev(base, 'medium', 2030, 'unmanaged')

        self.assertEqual(result.n_rows, N_INTERVALS)
        self.assertEqual(result.title, 'Base demand + EV medium 2030')
        self.assertEqual(result.ev_annual_energy_mwh, 876000.0)
        self.assertEqual(result.notes, [])
        self.assertTrue(facilities.objects.filter(pk=result.facility.pk).exists())

        clear_trace.assert_called_once_with(2030, result.facility.idfacilities)
        year, facility_id, saved = set_trace.call_args.args
        self.assertEqual((year, facility_id), (2030, result.facility.idfacilities))
        np.testing.assert_allclose(saved, 2100.0)

    def test_integral_check_note_when_over_tolerance(self):
        base = Scenarios.objects.create(title='Base demand', interval_minutes=30)
        ev_record = SimpleNamespace(annual_energy_mwh=1.0, integral_check_pct=0.5)

        with mock.patch.object(ev_scenario_views, '_get_or_build_ev_load_trace', return_value=ev_record), \
                mock.patch.object(ev_scenario_views, 'load_trace', return_value=np.zeros(48)), \
                mock.patch.object(ev_scenario_views, '_base_trace', return_value=np.ones(48)), \
                mock.patch.object(ev_scenario_views, 'clear_facility_trace'), \
                mock.patch.object(ev_scenario_views, 'set_facility_trace'):
            result = ev_scenario_views.build_scenario_from_ev(base, 'low', 2030, 'unmanaged')

        self.assertEqual(len(result.notes), 1)
        self.assertIn('exceeds FR-09', result.notes[0])


class BaseTraceClockGuardTests(TestCase):
    def test_esoo_base_built_before_the_clock_fix_is_refused(self):
        old = Scenarios.objects.create(
            title='Old ESOO', interval_minutes=30,
            description='Auto-built from WEM ESOO 2023 (expected, POE10) demand forecast for 2030 (FR-G1-01).')
        with self.assertRaises(ev_scenario_views.BaseTraceNotFoundError) as ctx:
            ev_scenario_views._base_trace(old, 2030)
        self.assertIn('Rebuild it', str(ctx.exception))

    def test_esoo_base_with_the_marker_gets_past_the_guard(self):
        new = Scenarios.objects.create(
            title='New ESOO', interval_minutes=30,
            description=f'Auto-built ... (FR-G1-01; {ESOO_TRACE_CLOCK_MARKER}).')
        with self.assertRaises(ev_scenario_views.BaseTraceNotFoundError) as ctx:
            ev_scenario_views._base_trace(new, 2030)
        self.assertIn('has no Load supplyfactors', str(ctx.exception))  # no trace yet, but not the clock error
