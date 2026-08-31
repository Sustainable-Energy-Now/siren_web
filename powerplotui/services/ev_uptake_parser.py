# powerplotui/services/ev_uptake_parser.py
"""
FR-01/FR-20 — parse the real CSIRO EV Uptake Projections postcode
dataset (CSIRO Data Shop, agdatashop.csiro.au/ev-uptake-projections)
into EvUptakePostcodeFigure-shaped dicts.

Replaces an earlier, purely speculative single-file CSV/XLSX contract
written before any real CSIRO export had been inspected. The real
release (verified 2026-08-26 against a WA download dated 2022-07-03) is
genuinely five separate files, one per TECH_TYPE, registered as
SourceDocument(doc_type='csiro_postcode_fleet_csv') rows under one
EvVintage — not a single "core dataset" file:

  FLEET_CONSUMPTION_PROJECTIONS_{BEV,PHEV,HV,HYB,ICE}_POSTCODE_WA_*.csv
  columns: MONTH, YEAR, TECH_TYPE, VEHICLE_TYPE, UNIT, SCENARIO, POSTCODE, VALUE

TECH_TYPE (confirmed via the release's own ScenarioAssumptions.xlsx
"Data label definitions" sheet): BEV = battery-electric, PHEV =
plug-in hybrid, HV = hydrogen vehicle (FCEV), ICE = internal combustion,
HYB = non-plug-in hybrid. Only BEV/PHEV/HV are EVs or EV-adjacent; ICE
and non-plug-in HYB are excluded entirely (not this pipeline's concern).
HV consumption (UNIT='MWh') is electrolysis energy, not grid charging —
D10 excludes it ("H2-electrolysis out of scope"); HV's fleet count
(UNIT='Number') is kept as context, folded into fleet_count alongside
BEV/PHEV, per D10 ("FCEV fleet rows retained as context, zero charging
load") and D6 ("fleet numbers retained for context/tracking, not the
primary driver").

MONTH is 'Jun' or 'Dec' (semi-annual snapshots). Checked against real
values for the same postcode/scenario across years: Dec is consistently
~10-30% above Jun of the same calendar year, not ~2x -- i.e. both are
independently-computed ANNUAL run-rate snapshots reflecting the fleet as
it stood at that month (confirmed by the source's own field definition:
UNIT=MWh is "Annual cumulative electricity consumption to the month"),
not a half-year partial sum that resets each January. Dec is used by
default as the more mature/complete snapshot for a given calendar year.

No privacy-suppression marker (column or sentinel value) was found in
this real export -- FR-20's EvSuppressionFlag is therefore not populated
from this source; this parser always returns an empty suppression list.
If a future CSIRO release turns out to suppress small-count cells
differently, revisit this.
"""
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

TECH_TYPES_FOR_CONSUMPTION = {'BEV', 'PHEV'}          # grid-charging EVs (D6)
TECH_TYPES_FOR_FLEET_CONTEXT = {'BEV', 'PHEV', 'HV'}  # + FCEV context (D10)
SCENARIO_MAP = {'LOW': 'low', 'MEDIUM': 'medium', 'HIGH': 'high'}
DEFAULT_SNAPSHOT_MONTH = 'Dec'


class EvUptakeParseError(ValueError):
    pass


def parse_ev_postcode_dataset_to_figures(
    vintage, archive_dir: Path, month: str = DEFAULT_SNAPSHOT_MONTH,
) -> Tuple[List[dict], List[dict]]:
    """
    Reads every csiro_postcode_fleet_csv SourceDocument registered
    under `vintage`, and returns (figures, suppression_flags) as plain
    dicts ready for EvUptakePostcodeFigure.objects.update_or_create(...)
    / EvSuppressionFlag.objects.update_or_create(...) (the latter always
    empty — see module docstring).
    """
    from siren_web.models import SourceDocument  # local import: keeps this module importable without Django configured, matching ev_charging_profile_parser's layering

    docs = SourceDocument.objects.filter(ev_vintage=vintage, doc_type='csiro_postcode_fleet_csv')
    if not docs:
        raise EvUptakeParseError(
            f"No csiro_postcode_fleet_csv SourceDocument rows registered under vintage '{vintage.version}' "
            "— run register_local_ev_files first."
        )

    fleet_frames, consumption_frames = [], []
    for doc in docs:
        path = archive_dir / doc.local_file_path
        if not path.exists():
            raise EvUptakeParseError(f"{path} does not exist")

        df = pd.read_csv(path, dtype={'POSTCODE': str, 'SCENARIO': str, 'TECH_TYPE': str, 'MONTH': str})
        df = df[df['MONTH'] == month]
        if df.empty:
            continue

        fleet_df = df[(df['UNIT'] == 'Number') & (df['TECH_TYPE'].isin(TECH_TYPES_FOR_FLEET_CONTEXT))]
        if not fleet_df.empty:
            fleet_frames.append(fleet_df.groupby(['POSTCODE', 'YEAR', 'SCENARIO'])['VALUE'].sum())

        consumption_df = df[(df['UNIT'] == 'MWh') & (df['TECH_TYPE'].isin(TECH_TYPES_FOR_CONSUMPTION))]
        if not consumption_df.empty:
            consumption_frames.append(consumption_df.groupby(['POSTCODE', 'YEAR', 'SCENARIO'])['VALUE'].sum())

    if not fleet_frames and not consumption_frames:
        raise EvUptakeParseError(f"No usable rows found for month='{month}' across {len(docs)} registered file(s)")

    fleet_total = pd.concat(fleet_frames).groupby(level=[0, 1, 2]).sum() if fleet_frames else None
    consumption_total = pd.concat(consumption_frames).groupby(level=[0, 1, 2]).sum() if consumption_frames else None

    keys = set(fleet_total.index if fleet_total is not None else []) | \
        set(consumption_total.index if consumption_total is not None else [])

    figures = []
    for postcode, year, scenario in keys:
        csiro_scenario = SCENARIO_MAP.get(scenario)
        if csiro_scenario is None:
            continue  # unrecognised scenario label -- not this pipeline's Low/Medium/High axis (D1)

        fleet_count = float(fleet_total.get((postcode, year, scenario), 0.0)) if fleet_total is not None else None
        consumption_mwh = float(consumption_total.get((postcode, year, scenario), 0.0)) if consumption_total is not None else None

        figures.append({
            'postcode': str(postcode), 'forecast_year': int(year), 'csiro_scenario': csiro_scenario,
            'fleet_count': fleet_count,
            'consumption_kwh': (consumption_mwh * 1000.0) if consumption_mwh is not None else None,
            'source_version': vintage.version, 'extraction_method': 'structured',
        })

    return figures, []


def parse_wa_summary_to_published_aggregates(
    vintage, archive_dir: Path, month: str = DEFAULT_SNAPSHOT_MONTH,
) -> Dict[Tuple[str, int], float]:
    """
    FR-07 pipeline-fidelity check: parses the vintage's registered
    csiro_summary SourceDocument (WA_SUMMARY_*.csv — CSIRO's own
    already-aggregated WA-STATEWIDE total, columns MONTH/YEAR/STATE/
    TECH_TYPE/VEHICLE_TYPE/UNIT/SCENARIO/VALUE, no POSTCODE column) into
    {(csiro_scenario, forecast_year): mwh}, using the same TECH_TYPE
    filter (BEV+PHEV only, D6) and month convention (Dec, see module
    docstring) as parse_ev_postcode_dataset_to_figures, so the two totals
    are directly comparable via
    powermatchui.utils.ev_reconciliation.aggregate_statewide_annual_energy.
    """
    from siren_web.models import SourceDocument

    doc = SourceDocument.objects.filter(ev_vintage=vintage, doc_type='csiro_summary').first()
    if doc is None:
        raise EvUptakeParseError(
            f"No csiro_summary SourceDocument registered under vintage '{vintage.version}' "
            "— run register_local_ev_files first."
        )
    path = archive_dir / doc.local_file_path
    if not path.exists():
        raise EvUptakeParseError(f"{path} does not exist")

    df = pd.read_csv(path, dtype={'SCENARIO': str, 'TECH_TYPE': str, 'MONTH': str})
    df = df[(df['MONTH'] == month) & (df['UNIT'] == 'MWh') & (df['TECH_TYPE'].isin(TECH_TYPES_FOR_CONSUMPTION))]
    if df.empty:
        raise EvUptakeParseError(f"No usable rows found in {path} for month='{month}'")

    grouped = df.groupby(['YEAR', 'SCENARIO'])['VALUE'].sum()

    published: Dict[Tuple[str, int], float] = {}
    for (year, scenario), mwh in grouped.items():
        csiro_scenario = SCENARIO_MAP.get(scenario)
        if csiro_scenario is None:
            continue
        published[(csiro_scenario, int(year))] = float(mwh)

    return published
