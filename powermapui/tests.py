import datetime as dt
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, TestCase

from powermapui.utils import cel_document_extraction as ex
from powermapui.utils import cel_gis_sync as gis
from powermapui.utils import cel_source_watcher as watcher


class StatusDetectionTests(SimpleTestCase):
    def test_construction_started(self):
        self.assertEqual(
            ex.detect_status('Construction has started on four key Western Power sites as part of the project.'),
            'under_construction')

    def test_construction_with_future_completion_still_counts(self):
        s = 'Construction began in mid-2025 and the project will be completed by the end of 2027.'
        self.assertEqual(ex.detect_status(s), 'under_construction')

    def test_future_energisation_is_not_operational(self):
        self.assertIsNone(ex.detect_status('The line is expected to be energised in 2027.'))

    def test_past_energisation_is_operational(self):
        self.assertEqual(ex.detect_status('The 330 kV line has been energised.'), 'operational')

    def test_funding_commitment(self):
        self.assertEqual(
            ex.detect_status('The State Government has committed $584 million to the project.'), 'funded')

    def test_unrelated_sentence(self):
        self.assertIsNone(ex.detect_status('More than 400 jobs will be created.'))


class DateAndCapacityTests(SimpleTestCase):
    def test_end_of_year(self):
        self.assertEqual(ex.detect_completion_date('On schedule to be delivered by the end of 2027.'),
                         dt.date(2027, 12, 31))

    def test_month_year(self):
        self.assertEqual(ex.detect_completion_date('expected to be in service by December 2027'),
                         dt.date(2027, 12, 31))

    def test_mid_year_and_quarter(self):
        self.assertEqual(ex.detect_completion_date('to be completed by mid-2028'), dt.date(2028, 6, 30))
        self.assertEqual(ex.detect_completion_date('operational in Q3 2026'), dt.date(2026, 9, 30))

    def test_sept_abbreviation(self):
        self.assertEqual(ex.detect_completion_date('online by Sept 2029'), dt.date(2029, 9, 30))

    def test_no_completion_phrase(self):
        self.assertIsNone(ex.detect_completion_date('The 2026-27 State Budget allocated funds.'))

    def test_capacity_new_and_existing(self):
        s = 'It will make around 400 MW of existing wind and another 1 GW of new renewable energy available.'
        self.assertEqual(ex.detect_capacity(s),
                         {'capacity_unlocked_existing_mw': 400.0, 'capacity_new_mw': 1000.0})

    def test_mva_is_not_capacity(self):
        self.assertEqual(ex.detect_capacity('The first two 550 MVA transformers have arrived.'), {})


class ExtractFindingsTests(SimpleTestCase):
    def setUp(self):
        self.programs = [
            ex.ProgramRef(1, ex.program_aliases('Clean Energy Link – North', 'CEL-N'), (10,)),
            ex.ProgramRef(2, ex.program_aliases('Clean Energy Link – East', 'CEL-E'), (20, 21)),
        ]
        self.stages = [
            ex.StageRef(10, 1, ('cel-north - malaga to three springs',)),
            ex.StageRef(20, 2, ('east stage 1',)),
            ex.StageRef(21, 2, ('east stage 2',)),
        ]

    def test_aliases_cover_dash_and_short_forms(self):
        aliases = ex.program_aliases('Clean Energy Link – North', 'CEL-N')
        self.assertIn('clean energy link - north', aliases)
        self.assertIn('cel-north', aliases)
        self.assertNotIn('cel', aliases)

    def test_single_stage_program_resolves_to_stage(self):
        text = ('Construction has started on Clean Energy Link - North. '
                'Clean Energy Link – North is on schedule to be delivered by the end of 2027.')
        found = {f.field_name: f for f in ex.extract_findings(text, self.programs, self.stages)}
        self.assertEqual(found['funding_status'].value, 'under_construction')
        self.assertEqual(found['funding_status'].stage_id, 10)
        self.assertEqual(found['expected_operational_date'].value, dt.date(2027, 12, 31))

    def test_multi_stage_program_without_stage_name_is_program_level(self):
        found = ex.extract_findings('Construction has started on Clean Energy Link - East.',
                                    self.programs, self.stages)
        self.assertEqual(len(found), 1)
        self.assertEqual((found[0].program_id, found[0].stage_id), (2, None))

    def test_stage_name_picks_stage(self):
        found = ex.extract_findings('Construction has started on East Stage 1 of the program.',
                                    self.programs, self.stages)
        self.assertEqual(found[0].stage_id, 20)

    def test_sentence_naming_two_programs_is_skipped(self):
        found = ex.extract_findings(
            'Construction has started on Clean Energy Link - North while Clean Energy Link - East is in planning.',
            self.programs, self.stages)
        self.assertEqual(found, [])

    def test_default_program_from_document(self):
        text = 'Clean Energy Link - North news.\nConstruction is underway at Eneabba.'
        pid = ex.document_default_program(text, self.programs)
        self.assertEqual(pid, 1)
        found = ex.extract_findings('Construction is underway at Eneabba.', self.programs, self.stages, pid)
        self.assertEqual(found[0].stage_id, 10)

    def test_unattributed_sentence_ignored(self):
        self.assertEqual(ex.extract_findings('Construction has started.', self.programs, self.stages), [])


class WatcherHelperTests(SimpleTestCase):
    def test_html_to_text_prefers_main_and_finds_links(self):
        html = ('<html><body><nav>Menu Afrikaans Albanian</nav><main><h1>CEL North</h1>'
                '<p>Construction has started.</p><a href="/x.pdf">Clean Energy Link determination</a>'
                '</main><footer>Footer</footer></body></html>')
        text, links = watcher.html_to_text(html, 'https://www.wa.gov.au/page')
        self.assertEqual(text.splitlines()[:2], ['CEL North', 'Construction has started.'])
        self.assertNotIn('Afrikaans', text)
        self.assertIn(('Clean Energy Link determination', 'https://www.wa.gov.au/x.pdf'), links)

    def test_clean_url_strips_tracking(self):
        self.assertEqual(
            watcher.clean_url('https://letstalkpower.westernpower.com.au/clean-energy-link-north?_gl=1*abc#content'),
            'https://letstalkpower.westernpower.com.au/clean-energy-link-north')

    def test_clean_url_keeps_bare_flags(self):
        url = 'https://www.legislation.wa.gov.au/x/Gg2026_076.pdf/$FILE/Gg2026_076.pdf?OpenElement&utm_source=x'
        self.assertTrue(watcher.clean_url(url).endswith('.pdf?OpenElement'))

    def test_discover_skips_redirect_target_of_page(self):
        links = [('', 'https://letstalkpower.westernpower.com.au/clean-energy-link-east'),
                 ('Skip to main content', 'https://letstalkpower.westernpower.com.au/clean-energy-link-east#content')]
        self.assertEqual(watcher.discover(
            links, 'https://letstalkpower.westernpower.com.au/clean-energy-link/clean-energy-link-east'), [])

    def test_discover_filters_domain_keyword_and_self(self):
        links = [
            ('Clean Energy Link - East', 'https://letstalkpower.westernpower.com.au/clean-energy-link/clean-energy-link-east'),
            ('Clean Energy Link news', 'https://example.com/clean-energy-link'),       # off allow-list
            ('Contact us', 'https://www.wa.gov.au/contact'),                           # no keyword
            ('Share', 'https://www.facebook.com/sharer/sharer.php?u=clean-energy-link'),
            ('Skip', 'https://www.wa.gov.au/page#main-content'),                        # self
        ]
        found = watcher.discover(links, 'https://www.wa.gov.au/page')
        self.assertEqual([u for u, _ in found],
                         ['https://letstalkpower.westernpower.com.au/clean-energy-link/clean-energy-link-east'])

    def test_added_lines(self):
        self.assertEqual(watcher.added_lines('a\nb\nc', 'b\na\nd\nc'), 'd')


def _line_feature(coords_latlon, kv, extra=None):
    props = {'VOLTAGE': f'{kv:g}kV'}
    props.update(extra or {})
    return {'type': 'Feature', 'properties': props,
            'geometry': {'type': 'LineString', 'coordinates': [[lon, lat] for lat, lon in coords_latlon]}}


def _gridline(route_latlon, kv, name='L1'):
    kml = {'coordinates': [[lon, lat] for lat, lon in route_latlon]}
    return SimpleNamespace(line_name=name, voltage_level=kv, get_kml_geometry_data=lambda: kml)


class GisMatchingTests(SimpleTestCase):
    route = [(-31.0, 115.8), (-30.0, 115.6), (-29.2, 115.4)]

    def test_voltage_parsing(self):
        self.assertEqual(gis.feature_voltage_kv({'Operating_Voltage': '330 kV'}), 330.0)
        self.assertEqual(gis.feature_voltage_kv({'NOMINAL_VOLTAGE': 132000}), 132.0)
        self.assertIsNone(gis.feature_voltage_kv({'NAME': 'Line 1'}))

    def test_new_line_confirmed(self):
        index = gis.index_lines([_line_feature(self.route, 330)])
        self.assertEqual(gis.check_line(_gridline(self.route, 330), index).state, 'confirmed')

    def test_new_line_at_lower_voltage_not_built(self):
        index = gis.index_lines([_line_feature(self.route, 132)])
        check = gis.check_line(_gridline(self.route, 330), index)
        self.assertEqual(check.state, 'not_built')
        self.assertIn('132 kV', check.detail)

    def test_upgrade_line_needs_higher_voltage_than_stored(self):
        # CEL-North stores its upgrade lines at the pre-CEL 132 kV.
        gl = _gridline(self.route, 132)
        still_132 = gis.index_lines([_line_feature(self.route, 132)])
        now_330 = gis.index_lines([_line_feature(self.route, 330)])
        self.assertEqual(gis.check_line(gl, still_132, role='upgrade').state, 'not_built')
        self.assertEqual(gis.check_line(gl, now_330, role='upgrade').state, 'confirmed')

    def test_upgrade_not_fooled_by_parallel_higher_voltage_circuit(self):
        # Real CEL-North corridors: an existing 330 kV line runs 0-50 m from the 132 kV one.
        gl = _gridline(self.route, 132)
        shared = gis.index_lines([_line_feature(self.route, 132), _line_feature(self.route, 330)])
        check = gis.check_line(gl, shared, role='upgrade')
        self.assertEqual(check.state, 'not_built')
        self.assertIn('0%', check.detail)

    def test_out_of_service_line_ignored(self):
        index = gis.index_lines([_line_feature(self.route, 330, {'STATUS': 'Out of Service'})])
        self.assertEqual(gis.check_line(_gridline(self.route, 330), index).state, 'not_built')

    def test_line_without_kml_is_unknown(self):
        gl = SimpleNamespace(line_name='L', voltage_level=330, get_kml_geometry_data=lambda: None)
        self.assertEqual(gis.check_line(gl, []).state, 'unknown')

    def test_terminal_match(self):
        subs = gis.index_substations([{'type': 'Feature', 'properties': {'SUBSTATION_NAME': 'Eneabba'},
                                       'geometry': {'type': 'Point', 'coordinates': [115.27, -29.82]}}])
        near = SimpleNamespace(terminal_name='Eneabba 132', latitude=-29.825, longitude=115.272)
        far = SimpleNamespace(terminal_name='Elsewhere', latitude=-30.5, longitude=115.9)
        self.assertEqual(gis.check_terminal(near, subs).state, 'confirmed')
        self.assertEqual(gis.check_terminal(far, subs).state, 'not_built')


class ProposalLifecycleTests(TestCase):
    def setUp(self):
        from siren_web.models import CELProgram, CELStage
        self.program = CELProgram.objects.create(name='Clean Energy Link – North', code='CEL-N')
        self.stage = CELStage.objects.create(
            cel_program=self.program, stage_number=1, name='CEL-North – Malaga to Three Springs',
            funding_status='funded', capacity_new_mw=1000, alignment_radius_km=50)

    def _propose(self, field, value):
        from powermapui.utils.cel_proposals import create_proposal
        return create_proposal(program_id=self.program.pk, stage=self.stage, field_name=field,
                               value=value, evidence='e', source='document')

    def test_backward_status_and_unchanged_values_not_proposed(self):
        self.assertIsNone(self._propose('funding_status', 'planning'))
        self.assertIsNone(self._propose('capacity_new_mw', 1004.0))

    def test_duplicate_and_rejected_suppressed(self):
        from powermapui.utils.cel_proposals import reject_proposal
        p = self._propose('funding_status', 'under_construction')
        self.assertIsNotNone(p)
        self.assertIsNone(self._propose('funding_status', 'under_construction'))
        reject_proposal(p)
        self.assertIsNone(self._propose('funding_status', 'under_construction'))

    def test_accept_applies_value_notes_and_supersedes(self):
        from powermapui.utils.cel_proposals import accept_proposal
        a = self._propose('expected_operational_date', dt.date(2027, 12, 31))
        b = self._propose('expected_operational_date', dt.date(2028, 6, 30))
        with mock.patch('powermapui.utils.cel_viability_service.CELViabilityService.score_facilities_for_stage') as score:
            accept_proposal(b)
            score.assert_not_called()                   # dates don't feed the viability score
        self.stage.refresh_from_db()
        a.refresh_from_db()
        self.assertEqual(self.stage.expected_operational_date, dt.date(2028, 6, 30))
        self.assertIn('expected_operational_date', self.stage.notes)
        self.assertEqual(a.status, 'superseded')

    def test_accept_status_recomputes_viability(self):
        from powermapui.utils.cel_proposals import accept_proposal
        p = self._propose('funding_status', 'under_construction')
        with mock.patch('powermapui.utils.cel_viability_service.CELViabilityService.score_facilities_for_stage') as score:
            accept_proposal(p)
            score.assert_called_once()

    def test_review_page_renders_and_accepts_program_level_proposal(self):
        from django.contrib.auth import get_user_model
        from django.urls import reverse
        from powermapui.utils.cel_proposals import create_proposal
        user = get_user_model().objects.create_user('reviewer', password='pw', is_staff=True)
        self.client.force_login(user)
        p = create_proposal(program_id=self.program.pk, stage=None, field_name='funding_status',
                            value='under_construction', evidence='Construction has started.', source='document')
        page = self.client.get(reverse('powermapui:cel_proposals'))
        self.assertContains(page, 'Construction has started.')
        self.assertContains(page, 'Choose stage')
        with mock.patch('powermapui.utils.cel_viability_service.CELViabilityService.score_facilities_for_stage'):
            self.client.post(reverse('powermapui:cel_proposal_accept', args=[p.pk]), {'cel_stage': self.stage.pk})
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.funding_status, 'under_construction')

    def test_dry_run_with_no_sources_previews_defaults_without_writing(self):
        from io import StringIO
        from django.core.management import call_command
        from siren_web.models import CELSourceWatch
        page = 'Clean Energy Link - North\nConstruction has started at four sites.'
        out = StringIO()
        with mock.patch.object(watcher, 'fetch', return_value=(200, 'html', page, [])):
            call_command('check_cel_sources', '--dry-run', stdout=out)
        self.assertIn('previewing the default source list', out.getvalue())
        self.assertIn('would propose funding_status = under_construction', out.getvalue())
        self.assertEqual(CELSourceWatch.objects.count(), 0)

    def test_dry_run_hides_findings_that_match_current_values(self):
        self.stage.funding_status = 'under_construction'
        self.stage.save()
        w = watcher.CELSourceWatch(url='https://www.wa.gov.au/x', label='x')
        page = 'Clean Energy Link - North\nConstruction has started at four sites.'
        with mock.patch.object(watcher, 'fetch', return_value=(200, 'html', page, [])):
            r = watcher.check_watch(w, dry_run=True)
        self.assertEqual(r['proposals'], [])

    def test_check_watch_snapshots_and_proposes(self):
        from siren_web.models import CELSourceWatch, CELProposedUpdate
        w = CELSourceWatch.objects.create(url='https://www.wa.gov.au/cel-north', label='t')
        page = ('Clean Energy Link - North update\n'
                'Construction has started at four sites.\n'
                'Clean Energy Link – North is on schedule to be delivered by the end of 2027.')
        with mock.patch.object(watcher, 'fetch', return_value=(200, 'html', page, [])):
            r1 = watcher.check_watch(w)
            r2 = watcher.check_watch(w)
        self.assertTrue(r1['changed'] and r1['initial'])
        self.assertFalse(r2['changed'])
        self.assertEqual(w.snapshots.count(), 1)
        fields = set(CELProposedUpdate.objects.values_list('field_name', flat=True))
        self.assertEqual(fields, {'funding_status', 'expected_operational_date'})
