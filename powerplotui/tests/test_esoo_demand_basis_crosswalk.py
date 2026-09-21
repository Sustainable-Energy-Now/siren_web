# powerplotui/tests/test_esoo_demand_basis_crosswalk.py
"""
Tests for the FR-F07/D13 underlying -> operational energy crosswalk
(powerplotui.services.esoo_demand_basis_crosswalk), its management command,
and the delivered-consumption loader that feeds it.

The maths under test, per (vintage, forecast_year):

    DPV_btm = U_expected - D_expected
    O_s     = (U_s - DPV_btm) * k,   k = O_expected / D_expected
"""
from io import StringIO

import openpyxl
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from powerplotui.services.esoo_demand_basis_crosswalk import (
    CrosswalkSkipped,
    DemandBasisCrosswalk,
    derive_operational_energy_figure,
)
from powerplotui.services.esoo_workbook_parser import _extract_delivered_energy
from siren_web.models import EsooFigure, EsooVintage


def _fig(vintage, year, basis, scenario, value, **extra):
    return EsooFigure.objects.create(
        vintage=vintage, domain='demand', metric='energy', forecast_year=year,
        demand_growth_scenario=scenario, poe_level=None, demand_basis=basis,
        value=value, unit='GWh', **extra,
    )


class CrosswalkFixtureMixin:
    """
    2025 vintage publishes Expected underlying/delivered/operational (k = 1.0666..
    in 2030 and 1.0638.. in 2031). 2026 vintage publishes only underlying (all
    scenarios) plus Expected delivered -- the shape of the real archive.
    """

    @classmethod
    def build_fixture(cls):
        cls.v25 = EsooVintage.objects.create(year=2025, tier='modern_comparable')
        cls.v26 = EsooVintage.objects.create(year=2026, tier='modern_comparable')

        for year, u, d, o in ((2030, 24000.0, 18000.0, 19200.0), (2031, 25000.0, 18800.0, 20000.0)):
            _fig(cls.v25, year, 'underlying', 'expected', u)
            _fig(cls.v25, year, 'delivered', 'expected', d)
            _fig(cls.v25, year, 'operational', 'expected', o, extraction_method='structured')
        cls.v25_low_2030 = _fig(cls.v25, 2030, 'underlying', 'low', 23000.0)

        for year, u, d in ((2030, 25000.0, 19000.0), (2032, 27000.0, 20000.0)):
            _fig(cls.v26, year, 'underlying', 'expected', u)
            _fig(cls.v26, year, 'delivered', 'expected', d)
        cls.v26_expected_2030 = EsooFigure.objects.get(
            vintage=cls.v26, forecast_year=2030, demand_basis='underlying', demand_growth_scenario='expected')
        cls.v26_high_2030 = _fig(cls.v26, 2030, 'underlying', 'high', 26000.0)
        cls.v26_expected_2032 = EsooFigure.objects.get(
            vintage=cls.v26, forecast_year=2032, demand_basis='underlying', demand_growth_scenario='expected')


class DeriveOperationalEnergyTests(CrosswalkFixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.build_fixture()

    def test_reproduces_published_expected_operational(self):
        # A vintage that publishes O_expected must be reproduced exactly (k is defined from it).
        underlying = EsooFigure.objects.get(
            vintage=self.v25, forecast_year=2030, demand_basis='underlying', demand_growth_scenario='expected')
        derived = derive_operational_energy_figure(underlying)
        self.assertAlmostEqual(derived['value'], 19200.0, places=6)

    def test_low_scenario_applies_expected_dpv_and_losses(self):
        derived = derive_operational_energy_figure(self.v25_low_2030)
        # DPV 6000, k = 19200 / 18000
        self.assertAlmostEqual(derived['value'], (23000.0 - 6000.0) * 19200.0 / 18000.0, places=6)
        self.assertEqual(derived['demand_basis'], 'operational')
        self.assertEqual(derived['extraction_method'], 'dpv_subtraction')
        self.assertIn('Low scenario assumes the Expected scenario', derived['reconciliation_adjustment'])

    def test_vintage_without_published_operational_borrows_k_from_latest_vintage(self):
        derived = derive_operational_energy_figure(self.v26_high_2030)
        # DPV = 25000 - 19000 = 6000 (from the 2026 vintage itself); k from the 2025 vintage, same year.
        self.assertAlmostEqual(derived['value'], (26000.0 - 6000.0) * 19200.0 / 18000.0, places=6)
        self.assertIn('ESOO 2025', derived['reconciliation_adjustment'])
        self.assertNotIn('held from', derived['reconciliation_adjustment'])

    def test_year_beyond_every_published_k_holds_last_available_k(self):
        derived = derive_operational_energy_figure(self.v26_expected_2032)
        # DPV = 27000 - 20000 = 7000; no vintage publishes k for 2032 -> hold 2031's (20000 / 18800).
        self.assertAlmostEqual(derived['value'], (27000.0 - 7000.0) * 20000.0 / 18800.0, places=6)
        self.assertIn('held from forecast year 2031', derived['reconciliation_adjustment'])

    def test_skips_when_vintage_has_no_delivered_series(self):
        v24 = EsooVintage.objects.create(year=2024, tier='modern_comparable')
        underlying = _fig(v24, 2030, 'underlying', 'low', 22000.0)
        with self.assertRaises(CrosswalkSkipped):
            derive_operational_energy_figure(underlying)

    def test_skips_when_no_vintage_publishes_a_loss_factor(self):
        v27 = EsooVintage.objects.create(year=2027, tier='modern_comparable')
        _fig(v27, 2020, 'underlying', 'expected', 20000.0)
        _fig(v27, 2020, 'delivered', 'expected', 15000.0)
        # k only exists for 2030/2031, none at or before 2020.
        with self.assertRaises(CrosswalkSkipped):
            derive_operational_energy_figure(
                EsooFigure.objects.get(vintage=v27, demand_basis='underlying'))

    def test_previously_derived_rows_do_not_feed_k(self):
        # A derived (not AEMO-published) operational figure must never be used to calibrate k.
        _fig(self.v26, 2030, 'operational', 'expected', 999999.0, extraction_method='dpv_subtraction')
        crosswalk = DemandBasisCrosswalk()
        self.assertNotIn((2026, 2030), crosswalk._k)
        self.assertAlmostEqual(crosswalk.loss_factor(2026, 2030).value, 19200.0 / 18000.0)

    def test_rejects_non_underlying_or_non_energy(self):
        published = EsooFigure.objects.get(
            vintage=self.v25, forecast_year=2030, demand_basis='operational', demand_growth_scenario='expected')
        with self.assertRaises(ValueError):
            derive_operational_energy_figure(published)


class ApplyCrosswalkCommandTests(CrosswalkFixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.build_fixture()

    def _run(self, *args):
        out = StringIO()
        call_command('apply_esoo_demand_basis_crosswalk', *args, stdout=out)
        return out.getvalue()

    def _operational(self, vintage, year, scenario):
        return EsooFigure.objects.get(
            vintage=vintage, forecast_year=year, demand_growth_scenario=scenario,
            metric='energy', demand_basis='operational', poe_level__isnull=True)

    def test_writes_derived_rows_and_never_overwrites_published(self):
        self._run()
        published = self._operational(self.v25, 2030, 'expected')
        self.assertEqual(published.extraction_method, 'structured')
        self.assertEqual(published.value, 19200.0)

        low = self._operational(self.v25, 2030, 'low')
        self.assertEqual(low.extraction_method, 'dpv_subtraction')
        self.assertAlmostEqual(low.value, (23000.0 - 6000.0) * 19200.0 / 18000.0, places=6)

        high = self._operational(self.v26, 2030, 'high')
        self.assertAlmostEqual(high.value, (26000.0 - 6000.0) * 19200.0 / 18000.0, places=6)

    def test_recomputes_a_stale_derived_row(self):
        _fig(self.v25, 2030, 'operational', 'low', 15000.0, extraction_method='dpv_subtraction')
        self._run('--year', '2025')
        self.assertAlmostEqual(
            self._operational(self.v25, 2030, 'low').value, (23000.0 - 6000.0) * 19200.0 / 18000.0, places=6)

    def test_dry_run_writes_nothing(self):
        self._run('--dry-run')
        self.assertFalse(EsooFigure.objects.filter(extraction_method='dpv_subtraction').exists())


def _workbook(rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Ch 2_F.9'
    ws.append(['Figure 9 - components'])
    ws.append([None, 'Component', 'Unit', '2023-24', '2024-25', '2025-26', '2026-27'])
    for row in rows:
        ws.append([None, *row])
    return wb


class ExtractDeliveredEnergyTests(SimpleTestCase):
    class _Vintage:
        year = 2025

    def test_sums_only_wanted_rows_and_skips_pre_forecast_years(self):
        wb = _workbook([
            ['Business consumption (delivered)', 'GWh', 100.0, 110.0, 120.0, 130.0],
            ['Residential consumption (delivered)', 'GWh', 50.0, 40.0, 30.0, 20.0],
            ['Operational consumption (as sent-out)', 'GWh', 999.0, 999.0, 999.0, 999.0],  # must be ignored
        ])
        figures = _extract_delivered_energy(
            self._Vintage(), wb, 'Ch 2_F.9',
            ['Business consumption (delivered)', 'Residential consumption (delivered)'])
        self.assertEqual({f['forecast_year']: f['value'] for f in figures}, {2024: 150.0, 2025: 150.0, 2026: 150.0})
        self.assertTrue(all(f['demand_basis'] == 'delivered' and f['demand_growth_scenario'] == 'expected'
                            and f['unit'] == 'GWh' and f['metric'] == 'energy' for f in figures))

    def test_row_labels_none_sums_every_component_row(self):
        wb = _workbook([
            ['Residential', 'GWh', 1.0, 2.0, 3.0, 4.0],
            ['Data centres', 'GWh', 10.0, 20.0, 30.0, 40.0],
        ])
        figures = _extract_delivered_energy(self._Vintage(), wb, 'Ch 2_F.9', None)
        self.assertEqual({f['forecast_year']: f['value'] for f in figures}, {2024: 22.0, 2025: 33.0, 2026: 44.0})

    def test_missing_expected_row_extracts_nothing_rather_than_a_partial_sum(self):
        wb = _workbook([['Business consumption (delivered)', 'GWh', 100.0, 110.0, 120.0, 130.0]])
        figures = _extract_delivered_energy(
            self._Vintage(), wb, 'Ch 2_F.9',
            ['Business consumption (delivered)', 'Residential consumption (delivered)'])
        self.assertEqual(figures, [])

    def test_missing_sheet_extracts_nothing(self):
        self.assertEqual(_extract_delivered_energy(self._Vintage(), _workbook([]), 'No such sheet', None), [])
