# powerplotui/services/dot_wa_ev_parser.py
"""
FR-19 — parse the WA Department of Transport and Major Infrastructure
quarterly "electric vehicle licensing data" PDF into a cumulative
fleet-stock series (BEV / PHEV / Total by quarter-end).

Source: transport.wa.gov.au/projects/western-australian-electric-vehicle-registrations
(one PDF per quarter, `PROJ_P_WA_EV_analysis_summary_<Month>_<Year>.pdf`).

Extraction strategy — deliberately ONE reliable path, not a stack of
brittle fallbacks:

  The modern PDFs carry "Figure 1b: Table - Cumulative electric vehicle
  data", a clean 4-column table (Period | BEV | PHEV | Total) that
  pdfplumber lifts verbatim. Crucially this table is *fully backfilled*
  every quarter (Dec-21 onward), so the latest PDF alone reconstructs the
  whole series; each new quarter just appends one row. The modern series
  is semi-annual (Jun/Dec rows only) even though the PDFs are quarterly.

  Older PDFs (pre~2025) have only the Figure 1 *chart* — its data labels
  render as scrambled digit runs that cannot be parsed reliably. For
  those, parse_actuals_pdf returns an empty series; the caller keeps the
  document for provenance and moves on (the current PDF's table already
  covers that history). callers that get an empty series from EVERY PDF
  should treat that as a failure (the table layout changed again).

No FCEV: DoT suppresses FCEV counts (low volume, re-identification risk),
so Total == BEV + PHEV in this source. That identity is asserted per row.
"""
import calendar
import datetime as _dt
import re
from pathlib import Path
from typing import List, Optional

import pdfplumber

_FIG1B_HEADER = ('period', 'bev', 'phev', 'total')

_MONTHS = {
    'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3,
    'apr': 4, 'april': 4, 'may': 5, 'jun': 6, 'june': 6, 'jul': 7, 'july': 7,
    'aug': 8, 'august': 8, 'sep': 9, 'sept': 9, 'september': 9,
    'oct': 10, 'october': 10, 'nov': 11, 'november': 11, 'dec': 12, 'december': 12,
}

# e.g. PROJ_P_WA_EV_analysis_summary_Sept_2025.pdf
#      PROJ_P_WA_EV_analysis_summary_Dec_2023_quarter.pdf
_FILENAME_RE = re.compile(
    r'analysis_summary_([A-Za-z]+)[_ ](\d{4})', re.IGNORECASE
)


class DotWaEvParseError(ValueError):
    pass


def _end_of_month(year: int, month: int) -> _dt.date:
    return _dt.date(year, month, calendar.monthrange(year, month)[1])


def period_end_from_filename(filename: str) -> Optional[_dt.date]:
    """'..._Sept_2025.pdf' -> date(2025, 9, 30). None if unrecognised."""
    m = _FILENAME_RE.search(Path(filename).name)
    if not m:
        return None
    month = _MONTHS.get(m.group(1).lower())
    if not month:
        return None
    return _end_of_month(int(m.group(2)), month)


def quarter_label_from_date(d: _dt.date) -> str:
    """date(2025, 12, 31) -> 'Dec 2025'."""
    return f"{calendar.month_abbr[d.month]} {d.year}"


def _period_token_to_date(token: str) -> Optional[_dt.date]:
    """Figure 1b 'Period' cell, e.g. 'Dec-21' / 'Jun-25' -> quarter-end date."""
    token = token.strip().replace('–', '-').replace('—', '-')
    m = re.match(r'^([A-Za-z]{3,9})[-/ ](\d{2,4})$', token)
    if not m:
        return None
    month = _MONTHS.get(m.group(1).lower())
    if not month:
        return None
    yr = int(m.group(2))
    if yr < 100:
        yr += 2000
    return _end_of_month(yr, month)


def _to_number(cell) -> Optional[float]:
    if cell is None:
        return None
    s = str(cell).strip().replace(',', '').replace(' ', '')
    if not s or not re.match(r'^-?\d+(\.\d+)?$', s):
        return None
    return float(s)


def _looks_like_fig1b(table) -> bool:
    if not table or not table[0]:
        return False
    header = [str(c).strip().lower() if c else '' for c in table[0]]
    return tuple(h for h in header if h) == _FIG1B_HEADER


def _parse_prepared_date(full_text: str) -> Optional[_dt.date]:
    """
    Pull the report's "prepared" date. Layout varies across vintages:
      'Prepared by Department of Transport and Major Infrastructure\\n9 February 2026'
      'Prepared by Department of Transport\\n...\\nDate 23 January 2025'
      'Prepared by Department of Transport\\n9 September 2024'
    """
    date_re = r'(\d{1,2}\s+[A-Za-z]+\s+\d{4})'
    candidates = []
    m = re.search(r'Prepared by Department of Transport[^\n]*\n\s*' + date_re, full_text)
    if m:
        candidates.append(m.group(1))
    m = re.search(r'\bDate\s+' + date_re, full_text)
    if m:
        candidates.append(m.group(1))
    for raw in candidates:
        for fmt in ('%d %B %Y', '%d %b %Y'):
            try:
                return _dt.datetime.strptime(raw.strip(), fmt).date()
            except ValueError:
                continue
    return None


def parse_actuals_pdf(path) -> dict:
    """
    Parse one DoT WA quarterly EV PDF.

    Returns a dict:
      {
        'quarter_label': 'Dec 2025',
        'period_end': date(2025, 12, 31),          # this report's quarter
        'report_prepared_date': date(2026, 2, 9),  # or None
        'series': [                                # may be empty (old layout)
          {'period_end': date(2021, 12, 31), 'bev': 3095.0,
           'phev': 675.0, 'total': 3770.0},
          ...
        ],
      }

    Raises DotWaEvParseError only for an unreadable / zero-page file — a
    readable PDF with no Figure 1b table yields series=[] (not an error).
    """
    path = Path(path)
    try:
        pdf = pdfplumber.open(path)
    except Exception as e:  # noqa: BLE001 - pdfplumber raises assorted types
        raise DotWaEvParseError(f"cannot open {path.name}: {e}") from e

    with pdf:
        if not pdf.pages:
            raise DotWaEvParseError(f"{path.name} has no pages")
        full_text = '\n'.join((p.extract_text() or '') for p in pdf.pages)
        series_rows: List[dict] = []
        seen = set()
        for page in pdf.pages:
            for table in page.extract_tables():
                if not _looks_like_fig1b(table):
                    continue
                for row in table[1:]:
                    if not row or not row[0]:
                        continue
                    period_end = _period_token_to_date(str(row[0]))
                    if period_end is None or period_end in seen:
                        continue
                    cells = [_to_number(c) for c in row[1:] if str(c or '').strip() != '']
                    if len(cells) < 3:
                        continue
                    bev, phev, total = cells[0], cells[1], cells[2]
                    if None in (bev, phev, total):
                        continue
                    if abs((bev + phev) - total) > 1.0:
                        raise DotWaEvParseError(
                            f"{path.name}: Figure 1b row {row[0]!r} fails "
                            f"BEV+PHEV==Total ({bev}+{phev} != {total})"
                        )
                    seen.add(period_end)
                    series_rows.append({
                        'period_end': period_end, 'bev': bev,
                        'phev': phev, 'total': total,
                    })

    series_rows.sort(key=lambda r: r['period_end'])
    for a, b in zip(series_rows, series_rows[1:]):
        if b['total'] < a['total']:
            raise DotWaEvParseError(
                f"{path.name}: cumulative Total decreases "
                f"{a['period_end']} ({a['total']}) -> {b['period_end']} ({b['total']})"
            )

    period_end = period_end_from_filename(path.name)
    if period_end is None and series_rows:
        period_end = series_rows[-1]['period_end']
    if period_end is None:
        raise DotWaEvParseError(
            f"{path.name}: cannot determine the report quarter from the "
            "filename or a Figure 1b table"
        )

    return {
        'quarter_label': quarter_label_from_date(period_end),
        'period_end': period_end,
        'report_prepared_date': _parse_prepared_date(full_text),
        'series': series_rows,
    }
