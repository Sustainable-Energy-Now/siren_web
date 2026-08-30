# powerplotui/services/ev_charging_profile_parser.py
"""
FR-03 — parse AEMO's real IASR EV workbook (e.g.
aemo-2025-iasr-ev-workbook.xlsx) into EvChargingProfile-shaped dicts.

Replaces an earlier, purely speculative generic-CSV contract written
before any real AEMO file had been inspected. The real workbook's shape
was mapped out directly (openpyxl) against the 2023 and 2025 IASR EV
workbooks:

  - 'BEV_PHEV_Charge_Type (%)': nested Region > Scenario > row blocks,
    each row labelled "<vehicle_group> - <charging_type_label>" (vehicle_group
    in {Residential, Commercial, Buses and Trucks}), columns are financial
    years ('2025-26', ...) holding the fraction of fleet using that
    charging type that year.
  - 'BEV_PHEV_Profile_kW (Weekday)' / '(Weekend)': nested Region > row
    blocks (no scenario axis -- a single Step Change-scenario snapshot,
    per the sheet's own note, e.g. "for a weekday in January 2040 (Step
    Change)"), each row labelled "<vehicle_class>, <charging_type_label>"
    (a finer 10-class vehicle breakdown than the % sheet's 3 groups),
    columns are the 48 half-hourly kW/vehicle values.

The 2025 workbook is the first vintage to publish a 'WEM' region
alongside the five NEM regions -- i.e. a genuine WA-specific charging
profile, resolving obstacle O5 for charging BEHAVIOUR (O5 remains live
for any earlier vintage that lacks a WEM row, where a NEM region must be
borrowed and documented as a stated limitation instead).

AEMO's charging-type label vocabulary drifts between vintages (2023:
Convenience/Daytime/Nighttime/Highway Fast/Coordinated Charging; 2025:
Unscheduled/TOU Grid Solar/Public/Off-peak and Solar/TOU Dynamic
Charging). classify_charging_mode() below buckets by keyword match
against both vocabularies rather than an exact-label enum, so it
degrades to 'other' (excluded downstream) on an unrecognised future
label rather than mis-bucketing it silently.
"""
from collections import defaultdict
from typing import Dict, List, Optional

INTERVALS_PER_DAY = 48

# Keyword sets checked case-insensitively against the raw charging_type
# label. V2X is checked first since "Vehicle to Grid"/"Vehicle to Home"
# would otherwise not collide with the other buckets, but is listed first
# for clarity that it takes priority.
V2X_KEYWORDS = ('vehicle to home', 'vehicle to grid')
MANAGED_KEYWORDS = ('tou', 'off-peak', 'off peak', 'coordinated')
UNMANAGED_KEYWORDS = ('unscheduled', 'convenience', 'public', 'daytime', 'nighttime', 'highway fast')


class EvChargingProfileParseError(ValueError):
    pass


# Region-header rows and scenario-header rows are both formatted as
# (label in column B, nothing in column C) in these sheets -- e.g. 'WEM'
# immediately followed by 'Slower Growth' -- so a naive "column C is
# empty" scan misidentifies a scenario header as the next region
# boundary. Restricting region-boundary detection to this known label
# set (both sheets' slightly different NSW wording included) avoids that.
KNOWN_REGION_LABELS = frozenset({
    'New South Wales', 'New South Wales (includes ACT)',
    'Queensland', 'South Australia', 'Tasmania', 'Victoria', 'WEM',
})


def classify_charging_mode(charging_type_label: str) -> str:
    label = charging_type_label.lower()
    if any(k in label for k in V2X_KEYWORDS):
        return 'v2x'
    if any(k in label for k in MANAGED_KEYWORDS):
        return 'managed'
    if any(k in label for k in UNMANAGED_KEYWORDS):
        return 'unmanaged'
    return 'other'


def _find_region_block(ws, region: str):
    """Return (start_row, end_row) exclusive of the next top-level region
    header, for sheets where region headers are rows with a label in
    column B and nothing in column C."""
    region_rows = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        c1, c2 = row[1], row[2]
        if c1 and c2 is None and str(c1).strip() in KNOWN_REGION_LABELS:
            region_rows.append((i, str(c1).strip()))
    matches = [i for i, label in region_rows if label == region]
    if not matches:
        available = sorted({label for _, label in region_rows})
        raise EvChargingProfileParseError(f"Region '{region}' not found. Available: {available}")
    start = matches[0]
    later = [i for i, _ in region_rows if i > start]
    end = min(later) if later else None
    return start, end


def parse_profile_kw_sheet(ws, region: str) -> Dict[str, List[float]]:
    """
    Parses one BEV_PHEV_Profile_kW sheet for `region`, averaging kW/vehicle
    shapes across whichever vehicle classes share the same charging_type_label
    (D6: vehicle-class detail is context only, not primary driver this Sprint).
    Returns {charging_type_label: [48 raw kW/vehicle values, un-normalised]}.
    """
    start, end = _find_region_block(ws, region)
    sums: Dict[str, List[float]] = defaultdict(lambda: [0.0] * INTERVALS_PER_DAY)
    counts: Dict[str, int] = defaultdict(int)

    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i <= start or (end is not None and i >= end):
            continue
        label = row[1]
        if not label or ',' not in str(label):
            continue  # header/time-axis row
        _, charging_type_label = str(label).split(',', 1)
        charging_type_label = charging_type_label.strip()
        values = row[2:2 + INTERVALS_PER_DAY]
        if any(v is None for v in values):
            continue
        for h, v in enumerate(values):
            sums[charging_type_label][h] += float(v)
        counts[charging_type_label] += 1

    if not sums:
        raise EvChargingProfileParseError(f"No charging-type rows found for region '{region}' in this sheet")

    return {label: [v / counts[label] for v in vals] for label, vals in sums.items()}


def parse_charge_type_pct_sheet(ws, region: str, scenario: str, target_year: int) -> Dict[str, float]:
    """
    Parses the BEV_PHEV_Charge_Type (%) sheet for `region`/`scenario`,
    averaging the fleet-share fraction across vehicle groups (Residential/
    Commercial/Buses and Trucks) for whichever financial-year column's
    start year matches target_year. Returns {charging_type_label: share_of_charging}.
    """
    region_start, region_end = _find_region_block(ws, region)

    scenario_rows = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i <= region_start or (region_end is not None and i >= region_end):
            continue
        c1, c2 = row[1], row[2]
        if c1 and c2 is None:
            scenario_rows.append((i, str(c1).strip()))
    matches = [i for i, label in scenario_rows if label == scenario]
    if not matches:
        available = sorted({label for _, label in scenario_rows})
        raise EvChargingProfileParseError(f"Scenario '{scenario}' not found in region '{region}'. Available: {available}")
    scenario_start = matches[0]
    later = [i for i, _ in scenario_rows if i > scenario_start]
    scenario_end = min(later) if later else region_end

    year_col_idx: Optional[int] = None
    header_row_idx = scenario_start + 1
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i != header_row_idx:
            continue
        for col_idx, val in enumerate(row):
            if isinstance(val, str) and val[:4].isdigit() and int(val[:4]) == target_year:
                year_col_idx = col_idx
                break
        break
    if year_col_idx is None:
        raise EvChargingProfileParseError(
            f"No financial-year column starting {target_year} found in the header row for "
            f"region '{region}' / scenario '{scenario}'"
        )

    sums: Dict[str, float] = defaultdict(float)
    counts: Dict[str, int] = defaultdict(int)
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i <= header_row_idx or (scenario_end is not None and i >= scenario_end):
            continue
        label = row[1]
        if not label or ' - ' not in str(label):
            continue
        _, charging_type_label = str(label).split(' - ', 1)
        charging_type_label = charging_type_label.strip()
        val = row[year_col_idx] if year_col_idx < len(row) else None
        if val is None:
            continue
        sums[charging_type_label] += float(val)
        counts[charging_type_label] += 1

    if not sums:
        raise EvChargingProfileParseError(
            f"No charging-type rows found for region '{region}' / scenario '{scenario}'"
        )
    return {label: sums[label] / counts[label] for label in sums}


def build_ev_charging_profile_rows(
    workbook, region: str, scenario: str, target_year: int,
    report_citation: str = '', table_ref: str = '',
) -> List[dict]:
    """
    Orchestrates the three sheets into EvChargingProfile-ready dicts (one
    per charging_type_label found in the kW profile sheets -- the % sheet's
    share_of_charging is joined in where a matching label exists, and
    reported as 0.0 with a note otherwise rather than silently dropping
    the shape data).
    """
    weekday_shapes = parse_profile_kw_sheet(workbook['BEV_PHEV_Profile_kW (Weekday)'], region)
    weekend_shapes = parse_profile_kw_sheet(workbook['BEV_PHEV_Profile_kW (Weekend)'], region)
    shares = parse_charge_type_pct_sheet(workbook['BEV_PHEV_Charge_Type (%)'], region, scenario, target_year)

    def _share_for(label: str) -> float:
        # The kW sheets suffix V2H/V2G rows with " - vehicle charging"
        # (e.g. "Vehicle to Grid - vehicle charging"); the % sheet does
        # not (just "Vehicle to Grid"). Strip that one known suffix
        # rather than fuzzy-matching generally, so a genuine share/shape
        # naming mismatch elsewhere still surfaces via _unmatched_share_labels.
        if label in shares:
            return shares[label]
        stripped = label.removesuffix(' - vehicle charging').strip()
        return shares.get(stripped, 0.0)

    rows = []
    all_labels = sorted(set(weekday_shapes) | set(weekend_shapes))
    for label in all_labels:
        wd = weekday_shapes.get(label)
        we = weekend_shapes.get(label)
        if wd is None or we is None:
            continue  # only present on one of weekday/weekend -- not enough to build both shapes honestly
        wd_sum, we_sum = sum(wd), sum(we)
        if wd_sum <= 0 or we_sum <= 0:
            continue

        rows.append({
            'region': region,
            'charging_type_label': label,
            'charging_mode': classify_charging_mode(label),
            'share_of_charging': _share_for(label),
            'weekday_halfhourly_shape': [v / wd_sum for v in wd],
            'weekend_halfhourly_shape': [v / we_sum for v in we],
            'report_citation': report_citation,
            'table_ref': table_ref,
            'citation_year': target_year,
        })

    matched_or_stripped = set(all_labels) | {l.removesuffix(' - vehicle charging').strip() for l in all_labels}
    unmatched = set(shares) - matched_or_stripped
    if unmatched:
        rows.append({'_unmatched_share_labels': sorted(unmatched)})  # surfaced by the caller, not persisted

    return rows


def parse_wem_annual_totals(workbook, sheet_name: str, scenario: str, region: str = 'WEM') -> Dict[int, float]:
    """
    FR-07 informational cross-reference: parses a Scenario > Region >
    VehicleType > year-columns sheet ('BEV_PHEV_Consumption (GWh)' or
    'BEV_Numbers') for one scenario/region, summing across vehicle types.
    Returns {year: total}.

    Unlike BEV_PHEV_Charge_Type (%) (Region outer, Scenario inner --
    see combine_charging_type_shapes' caller), these "totals" sheets nest
    the OTHER way around: Scenario outer, Region inner. Confirmed by
    direct inspection (2026-08-27), not assumed from the other sheet's
    layout.

    Not paired with a strict tolerance (see
    powermatchui.utils.ev_reconciliation's DEFAULT_TOLERANCE_PCT
    comment): AEMO's scenario framework (Slower Growth/Step Change/
    Accelerated Transition) is a different axis to CSIRO's postcode-file
    Low/Medium/High, and the correspondence between them is an unconfirmed
    working hypothesis (Step Change ~ Medium, per D8 calling Step Change
    "AEMO's central planning anchor") -- report this as a ratio/sanity
    check, not a pass/fail gate.
    """
    ws = workbook[sheet_name]

    scenario_rows = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        c1, c2 = row[1], row[2]
        if c1 and c2 is None and str(c1).strip() not in KNOWN_REGION_LABELS:
            scenario_rows.append((i, str(c1).strip()))
    matches = [i for i, label in scenario_rows if label == scenario]
    if not matches:
        available = sorted({label for _, label in scenario_rows})
        raise EvChargingProfileParseError(f"Scenario '{scenario}' not found in {sheet_name}. Available: {available}")
    scenario_start = matches[0]
    later = [i for i, _ in scenario_rows if i > scenario_start]
    scenario_end = min(later) if later else None

    region_start, region_end = None, None
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i <= scenario_start or (scenario_end is not None and i >= scenario_end):
            continue
        c1, c2 = row[1], row[2]
        if c1 and c2 is None and str(c1).strip() in KNOWN_REGION_LABELS:
            if str(c1).strip() == region and region_start is None:
                region_start = i
            elif region_start is not None and region_end is None:
                region_end = i
    if region_start is None:
        raise EvChargingProfileParseError(f"Region '{region}' not found under scenario '{scenario}' in {sheet_name}")
    if region_end is None:
        region_end = scenario_end

    header_row_idx = region_start + 1
    year_cols: Dict[int, int] = {}
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i != header_row_idx:
            continue
        for col_idx, val in enumerate(row):
            if isinstance(val, str) and val[:4].isdigit():
                year_cols[col_idx] = int(val[:4])
        break
    if not year_cols:
        raise EvChargingProfileParseError(f"No year-header row found at row {header_row_idx} in {sheet_name}")

    totals: Dict[int, float] = defaultdict(float)
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i <= header_row_idx or (region_end is not None and i >= region_end):
            continue
        label = row[1]
        if not label or label == 'Vehicle Type':
            continue
        for col_idx, year in year_cols.items():
            val = row[col_idx] if col_idx < len(row) else None
            if val is not None:
                totals[year] += float(val)

    if not totals:
        raise EvChargingProfileParseError(f"No data rows found for {scenario}/{region} in {sheet_name}")
    return dict(totals)
