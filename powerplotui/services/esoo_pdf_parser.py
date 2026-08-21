# powerplotui/services/esoo_pdf_parser.py
"""
FR-F02 — PDF fallback extraction. Structured sources (the Electricity
Forecasting Data Portal, ESOO Excel workbooks — see esoo_workbook_parser.py)
are the preferred path; PDF extraction is used only where no structured
source exists, per FR-F02's acceptance criteria.

extract_raw_tables() is a fully working, generic extraction pass with full
page/table provenance. The per-vintage FIGURE_EXTRACTORS mapping that turns
raw tables into EsooFigure rows is populated only for vintages whose actual
table layout has been inspected — see _extract_2026() below for the first
one, registered after inspecting the real 2026 WEM ESOO PDF. Other vintages
raise NotImplementedError until inspected the same way, rather than guessing
column positions (FR-F07: "without fabricating precision").

Findings from inspecting the 2026 edition (worth checking against future
vintages, since layout can change year to year):
  - Only two tables in the whole 128-page document carry clean per-year
    numeric series for the figures this schema tracks: Table 1 (p.5,
    executive summary: underlying energy consumption, Peak RCT, existing+
    committed peak capacity — Expected scenario only) and Table 10 (p.39:
    summer/winter peak and minimum operational demand, 10%/90% POE,
    Expected scenario only).
  - AEMO reports summer and winter peak as two separate series, not one
    'peak' figure — the schema's ESOO_METRIC_CHOICES was extended
    ('peak_summer'/'peak_winter') to match.
  - Low/High-scenario values and the full POE10/50/90 peak band are
    presented only as charts (Figures 7-19), not extractable tables, in
    this PDF — getting them structurally likely requires the Electricity
    Forecasting Data Portal instead (bears on OQ-1/OQ-2).
  - Table 11 (p.40) is AEMO's own actual-vs-prior-vintage-forecast
    comparison (2025 ESOO forecast vs. 2025-26 actuals) — a strong
    candidate for D11/FR-G2-06's validation-first backcast reference, but
    is not wired into figure extraction here since it belongs to G2
    (Phase 3b), not the Foundation's per-vintage figure store.
"""
import logging
import re
from datetime import date
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

import pdfplumber
from django.conf import settings

# pdfminer (pdfplumber's parsing backend) emits one DEBUG log line per PDF
# content-stream token/operator it encounters — tens of thousands of lines
# for a single 100+ page report. Left at whatever level the root logger is
# configured to (DEBUG in some deployments), a single request through this
# module can flood production logs and add significant I/O overhead on top
# of the parsing time itself. This isn't something a caller should have to
# know to configure — cap it here, at the one place pdfplumber gets used.
for _pdfminer_logger in ('pdfminer', 'pdfplumber'):
    logging.getLogger(_pdfminer_logger).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def _compact_row(row) -> List[str]:
    """Strip None/blank cells and normalise whitespace, preserving order."""
    out = []
    for cell in row:
        if cell is None:
            continue
        text = ' '.join(str(cell).split())
        if text:
            out.append(text)
    return out


def _find_table_by_row_label(raw_tables: List[dict], label: str):
    """Return the first raw table entry containing a row whose first
    (compacted) cell exactly matches `label`."""
    for entry in raw_tables:
        for row in entry['rows']:
            compacted = _compact_row(row)
            if compacted and compacted[0] == label:
                return entry
    return None


def _row_lookup(entry: dict) -> Dict[str, List[str]]:
    """Map each row's first compacted cell -> remaining compacted cells,
    for a single extracted table."""
    lookup = {}
    for row in entry['rows']:
        compacted = _compact_row(row)
        if compacted:
            lookup[compacted[0]] = compacted[1:]
    return lookup


def _capacity_year_to_int(label: str) -> int:
    """'2026-27' -> 2026 (WEM capacity years are labelled by start year)."""
    return int(label[:4])


def _to_number(text: str):
    text = text.replace(',', '').strip()
    if text in ('', '-'):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def extract_raw_tables(pdf_path, pages: Optional[Sequence[int]] = None) -> List[dict]:
    """
    Generic pass-1 extraction: every table pdfplumber finds in the document,
    tagged with its page number and index-on-page for FR-F04 provenance
    (page_ref/table_ref). Does not attempt to interpret content.

    pages: optional 1-indexed page numbers to restrict extraction to (e.g.
    [40] for just page 40). Defaults to every page. Scanning a 100+ page
    report page-by-page is slow (multiple minutes) — pass `pages` whenever
    the caller already knows where its target table lives, rather than
    walking the whole document to find it again on every call. This
    matters most for a caller invoked inside a web request (see
    esoo_bias_views.py's Table 11 backcast, which runs on every page load
    with no caching): an unscoped scan there is slow enough to time out
    the request, not just slow.
    """
    pdf_path = Path(pdf_path)
    tables = []
    with pdfplumber.open(pdf_path) as pdf:
        if pages is not None:
            page_iter = ((p, pdf.pages[p - 1]) for p in pages)
        else:
            page_iter = enumerate(pdf.pages, start=1)
        for page_num, page in page_iter:
            for table_index, raw_table in enumerate(page.extract_tables()):
                tables.append({
                    'page': page_num,
                    'table_index': table_index,
                    'rows': raw_table,
                })
    logger.info(f"Extracted {len(tables)} raw table(s) from {pdf_path.name}" + (f" (pages {list(pages)})" if pages else ""))
    return tables


def _extract_2026(vintage, raw_tables: List[dict]) -> List[dict]:
    """
    FIGURE_EXTRACTORS mapper for the 2026 WEM ESOO PDF, built and verified
    against the actual downloaded document (see module docstring).
    """
    figures = []

    # --- Table 1 (p.5): executive summary — Expected scenario only ---
    t1 = _find_table_by_row_label(raw_tables, 'Forecast underlying consumption (TWh)')
    if t1 is None:
        logger.warning("2026 extractor: Table 1 ('Forecast underlying consumption (TWh)') not found")
    else:
        rows = _row_lookup(t1)
        years = rows['Capacity Year']

        def add_t1_series(row_label, metric, domain, demand_basis, unit, scale=1.0):
            values = rows.get(row_label)
            if values is None:
                logger.warning(f"2026 extractor: row '{row_label}' not found in Table 1")
                return
            for year_label, raw_value in zip(years, values):
                num = _to_number(raw_value)
                if num is None:
                    continue
                figures.append({
                    'domain': domain, 'metric': metric,
                    'forecast_year': _capacity_year_to_int(year_label),
                    'demand_growth_scenario': 'expected', 'poe_level': None,
                    'demand_basis': demand_basis, 'value': num * scale, 'unit': unit,
                    'table_ref': 'Table 1', 'page_ref': str(t1['page']),
                    'cell_ref': f"{row_label} / {year_label}",
                })

        add_t1_series('Forecast underlying consumption (TWh)', 'energy', 'demand', 'underlying', 'GWh', scale=1000)
        add_t1_series('Forecast Peak Reserve Capacity Target', 'rct', 'supply_adequacy', 'other', 'MW')
        add_t1_series('Forecast existing and committed peak capacity', 'capacity_outlook', 'supply_adequacy', 'other', 'MW')

    # --- Table 10 (p.39): peak/minimum operational demand — Expected scenario only ---
    t10 = _find_table_by_row_label(raw_tables, 'Summer peak (10% POE)')
    if t10 is None:
        logger.warning("2026 extractor: Table 10 ('Summer peak (10% POE)') not found")
    else:
        rows = _row_lookup(t10)
        year_re = re.compile(r'^20\d\d-\d\d$')
        years = None
        for row in t10['rows']:
            compacted = _compact_row(row)
            if len(compacted) >= 4 and all(year_re.match(x) for x in compacted):
                years = compacted
                break
        if years is None:
            logger.warning("2026 extractor: could not locate the year header row in Table 10")
        else:
            # Table 10 also lists two 'most recent actual' columns (not a
            # forecast) ahead of the genuine forecast years — skip those.
            forecast_years = {y for y in years if _capacity_year_to_int(y) >= vintage.year}

            def add_t10_series(row_label, metric, poe_level):
                values = rows.get(row_label)
                if values is None:
                    logger.warning(f"2026 extractor: row '{row_label}' not found in Table 10")
                    return
                for year_label, raw_value in zip(years, values):
                    if year_label not in forecast_years:
                        continue
                    num = _to_number(raw_value)
                    if num is None:
                        continue
                    figures.append({
                        'domain': 'demand', 'metric': metric,
                        'forecast_year': _capacity_year_to_int(year_label),
                        'demand_growth_scenario': 'expected', 'poe_level': poe_level,
                        'demand_basis': 'operational', 'value': num, 'unit': 'MW',
                        'table_ref': 'Table 10', 'page_ref': str(t10['page']),
                        'cell_ref': f"{row_label} / {year_label}",
                    })

            add_t10_series('Summer peak (10% POE)', 'peak_summer', 10)
            add_t10_series('Winter peak (10% POE)', 'peak_winter', 10)
            add_t10_series('Minimum (90% POE)', 'minimum', 90)

    return figures


# Registered per-vintage table -> figure mappers. Populate this during WS1
# once a vintage's actual table layout has been inspected (see module
# docstring). Signature:
#
#   extractor(vintage: EsooVintage, raw_tables: List[dict]) -> List[dict]
#
# Each returned dict should carry the keys EsooFigure expects: domain,
# metric, forecast_year, demand_growth_scenario, poe_level, demand_basis,
# value, unit, table_ref, page_ref, cell_ref. parse_esoo_pdf_to_figures()
# below fills in the remaining common provenance fields (source_document,
# source_version, extraction_date, extraction_method) from the vintage.
FIGURE_EXTRACTORS: Dict[int, Callable] = {
    2026: _extract_2026,
}


def parse_esoo_pdf_to_figures(vintage) -> List[dict]:
    """
    FR-F02 PDF-fallback entry point. Extracts raw tables, then hands them to
    the vintage's registered FIGURE_EXTRACTORS mapper.

    Raises NotImplementedError if no mapper is registered yet for this
    vintage year. This is intentional: it surfaces missing WS1
    reconnaissance work rather than silently emitting fabricated figures.
    """
    if not vintage.local_file_path:
        raise ValueError(
            f"EsooVintage {vintage.year} has no local_file_path; "
            f"fetch it first via ingest_esoo_vintage."
        )

    pdf_path = Path(settings.ESOO_ARCHIVE_DIR) / vintage.local_file_path
    raw_tables = extract_raw_tables(pdf_path)

    extractor = FIGURE_EXTRACTORS.get(vintage.year)
    if extractor is None:
        raise NotImplementedError(
            f"No FIGURE_EXTRACTORS mapping registered for ESOO {vintage.year}. "
            f"Extracted {len(raw_tables)} raw table(s) for manual inspection; "
            f"register a mapper in esoo_pdf_parser.FIGURE_EXTRACTORS once the "
            f"table layout is confirmed (see spec §11 OQ-1/OQ-2)."
        )

    figures = extractor(vintage, raw_tables)

    today = date.today()
    for figure in figures:
        figure.setdefault('source_document', vintage.local_file_path or f"WEM ESOO {vintage.year}")
        figure.setdefault('source_version', str(vintage.year))
        figure.setdefault('extraction_date', today)
        figure.setdefault('extraction_method', 'pdf')

    return figures


# ============================================================
# D4 heritage tier — IMO-era WEM Statement of Opportunities editions
# (pre-AEMO; archive currently covers 2006-2012).
#
# Format is fundamentally different from the modern AEMO Data Register
# (and from the modern-tier PDF tables above): plain narrative-report
# appendix tables, not clean spreadsheet cells. Confirmed by inspecting
# the 2006, 2009 and 2012 editions directly, appendix NUMBERING and even
# structure shift across vintages, the same lesson learned building the
# modern workbook extractor's SHEET_PLANS:
#   - 2006: one combined "Maximum Demand" appendix (no Summer/Winter
#     split), Appendix 3 (demand) + Appendix 4 (energy).
#   - 2009, 2012: separate Summer/Winter Maximum Demand appendices,
#     numbered differently in each edition (Appendix 2/3/4 in 2009,
#     Appendix 3/4/5 in 2012).
#   - Energy appendix wording varies too: "FORECAST OF SENT OUT ENERGY"
#     (2006), "Forecasts of Energy Sent-Out" (2009, hyphenated),
#     "Forecasts of Energy Sent Out ... Capacity Year" / "... Financial
#     Year" as TWO separate tables (2012 only).
# Rather than a per-vintage page/appendix-number config, this scans the
# whole document by CONTENT (the "<season> Maximum Demand Forecasts with
# <scenario> Economic Growth" and "Forecasts of ... Sent[- ]Out Energy
# ... (GWh)" header text is consistent even when appendix numbers and
# page layout aren't), the same principle as the SHEET_PLANS engine but
# applied to text instead of spreadsheet cells.
# ============================================================

_IMO_DEMAND_HEADER_RE = re.compile(
    r'(Summer\s+Maximum\s+Demand|Winter\s+Maximum\s+Demand|Maximum\s+Demand)\s+'
    r'Forecasts?\s+with\s+(Expected|High|Low)\s+Economic\s+Growth',
    re.IGNORECASE,
)
_IMO_ENERGY_HEADER_RE = re.compile(
    r'Forecasts?\s+of\s+(?:Energy\s+Sent[\s-]*Out|Sent[\s-]*Out\s+Energy)'
    r'.*?\(?GWh\)?(?:\s*[-–—]\s*(Capacity\s+Year|Financial\s+Year))?',
    re.IGNORECASE,
)
_IMO_DEMAND_COLHEADER_RE = re.compile(r'^(?:Year\s+)?(?:\d+%\s*Po?E\s*)+$', re.IGNORECASE)
_IMO_ENERGY_COLHEADER_RE = re.compile(r'^(?:Year\s+)?Expected\s+High\s+Low$', re.IGNORECASE)
_IMO_ROW_RE = re.compile(r'^(\d{4}(?:/\d{2})?)\s+(.+)$')
_IMO_NUMBER_RE = re.compile(r'-?[\d,]+(?:\.\d+)?')

_IMO_DEMAND_POE_ORDER = (10, 50, 90)
_IMO_ENERGY_SCENARIO_ORDER = ('expected', 'high', 'low')

# Table-of-contents entries repeat the exact same appendix heading text,
# followed by dot-leaders and a page number (e.g. 'Maximum Demand
# Forecasts with Expected Economic Growth (MW)..................v') --
# confirmed to false-trigger the header regexes above on the ToC page,
# many pages before the real appendix, corrupting everything in between
# with unrelated tables. A run of 2+ dots is a reliable, simple signature
# a genuine appendix heading never has.
_IMO_TOC_LEADER_RE = re.compile(r'\.{2,}')

# In 2009/2012, the Summer/Winter qualifier is repeated on the per-scenario
# sub-header ('Summer Maximum Demand Forecasts with Expected Economic
# Growth'). In 2008, it is NOT -- the sub-header is just 'Maximum Demand
# Forecasts with Expected Economic Growth' for BOTH its Summer and Winter
# appendices, with the season only stated once on the Appendix TITLE line
# ('Appendix 2 - Forecasts of Summer Maximum Demand' / 'Appendix 3 -
# Forecasts of Winter Maximum Demand'). Confirmed as a real bug: without
# tracking this separately, both appendices' sub-headers fell back to the
# same default season and silently collided on the same natural key, with
# the second table's values overwriting the first's. This title-line
# regex captures the season as a fallback for a sub-header that doesn't
# repeat it.
_IMO_APPENDIX_TITLE_SEASON_RE = re.compile(
    r'Appendix\s+\d+.*?Forecasts?\s+of\s+(Summer\s+Maximum\s+Demand|Winter\s+Maximum\s+Demand|Maximum\s+Demand)',
    re.IGNORECASE,
)

# A new 'Appendix N' heading unambiguously marks a transition to different
# content -- confirmed necessary after finding a real bug: the energy
# table on one page's Appendix 5 (Sent-out Energy) has no explicit 'end of
# table' marker, so the very next appendix's *different* table (Appendix
# 6, Generation and DSM Capacity -- 5 numeric columns, coincidentally also
# year-led) was silently consumed as more energy rows, overwriting correct
# data with bogus constants-per-year for every subsequent year. Reset
# state on ANY 'Appendix N' heading, even one this parser doesn't
# otherwise recognise, rather than only on a demand/energy header match.
_IMO_APPENDIX_HEADING_RE = re.compile(r'^Appendix\s+\d+\b', re.IGNORECASE)


def _imo_year_to_forecast_year(label: str) -> int:
    """'2012/13' -> 2012. A bare 'YYYY' label (used for Winter Maximum
    Demand rows in some vintages, e.g. 2012's '2012' vs its Summer
    table's '2012/13') is taken to denote the SAME capacity year, i.e.
    also forecast_year=int(label[:4]). This is an ASSUMPTION -- no IMO
    edition inspected so far states explicitly what the bare-year Winter
    label means -- not a confirmed fact; revisit if a vintage's own text
    ever clarifies it (heritage tier, D4/D7)."""
    return int(label[:4])


def _imo_clean_numbers(rest: str):
    """Return the numeric values in `rest` if `rest` is nothing BUT
    numbers (plus an optional '(Projected)'-style annotation) -- None
    otherwise. Guards against page furniture that happens to start with
    a 4-digit token, e.g. a running footer like '2009 Statement of
    Opportunities Report Page 50 of 56', being mistaken for a real data
    row (it would match _IMO_ROW_RE's leading-year pattern, but 'Page 50
    of 56' fails this cleanliness check and gets rejected)."""
    cleaned = re.sub(r'\((?:Projected|Estimate[d]?|Actual)\)', '', rest, flags=re.IGNORECASE)
    numbers = _IMO_NUMBER_RE.findall(cleaned)
    leftover = _IMO_NUMBER_RE.sub('', cleaned).strip()
    if leftover or not numbers:
        return None
    values = []
    for n in numbers:
        try:
            values.append(float(n.replace(',', '')))
        except ValueError:
            return None
    return values


def _imo_page_lines(pdf_path):
    """Yield (page_num, line_text) for every non-blank line, in reading
    order. Plain-text regex parsing (not extract_tables()) is the robust
    choice here: multiple scenario sub-tables can share a page without
    reliably separating into distinct pdfplumber Table objects, but the
    'with <Scenario> Economic Growth' header text in front of each one
    always does."""
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ''
            for line in text.split('\n'):
                line = line.strip()
                if line:
                    yield page_num, line


def _parse_imo_appendices(pdf_path):
    """Single pass producing raw (not yet EsooFigure-shaped) demand and
    energy rows tagged with page/scenario/metric context. See the
    heritage-tier section docstring above for why this is content-driven
    rather than a per-vintage page/appendix-number config."""
    demand_rows = []
    energy_rows = []

    demand_metric = None
    demand_scenario = None
    energy_variant = None  # 'capacity_year' | 'financial_year'
    energy_active = False
    appendix_season = None  # fallback season from the enclosing Appendix's title line

    for page_num, line in _imo_page_lines(pdf_path):
        if _IMO_TOC_LEADER_RE.search(line):
            continue  # table-of-contents entry, not a real appendix heading or data row

        title_season = _IMO_APPENDIX_TITLE_SEASON_RE.search(line)
        if title_season:
            season_text = title_season.group(1).lower()
            appendix_season = 'winter' if 'winter' in season_text else ('summer' if 'summer' in season_text else None)
            demand_metric = None
            energy_active = False
            continue

        dm = _IMO_DEMAND_HEADER_RE.search(line)
        if dm:
            season_text = dm.group(1).lower()
            if 'winter' in season_text:
                demand_metric = 'peak_winter'
            elif 'summer' in season_text:
                demand_metric = 'peak_summer'
            else:
                # Sub-header doesn't repeat the season itself (2008-style)
                # -- fall back to the enclosing Appendix title's season;
                # if that's also unset (2006/2007-style single combined
                # appendix, no Summer/Winter split at all), default to
                # peak_summer, matching the convention used throughout
                # this project for an unqualified/general system peak.
                demand_metric = 'peak_winter' if appendix_season == 'winter' else 'peak_summer'
            demand_scenario = dm.group(2).lower()
            energy_active = False
            continue

        em = _IMO_ENERGY_HEADER_RE.search(line)
        if em:
            variant_text = (em.group(1) or '').lower()
            energy_variant = 'financial_year' if 'financial' in variant_text else 'capacity_year'
            energy_active = True
            demand_metric = None
            continue

        if _IMO_APPENDIX_HEADING_RE.match(line):
            # A new appendix that ISN'T itself a demand/energy header we
            # recognise -- e.g. 'Appendix 6 Generation and DSM Capacity'.
            # Stop treating subsequent rows as belonging to whatever table
            # was active before.
            demand_metric = None
            appendix_season = None
            energy_active = False
            continue

        if _IMO_DEMAND_COLHEADER_RE.match(line) or _IMO_ENERGY_COLHEADER_RE.match(line):
            continue  # column-header line, not data

        row_match = _IMO_ROW_RE.match(line)
        if not row_match:
            continue
        year_label, rest = row_match.groups()
        values = _imo_clean_numbers(rest)
        if values is None:
            continue

        if energy_active:
            energy_rows.append({
                'page': page_num, 'variant': energy_variant,
                'year_label': year_label, 'values': values[:3],
            })
        elif demand_metric:
            demand_rows.append({
                'page': page_num, 'metric': demand_metric, 'scenario': demand_scenario,
                'year_label': year_label, 'values': values[:3],
            })

    return demand_rows, energy_rows


def parse_imo_heritage_pdf_to_figures(vintage) -> List[dict]:
    """
    D4 heritage-tier PDF extraction entry point for IMO-era WEM SOO
    editions. See the section docstring above for the format differences
    from the modern-tier extractors this parses instead of.

    Demand basis: IMO reports 'Sent Out Energy' and 'Maximum Demand' --
    mapped to this schema's 'operational' basis (grid-supplied) as the
    closest available match, per FR-F07, but NOT confirmed identical to
    AEMO's later operational definition; every figure carries that
    caveat in reconciliation_adjustment rather than asserting equivalence
    silently.

    Raises ValueError if no recognisable appendix content is found at
    all -- surfacing an unfamiliar layout rather than silently returning
    nothing (FR-F07: "without fabricating precision").
    """
    if not vintage.local_file_path:
        raise ValueError(f"EsooVintage {vintage.year} has no local_file_path; fetch it first.")

    pdf_path = Path(settings.ESOO_ARCHIVE_DIR) / vintage.local_file_path
    demand_rows, energy_rows = _parse_imo_appendices(pdf_path)

    if not demand_rows and not energy_rows:
        raise ValueError(
            f"No IMO-style demand/energy appendix tables found in {vintage.local_file_path} -- "
            f"layout may differ from the 2006/2009/2012 editions this parser was built against; "
            f"inspect the PDF directly before extending _IMO_DEMAND_HEADER_RE/_IMO_ENERGY_HEADER_RE."
        )

    figures = []
    basis_note = (
        "IMO-era 'Sent Out'/'Maximum Demand' terminology mapped to this project's "
        "operational basis as the closest available match (heritage tier, D4) -- not "
        "confirmed identical to AEMO's later operational definition."
    )

    for row in demand_rows:
        for poe_level, value in zip(_IMO_DEMAND_POE_ORDER, row['values']):
            figures.append({
                'domain': 'demand', 'metric': row['metric'],
                'forecast_year': _imo_year_to_forecast_year(row['year_label']),
                'demand_growth_scenario': row['scenario'], 'poe_level': poe_level,
                'demand_basis': 'operational', 'value': value, 'unit': 'MW',
                'table_ref': f"Appendix ({row['metric']}, {row['scenario']})",
                'page_ref': str(row['page']), 'cell_ref': f"{row['year_label']} / POE{poe_level}",
                'reconciliation_adjustment': basis_note,
            })

    # Prefer the Capacity Year energy table over a Financial Year one when
    # a vintage publishes both (2012-style) -- matches this project's
    # established forecast_year convention (WEM Capacity Year, Oct-Oct)
    # rather than whichever table happened to print first in the PDF.
    variants_present = {row['variant'] for row in energy_rows}
    energy_variant_to_use = 'capacity_year' if 'capacity_year' in variants_present else 'financial_year'

    for row in energy_rows:
        if row['variant'] != energy_variant_to_use:
            continue
        for scenario, value in zip(_IMO_ENERGY_SCENARIO_ORDER, row['values']):
            figures.append({
                'domain': 'demand', 'metric': 'energy',
                'forecast_year': _imo_year_to_forecast_year(row['year_label']),
                'demand_growth_scenario': scenario, 'poe_level': None,
                'demand_basis': 'operational', 'value': value, 'unit': 'GWh',
                'table_ref': f"Appendix (energy sent out, {row['variant']})",
                'page_ref': str(row['page']), 'cell_ref': f"{row['year_label']} / {scenario}",
                'reconciliation_adjustment': basis_note,
            })

    today = date.today()
    for figure in figures:
        figure.setdefault('source_document', vintage.local_file_path)
        figure.setdefault('source_version', str(vintage.year))
        figure.setdefault('extraction_date', today)
        figure.setdefault('extraction_method', 'pdf')

    return figures
