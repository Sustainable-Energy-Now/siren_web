# powermatchui/tests/test_iasr_ev_energy.py
"""
The EV load builder's annual-energy source: AEMO's 2025 IASR WEM trajectories
(replacing the older 2022 CSIRO postcode files).
"""
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
from django.test import SimpleTestCase, TestCase, override_settings

from powermatchui.utils import iasr_ev_energy
from powermatchui.utils.iasr_ev_energy import (
    CSIRO_TO_IASR,
    IasrDataNotAvailableError,
    iasr_wem_energy_mwh,
    scenario_energy_mwh,
)
from powermatchui.views import ev_scenario_views
from siren_web.models import EvLoadTrace


def _fake_workbook(totals_by_trajectory):
    doc = SimpleNamespace(local_file_path='2025/wb.xlsx', ev_vintage=SimpleNamespace(version='2025'))
    fake_path = mock.Mock(spec=Path)
    fake_path.stat.return_value = SimpleNamespace(st_mtime=1.0)
    fake_path.__str__ = lambda self: 'wb.xlsx'
    return (
        mock.patch.object(iasr_ev_energy, '_iasr_workbooks', return_value=[(doc, fake_path)]),
        mock.patch.object(iasr_ev_energy, '_iasr_wem_gwh', side_effect=lambda p, m, traj: totals_by_trajectory[traj]),
    )


class ScenarioEnergyTests(SimpleTestCase):
    TOTALS = {
        'Slower Growth': {2035: 1300.8},
        'Step Change': {2035: 1993.8},
        'Accelerated Transition': {2035: 3225.4},
    }

    def test_low_medium_high_map_to_the_iasr_trajectories(self):
        self.assertEqual(CSIRO_TO_IASR, {'low': 'Slower Growth', 'medium': 'Step Change', 'high': 'Accelerated Transition'})
        a, b = _fake_workbook(self.TOTALS)
        with a, b:
            got = {s: scenario_energy_mwh(s, 2035)[0] for s in ('low', 'medium', 'high')}
        self.assertEqual(got, {'low': 1_300_800.0, 'medium': 1_993_800.0, 'high': 3_225_400.0})

    def test_source_names_the_workbook_region_and_trajectory(self):
        a, b = _fake_workbook(self.TOTALS)
        with a, b:
            _, source = scenario_energy_mwh('medium', 2035)
        self.assertIn('WEM', source)
        self.assertIn('Step Change', source)
        self.assertIn('2025', source)

    def test_year_outside_the_workbook_raises(self):
        a, b = _fake_workbook(self.TOTALS)
        with a, b, self.assertRaises(IasrDataNotAvailableError) as ctx:
            iasr_wem_energy_mwh('Step Change', 2021)
        self.assertIn('2021', str(ctx.exception))

    def test_no_workbook_raises(self):
        with mock.patch.object(iasr_ev_energy, '_iasr_workbooks', return_value=[]):
            with self.assertRaises(IasrDataNotAvailableError):
                scenario_energy_mwh('low', 2035)

    def test_unknown_scenario_raises(self):
        with self.assertRaises(IasrDataNotAvailableError):
            scenario_energy_mwh('extreme', 2035)


class GetOrBuildTraceTests(TestCase):
    """_get_or_build_ev_load_trace reuses a stored trace only if it matches the IASR energy."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.settings_ctx = override_settings(EV_TRACE_DIR=self._tmp.name)
        self.settings_ctx.enable()
        self.addCleanup(self.settings_ctx.disable)

    def _store(self, energy_mwh):
        (Path(self._tmp.name) / 'medium' / 'unmanaged').mkdir(parents=True, exist_ok=True)
        rel = 'medium/unmanaged/2035.npy'
        np.save(Path(self._tmp.name) / rel, np.ones(17520))
        return EvLoadTrace.objects.create(
            csiro_scenario='medium', year=2035, charging_mode='unmanaged', file_path=rel,
            n_intervals=17520, annual_energy_mwh=energy_mwh, integral_check_pct=0.0,
        )

    def _call(self, iasr_mwh=1_993_800.0):
        with mock.patch.object(ev_scenario_views, 'scenario_energy_mwh', return_value=(iasr_mwh, 'IASR test')), \
                mock.patch.object(ev_scenario_views, '_charging_profiles', return_value=['profiles']), \
                mock.patch.object(ev_scenario_views, '_synthesise_trace', return_value=(np.ones(17520), 0.0)) as synth:
            record = ev_scenario_views._get_or_build_ev_load_trace('medium', 2035, 'unmanaged')
        return record, synth

    def test_builds_from_the_iasr_energy_when_nothing_is_stored(self):
        record, synth = self._call()
        synth.assert_called_once_with(1_993_800.0, 2035, 'unmanaged', ['profiles'])
        self.assertEqual(record.annual_energy_mwh, 1_993_800.0)

    def test_reuses_a_stored_trace_that_matches(self):
        stored = self._store(1_993_800.0)
        record, synth = self._call()
        synth.assert_not_called()
        self.assertEqual(record.pk, stored.pk)

    def test_rebuilds_a_trace_built_from_the_old_source(self):
        stored = self._store(3_321_906.2)  # the retired 2022 CSIRO medium/2035 energy
        record, synth = self._call()
        synth.assert_called_once()
        self.assertEqual(record.pk, stored.pk)  # same (scenario, year, mode) row, updated in place
        self.assertEqual(record.annual_energy_mwh, 1_993_800.0)

    def test_rebuilds_when_the_file_is_missing(self):
        stored = self._store(1_993_800.0)
        (Path(self._tmp.name) / stored.file_path).unlink()
        _, synth = self._call()
        synth.assert_called_once()

    def test_missing_iasr_data_becomes_ev_load_not_available(self):
        with mock.patch.object(ev_scenario_views, 'scenario_energy_mwh', side_effect=IasrDataNotAvailableError('no workbook')):
            with self.assertRaises(ev_scenario_views.EvLoadNotAvailableError) as ctx:
                ev_scenario_views._get_or_build_ev_load_trace('medium', 2035, 'unmanaged')
        self.assertIn('no workbook', str(ctx.exception))
