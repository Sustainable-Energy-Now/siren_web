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
