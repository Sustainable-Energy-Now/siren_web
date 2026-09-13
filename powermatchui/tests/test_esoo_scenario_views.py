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

from powermatchui.views.esoo_scenario_views import build_scenario_from_esoo
from siren_web.models import (
    AnnualDemandActual,
    EsooFigure,
    EsooForecastAdjustment,
    EsooVintage,
    FacilityScada,
    Technologies,
    facilities,
)

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

        # One full reference year of FacilityScada -- smooth daily cycle,
        # magnitude is irrelevant to fit_ldc_to_anchors (only the relative
        # shape matters; the exact anchors above set the absolute scale).
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
        FacilityScada.objects.bulk_create(
            [
                FacilityScada(
                    facility=facility, dispatch_interval=start + timedelta(minutes=30 * i),
                    quantity=float(shape_mwh[i]),
                )
                for i in range(n_intervals)
            ],
            batch_size=2000,
        )

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
