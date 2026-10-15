# powermatchui/tests/test_supply_matrix_views.py
"""Supply Trace Years page: listing, per-year breakdown, CSV download and delete."""
import numpy as np
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from siren_web.models import Demand, SupplyFactorMatrix, Technologies, facilities
from siren_web.services.supply_matrix import facility_has_trace, load_year_matrix, set_facility_trace

URL = 'powermatchui:supply_matrix_years'


class SupplyMatrixYearsTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user('supply_user', password='pw'))
        tech = Technologies.objects.create(technology_name='Test Wind', technology_signature='TESTWIND', category='Wind')
        self.facility = facilities.objects.create(
            facility_name='Test Wind Farm', facility_code='TESTWF', idtechnologies=tech,
            active=True, existing=True, capacity=10,
        )
        # 2023: live facility at 5 MW (5000 kW) flat -> 50% capacity factor, 43.8 GWh.
        set_facility_trace(2023, self.facility.idfacilities, np.full(8760, 5000.0))
        # 2031: only a facility id that doesn't exist (orphaned), half-hourly.
        set_facility_trace(2031, 999999, np.full(17520, 1000.0))
        self.demand = Demand.objects.create(name='Uses 2023', interval_minutes=30, forecast_year=2030, reference_year=2023)

    def test_lists_years_with_status(self):
        r = self.client.get(reverse(URL))
        self.assertEqual(r.status_code, 200)
        years = {y['year']: y for y in r.context['years']}
        self.assertEqual(set(years), {2023, 2031})
        self.assertTrue(years[2023]['in_use'])
        self.assertEqual([d.name for d in years[2023]['demands']], ['Uses 2023'])
        self.assertEqual(years[2031]['n_deleted'], 1)
        self.assertEqual(years[2031]['resolution'], 'half-hourly')
        self.assertIn('Orphaned', years[2031]['status'])

    def test_inactive_demand_does_not_count_as_using_a_year(self):
        self.demand.is_active = False
        self.demand.save()
        years = {y['year']: y for y in self.client.get(reverse(URL)).context['years']}
        self.assertFalse(years[2023]['in_use'])

    def test_year_breakdown_shows_energy_and_capacity_factor(self):
        r = self.client.get(reverse(URL), {'year': 2023})
        self.assertEqual(r.status_code, 200)
        row = r.context['breakdown'][0]
        self.assertEqual(row['name'], 'Test Wind Farm')
        self.assertAlmostEqual(row['energy_gwh'], 43.8, places=3)
        self.assertAlmostEqual(row['capacity_factor_pct'], 50.0, places=3)
        self.assertContains(r, 'Delete it anyway')  # in-use override shown

    def test_half_hourly_breakdown_uses_half_hour_intervals(self):
        row = self.client.get(reverse(URL), {'year': 2031}).context['breakdown'][0]
        self.assertTrue(row['deleted'])
        self.assertEqual(row['hours_with_data'], 8760)
        self.assertAlmostEqual(row['energy_gwh'], 8.76, places=3)  # 1 MW for a year

    def test_unknown_year_and_garbage(self):
        r = self.client.get(reverse(URL), {'year': '1999'})
        self.assertContains(r, 'There is no stored supply trace year 1999')
        r = self.client.get(reverse(URL), {'year': 'abc'})
        self.assertEqual(r.status_code, 200)

    def test_csv_download(self):
        r = self.client.get(reverse(URL), {'year': 2023, 'download': 'csv'})
        self.assertEqual(r['Content-Type'], 'text/csv')
        lines = r.content.decode().splitlines()
        self.assertEqual(lines[0], f'interval,{self.facility.idfacilities}: Test Wind Farm')
        self.assertEqual(lines[1], '0,5000')
        self.assertEqual(len(lines), 8761)

    def test_delete_unused_year(self):
        r = self.client.post(reverse('powermatchui:supply_matrix_year_delete', args=[2031]))
        self.assertRedirects(r, reverse(URL))
        self.assertFalse(SupplyFactorMatrix.objects.filter(year=2031).exists())
        self.assertFalse(facility_has_trace(2031, 999999))

    def test_delete_in_use_year_needs_override(self):
        load_year_matrix(2023)  # warm the cache to check it's cleared
        url = reverse('powermatchui:supply_matrix_year_delete', args=[2023])
        self.client.post(url)
        self.assertTrue(SupplyFactorMatrix.objects.filter(year=2023).exists())
        self.client.post(url, {'confirm_in_use': '1'})
        self.assertFalse(SupplyFactorMatrix.objects.filter(year=2023).exists())
        self.assertFalse(facility_has_trace(2023, self.facility.idfacilities))

    def test_delete_requires_post_and_login(self):
        url = reverse('powermatchui:supply_matrix_year_delete', args=[2031])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.logout()
        self.assertEqual(self.client.get(reverse(URL)).status_code, 302)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertTrue(SupplyFactorMatrix.objects.filter(year=2031).exists())
