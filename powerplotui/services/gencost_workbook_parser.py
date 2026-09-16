# powerplotui/services/gencost_workbook_parser.py
"""
Parses a CSIRO GenCost "Appendix Tables" workbook into GencostCostFigure
rows. This is a human-report export (merged cells, per-table bespoke
headers), not a flat machine-friendly table -- see the module-level notes
below for the layout inspected in GenCost2025-26FinalApxTables.

Phase 1 (this module): only the capital-cost-by-scenario tables (named
"Apx Table B.1/B.2/B.3" in the 2025-26 edition, but sheet numbering shifts
between editions -- matched by title text, not sheet name). Each is a
clean single-header-row grid: technology names across columns, years down
rows, one sheet per cost case (the case name is embedded in the sheet's
title cell). Deliberately NOT handling (see plan doc for rationale):
  - battery/PHES storage cost tables (duration x scenario x component,
    multi-level merged headers, no single "technology" column)
  - the LCOE assumptions/outputs sheet (constants, not a year time series,
    crammed together with a separate LCOE-by-year table on one sheet)
  - the hydrogen electrolyser table (scenario x technology x year, its own
    two-level header layout)
"""
import logging
import re
from pathlib import Path
from typing import List

import openpyxl

logger = logging.getLogger(__name__)

_TITLE_RE = re.compile(r'capital costs? under the (.+?) scenario', re.IGNORECASE)

_CASE_SLUG_MAP = {
    'current policies': 'current_policies',
    'global nze by 2050': 'global_nze_2050',
    'global nze post 2050': 'global_nze_post_2050',
}


def _slugify_case(native_label: str) -> str:
    return _CASE_SLUG_MAP.get(native_label.strip().lower(), 'other')


def open_workbook(path):
    """Open a workbook for raw row-level access (data_only=True reads
    Excel's cached formula results rather than the formulas themselves)."""
    return openpyxl.load_workbook(Path(path), read_only=True, data_only=True)


def _find_title(ws, max_row=6) -> str | None:
    """GenCost's title cell isn't at a fixed row/column across sheets --
    scan the first few rows for the first non-empty string cell."""
    for row in ws.iter_rows(min_row=1, max_row=max_row, values_only=True):
        for cell in row:
            if isinstance(cell, str) and cell.strip():
                return cell.strip()
    return None


def parse_capex_sheets(wb) -> List[dict]:
    """
    Find every sheet whose title matches the capital-cost-by-scenario
    pattern and extract (raw_technology_label, cost_case, 'capex',
    financial_year, value, unit) tuples from each.
    """
    figures = []

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        title = _find_title(ws)
        if not title:
            continue
        m = _TITLE_RE.search(title)
        if not m:
            continue

        cost_case = _slugify_case(m.group(1))
        rows = list(ws.iter_rows(values_only=True))

        # Header row: first row (after the title) with more than one
        # non-empty string cell from column C onward (column B holds the
        # year in data rows, so the technology-name row is identified by
        # its column B cell NOT being a year/int).
        header_row_idx = None
        for i, row in enumerate(rows):
            tech_names = [c for c in row[2:] if isinstance(c, str) and c.strip()]
            if len(tech_names) >= 2:
                header_row_idx = i
                break
        if header_row_idx is None:
            logger.warning(f"'{sheet_name}': couldn't find a technology-name header row, skipped")
            continue

        header = rows[header_row_idx]
        tech_columns = {
            col_idx: name.strip()
            for col_idx, name in enumerate(header)
            if col_idx >= 2 and isinstance(name, str) and name.strip()
        }

        # Unit row: the row immediately after the header, if it's all
        # unit-like strings (e.g. '$/kW') rather than numeric data.
        unit_row_idx = header_row_idx + 1
        units = {}
        if unit_row_idx < len(rows):
            candidate = rows[unit_row_idx]
            if all(
                candidate[c] is None or isinstance(candidate[c], str)
                for c in tech_columns
            ):
                units = {c: (candidate[c] or '').strip() for c in tech_columns}
                data_start = unit_row_idx + 1
            else:
                data_start = unit_row_idx
        else:
            data_start = unit_row_idx

        for row in rows[data_start:]:
            year = row[1] if len(row) > 1 else None
            if not isinstance(year, (int, float)):
                continue
            year = int(year)
            for col_idx, tech_label in tech_columns.items():
                if col_idx >= len(row):
                    continue
                value = row[col_idx]
                if value is None:
                    continue
                figures.append({
                    'raw_technology_label': tech_label,
                    'cost_case': cost_case,
                    'cost_component': 'capex',
                    'financial_year': year,
                    'value': float(value),
                    'unit': units.get(col_idx, '$/kW'),
                    'sheet_ref': sheet_name,
                })

        logger.info(f"'{sheet_name}' ({title}): {len(tech_columns)} technologies, cost_case={cost_case}")

    return figures
