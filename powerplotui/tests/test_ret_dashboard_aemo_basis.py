# powerplotui/tests/test_ret_dashboard_aemo_basis.py
"""
Tests that the RET dashboard's RE%, emissions intensity and month windows
follow AEMO's Quarterly Energy Dynamics (QED) WEM method:

- renewable share = (grid solar + wind + biomass + DPV)
                    / (grid generation excl. storage + DPV)
  i.e. battery / pumped-hydro discharge is in neither numerator nor
  denominator (QED Q2 2026 Table 8 has no storage column);
- emissions intensity = emissions / operational demand, t/MWh (= kg/kWh);
- months are AWST calendar months.
"""
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest import mock
from zoneinfo import ZoneInfo

import numpy as np
from django.test import SimpleTestCase, TestCase

from siren_web.management.commands.update_ret_dashboard import Command
from siren_web.models import MonthlyREPerformance
from siren_web.services import facility_scada_matrix as fsm
from siren_web.services import re_classification as rec

AWST = ZoneInfo('Australia/Perth')


def _month(**overrides):
    fields = dict(
        year=2026, month=4,
        wind_generation=250.0, solar_generation=30.0, dpv_generation=260.0,
        biomass_generation=15.0, gas_generation=700.0, coal_generation=470.0,
        storage_discharge=90.0, storage_charge=100.0,
        hydro_discharge=0.0, hydro_charge=0.0,
        total_emissions_tonnes=780_000.0, emissions_intensity_kg_kwh=0.5,
        wholesale_price_avg=100.0, wholesale_price_std_dev=20.0,
        wholesale_price_max=300.0, wholesale_price_min=-50.0,
    )
    fields.update(overrides)
    op = (fields['wind_generation'] + fields['solar_generation'] + fields['biomass_generation']
          + fields['gas_generation'] + fields['coal_generation']
          + fields['storage_discharge'] + fields['hydro_discharge'])
    fields.setdefault('operational_demand', op)
    fields.setdefault('total_generation', op)
    fields.setdefault('underlying_demand', op + fields['dpv_generation'])
    return MonthlyREPerformance(**fields)


class ClassificationTests(SimpleTestCase):
    def test_buckets(self):
        self.assertEqual(rec.fuel_bucket('WIND', 'Generator', 'Onshore Wind'), rec.WIND)
        self.assertEqual(rec.fuel_bucket('SOLAR', 'Generator', 'Single Axis PV'), rec.SOLAR)
        self.assertEqual(rec.fuel_bucket('BESS', 'Storage', 'Battery'), rec.STORAGE)
        self.assertEqual(rec.fuel_bucket('HYDRO', 'Storage', 'PHES'), rec.HYDRO_STORAGE)
        self.assertEqual(rec.fuel_bucket('WASTE', 'Generator', 'Waste to energy'), rec.BIOMASS)
        self.assertEqual(rec.fuel_bucket('DISTILLATE', 'Generator', 'Distillate'), rec.GAS)
        self.assertEqual(rec.fuel_bucket('UNKNOWN', 'Generator', 'Unknown'), rec.OTHER)
        self.assertEqual(rec.bucket_for_technology(None), rec.OTHER)

    def test_storage_is_not_renewable(self):
        self.assertFalse(rec.is_renewable_bucket(rec.STORAGE))
        self.assertFalse(rec.is_renewable_bucket(rec.HYDRO_STORAGE))
        self.assertTrue(rec.is_storage_bucket(rec.STORAGE))


class MonthlyPropertyTests(SimpleTestCase):
    def test_qed_q2_2025_fuel_mix_arithmetic(self):
        # QED Q2 2026 Table 8, Q2 2025 row, as shares of a 1000-unit fuel mix:
        # coal 32.6, gas 32.8, grid solar 1.1 + hybrid 0.5, wind 16.9,
        # biomass 0.4, DPV 14.7 -> RE 33.6%. The printed shares sum to 99.1%
        # (rounding, embedded systems, distillate), so gas absorbs the rest.
        m = _month(coal_generation=326.0, gas_generation=338.0, solar_generation=16.0,
                   wind_generation=169.0, biomass_generation=4.0, dpv_generation=147.0,
                   storage_discharge=40.0)
        self.assertAlmostEqual(m.re_percentage_underlying, 33.6, places=1)

    def test_storage_discharge_excluded_from_denominator(self):
        with_storage = _month(storage_discharge=90.0)
        without = _month(storage_discharge=0.0)
        self.assertAlmostEqual(with_storage.re_percentage_underlying, without.re_percentage_underlying)
        self.assertAlmostEqual(with_storage.re_percentage_operational, without.re_percentage_operational)
        self.assertAlmostEqual(with_storage.grid_generation_ex_storage, 1465.0)


class AggregateSummaryTests(TestCase):
    def test_re_pct_and_intensity_units(self):
        _month(month=4).save()
        _month(month=5).save()
        s = MonthlyREPerformance.aggregate_summary(MonthlyREPerformance.objects.filter(year=2026))
        re_gen = 2 * (250 + 30 + 15 + 260)
        fuel_mix = 2 * (250 + 30 + 15 + 700 + 470 + 260)
        self.assertAlmostEqual(s['re_percentage_underlying'], 100 * re_gen / fuel_mix)
        self.assertAlmostEqual(s['fuel_mix_total'], fuel_mix)
        # 1.56 Mt / 3110 GWh = 0.5016 t/MWh (kg/kWh), not ~501,600
        op = 2 * (250 + 30 + 15 + 700 + 470 + 90)
        self.assertAlmostEqual(s['emissions_intensity'], 1_560_000 / (op * 1000))
        self.assertLess(s['emissions_intensity'], 1.0)

    def test_price_stats_interval_weighted_and_pooled(self):
        # April 30 days, May 31 days
        _month(month=4, wholesale_price_avg=100.0, wholesale_price_std_dev=10.0).save()
        _month(month=5, wholesale_price_avg=200.0, wholesale_price_std_dev=20.0).save()
        s = MonthlyREPerformance.aggregate_summary(MonthlyREPerformance.objects.filter(year=2026))
        n1, n2 = 30 * 48, 31 * 48
        mean = (100 * n1 + 200 * n2) / (n1 + n2)
        second = ((10 ** 2 + 100 ** 2) * n1 + (20 ** 2 + 200 ** 2) * n2) / (n1 + n2)
        self.assertAlmostEqual(s['wholesale_price_avg'], mean)
        self.assertAlmostEqual(s['wholesale_price_std_dev'], (second - mean ** 2) ** 0.5)
        # Pooled spread includes the between-month difference -- far above 15
        self.assertGreater(s['wholesale_price_std_dev'], 45)


class SpanningMatrixTests(SimpleTestCase):
    def test_awst_january_spans_two_utc_years(self):
        def fake_load(year):
            n = (datetime(year + 1, 1, 1) - datetime(year, 1, 1)).days * 48
            if year == 2025:
                return [1, 2], np.vstack([np.full(n, 1.0, 'float32'), np.full(n, 2.0, 'float32')])
            return [2, 3], np.vstack([np.full(n, 20.0, 'float32'), np.full(n, 30.0, 'float32')])

        start = datetime(2026, 1, 1, tzinfo=AWST)
        end = start + timedelta(days=31)
        with mock.patch.object(fsm, 'load_year_matrix', side_effect=fake_load):
            ids, m = fsm.facility_matrix_spanning_range(start, end)

        self.assertEqual(ids, [1, 2, 3])
        self.assertEqual(m.shape, (3, 31 * 48))
        # First 16 half-hours (31 Dec 16:00-24:00 UTC) come from 2025
        self.assertTrue(np.all(m[0, :16] == 1.0) and np.all(np.isnan(m[0, 16:])))
        self.assertTrue(np.all(m[1, :16] == 2.0) and np.all(m[1, 16:] == 20.0))
        self.assertTrue(np.all(np.isnan(m[2, :16])) and np.all(m[2, 16:] == 30.0))

    def test_single_year_passthrough(self):
        n = 365 * 48
        with mock.patch.object(fsm, 'load_year_matrix', return_value=([7], np.ones((1, n), 'float32'))):
            ids, m = fsm.facility_matrix_spanning_range(
                datetime(2026, 4, 1, tzinfo=AWST), datetime(2026, 5, 1, tzinfo=AWST))
        self.assertEqual(ids, [7])
        self.assertEqual(m.shape, (1, 30 * 48))


class CommandIntervalRETests(SimpleTestCase):
    def test_best_interval_excludes_storage(self):
        meta = {
            1: {'bucket': rec.WIND},
            2: {'bucket': rec.GAS},
            3: {'bucket': rec.STORAGE},
        }
        # interval 0: wind 50, gas 50, battery 100 -> 50% (storage ignored)
        matrix = np.array([[50.0, 10.0], [50.0, 90.0], [100.0, -40.0]])
        cmd = Command()
        re_gen, total = cmd._re_and_total_per_interval(matrix, [1, 2, 3], meta)
        np.testing.assert_allclose(re_gen, [50.0, 10.0])
        np.testing.assert_allclose(total, [100.0, 100.0])

    def test_generation_buckets_and_operational_demand(self):
        meta = {
            1: {'bucket': rec.WIND}, 2: {'bucket': rec.STORAGE},
            3: {'bucket': rec.OTHER}, 4: {'bucket': rec.BIOMASS},
        }
        matrix = np.array([[1000.0, np.nan], [500.0, -700.0], [200.0, 0.0], [300.0, 0.0]])
        g = Command().calculate_generation([1, 2, 3, 4], matrix, meta)
        self.assertAlmostEqual(g['wind'], 1.0)
        self.assertAlmostEqual(g['storage_discharge'], 0.5)
        self.assertAlmostEqual(g['storage_charge'], 0.7)
        self.assertAlmostEqual(g['other'], 0.2)
        self.assertAlmostEqual(g['biomass'], 0.3)
        self.assertAlmostEqual(g['operational_demand'], 2.0)
