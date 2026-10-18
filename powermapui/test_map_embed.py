"""Grid Map iframe embedding: membership login, hidden menus, modeller-only updates."""
import json

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings

TEST_USER_PASS = {'member_pass': 'm-pass', 'lapsed_pass': 'l-pass', 'subscriber_pass': 's-pass'}


@override_settings(USER_PASS=TEST_USER_PASS)
class MapEmbedTests(TestCase):

    def setUp(self):
        from siren_web.models import Technologies, facilities
        self.member = User.objects.create_user('member', password='m-pass')
        User.objects.create_user('subscriber', password='s-pass')
        self.modeller = User.objects.create_user('modeller', password='x')
        self.modeller.groups.add(Group.objects.create(name='modellers'))
        tech = Technologies.objects.create(
            technology_name='Onshore Wind', technology_signature='ONW', category='Wind',
            renewable=1, dispatchable=0, fuel_type='WIND')
        self.facility = facilities.objects.create(
            facility_name='Test Farm', facility_code='TESTFARM', active=True, existing=False,
            status='proposed', latitude=-33.0, longitude=116.0, idtechnologies=tech)

    def move_facility(self):
        return self.client.post(
            f'/facility/{self.facility.pk}/move/',
            data=json.dumps({'latitude': -31.0, 'longitude': 115.0}),
            content_type='application/json')

    def test_membership_link_logs_in_and_page_is_frameable(self):
        resp = self.client.get('/map/?membership_status=Active')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.wsgi_request.user.username, 'member')
        self.assertNotIn('X-Frame-Options', resp.headers)

    def test_anonymous_in_iframe_gets_notice_otherwise_redirect(self):
        resp = self.client.get('/map/', headers={'Sec-Fetch-Dest': 'iframe'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Login required')
        self.assertNotContains(resp, 'Powermap Home')
        resp = self.client.get('/map/')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/accounts/login/', resp['Location'])

    def test_menus_hidden_only_when_embedded(self):
        self.client.force_login(self.member)
        self.assertContains(self.client.get('/map/'), 'Powermap Home')
        for resp in (self.client.get('/map/?embed=1'),
                     self.client.get('/map/', headers={'Sec-Fetch-Dest': 'iframe'})):
            self.assertNotContains(resp, 'Powermap Home')
            self.assertNotContains(resp, 'href="/powermatchui/"')

    def test_non_modeller_gets_view_only_map(self):
        self.client.force_login(self.member)
        resp = self.client.get('/map/')
        for marker in ('addFacilityBtn"', 'addTerminalBtn"', 'addGridLineBtn"', 'drawZoneBtn"',
                       'editSwisBoundaryBtn"', 'showGridUtilization()"', 'Connections Overview'):
            self.assertNotContains(resp, marker)
        self.assertContains(resp, 'var CAN_EDIT = false;')
        self.assertEqual(self.move_facility().status_code, 403)
        self.facility.refresh_from_db()
        self.assertEqual(self.facility.latitude, -33.0)

    def test_modeller_keeps_update_tools(self):
        self.client.force_login(self.modeller)
        resp = self.client.get('/map/')
        self.assertContains(resp, 'id="addFacilityBtn"')
        self.assertContains(resp, 'id="editSwisBoundaryBtn"')
        self.assertContains(resp, 'var CAN_EDIT = true;')
        self.assertEqual(self.move_facility().status_code, 200)
        self.facility.refresh_from_db()
        self.assertEqual(self.facility.latitude, -31.0)

    def test_membership_status_matching_ignores_case(self):
        resp = self.client.get('/map/?membership_status=Non+Member')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.wsgi_request.user.username, 'subscriber')

    def test_login_page_accepts_credentials_in_next(self):
        url = ('/accounts/login/?next=/map/%3Fmember_name%3DRob%26email_address%3D'
               'robin.perkins%2540internode.on.net%26membership_status%3DNon%2BMember')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp['Location'].startswith('/map/?member_name=Rob&'))
        self.assertEqual(self.client.get(resp['Location']).wsgi_request.user.username, 'subscriber')

    def test_login_page_ignores_offsite_next_and_shows_form(self):
        resp = self.client.get('/accounts/login/?next=https://evil.example/%3Fmembership_status%3DActive')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.wsgi_request.user.is_authenticated)
        resp = self.client.get('/accounts/login/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'name="password"')

    def test_write_endpoints_reject_anonymous(self):
        self.assertEqual(self.move_facility().status_code, 401)
