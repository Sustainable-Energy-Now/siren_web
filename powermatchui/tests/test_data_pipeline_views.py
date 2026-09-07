from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from siren_web.models import CommandRun

User = get_user_model()


class DataPipelineViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user('staffy', password='pw', is_staff=True)
        cls.plain = User.objects.create_user('planey', password='pw')

    def test_dashboard_requires_login(self):
        r = self.client.get(reverse('powermatchui:data_pipeline_dashboard'))
        self.assertEqual(r.status_code, 302)

    def test_dashboard_renders_for_plain_user_without_run_forms(self):
        self.client.force_login(self.plain)
        r = self.client.get(reverse('powermatchui:data_pipeline_dashboard'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Freshness')
        self.assertContains(r, 'staff account')

    def test_submit_requires_staff(self):
        self.client.force_login(self.plain)
        r = self.client.post(reverse('powermatchui:submit_pipeline_command'),
                             {'command_key': 'validate_esoo_data'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(CommandRun.objects.count(), 0)

    def test_submit_rejects_get(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse('powermatchui:submit_pipeline_command'))
        self.assertEqual(r.status_code, 405)

    def test_submit_creates_run(self):
        self.client.force_login(self.staff)
        with mock.patch('powermatchui.views.data_pipeline_views.start_background_run') as m:
            m.return_value = CommandRun.objects.create(
                command_key='validate_esoo_data', management_command='validate_esoo_data',
                args=['--year', '2026'], label='Validate ESOO figures')
            r = self.client.post(reverse('powermatchui:submit_pipeline_command'),
                                 {'command_key': 'validate_esoo_data', 'param_year': '2026'})
        self.assertEqual(r.status_code, 302)
        m.assert_called_once()
        self.assertEqual(m.call_args[0][0], 'validate_esoo_data')

    def test_submit_unknown_command(self):
        self.client.force_login(self.staff)
        r = self.client.post(reverse('powermatchui:submit_pipeline_command'),
                             {'command_key': 'definitely_not_real'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(CommandRun.objects.count(), 0)

    def test_run_status_json(self):
        self.client.force_login(self.plain)
        run = CommandRun.objects.create(command_key='x', management_command='x', args=[],
                                        label='x', status='running')
        r = self.client.get(reverse('powermatchui:pipeline_run_status', args=[run.pk]))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data['status'], 'running')
        self.assertTrue(data['is_active'])

    def test_run_detail_renders(self):
        self.client.force_login(self.plain)
        run = CommandRun.objects.create(command_key='x', management_command='x', args=[],
                                        label='My Run', status='success', output='hello')
        r = self.client.get(reverse('powermatchui:pipeline_run_detail', args=[run.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'My Run')
        self.assertContains(r, 'hello')
