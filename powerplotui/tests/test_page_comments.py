"""Comments + 'Contact SEN Modelling' on the EV uptake tracker and the grid map."""
from django.contrib.auth.models import User
from django.test import TestCase

from siren_web.models import ReportComment

PAGES = {'ev_uptake': '/ev-uptake-tracking/', 'grid_map': '/map/'}


class PageCommentsTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('member', password='x')

    def add(self, report_type, content):
        return self.client.post('/ret_dashboard/comments/add/', {
            'report_type': report_type, 'year': 2026, 'content': content, 'category': 'question',
        }, headers={'X-Requested-With': 'XMLHttpRequest'})

    def test_logged_in_user_can_comment_on_each_page(self):
        self.client.force_login(self.user)
        for report_type, url in PAGES.items():
            resp = self.client.get(url)
            self.assertContains(resp, 'mailto:modelling.lead@sen.asn.au')
            self.assertContains(resp, f'name="report_type" value="{report_type}"')

            self.assertTrue(self.add(report_type, f'Note on {report_type}').json()['success'])
            # Page-wide thread: shown regardless of the year it was made in
            ReportComment.objects.create(report_type=report_type, year=2024, author=self.user,
                                         content=f'Older note on {report_type}')
            resp = self.client.get(url)
            self.assertContains(resp, f'Note on {report_type}')
            self.assertContains(resp, f'Older note on {report_type}')
            self.assertNotContains(resp, 'Note on ' + ({'ev_uptake', 'grid_map'} - {report_type}).pop())

    def test_anonymous_ev_page_prompts_login_and_comments_are_rejected(self):
        resp = self.client.get(PAGES['ev_uptake'])
        self.assertContains(resp, 'to add comments')
        self.assertNotContains(resp, 'id="comment-form"')
        self.assertEqual(self.add('ev_uptake', 'x').status_code, 302)

    def test_unknown_report_type_rejected(self):
        self.client.force_login(self.user)
        self.assertEqual(self.add('bogus', 'x').status_code, 400)
        self.assertFalse(ReportComment.objects.exists())
