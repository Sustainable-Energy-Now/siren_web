# Powermap Module

## Overview
---
Powermap is an interactive mapping and analysis tool for modelling renewable and conventional energy infrastructure in the South West Interconnected System (SWIS). It provides scenario-based planning, transmission network analysis, SAM-based generation simulation, and a pipeline of proposed and committed projects.

The module consists of several integrated sub-systems:
- **Grid Map** — Interactive Leaflet map of facilities, grid lines and terminals (see <a href="/help/grid_map/" target="_blank" rel="noopener noreferrer">Grid Map Help</a>)
- **CEL Planner** — Transmission expansion planning with viability scoring
- **Network Overview** — Node-link diagram of the full infrastructure network
- **Pipeline Charts** — Gantt and waterfall charts for project timelines and capacity buildup
- **Data Take-up** — Data Pipelines dashboard and CSIRO GenCost data management
- **Run Power** — SAM-based generation simulation now lives under the **Powermatch** menu (see the Powermatch help)
- **Data Management** — CRUD interfaces for all infrastructure records

---

## Grid Map

The Grid Map is the interactive map of facilities, grid lines and terminals in the SWIS. Use it to:

- filter facilities by scenario, status, technology and timeline year
- view facility, grid line and terminal details
- add facilities, terminals and grid lines by clicking on the map
- move facilities and terminals, and manage grid connections
- draw zones and edit the SWIS boundary

Open it from **Grid Map → Display Map**.

Full instructions, including the line-loss and utilisation calculations, are in the <a href="/help/grid_map/" target="_blank" rel="noopener noreferrer">Grid Map Help</a>, which opens in a new tab. You can also reach it from the **❓ Help** button on the map, or **Grid Map → Grid Map Help**.

---

## CEL Planner

**CEL** stands for **Clean Energy Link** — a system for planning and tracking transmission expansion programs.

The CEL Planner allows assessment of which proposed generation facilities can be accommodated by planned or in-flight transmission upgrades, and scores each facility's viability against each transmission stage.

### Structure

- **CEL Program**: A named transmission expansion initiative with a program code and target dates
- **CEL Stage**: A discrete route or corridor within a program, with planned new capacity (MVA) and associated grid lines and terminals
- **Facility Alignment**: Each facility within a configurable radius of a CEL stage route is scored for viability

### CEL Map

The CEL Map (`/cel-map/`) overlays CEL stage routes on the grid map and colour-codes facilities by their viability score. Use the program and stage selectors to filter the view.

### Viability Scoring

Each facility's viability against a CEL stage is scored on a 0–1 scale, combining three factors:

**1. CEL Stage Status Weight** (reflects how far along the transmission project is):

| Stage Status | Weight |
|---|---|
| Planning | 0.30 |
| Environmental Approval | 0.50 |
| Funded | 0.80 |
| Under Construction | 0.90 |
| Operational | 1.00 |

**2. Facility Status Weight** (reflects the facility's own development status):

| Facility Status | Weight |
|---|---|
| Proposed | 0.30 |
| Planned | 0.60 |
| Under Construction | 0.85 |
| Commissioned | 1.00 |
| Decommissioned | 0.00 |

**3. Capacity Feasibility Score** (reflects whether the CEL stage has headroom for this facility):

```
If facility_mw ≤ available_capacity_mw:
    score = 1.0

If facility_mw > available_capacity_mw but ≤ total_stage_capacity_mw:
    score = max(0.1, available_capacity_mw / facility_mw)

If facility_mw > total_stage_capacity_mw:
    score = 0.1   (facility would require CEL expansion)

If facility has no capacity data:
    score = 0.5
```

**Combined Viability Score:**

```
Viability Score = CEL_Stage_Weight × Facility_Status_Weight × Capacity_Feasibility_Score
```

**Viability Tiers:**

| Tier | Score Range |
|---|---|
| High | ≥ 0.70 |
| Medium | 0.40 – 0.69 |
| Low | < 0.40 |
| Exception | Manually flagged override |
| Unscored | No CEL stage alignment found |

**Alignment Radius:** Facilities are only aligned to a CEL stage if they fall within the configured `alignment_radius_km` (typically 50 km) of the stage route.

### CEL Alignment Exceptions

An administrator can manually mark a facility–stage alignment as an **Exception** when the standard scoring does not apply (e.g., a special connection agreement or non-geographic relationship). Exceptions are displayed distinctly on the CEL map.

### Automated CEL Progress Tracking

No authority publishes CEL progress as data. Status, dates and capacities appear only in web pages and PDFs from Energy Policy WA, the Department of the Premier and Cabinet, and Western Power. Two background commands now read those sources and **propose** updates to CEL stages. **Nothing changes on a stage until someone accepts the proposal.**

| Command (Data Pipelines → *Clean Energy Link progress*) | Source | Suggested schedule |
|---|---|---|
| **Check CEL publications for changes** (`check_cel_sources`) | Watched CEL web pages and PDFs | Weekly |
| **Sync CEL progress from Western Power GIS** (`sync_cel_gis`) | Western Power's network layers on data.wa.gov.au (SLIP), plus the facilities aligned to each stage | Monthly |

Both commands have a **Dry run** option that reports what they would propose without writing anything.

#### Proposed Updates page (`/cel/proposals/`)

Open it from **CEL Update Proposals** in the CEL Planner menu, or from the **Proposed updates** button on the CEL Programs list. The red badge on that button counts the pending proposals.

- **Pending**: each proposal shows the stage, the field, its current and proposed values, where the proposal came from (*Published document*, *Western Power GIS* or *Derived from facilities*) and the evidence: the quoted sentence, or a summary of the matched assets, with a link to the source.
  - **Accept** writes the value to the stage. It also adds a dated line to the stage's notes recording the change and its source, and marks any other pending proposals for the same field as *Superseded*. If the field affects viability (funding status or any MW figure), the stage's viability scores are recalculated.
  - **Reject** discards the proposal. The same value is never proposed again for that field.
  - Sometimes a document names a program with several stages but not the specific stage (for example, CEL-East wording such as "Stage 1"). The proposal then shows *stage not identified*, and you choose the stage from a drop-down before accepting.
- **Watched sources**: every page or PDF being watched, with when it was last checked and last changed, and any fetch error. Use **Pause/Resume** to stop or restart watching a source. Use the form at the bottom to watch another URL; tick **Find links** to also pick up CEL-related links on that page.
- **Recently reviewed**: the last 25 accepted, rejected or superseded proposals.

The fields that can be proposed are funding status, expected operational date, actual operational date, new capacity (MW), unlocked existing capacity (MW) and reserved capacity (MW).

#### How the document watcher works

1. The first run adds a starting list of sources: the State of Energy CEL page, the EPWA SWIS Transmission Plan pages, the DPC priority-project pages for CEL North, East Stage 1 and Kwinana, Western Power's *Let's Talk* pages for CEL North and East, and the CEL-East Stage One priority-determination PDF.
2. Each run downloads every active source and reduces it to plain text. For web pages it uses the main content only, so menus and footers don't count as changes. If the text has changed, a snapshot is saved and only the **new lines** are examined.
3. Sources marked *finds links* add CEL-related links they contain (fact sheets, gazette notices, project sub-pages) as new sources. This goes one level deep only, and only on government, Western Power and AEMO sites.
4. Each sentence is matched to a program or stage by name, using forms such as "Clean Energy Link – North" and "CEL-North". If a page is clearly about a single program, sentences that name none are attributed to that program. Narrow phrase rules then pick out:
   - **Funding status**, e.g. "construction has started" → Under Construction, "$584 million committed" → Funded, "has been energised" → Operational. A status is only proposed if it is *further along* than the stage's current status. A sentence written in the future tense ("will be energised by…") is never taken as evidence that the stage is Operational.
   - **Dates**, e.g. "delivered by the end of 2027" → 31 Dec 2027, "mid-2028" → 30 Jun 2028, "Q3 2026" → 30 Sep 2026.
   - **Capacity**, e.g. "400 MW of existing wind" → unlocked existing capacity, "another 1 GW of new renewable" → new capacity. MVA transformer ratings are ignored.

The rules are deliberately conservative: a missed fact is cheaper than a wrong proposal. Sentences that name two programs at once are skipped.

#### How the GIS sync works

Western Power publishes its **existing** network monthly: WP-051 *HV Overhead Transmission Lines* (route and kV) and WP-049 *Existing Substations/Terminals/Power Stations*. These layers contain no planned assets, so they can only confirm that something has been **built**. Funding status and expected dates still come from documents.

For each active stage:

- **Linked grid lines** (added on the stage page) are tested at 12 points along the line's stored KML route.
  - A **new** line is confirmed when an in-service GIS line at or above the line's `voltage_level` lies within 1 km of at least 80% of those points.
  - An **upgrade** line keeps its *pre-CEL* `voltage_level` (e.g. 132 kV for CEL-North's 132 → 330 kV conversions). It is confirmed only where GIS shows a **higher** voltage **and no in-service line at the old voltage remains**. The second condition matters because existing higher-voltage circuits share these corridors, often 0–50 m apart. As a result, a capacity-only upgrade, or one that leaves the old circuit in place, can't be detected and stays *not built*.
  - A grid line without KML route geometry can't be tested and is reported as *unknown*.
- **New terminals** (terminal role *New*) are confirmed when an existing substation lies within 1.5 km of the terminal's coordinates. Upgraded terminals can't be checked, because the layer carries no capacity.
- If at least one asset is confirmed, the command proposes **Under Construction**. If all are confirmed, it proposes **Operational**, with an actual operational date of the day it was first seen. Western Power refreshes the layers monthly, so that date can be up to about a month late.
- **Reserved capacity** is also derived: the total capacity of facilities aligned to the stage (not exceptions) whose status is *Under Construction*. The evidence lists those facilities.

**SLIP account required:** the Western Power layers need a free SLIP login from data.wa.gov.au. Set `username` and `password` under `[slip]` in `.django/secrets.toml`, or set the `SLIP_USERNAME` / `SLIP_PASSWORD` environment variables. Without credentials, the GIS checks are skipped with a warning and only reserved capacity is derived. From the command line, you can instead pass GeoJSON files you've downloaded yourself with `--lines-file` and `--substations-file`.

---

## Network Overview

The Network Overview (`/infrastructure-network/`) displays the full infrastructure as an interactive node-link diagram rendered using **D3.js**.

### Visual Encoding

| Element | Encoding |
|---|---|
| Node shape | Circle = Terminal; Diamond = Facility |
| Node colour | Development status (Commissioned=green, Planned=amber, etc.) |
| Node opacity | Commissioning probability (0.0–1.0) |
| Node size | Proportional to capacity (MW) |
| Terminal border | Red = bottleneck (connected capacity > transformer capacity) |
| Link colour | Grid line type (transmission/sub-transmission/distribution) |
| Link width | Proportional to voltage level |

### Statistics Panel

The panel alongside the diagram shows:
- Total terminal count, facility count
- Total connections, number of bottleneck terminals
- Pipeline summary: counts by development status

### Interaction

- **Drag** nodes to reposition them
- **Click** a node to open facility or terminal details
- **Zoom** with mouse wheel
- **Reset View** button restores default layout

---

## Pipeline Charts

### Gantt Chart

The Gantt chart (`/pipeline-gantt/`) shows each facility as a horizontal bar spanning from commissioning date to decommissioning (or assumed retirement) date.

- **Sorted by**: technology category → commissioning date → facility name
- **Filtered by**: scenario
- **Hover** for facility details (name, capacity, technology, status)

### Waterfall / Capacity Buildup Chart

The waterfall chart (`/pipeline-waterfall/`) shows cumulative installed capacity year by year, stacked by technology category.

Three series are displayed:

| Series | Definition |
|---|---|
| Committed | Facilities with status Commissioned or Under Construction |
| Probable | Probability-weighted capacity for Proposed and Planned facilities |
| Retirements | Capacity retiring in each year (decommissioned or end-of-life) |

**Probable Capacity Formula:**

```
Probable_capacity_MW = facility_capacity_MW × commissioning_probability
```

The chart covers a configurable projection period (default 2020–2050).

---

## Data Take-up

Two tools for keeping the external data that Powermap and Powermatch depend on up to date. The menu item sits after **SWIS Boundary**.

### Data Pipelines (`/data-pipelines/`)

A dashboard for the background commands that ingest external data (WEM ESOO, EV uptake,
AEMO SCADA, CSIRO GenCost, Clean Energy Link progress, etc.):

- **Freshness** cards at the top show one card per tracked dataset, each with a coloured
  dot indicating how stale it is.
- **Run a job**: each runnable command is listed with its parameters (choice fields, flags,
  free text) and a **Run** button. Only staff users can actually submit a run — everyone
  else sees the dashboard read-only. Only one run of a given command can be active at a
  time; submitting again while one is running is refused.
- **Recent runs**: the last 25 runs, each with status, duration and a "log" link
  (`pipeline_run_detail`) showing the command's full captured output.
- Runs execute in a background thread server-side; the dashboard page itself doesn't need
  to stay open, and `pipeline_run_status` is polled by the run-detail page for live status.

### GenCost Data (`/gencost/upload/`)

Manages CSIRO GenCost technology cost vintages, which feed the `TechnologyYears` cost data
used throughout PowerMatch (capex, FOM, VOM, lifetime). The primary way a new vintage
arrives is the automatic fetch command on the Data Pipelines dashboard; this page is the
manual fallback plus the review/apply workflow:

1. **Upload & register** (`/gencost/upload/`): upload a GenCost source document for an
   edition (e.g. "2024-25") and document type; it's archived to disk and registered as a
   `SourceDocument` against a `GencostVintage`.
2. **Vintage detail** (`/gencost/<id>/`): shows the vintage's registered documents, the
   number of extracted cost figures, and one row per cost case (e.g. "Current Policies",
   "Global NZE 2050") with how many technology labels in that case are still unmapped.
   - **Extract**: parses the uploaded document(s) into `GencostCostFigure` rows (runs the
     `extract_gencost_figures` pipeline command in the background).
   - **Apply** (per cost case): pushes that case's figures onto the live `TechnologyYears`
     table (`apply_gencost_cost_case`), with an optional capex premium percentage. Disabled
     until every raw technology label in that case has been mapped or explicitly ignored.
   - **Recent runs**: the extract/apply command runs for this vintage, same log-link
     pattern as Data Pipelines.
3. **Technology Mapping Review** (`/gencost/mapping/`): GenCost's raw technology labels
   don't match this project's `Technologies` names one-to-one, so each raw label is mapped
   by hand to a `Technologies` row, or marked "ignore" (not applicable to this project).
   Pending (unmapped, not ignored) rows are listed first since they're what blocks Apply.

---

## Facilities Management

### Facilities List

The facilities list (`/facilities/`) shows all facilities in the system with filtering by:
- Technology category
- Development status
- Scenario
- Zone

Summary statistics (total count, total capacity MW) are shown at the top.

### Facility Detail

The facility detail page shows all parameters, linked installations (wind turbines, solar arrays, storage), grid connections, and SAM-generated generation statistics if available.

### Technology-Specific Sub-Records

Each facility can have one or more technology sub-records that store detailed technical parameters:

- **FacilityWindTurbines** — links a turbine model, hub height, number of turbines, rotor dimensions
- **FacilitySolar** — PV array parameters (tilt, azimuth, tracking type, DC/AC capacities, system losses)
- **FacilityStorage** — links a storage technology, power and energy capacity, state-of-charge limits

---

## Technologies

Technologies (`/technologies/` for the full table, `/technologies/list/` to manage them) define reusable technology specifications:

### Generator Technologies

| Parameter | Description |
|---|---|
| Name, Signature | Descriptive name and short code |
| Category | Technology class (e.g. Wind, Solar, Gas CCGT) |
| Fuel type | Wind / Solar / Gas / Coal / Hydro / Biomass / Other |
| Renewable | Boolean flag |
| Dispatchable | Boolean flag |
| Lifetime (years) | Expected operational life |
| Discount rate (%) | For economic modelling |
| Emissions (kg CO₂/MWh) | Carbon intensity |
| Capacity (MW) | Reference unit capacity |
| FOM ($/MW/yr) | Fixed operating and maintenance cost |
| VOM ($/MWh) | Variable operating and maintenance cost |

Year-by-year cost trajectories are stored in **TechnologyYears** records, allowing cost projections to change over the planning horizon.

### Storage Technologies

Storage technologies (`/storage/`) add:

| Parameter | Description |
|---|---|
| Charge efficiency (%) | Efficiency of charging |
| Discharge efficiency (%) | Efficiency of discharging |
| Round-trip efficiency | `RTE = charge_efficiency × discharge_efficiency / 10000` (if entered as %) |
| Min SOC (%) | Minimum state of charge |
| Max SOC (%) | Maximum state of charge |
| Usable capacity | `Usable_MWh = Energy_MWh × (Max_SOC - Min_SOC) / 100` |
| Cycle life | Full charge-discharge cycles before significant degradation |
| Calendar life (years) | Operational life independent of usage |
| Self-discharge rate (%/day) | Passive energy loss when idle |
| Auxiliary load (kW) | Parasitic power draw by the system itself |
| Degradation rate (%/year) | Annual capacity fade |

### Wind Turbine Models

Wind turbine models (`/wind_turbines/`) store:
- Manufacturer and model name
- Rated capacity (MW), hub height(s) (m), rotor diameter (m)
- Power curve: wind speed (m/s) → power output (kW) at each speed step
- Cut-in, rated and cut-out wind speeds

Power curves are used directly by the SAM simulation.

---

## Terminals (Substations)

Terminals represent substations and network switching points that define the topology of the transmission network.

### Parameters

| Parameter | Description |
|---|---|
| Name, Code | Identifier fields |
| Type | Substation, Switching Station, etc. |
| Primary Voltage (kV) | Operating voltage; determines voltage class |
| Voltage Class | Auto-assigned: Low / Medium / High / Extra High / Ultra High |
| Transformer Capacity (MVA) | Maximum throughput |
| Bay Count | Number of connection bays |
| Coordinates | Latitude, Longitude for map placement |

### Voltage Class Assignment

| Voltage Range | Class |
|---|---|
| < 11 kV | Low |
| 11–66 kV | Medium |
| 66–220 kV | High |
| 220–330 kV | Extra High |
| ≥ 330 kV | Ultra High |

### Terminal Node Diagram

Each terminal has a **Node Diagram** view (D3.js force-directed graph) showing:
- The terminal as the central node
- Connected grid lines as edges
- Facilities connected via those grid lines as outer nodes
- Click any node for details

### Terminal Health Check

The Terminal Health Check screen summarises:
- Terminals where connected capacity exceeds transformer capacity (bottlenecks)
- Terminals with no connected grid lines (isolated)
- Terminals with no connected facilities

---

## Grid Lines

Grid lines record the physical transmission and distribution network.

### Parameters

| Parameter | Description |
|---|---|
| Name, Code | Identifier fields |
| Voltage Level (kV) | Operating voltage (determines map colour and line weight) |
| Line Type | Transmission / Sub-transmission / Distribution |
| Length (km) | Physical route length |
| Thermal Capacity (MVA) | Maximum continuous power transfer |
| Emergency Capacity (MVA) | Short-term overload rating |
| Resistance per km (Ω/km) | Used in loss calculations |
| Reactance per km (Ω/km) | Used in impedance calculations |
| From Terminal / To Terminal | Endpoints in the network topology |
| KML Route | Optional polyline geometry for accurate map routing |

### Calculated Values

| Value | Formula |
|---|---|
| Total resistance | `R = resistance_per_km × length_km` |
| Total reactance | `X = reactance_per_km × length_km` |
| Total impedance | `Z = √(R² + X²)` |
| Losses at full capacity | See Transmission Loss Calculations above |

---

## Zones

Zones define geographic sub-regions of the SWIS used for planning and filtering.

- Each zone has a name, code and optional KML boundary polygon
- Facilities can be assigned to zones
- Map and list views can be filtered by zone
- Zone boundaries are overlaid on the grid map as a toggleable layer

---

## Glossary

**Azimuth**: Compass bearing of a solar panel face (180° = due north, 0°/360° = due south in southern hemisphere convention).

**BESS**: Battery Energy Storage System — typically lithium-ion.

**Bottleneck**: A terminal where the total connected facility capacity exceeds the terminal's transformer capacity (MVA).

**Calendar Life**: Expected operational life in years, independent of how often the system cycles.

**Capacity Factor**: Ratio of actual annual energy output to the maximum possible output at rated capacity. `CF = Energy_MWh / (Capacity_MW × 8760)`.

**CEL (Clean Energy Link)**: A transmission expansion program comprising stages (routes) that enable new generation to connect to the grid.

**CEL Proposed Update**: A suggested change to one CEL stage field, raised automatically from a published document, Western Power's network GIS or the facilities aligned to the stage. It is applied only when accepted on the Proposed Updates page (`/cel/proposals/`).

**Commissioning Probability**: A value 0.0–1.0 expressing the likelihood that a proposed or planned facility will proceed. Used to weight capacity in the pipeline waterfall chart.

**Cycle Life**: Number of full charge-discharge cycles before a storage system loses a defined percentage of its original capacity.

**DC:AC Ratio**: The ratio of a solar array's DC panel capacity to its inverter's AC output capacity. Values > 1.0 mean the array is oversized ("clipping" occurs at peak irradiance).

**Depth of Discharge (DoD)**: Fraction of energy capacity used in a cycle. `DoD = 1 − SOC_min`.

**DHI (Diffuse Horizontal Irradiance)**: Solar radiation received from the sky (not directly from the sun), measured on a horizontal surface.

**DNI (Direct Normal Irradiance)**: Solar radiation received directly from the sun on a surface perpendicular to the sun's rays.

**Duration (h)**: How long a storage system can discharge at rated power. `Duration = Energy_MWh / Power_MW`.

**FOM**: Fixed Operating and Maintenance cost ($/MW/year) — costs that do not vary with output.

**GHI (Global Horizontal Irradiance)**: Total solar radiation (direct + diffuse) on a horizontal surface.

**Haversine Formula**: Calculates the great-circle distance between two points on a sphere given their latitudes and longitudes. Used for line length calculation and weather file lookup.

**Hub Height**: Height from ground to the centre of a wind turbine's rotor (metres). Higher hubs access stronger, more consistent winds.

**Impedance (Z)**: Combined opposition to AC current flow. `Z = √(R² + X²)` where R is resistance and X is reactance.

**MW (Megawatt)**: Unit of power. 1 MW = 1,000 kW.

**MVA (Megavolt-Ampere)**: Unit of apparent power, approximately equal to MW for typical power factors.

**MWh (Megawatt-hour)**: Unit of energy. 1 MWh = 1 MW sustained for 1 hour.

**OCGT**: Open Cycle Gas Turbine — fast-start peaking plant.

**CCGT**: Combined Cycle Gas Turbine — high-efficiency baseload/intermediate plant.

**PHES**: Pumped Hydro Energy Storage — stores energy by pumping water uphill; recovers it through turbines.

**Power Curve**: A wind turbine's characteristic curve mapping hub-height wind speed (m/s) to electrical output (kW).

**Power Factor (cos φ)**: Ratio of real power (MW) to apparent power (MVA). Assumed 0.95 in loss calculations.

**Reactance (X)**: Opposition to AC current flow due to inductance. `X = reactance_per_km × length_km`.

**Resistance (R)**: Opposition to current flow that converts electrical energy to heat (losses). `R = resistance_per_km × length_km`.

**Round-Trip Efficiency (RTE)**: Ratio of energy recovered from storage to energy put in. `RTE = charge_efficiency × discharge_efficiency`.

**SAM (System Advisor Model)**: NREL's open-source simulation tool for renewable energy systems. Used here to produce hourly generation profiles from weather data.

**Self-Discharge**: Gradual loss of stored energy over time when a storage system is idle.

**SOC (State of Charge)**: Current energy level in a storage system expressed as a fraction (0.0–1.0) or percentage (0–100%) of maximum capacity.

**SWIS**: South West Interconnected System — the main electricity grid of south-west Western Australia.

**Thermal Capacity**: Maximum continuous power that a grid line or transformer can carry without exceeding its temperature rating (MVA or MW).

**Tilt**: Angle of a solar panel or wind turbine rotor relative to horizontal (degrees).

**Usable Capacity**: Energy available within the permitted SOC window. `Usable_MWh = Energy_MWh × (Max_SOC − Min_SOC) / 100`.

**VOM**: Variable Operating and Maintenance cost ($/MWh) — costs that scale with energy output.

**Viability Score**: A composite 0–1 score used in the CEL Planner to rank how feasible it is for a facility to connect via a given CEL stage.

---
