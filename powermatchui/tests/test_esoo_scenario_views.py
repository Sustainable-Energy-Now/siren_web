# powermatchui/tests/test_esoo_scenario_views.py
"""
DB-backed test for the "Apply ESOO bias correction" path added to
powermatchui.views.esoo_scenario_views.build_scenario_from_esoo.

Builds a full fixture: six historical (vintage, forecast_year) pairs at
horizon=2 for peak_summer/expected/POE10, each running ~400 MW high (with
some variance, so assess_systematic_bias can actually run a t-test) --
enough for a 'forecasts_run_high' verdict -- then a seventh vintage whose
POE10 peak_summer anchor should be corrected downward by that same
~400 MW when a scenario is built with apply_bias_correction=True.

Also builds one full reference year of FacilityScada (17520 half-hourly
rows) since build_reference_shape() requires a real shape prior; this is
the first real exercise of that path in this codebase (esoo_scenario_views'
own module docstring flags it as unverified against live data), so this
test doubles as smoke coverage for the underlying (unmodified) anchor ->
LDC -> synthesis -> reconciliation chain, not just the new adjustment step.
"""
from datetime import datetime, timedelta

import numpy as np
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from powermatchui.views.esoo_scenario_views import (
    AnchorNotFoundError,
    build_scenario_from_esoo,
    resolve_esoo_anchors,
)
from siren_web.models import (
    AnnualDemandActual,
    EsooFigure,
    EsooForecastAdjustment,
    EsooVintage,
    Scenarios,
    Technologies,
    facilities,
)
from powermatchui.utils.time_alignment import ESOO_TRACE_CLOCK_MARKER
from siren_web.services.facility_scada_matrix import set_scada_values
from siren_web.services.supply_matrix import facility_trace

# errors = forecast(4000) - actual; mean 400, non-zero variance (see
# powerplotui/tests/test_esoo_bias_analysis.py's ComputeMeanErrorByGroupTests
# for why zero variance would make assess_systematic_bias refuse to test).
HISTORICAL_ERRORS = [380, 420, 390, 410, 405, 395]
HISTORICAL_FORECAST_PEAK = 4000.0
TARGET_PEAK_FORECAST = 4500.0
TARGET_MINIMUM_FORECAST = 1200.0
TARGET_ENERGY_GWH = 21900.0  # implies an 8760-hour average of 2500 MW, strictly between 1200 and 4500

REFERENCE_YEAR = 2021  # non-leap: 365 * 48 = 17520 half-hourly intervals

User = get_user_model()


class ApplyBiasCorrectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Six historical vintages, each forecasting POE10 peak_summer two
        # years ahead, running ~400 MW high against the matching actual.
        for i, error in enumerate(HISTORICAL_ERRORS):
            vintage_year = 2010 + i
            forecast_year = vintage_year + 2
            vintage = EsooVintage.objects.create(year=vintage_year, tier='modern_comparable')
            EsooFigure.objects.create(
                vintage=vintage, domain='demand', metric='peak_summer',
                forecast_year=forecast_year, demand_growth_scenario='expected',
                poe_level=10, demand_basis='operational',
                value=HISTORICAL_FORECAST_PEAK, unit='MW',
            )
            AnnualDemandActual.objects.create(
                year=forecast_year, demand_basis='operational',
                annual_energy_gwh=20000.0,
                peak_demand_mw=HISTORICAL_FORECAST_PEAK - error,
                peak_datetime=timezone.make_aware(datetime(forecast_year, 1, 15, 18, 0)),
                minimum_demand_mw=1000.0,
                minimum_datetime=timezone.make_aware(datetime(forecast_year, 7, 1, 4, 0)),
            )

        # Seventh vintage: the one actually being built into a scenario.
        cls.target_vintage = EsooVintage.objects.create(year=2016, tier='modern_comparable')
        cls.target_forecast_year = 2018
        cls.peak_figure = EsooFigure.objects.create(
            vintage=cls.target_vintage, domain='demand', metric='peak_summer',
            forecast_year=cls.target_forecast_year, demand_growth_scenario='expected',
            poe_level=10, demand_basis='operational', value=TARGET_PEAK_FORECAST, unit='MW',
        )
        EsooFigure.objects.create(
            vintage=cls.target_vintage, domain='demand', metric='minimum',
            forecast_year=cls.target_forecast_year, demand_growth_scenario='expected',
            poe_level=90, demand_basis='operational', value=TARGET_MINIMUM_FORECAST, unit='MW',
        )
        EsooFigure.objects.create(
            vintage=cls.target_vintage, domain='demand', metric='energy',
            forecast_year=cls.target_forecast_year, demand_growth_scenario='expected',
            poe_level=10, demand_basis='operational', value=TARGET_ENERGY_GWH, unit='GWh',
        )

        # One full reference year of FacilityScadaMatrix -- smooth daily
        # cycle, magnitude is irrelevant to fit_ldc_to_anchors (only the
        # relative shape matters; the exact anchors above set the absolute
        # scale).
        tech = Technologies.objects.create(
            technology_name='Test Wind', technology_signature='TESTWIND', category='Wind',
        )
        facility = facilities.objects.create(
            facility_name='Test Reference Facility', facility_code='TESTREF',
            idtechnologies=tech, active=True, existing=True, capacity=100,
        )
        n_intervals = 365 * 48
        t = np.arange(n_intervals)
        shape_mwh = 100.0 + 40.0 * np.sin(2 * np.pi * t / 48) + 15.0 * np.sin(2 * np.pi * t / (48 * 365))
        start = timezone.make_aware(datetime(REFERENCE_YEAR, 1, 1, 0, 0))
        set_scada_values([
            {
                'facility_id': facility.idfacilities,
                'dispatch_interval': start + timedelta(minutes=30 * i),
                'quantity': float(shape_mwh[i]),
            }
            for i in range(n_intervals)
        ])

    def test_bias_correction_reduces_the_peak_anchor(self):
        result = build_scenario_from_esoo(
            self.target_vintage, 'expected', 10, self.target_forecast_year,
            apply_bias_correction=True,
        )

        peak_adjustment = result.adjustments and next(
            (a for a in result.adjustments if a.metric == 'peak_summer'), None
        )
        self.assertIsNotNone(peak_adjustment)
        self.assertEqual(peak_adjustment.verdict, 'forecasts_run_high')
        self.assertAlmostEqual(peak_adjustment.adjustment_value, -400.0, places=6)
        self.assertAlmostEqual(peak_adjustment.adjusted_value, TARGET_PEAK_FORECAST - 400.0, places=6)

        # The built trace should hit the *adjusted* peak, not the raw one
        # (within reconcile_trace's tolerance).
        self.assertAlmostEqual(result.peak_mw, TARGET_PEAK_FORECAST - 400.0, places=6)
        self.assertAlmostEqual(result.achieved_peak_mw, TARGET_PEAK_FORECAST - 400.0, delta=1.0)

    def test_adjustment_row_is_persisted_and_linked_to_scenario(self):
        result = build_scenario_from_esoo(
            self.target_vintage, 'expected', 10, self.target_forecast_year,
            apply_bias_correction=True,
        )
        adj = EsooForecastAdjustment.objects.get(source_figure=self.peak_figure, category='growth_assumption')
        self.assertEqual(adj.source, 'computed')
        self.assertEqual(adj.applied_to_scenario_id, result.scenario.idscenarios)

    def test_without_the_flag_raw_anchor_is_used_unchanged(self):
        result = build_scenario_from_esoo(
            self.target_vintage, 'expected', 10, self.target_forecast_year,
            apply_bias_correction=False,
        )
        self.assertEqual(result.adjustments, [])
        self.assertAlmostEqual(result.peak_mw, TARGET_PEAK_FORECAST, places=6)
        self.assertFalse(
            EsooForecastAdjustment.objects.filter(source_figure=self.peak_figure).exists()
        )

    def test_stored_load_trace_is_on_the_awst_clock(self):
        # The SCADA reference shape is UTC-indexed (its daily sine peaks at
        # 06:00 UTC = index 12). The stored Load trace must be AWST, i.e. the
        # same peak at 14:00 local = index 28, so it lines up with the
        # local-clock EV and supply traces it is combined with.
        result = build_scenario_from_esoo(self.target_vintage, 'expected', 10, self.target_forecast_year)
        trace = facility_trace(self.target_forecast_year, result.facility.idfacilities)
        self.assertEqual(trace.size, 365 * 48)
        daily_mean = trace.reshape(365, 48).mean(axis=0)
        self.assertEqual(int(daily_mean.argmax()), 28)
        self.assertIn(ESOO_TRACE_CLOCK_MARKER, result.scenario.description)

    def test_rebuilding_an_old_scenario_restamps_its_description(self):
        first = build_scenario_from_esoo(self.target_vintage, 'expected', 10, self.target_forecast_year)
        Scenarios.objects.filter(pk=first.scenario.pk).update(description='Auto-built ... (FR-G1-01).')
        again = build_scenario_from_esoo(self.target_vintage, 'expected', 10, self.target_forecast_year)
        again.scenario.refresh_from_db()
        self.assertIn(ESOO_TRACE_CLOCK_MARKER, again.scenario.description)

    def test_selector_page_renders_with_bias_correction_checkbox_and_result(self):
        user = User.objects.create_user('analyst2', password='pw')
        self.client.force_login(user)
        r = self.client.post(reverse('powermatchui:esoo_scenario_selector'), {
            'vintage': self.target_vintage.pk,
            'esoo_scenario': 'expected',
            'poe_level': '10',
            'forecast_year': str(self.target_forecast_year),
            'apply_bias_correction': 'on',
        })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'apply_bias_correction')
        self.assertContains(r, 'ESOO Bias Corrections Applied')
        self.assertContains(r, 'Forecasts run high')


class AnchorNotFoundMessageTests(TestCase):
    """resolve_esoo_anchors' error should tell a horizon problem from a
    genuinely unpublished figure, and point at the crosswalk for the
    underlying-only-energy case."""

    @classmethod
    def setUpTestData(cls):
        cls.v2025 = EsooVintage.objects.create(year=2025, tier='modern_comparable')
        cls.v2026 = EsooVintage.objects.create(year=2026, tier='modern_comparable')
        # 2025 vintage: forecasts 2033-2034, underlying energy only.
        for year in (2033, 2034):
            EsooFigure.objects.create(
                vintage=cls.v2025, domain='demand', metric='peak_summer', forecast_year=year,
                demand_growth_scenario='expected', poe_level=10, demand_basis='operational',
                value=4500.0, unit='MW')
            EsooFigure.objects.create(
                vintage=cls.v2025, domain='demand', metric='energy', forecast_year=year,
                demand_growth_scenario='low', poe_level=None, demand_basis='underlying',
                value=25000.0, unit='GWh')
        # 2026 vintage reaches 2035.
        EsooFigure.objects.create(
            vintage=cls.v2026, domain='demand', metric='peak_summer', forecast_year=2035,
            demand_growth_scenario='expected', poe_level=10, demand_basis='operational',
            value=4700.0, unit='MW')

    def test_year_beyond_vintage_horizon_names_horizon_and_covering_vintage(self):
        with self.assertRaises(AnchorNotFoundError) as ctx:
            resolve_esoo_anchors(self.v2025, 'expected', 10, 2035)
        message = str(ctx.exception)
        self.assertIn('outside that horizon', message)
        self.assertIn('2033-2034', message)
        self.assertIn('2034-35', message)   # last capacity year
        self.assertIn('2035-36', message)   # the year that was asked for
        self.assertIn('2026', message)      # the vintage that does cover it

    def test_in_horizon_underlying_only_energy_points_at_the_crosswalk(self):
        with self.assertRaises(AnchorNotFoundError) as ctx:
            resolve_esoo_anchors(self.v2025, 'low', 10, 2034)
        message = str(ctx.exception)
        self.assertNotIn('outside that horizon', message)
        self.assertIn('missing required anchor', message)
        self.assertIn('apply_esoo_demand_basis_crosswalk', message)
