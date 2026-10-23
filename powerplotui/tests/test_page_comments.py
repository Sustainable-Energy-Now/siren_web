"""Comments + 'Contact SEN Modelling' on the EV uptake tracker and the grid map."""
from django.contrib.auth.models import User
from django.test import TestCase, override_settings

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

    @override_settings(USER_PASS={'member_pass': 'm-pass', 'lapsed_pass': 'l', 'subscriber_pass': 's'})
    def test_ev_page_logs_in_from_website_membership_link(self):
        self.user.set_password('m-pass'); self.user.save()
        resp = self.client.get('/ev-uptake-tracking/?member_name=Rob&email_address=x%40y'
                               '&membership_status=Active')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.wsgi_request.user.username, 'member')
        self.assertContains(resp, 'id="comment-form"')

    @override_settings(USER_PASS={'member_pass': 'm-pass', 'lapsed_pass': 'l', 'subscriber_pass': 's'})
    def test_members_sign_with_own_identity_and_only_manage_their_own(self):
        from django.test import Client
        self.user.set_password('m-pass'); self.user.save()
        link = '/ev-uptake-tracking/?member_name={}&email_address={}%40x.net&membership_status=Active'
        rob, sue = Client(), Client()
        rob.get(link.format('Rob', 'rob'))
        sue.get(link.format('Sue', 'sue'))
        xhr = {'X-Requested-With': 'XMLHttpRequest'}

        rob.post('/ret_dashboard/comments/add/', {'report_type': 'ev_uptake', 'year': 2026,
                 'content': 'Rob here', 'category': 'question'}, headers=xhr)
        comment = ReportComment.objects.get()
        self.assertEqual(comment.author_name, 'Rob (rob@x.net)')

        # Website members (shared account) see names only, including their own
        page = rob.get('/ev-uptake-tracking/')
        self.assertContains(page, '<span class="comment-author">Rob</span>', html=True)
        self.assertNotContains(page, 'rob@x.net')
        self.assertContains(page, f'deleteComment({comment.id})')
        page = sue.get('/ev-uptake-tracking/')
        self.assertNotContains(page, 'rob@x.net')
        self.assertNotContains(page, f'deleteComment({comment.id})')
        self.assertNotContains(page, f'toggleResolveComment({comment.id})')

        # Logged-out visitors see the name but not the email address
        page = Client().get('/ev-uptake-tracking/')
        self.assertContains(page, '<span class="comment-author">Rob</span>', html=True)
        self.assertNotContains(page, 'rob@x.net')

        # People logged in with their own Siren Web account see the email
        named = Client()
        named.force_login(User.objects.create_user('paul', password='x'))
        self.assertContains(named.get('/ev-uptake-tracking/'), 'Rob (rob@x.net)')
        ReportComment.objects.create(report_type='ev_uptake', year=2026, author=self.user,
                                     author_name='only@x.net', content='Email-only signature')
        page = Client().get('/ev-uptake-tracking/')
        self.assertNotContains(page, 'only@x.net')
        self.assertContains(page, 'SEN member')
        ReportComment.objects.filter(author_name='only@x.net').delete()

        delete_url = f'/ret_dashboard/comments/{comment.id}/delete/'
        self.assertEqual(sue.post(delete_url, headers=xhr).status_code, 403)
        self.assertEqual(rob.post(delete_url, headers=xhr).status_code, 200)
        self.assertFalse(ReportComment.objects.exists())

    def test_named_account_signs_with_username(self):
        modeller = User.objects.create_user('paul', password='x')
        self.client.force_login(modeller)
        self.add('ev_uptake', 'From a modeller')
        self.assertEqual(ReportComment.objects.get().author_name, 'paul')

    def test_unknown_report_type_rejected(self):
        self.client.force_login(self.user)
        self.assertEqual(self.add('bogus', 'x').status_code, 400)
        self.assertFalse(ReportComment.objects.exists())
