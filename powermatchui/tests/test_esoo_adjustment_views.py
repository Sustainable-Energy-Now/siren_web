# powermatchui/tests/test_esoo_adjustment_views.py
"""
DB-backed CRUD tests for the EsooForecastAdjustment management pages
(powermatchui.views.esoo_adjustment_views), mirroring the login/reverse
style of test_data_pipeline_views.py.
"""
from datetime import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from siren_web.models import (
    AnnualDemandActual,
    EsooFigure,
    EsooForecastAdjustment,
    EsooVintage,
)

User = get_user_model()

# Same shape as test_esoo_scenario_views.py's fixture: six historical
# pairs running ~400 MW high, enough for a significant 'forecasts_run_high'
# verdict on recompute.
HISTORICAL_ERRORS = [380, 420, 390, 410, 405, 395]
HISTORICAL_FORECAST_PEAK = 4000.0


class EsooAdjustmentViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('analyst', password='pw')

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
                peak_demand_mw=HISTORICAL_FORECAST_PEAK - error,
                peak_datetime=timezone.make_aware(datetime(forecast_year, 1, 15, 18, 0)),
            )

        cls.target_vintage = EsooVintage.objects.create(year=2016, tier='modern_comparable')
        cls.target_figure = EsooFigure.objects.create(
            vintage=cls.target_vintage, domain='demand', metric='peak_summer',
            forecast_year=2018, demand_growth_scenario='expected',
            poe_level=10, demand_basis='operational', value=4500.0, unit='MW',
        )

    def test_list_requires_login(self):
        r = self.client.get(reverse('powermatchui:esoo_adjustment_list'))
        self.assertEqual(r.status_code, 302)

    def test_list_renders_for_authenticated_user(self):
        EsooForecastAdjustment.objects.create(
            source_figure=self.target_figure, category='growth_assumption', horizon=2,
            original_value=4500.0, adjustment_value=-400.0, adjusted_value=4100.0, unit='MW',
            verdict='forecasts_run_high', p_value=0.01, n=6, source='computed',
        )
        self.client.force_login(self.user)
        r = self.client.get(reverse('powermatchui:esoo_adjustment_list'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Forecasts run high')

    def test_create_form_renders(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('powermatchui:esoo_adjustment_create'))
        self.assertEqual(r.status_code, 200)

    def test_edit_form_renders(self):
        adj = EsooForecastAdjustment.objects.create(
            source_figure=self.target_figure, category='growth_assumption', horizon=2,
            original_value=4500.0, adjustment_value=-400.0, adjusted_value=4100.0, unit='MW', source='computed',
        )
        self.client.force_login(self.user)
        r = self.client.get(reverse('powermatchui:esoo_adjustment_edit', args=[adj.pk]))
        self.assertEqual(r.status_code, 200)

    def test_create_manual_adjustment(self):
        self.client.force_login(self.user)
        r = self.client.post(reverse('powermatchui:esoo_adjustment_create'), {
            'source_figure': self.target_figure.pk,
            'category': 'weather_normalization',
            'adjustment_value': '-150.0',
            'methodology_notes': 'Hand-entered pending automated weather pipeline.',
        })
        self.assertEqual(r.status_code, 302)
        adj = EsooForecastAdjustment.objects.get(source_figure=self.target_figure, category='weather_normalization')
        self.assertEqual(adj.source, 'manual')
        self.assertEqual(adj.original_value, 4500.0)
        self.assertEqual(adj.adjustment_value, -150.0)
        self.assertEqual(adj.adjusted_value, 4350.0)

    def test_editing_a_computed_row_flips_it_to_manual(self):
        adj = EsooForecastAdjustment.objects.create(
            source_figure=self.target_figure, category='growth_assumption', horizon=2,
            original_value=4500.0, adjustment_value=-400.0, adjusted_value=4100.0, unit='MW',
            verdict='forecasts_run_high', p_value=0.01, n=6, source='computed',
        )
        self.client.force_login(self.user)
        r = self.client.post(reverse('powermatchui:esoo_adjustment_edit', args=[adj.pk]), {
            'adjustment_value': '-500.0',
            'methodology_notes': 'Analyst override after reviewing FY2026 conditions.',
        })
        self.assertEqual(r.status_code, 302)
        adj.refresh_from_db()
        self.assertEqual(adj.source, 'manual')
        self.assertEqual(adj.adjustment_value, -500.0)
        self.assertEqual(adj.adjusted_value, 4000.0)

    def test_delete_removes_row(self):
        adj = EsooForecastAdjustment.objects.create(
            source_figure=self.target_figure, category='growth_assumption', horizon=2,
            original_value=4500.0, adjustment_value=-400.0, adjusted_value=4100.0, unit='MW', source='computed',
        )
        self.client.force_login(self.user)
        r = self.client.post(reverse('powermatchui:esoo_adjustment_delete', args=[adj.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertFalse(EsooForecastAdjustment.objects.filter(pk=adj.pk).exists())

    def test_recompute_refuses_on_manual_row(self):
        adj = EsooForecastAdjustment.objects.create(
            source_figure=self.target_figure, category='growth_assumption', horizon=2,
            original_value=4500.0, adjustment_value=-999.0, adjusted_value=3501.0, unit='MW', source='manual',
        )
        self.client.force_login(self.user)
        r = self.client.post(reverse('powermatchui:esoo_adjustment_recompute', args=[adj.pk]))
        self.assertEqual(r.status_code, 302)
        adj.refresh_from_db()
        self.assertEqual(adj.adjustment_value, -999.0)  # unchanged

    def test_recompute_updates_a_computed_row_from_current_data(self):
        adj = EsooForecastAdjustment.objects.create(
            source_figure=self.target_figure, category='growth_assumption', horizon=2,
            original_value=4500.0, adjustment_value=0.0, adjusted_value=4500.0, unit='MW',
            verdict='insufficient_evidence', n=0, source='computed',
        )
        self.client.force_login(self.user)
        r = self.client.post(reverse('powermatchui:esoo_adjustment_recompute', args=[adj.pk]))
        self.assertEqual(r.status_code, 302)
        adj.refresh_from_db()
        self.assertEqual(adj.verdict, 'forecasts_run_high')
        self.assertAlmostEqual(adj.adjustment_value, -400.0, places=6)
        self.assertEqual(adj.n, 6)
