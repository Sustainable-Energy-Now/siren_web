# powerplotui/test_dot_wa_ev_parser.py
"""
Unit tests for the DoT WA EV actuals fetch/parse pipeline
(powerplotui.services.dot_wa_ev_fetcher / dot_wa_ev_parser).

The pure helpers are covered directly. The end-to-end PDF parse is
exercised only if a real report PDF is dropped at
powerplotui/tests_fixtures/PROJ_P_WA_EV_analysis_summary_*.pdf
(the archive dir is .gitignored, so fixtures are not committed).
"""
import datetime as dt
from pathlib import Path

from django.test import SimpleTestCase

from powerplotui.services.dot_wa_ev_fetcher import _PDF_HREF_RE, _normalise_url
from powerplotui.services.dot_wa_ev_parser import (
    _period_token_to_date,
    period_end_from_filename,
    quarter_label_from_date,
)

_FIXTURE_DIR = Path(__file__).resolve().parent / 'tests_fixtures'


class FilenameParsingTests(SimpleTestCase):
    def test_month_variants_map_to_quarter_end(self):
        cases = {
            'PROJ_P_WA_EV_analysis_summary_Sept_2025.pdf': dt.date(2025, 9, 30),
            'PROJ_P_WA_EV_analysis_summary_Dec_2025.pdf': dt.date(2025, 12, 31),
            'PROJ_P_WA_EV_analysis_summary_June_2026.pdf': dt.date(2026, 6, 30),
            'PROJ_P_WA_EV_analysis_summary_march_2024.pdf': dt.date(2024, 3, 31),
            'PROJ_P_WA_EV_analysis_summary_Mar_2026.pdf': dt.date(2026, 3, 31),
            'PROJ_P_WA_EV_analysis_summary_Dec_2023_quarter.pdf': dt.date(2023, 12, 31),
        }
        for name, expected in cases.items():
            self.assertEqual(period_end_from_filename(name), expected, name)

    def test_unrecognised_filename_returns_none(self):
        self.assertIsNone(period_end_from_filename('PROJ_P_WA_EV_Notes_on_methodology.pdf'))

    def test_quarter_label(self):
        self.assertEqual(quarter_label_from_date(dt.date(2025, 12, 31)), 'Dec 2025')
        self.assertEqual(quarter_label_from_date(dt.date(2026, 6, 30)), 'Jun 2026')


class PeriodTokenTests(SimpleTestCase):
    def test_two_digit_year(self):
        self.assertEqual(_period_token_to_date('Dec-21'), dt.date(2021, 12, 31))
        self.assertEqual(_period_token_to_date('Jun-25'), dt.date(2025, 6, 30))

    def test_full_month_and_four_digit_year(self):
        self.assertEqual(_period_token_to_date('September-2024'), dt.date(2024, 9, 30))

    def test_garbage_returns_none(self):
        for bad in ('', 'Total', '3770', 'Q4', 'Dec 21 22'):
            self.assertIsNone(_period_token_to_date(bad), bad)


class IndexScrapeRegexTests(SimpleTestCase):
    SAMPLE = '''
      <a href="https://www.transport.wa.gov.au:443/getmedia/abc-123/PROJ_P_WA_EV_analysis_summary_Dec_2025.pdf">Dec 2025</a>
      <a href='/getmedia/def-456/PROJ_P_WA_EV_analysis_summary_June_2026.pdf'>Jun 2026</a>
      <a href="/getmedia/999/PROJ_P_WA_EV_Notes_on_methodology.pdf">methodology</a>
    '''

    def test_only_analysis_summaries_matched(self):
        hrefs = _PDF_HREF_RE.findall(self.SAMPLE)
        self.assertEqual(len(hrefs), 2)
        self.assertTrue(all('analysis_summary' in h for h in hrefs))

    def test_normalise_drops_443_and_lowercases_host(self):
        self.assertEqual(
            _normalise_url('https://WWW.Transport.WA.gov.au:443/getmedia/x/y.pdf'),
            'https://www.transport.wa.gov.au/getmedia/x/y.pdf',
        )


class PdfParseIntegrationTests(SimpleTestCase):
    def _fixtures(self):
        return sorted(_FIXTURE_DIR.glob('PROJ_P_WA_EV_analysis_summary_*.pdf'))

    def test_figure_1b_series_parses_when_fixture_present(self):
        fixtures = self._fixtures()
        if not fixtures:
            self.skipTest(f'no report PDF in {_FIXTURE_DIR}')

        from powerplotui.services.dot_wa_ev_parser import parse_actuals_pdf

        parsed_any_series = False
        for pdf in fixtures:
            result = parse_actuals_pdf(pdf)
            self.assertIsNotNone(result['period_end'])
            self.assertEqual(
                result['quarter_label'],
                quarter_label_from_date(result['period_end']),
            )
            for a, b in zip(result['series'], result['series'][1:]):
                self.assertLessEqual(a['period_end'], b['period_end'])
                self.assertLessEqual(a['total'], b['total'])
            for row in result['series']:
                self.assertAlmostEqual(row['bev'] + row['phev'], row['total'], delta=1.0)
                parsed_any_series = True

        self.assertTrue(
            parsed_any_series,
            'every fixture parsed but none yielded a Figure 1b series',
        )
