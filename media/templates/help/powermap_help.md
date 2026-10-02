# Powermap Module

## Overview
---
Powermap is an interactive mapping and analysis tool for modelling renewable and conventional energy infrastructure in the South West Interconnected System (SWIS). It provides scenario-based planning, transmission network analysis, SAM-based generation simulation, and a pipeline of proposed and committed projects.

The module consists of several integrated sub-systems:
- **Grid Map** — Interactive Leaflet map of facilities, grid lines and terminals
- **CEL Planner** — Transmission expansion planning with viability scoring
- **Network Overview** — Node-link diagram of the full infrastructure network
- **Pipeline Charts** — Gantt and waterfall charts for project timelines and capacity buildup
- **Data Take-up** — Data Pipelines dashboard and CSIRO GenCost data management
- **Run Power** — SAM-based generation simulation now lives under the **Powermatch** menu (see the Powermatch help)
- **Data Management** — CRUD interfaces for all infrastructure records

---

## Grid Map

### Scenario and Year Filtering
The map displays infrastructure filtered by a selected scenario and demand year.

1. Use the **Scenario** dropdown to select the planning scenario
2. Use the **Demand Year** (or timeline slider) to set the reference year
3. Only facilities commissioned before and not yet decommissioned by that year are shown

#### Scenario Types
- **Current**: Existing infrastructure — read-only; new facilities and grid lines cannot be added
- **Planning/Custom Scenarios**: Modifiable — supports adding, editing and deleting infrastructure

> **Note**: To add facilities or grid lines you must select a modifiable scenario (not "Current").

---

### Map Interface

The map is built on **Leaflet.js** with OpenStreetMap tiles.

#### Navigation
- **Pan**: Click and drag
- **Zoom**: Mouse wheel or the +/− controls
- **Find Location**: Use the search/locate control to jump to a named place

#### Map Layers
Use the layer control (top-right of map) to toggle visibility:

| Layer | Description |
|---|---|
| SWIS Boundary | Outer boundary of the interconnected system |
| Zones | Geographic planning zones within SWIS |
| Grid Facilities | Power generation and storage facilities |
| Grid Lines | Transmission and distribution network |
| Terminals | Substations and switching stations |

---

### Facility Icons and Status Colours

Facility icons reflect their technology type. The **colour** of each icon reflects the facility's development status:

| Status | Colour |
|---|---|
| Commissioned | Green |
| Under Construction | Blue |
| Planned | Yellow/Amber |
| Proposed | Orange |
| Decommissioned | Grey |

Technology icons include: Wind, Solar PV, Battery Storage (BESS), Pumped Hydro (PHES), Gas (CCGT/OCGT), Reciprocating Engine, Coal, Biomass, and a default icon for other technologies.

**Commissioning Probability**: Where a facility has a probability value less than 1.0, its icon is rendered at reduced opacity to signal uncertainty.

---

### Grid Line Colours

Grid lines are colour-coded by operating voltage level:

| Voltage | Colour | Hex |
|---|---|---|
| ≥ 330 kV | Dark Red | `#8B0000` |
| ≥ 220 kV | Orange-Red | `#FF4500` |
| ≥ 132 kV | Orange | `#FFA500` |
| ≥ 66 kV | Gold | `#FFD700` |
| < 66 kV | Yellow | `#FFFF00` |

Line **width** scales with voltage:

```
Weight = max(2, min(8, voltage_level / 50))
```

Higher-voltage lines appear thicker for visual emphasis. Line labels (showing line name) can be toggled with the **Toggle Grid Line Labels** button.

---

### Viewing Facility Details

- **Hover** over a facility icon to see a tooltip with name and capacity
- **Click** a facility icon to open the detailed modal

The facility modal displays:

**Basic Information**
- Name, code, technology type
- Capacity (MW), status, commissioning probability
- Commissioning and decommissioning dates
- Coordinates (latitude, longitude)

**Technology-Specific Parameters**

*Wind Facilities:*
- Turbine model, hub height (m), number of turbines
- Rotor diameter (m), tilt angle
- Capacity per turbine (MW)

*Solar Facilities:*
- Panel tilt angle and azimuth
- Tracking system type (fixed, single-axis, dual-axis)
- DC capacity (MW), AC capacity (MW), DC:AC ratio
- System losses (%)

*Battery Storage (BESS):*
- Power capacity (MW), energy capacity (MWh), duration (h)
- Round-trip efficiency (%); calculated as: `RTE = charge_efficiency × discharge_efficiency`
- Minimum and maximum state of charge (%)
- Cycle life, calendar life (years)

*Pumped Hydro (PHES):*
- Upper and lower reservoir capacity (MWh)
- Generation and pumping power (MW)
- Round-trip efficiency

**Grid Connections**
- Connected grid lines with distance to connection point (km)
- Primary vs secondary connection flag
- Calculated connection losses (see Transmission Loss Calculations)

**Economic Data**
- Capital expenditure (CAPEX, $/MW or $M)
- Fixed operating cost (FOM, $/MW/year)
- Variable operating cost (VOM, $/MWh)
- Project lifetime (years) and discount rate (%)

---

### Viewing Grid Line Details

Click any grid line to open the grid line modal:

**Technical Specifications**
- Name, code, voltage level (kV)
- Line type (transmission, sub-transmission, distribution)
- Length (km), thermal capacity (MVA), emergency capacity (MVA)
- Resistance per km (Ω/km), reactance per km (Ω/km)
- Total impedance: `Z = √(R² + X²)` where `R = r_per_km × length`, `X = x_per_km × length`

**Calculated Losses at Full Capacity**
See *Transmission Loss Calculations* below.

**Connected Facilities**
List of all facilities with connections to this line and their connection distances.

---

### Transmission Loss Calculations

#### Line Losses

Power losses on a transmission line are calculated using:

```
P_loss = (P² × R) / (V² × cos²φ)
```

Where:
- `P` = power flow (MW)
- `R` = total line resistance = `resistance_per_km × length_km` (Ω)
- `V` = operating voltage (kV)
- `cos(φ)` = power factor = 0.95 (assumed)

Equivalently expressed via line current:

```
I = P / (V × √3 × pf)          [current in kA]
P_loss = I² × R × V²            [losses in MW]
```

**Utilisation Percentage:**

```
Utilisation (%) = (current_flow_MW / thermal_capacity_MVA) × 100
```

#### Connection Losses

Losses on the spur connection between a facility and its grid connection point are calculated the same way, using the connection distance as the effective line length and assuming standard cable specifications for the voltage class.

#### Impedance

```
R_total = resistance_per_km × length_km   (Ω)
X_total = reactance_per_km × length_km    (Ω)
Z_total = √(R_total² + X_total²)          (Ω)
```

---

### Adding Facilities

> **Prerequisite**: Select a modifiable scenario (not "Current").

1. Click **Add New Facility** — the cursor changes to a crosshair
2. Click on the map to set the facility location (coordinates are captured automatically)
3. Complete the facility form:
   - **Name** and optional **Code**
   - **Technology**: select from the technology list
   - **Capacity (MW)**
   - **Status** and **Commissioning Probability** (0.0–1.0)
   - **Commissioning / Decommissioning Dates**
   - Technology-specific parameters (turbine model and count for wind; tilt and tracking for solar)
4. Select a **Grid Connection**:
   - *Auto-connect* — system finds the nearest suitable grid line
   - *Select existing grid line* — choose from a dropdown
   - *No connection* — standalone or off-grid facility
5. Click **Save Facility**

To cancel at any time, click **Cancel Add Facility**.

---

### Editing and Moving Facilities

- Open a facility modal and click **Edit** to modify parameters
- Drag the facility marker on the map to update its location
- Location changes update the stored latitude and longitude immediately

---

### Adding Grid Lines

> **Prerequisite**: Select a modifiable scenario (not "Current").

1. Click **Add New Grid Line** — the cursor changes to a crosshair
2. Click the **first endpoint** (a "Start Point" marker appears)
3. Click the **second endpoint** (an "End Point" marker appears and a dashed line connects them)
4. Complete the grid line form:
   - **Name** and **Code**
   - **Voltage Level (kV)**
   - **Thermal Capacity (MVA)**
   - **Resistance and Reactance per km** (Ω/km)
   - **From Terminal** and **To Terminal** (optional)
5. Line **length** is automatically calculated from the two clicked points using the Haversine formula:

```
a = sin²(Δlat/2) + cos(lat1) × cos(lat2) × sin²(Δlon/2)
distance_km = 2 × R_earth × arcsin(√a)       [R_earth ≈ 6371 km]
```

6. Click **Save Grid Line**

To cancel, click **Cancel Add Grid Line**.

---

### Terminals (Substations)

Terminals represent substations and switching stations. They connect grid lines in the network topology.

**Parameters:**
- Name, code, type (substation, switching station, etc.)
- Voltage class: Low / Medium / High / Extra High / Ultra High
- Primary voltage (kV) — voltage class is auto-assigned from this value
- Transformer capacity (MVA)
- Bay count

**Viewing Terminals:**
- Click a terminal marker on the map to view connections and capacity
- The terminal detail page shows all connected grid lines and facilities, load, and available capacity
- A **Node Diagram** is available showing the terminal's local network topology (D3.js force-directed graph)

**Bottleneck Detection:**
A terminal is flagged as a **bottleneck** when the total capacity of connected facilities exceeds the terminal's transformer capacity (MVA). Bottlenecks are highlighted in red in the Network Overview.

---

## CEL Planner

**CEL** stands for **Clean Energy Link** — a system for planning and tracking transmission expansion programs.

The CEL Planner allows assessment of which proposed generation facilities can be accommodated by planned or in-flight transmission upgrades, and scores each facility's viability against each transmission stage.

### Structure

- **CEL Program**: A named transmission expansion initiative with a program code and target dates
- **CEL Stage**: A discrete route or corridor within a program, with planned new capacity (MVA) and associated grid lines and terminals
- **Facility Alignment**: Each facility within a configurable radius of a CEL stage route is scored for viability

### CEL Map

The CEL Map (`/powermapui/cel_map/`) overlays CEL stage routes on the grid map and colour-codes facilities by their viability score. Use the program and stage selectors to filter the view.

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

---

## Network Overview

The Network Overview (`/powermapui/network_overview/`) displays the full infrastructure as an interactive node-link diagram rendered using **D3.js**.

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

The Gantt chart (`/powermapui/pipeline_gantt/`) shows each facility as a horizontal bar spanning from commissioning date to decommissioning (or assumed retirement) date.

- **Sorted by**: technology category → commissioning date → facility name
- **Filtered by**: scenario
- **Hover** for facility details (name, capacity, technology, status)

### Waterfall / Capacity Buildup Chart

The waterfall chart (`/powermapui/pipeline_waterfall/`) shows cumulative installed capacity year by year, stacked by technology category.

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
AEMO SCADA, CSIRO GenCost, etc.):

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

The facilities list (`/powermapui/facilities/`) shows all facilities in the system with filtering by:
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

Technologies (`/powermapui/technologies/`) define reusable technology specifications:

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

Storage technologies add:

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

Wind turbine models (`/powermapui/wind_turbines/`) store:
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
