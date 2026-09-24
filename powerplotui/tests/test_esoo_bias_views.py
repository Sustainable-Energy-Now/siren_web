# powerplotui/tests/test_esoo_bias_views.py
"""
Smoke test for the ESOO Bias Tracking dashboard
(powerplotui.views.esoo_bias_views.bias_tracking_dashboard) after adding
the "Applied to Powermatch Scenarios" section -- confirms the template
still renders (no syntax errors, url tags resolve) both with an empty
archive and with an EsooForecastAdjustment applied to a scenario.
"""
from django.test import TestCase
from django.urls import reverse

from siren_web.models import Demand, EsooFigure, EsooForecastAdjustment, EsooVintage


class BiasTrackingDashboardRenderTests(TestCase):
    def test_renders_with_empty_archive(self):
        r = self.client.get(reverse('esoo_bias_tracking'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'No adjustments have been applied to a Powermatch scenario yet')

    def test_renders_applied_adjustments_section(self):
        vintage = EsooVintage.objects.create(year=2016, tier='modern_comparable')
        figure = EsooFigure.objects.create(
            vintage=vintage, domain='demand', metric='peak_summer',
            forecast_year=2018, demand_growth_scenario='expected',
            poe_level=10, demand_basis='operational', value=4500.0, unit='MW',
        )
        demand = Demand.objects.create(name='ESOO 2016 expected POE10 2018', forecast_year=2018)
        EsooForecastAdjustment.objects.create(
            source_figure=figure, category='growth_assumption', horizon=2,
            original_value=4500.0, adjustment_value=-400.0, adjusted_value=4100.0, unit='MW',
            verdict='forecasts_run_high', p_value=0.01, n=6, source='computed',
            applied_to_demand=demand,
        )
        r = self.client.get(reverse('esoo_bias_tracking'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'ESOO 2016 expected POE10 2018')
        self.assertContains(r, 'Growth assumption bias')
