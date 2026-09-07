from django.test import TestCase

from siren_web.models import CommandRun, EsooVintage, EvVintage
from powermatchui.services import pipeline_status as ps


class PipelineStatusTests(TestCase):
    def test_all_cards_shape_on_empty_db(self):
        cards = ps.all_cards()
        keys = {c['key'] for c in cards}
        self.assertEqual(keys, {'scada', 'dpv', 'esoo', 'esoo_actuals', 'ev', 'ev_actuals'})
        for c in cards:
            self.assertIn(c['staleness'], ('ok', 'warn', 'stale'))
            self.assertIn('detail', c)

    def test_esoo_card_lists_vintages(self):
        EsooVintage.objects.create(year=2024, tier='modern_comparable', ingestion_status='retrieved')
        EsooVintage.objects.create(year=2025, tier='modern_comparable', ingestion_status='pending')
        card = ps.esoo_card()
        self.assertEqual(card['n_vintages'], 2)
        self.assertEqual([v['year'] for v in card['vintages']], [2025, 2024])

    def test_ev_card_lists_vintages(self):
        EvVintage.objects.create(version='2024-Q3', ingestion_status='retrieved')
        card = ps.ev_uptake_card()
        self.assertEqual(card['n_vintages'], 1)
        self.assertEqual(card['vintages'][0]['version'], '2024-Q3')

    def test_recent_runs_limit(self):
        for i in range(30):
            CommandRun.objects.create(command_key='x', management_command='x', args=[],
                                      label=f'run {i}', status='success')
        self.assertEqual(len(ps.recent_runs(25)), 25)
