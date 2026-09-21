# powermatchui/utils/iasr_ev_energy.py
"""
WEM EV charging energy from AEMO's 2025 IASR Electric Vehicle workbook.

The workbook's "WEM" region gives BEV + PHEV consumption (GWh) by financial year
for three scenarios (Slower Growth / Step Change / Accelerated Transition):
"2025 CSIRO trajectories developed for AEMO". It is SWIS-wide already, so unlike
the older 2022 CSIRO postcode files (EvUptakePostcodeFigure) no postcode
aggregation or boundary apportionment is needed. The EV load builder uses it as
its annual-energy source; the EV load already inside an ESOO base uses the same
data (esoo_embedded_ev.py).

The page's Low / Medium / High keys map to the IASR scenarios below. That mapping
is a working hypothesis (Medium ~ Step Change, AEMO's central planning anchor), the
same axis-mismatch caveat recorded on parse_wem_annual_totals.
"""
from functools import lru_cache
from pathlib import Path
from typing import Iterator, Tuple

import openpyxl
from django.conf import settings

CSIRO_TO_IASR = {
    'low': 'Slower Growth',
    'medium': 'Step Change',
    'high': 'Accelerated Transition',
}

# Display labels for the page's scenario keys (the model's stored keys stay low/medium/high).
SCENARIO_LABELS = [
    ('low', 'Low — IASR Slower Growth'),
    ('medium', 'Medium — IASR Step Change'),
    ('high', 'High — IASR Accelerated Transition'),
]

CONSUMPTION_SHEET = 'BEV_PHEV_Consumption (GWh)'


class IasrDataNotAvailableError(ValueError):
    """No registered IASR EV workbook can supply the requested WEM figure."""


@lru_cache(maxsize=8)
def _iasr_wem_gwh(path: str, mtime: float, trajectory: str) -> dict:
    """{first year of the financial year: BEV+PHEV GWh} for the WEM region. Cached per file version."""
    # Imported here so a plain import of this module doesn't pull in the powerplotui parser.
    from powerplotui.services.ev_charging_profile_parser import parse_wem_annual_totals
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        return parse_wem_annual_totals(wb, CONSUMPTION_SHEET, trajectory, 'WEM')
    finally:
        wb.close()


def _iasr_workbooks() -> Iterator[Tuple[object, Path]]:
    """Registered AEMO IASR EV workbooks on disk, newest EV vintage first."""
    from siren_web.models import SourceDocument
    docs = (
        SourceDocument.objects.filter(doc_type='aemo_isp_step_change', ev_vintage__isnull=False)
        .exclude(local_file_path='')
        .select_related('ev_vintage')
        .order_by('-ev_vintage__version')
    )
    for doc in docs:
        path = Path(settings.EV_ARCHIVE_DIR) / doc.local_file_path
        if path.exists():
            yield doc, path


def iasr_wem_energy_mwh(trajectory: str, forecast_year: int) -> Tuple[float, str]:
    """(annual BEV+PHEV energy in MWh, source description) for one IASR trajectory and
    forecast year (the financial year's first year: 2035 = 2035-36)."""
    tried = []
    for doc, path in _iasr_workbooks():
        try:
            totals = _iasr_wem_gwh(str(path), path.stat().st_mtime, trajectory)
        except Exception as e:  # unreadable/older layout -- try the next workbook
            tried.append(f"{doc.local_file_path}: {e}")
            continue
        if forecast_year in totals:
            gwh = totals[forecast_year]
            return gwh * 1000.0, (
                f"AEMO IASR EV workbook ({doc.ev_vintage.version}), WEM region, {trajectory} "
                f"({gwh:,.0f} GWh, BEV+PHEV)"
            )
    detail = f" ({'; '.join(tried)})" if tried else ''
    raise IasrDataNotAvailableError(
        f"No registered AEMO IASR EV workbook has a WEM '{trajectory}' figure for {forecast_year}{detail}. "
        "The workbook covers financial years 2025-26 to 2054-55; register it with register_local_ev_files if missing."
    )


def scenario_energy_mwh(csiro_scenario: str, forecast_year: int) -> Tuple[float, str]:
    """Annual EV energy for the page's Low / Medium / High scenario (via CSIRO_TO_IASR)."""
    trajectory = CSIRO_TO_IASR.get(csiro_scenario)
    if trajectory is None:
        raise IasrDataNotAvailableError(f"No IASR trajectory is mapped to EV scenario '{csiro_scenario}'.")
    return iasr_wem_energy_mwh(trajectory, forecast_year)
