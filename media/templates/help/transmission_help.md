# Guide to the Transmission Module

## Overview

The Transmission module provides tools for managing and visualising the electricity transmission and distribution network infrastructure that connects generation facilities to the grid. It covers terminal (substation) management, grid line inventory, Clean Energy Link (CEL) programme tracking, and network topology analysis to support planning and monitoring of the South West Interconnected System (SWIS).

---

## Available Views

| View | Purpose | Access |
|------|---------|--------|
| **Grid Map** | Interactive geographic map of terminals and facilities | Transmission → Grid Map |
| **Terminals Dashboard** | System-wide capacity and utilisation overview | Transmission → Dashboard |
| **All Terminals** | Full list and management of terminals | Transmission → All Terminals |
| **All Grid Lines** | Full list and management of grid lines | Transmission → All Grid Lines |
| **Health Check** | Data integrity and connectivity diagnostics | Transmission → Health Check |
| **CEL Transmission Map** | Interactive map of CEL programme infrastructure | Transmission → Transmission Map |
| **CEL Programs** | Management of Clean Energy Link programmes and stages | Transmission → CEL Programs |
| **Infrastructure Network** | Full network topology with bottleneck detection | Facilities → Network View |

---

## Grid Map

### Purpose
The Grid Map provides an interactive geographic view of the transmission network, showing terminals (substations), generation facilities, and the grid lines that connect them.

### Navigation and Controls
- **Scenario selector** — choose the demand year and scenario to filter which facilities are shown
- **Drag and drop** — reposition terminals and facilities on the map to reflect their geographic location
- **Click a terminal** — view connected facilities and grid lines; manage connections
- **Click a facility** — view facility details and its terminal connections
- **Add connections** — link a facility to a terminal via the connection management panel

### Map Symbols
- **Circles** represent terminals (substations)
- **Squares / icons** represent generation facilities
- **Lines** represent grid connections between terminals and facilities

---

## Terminals Dashboard

### Purpose
The Terminals Network Dashboard provides a high-level summary of the transmission network's health and capacity.

### System Overview Cards
Four summary cards appear at the top of the dashboard:
- **Total Terminals** — count of all terminals in the system, with the number that have active connections shown below
- **Total Capacity (MVA)** — sum of all transformer capacities, with average voltage (kV)
- **Connected Grid Lines** — count of grid lines with terminal endpoints assigned, out of total grid lines
- **High Utilisation** — count of terminals operating above 80% of transformer capacity

### Alerts
If any terminals are operating above 80% utilisation or have no grid connections, alert panels appear:
- **High Utilisation Alert** — lists the worst-affected terminals with their utilisation percentage; links to the Health Check for a full list
- **Unconnected Terminals Alert** — lists terminals with no assigned grid connections

### Top Terminals by Capacity
A ranked table of terminals showing:
- Terminal name (linked to terminal detail page)
- Terminal type (e.g., zone substation, transmission substation)
- Primary / secondary voltage (kV)
- Transformer capacity (MVA)
- Number of connected facilities
- Number of connected grid lines

### Top Terminals by Utilisation
A ranked table of the most heavily loaded terminals showing utilisation percentage and connected facility count. Terminals above 80% are highlighted in amber.

### Technology Breakdown
A summary of generation technology types connected across all terminals (Wind, Solar, Storage, etc.) with capacity totals.

---

## Terminals Management

### All Terminals
The terminals list shows all substations and switching stations in the system. Use the search box to filter by name. Each row links to the terminal's detail page.

### Terminal Detail
The terminal detail page shows:
- **Attributes**: terminal type, primary and secondary voltage (kV), transformer capacity (MVA), owner, location coordinates
- **Connected Facilities**: generation facilities whose grid connections pass through this terminal
- **Connected Grid Lines**: transmission and distribution lines with endpoints at this terminal
- **Utilisation**: current loading relative to transformer capacity

### Adding a Terminal
Use **Transmission → Add Terminal** or the **Add New Terminal** button on the list page. Required fields are terminal name and terminal type. Voltage and capacity fields are optional but recommended for utilisation calculations.

### Editing and Deleting
Access edit and delete actions from the terminal detail page. Deleting a terminal will also remove its grid line endpoint associations.

### Connecting a Facility to a Terminal
From a terminal's detail page, use the **Connect Facility** button to assign a generation facility to that terminal. This links the facility through the terminal for network analysis purposes.

### Health Check
The Health Check page identifies data quality issues across the terminal network:
- Terminals with no connected grid lines
- Terminals with no connected facilities
- Grid lines with missing terminal endpoints
- Terminals with transformer capacity that may be under-specified

---

## Grid Lines Management

### All Grid Lines
The grid lines list shows all transmission and distribution infrastructure records. Filters available:
- **Search** — by name, code, or owner
- **Line Type** — Transmission, Sub-transmission, or Distribution
- **Voltage range** — minimum and maximum kV
- **Status** — Active or Inactive
- **Connected** — filter to lines with or without terminal endpoints

### Grid Line Detail
Each grid line record shows:
- Line name and code
- Line type and voltage (kV)
- From terminal and to terminal (the substations at each end)
- Thermal capacity (MVA) and length (km)
- Owner and active status
- Connected facilities

### Adding a Grid Line
Use **Transmission → Add Grid Line** or the **Add New Grid Line** button. Key fields:
- **Line name** — descriptive name for the line
- **Line type** — Transmission (≥66 kV), Sub-transmission (11–66 kV), or Distribution (<11 kV)
- **Voltage (kV)** — operating voltage
- **From terminal / To terminal** — the substations at each end of the line
- **Thermal capacity (MVA)** — maximum load rating

---

## Clean Energy Link (CEL)

### Overview
The Clean Energy Link section tracks planned and funded transmission expansion programmes and their associated infrastructure. CEL programmes are structured as a programme with one or more stages, each stage linked to specific grid lines and terminals.

### CEL Transmission Map

#### Purpose
The CEL Transmission Map is an interactive geographic view that overlays CEL programme infrastructure onto the facility map, allowing assessment of which generation facilities have access to planned transmission upgrades.

#### Facility Colour Modes
Toggle between two display modes using the radio buttons in the left panel:
- **Development Status** — colours facilities by their current pipeline stage (Proposed, Planned, Under Construction, Commissioned)
- **CEL Viability** — colours facilities by their pre-computed viability tier for CEL access (High, Medium, Low)

#### Development Status Colours
| Status | Colour |
|--------|--------|
| Proposed | Grey |
| Planned | Blue |
| Under Construction | Orange |
| Commissioned | Green |

#### CEL Viability Tier Filters
When in CEL Viability mode, the panel shows tier filters (High / Medium / Low) to show only facilities with a particular viability level. Viability is calculated by the CEL Viability Service based on proximity to CEL programme grid lines and terminals, capacity headroom, and development stage probability.

#### Scenario Selector
Select the demand year and scenario before loading the map to ensure facilities are filtered to the correct planning context.

### CEL Programs

#### Program List
The CEL Programs page lists all transmission expansion programmes. Each programme shows its name, code, status, and the number of stages.

#### Program Detail
The programme detail page shows all stages within a programme. For each stage:
- Stage name and description
- New capacity unlocked (MW) — capacity made available to new generation
- Existing capacity unlocked (MW) — freed capacity for existing but constrained generators
- Funding status
- Associated grid lines and terminals

#### Adding a CEL Program
Use the **Add CEL Program** button. Enter the programme name, code, description, and start date.

#### Adding a Stage
From the programme detail page, use **Add Stage**. Enter the stage name and capacity figures. After creating the stage, associate grid lines and terminals with it using the **Add Grid Line** and **Add Terminal** buttons on the stage detail page.

#### Stage Grid Lines and Terminals
Each stage can be linked to multiple grid lines and terminals. This association is used by the viability scoring service to determine which facilities benefit from the stage's infrastructure investment.

---

## Infrastructure Dependency Network

### Purpose
The Infrastructure Dependency Network view renders a full topology diagram of the transmission network, showing how terminals, grid lines, and facilities are interconnected. It is designed for identifying bottlenecks and understanding dependency chains.

### Scenario Selector
Select the demand year and scenario at the top of the page to filter the diagram to the relevant planning context.

### Network Diagram
The main panel shows an interactive node-link diagram:
- **Terminal nodes** are shown as large circles labelled with the terminal name
- **Facility nodes** are shown as smaller circles coloured by development status
- **Grid line edges** connect terminal nodes
- **Facility edges** connect facilities to their terminal

Hover over a node to highlight its direct connections. Click a node to navigate to its detail page. Use the **Reset View** button to clear any highlighting.

### Legend
The legend below the diagram shows the colour coding for facility development status and grid line types.

### Download SVG
Use the **Download SVG** button to export the current network diagram as a scalable vector graphic for use in reports or presentations.

### Bottleneck Indicators
Terminals with utilisation above 80% are highlighted in amber in the diagram, indicating potential network bottlenecks that may constrain additional generation connections.

---

## Glossary of Terms

### Network Infrastructure

| Term | Definition |
|------|------------|
| **Terminal** | A substation or switching station where voltage is transformed and grid lines or facilities connect. |
| **Grid Line** | A physical transmission or distribution line connecting two terminals or a terminal to a generation facility. |
| **Transformer Capacity (MVA)** | The maximum throughput rating of a terminal's transformer equipment, in megavolt-amperes. |
| **Thermal Capacity (MVA)** | The maximum sustained current rating of a grid line before thermal limits are reached. |
| **Utilisation** | Actual load through a terminal or grid line as a percentage of its rated capacity. |
| **Bottleneck** | A terminal or grid line operating near or above capacity, potentially constraining the connection of additional generation. |

### Terminal Types

| Type | Description |
|------|-------------|
| **Transmission Substation** | High-voltage substation (typically 132–330 kV) connecting bulk generation and transmission lines. |
| **Zone Substation** | Intermediate substation stepping voltage down from transmission to sub-transmission (typically 33–132 kV). |
| **Distribution Substation** | Lower-voltage substation (typically 11–33 kV) supplying distribution feeders. |
| **Switching Station** | A substation with switching equipment but no transformer, used for network sectionalisation. |

### Grid Line Types

| Type | Voltage Range | Purpose |
|------|--------------|---------|
| **Transmission** | ≥ 66 kV | Long-distance bulk power transfer between major substations |
| **Sub-transmission** | 11–66 kV | Regional distribution from zone substations to local networks |
| **Distribution** | < 11 kV | Final delivery to end consumers and small generators |

### CEL Terms

| Term | Definition |
|------|------------|
| **CEL Programme** | A planned transmission investment programme to unlock capacity for new generation. |
| **CEL Stage** | A discrete phase of a programme with defined grid lines, terminals, and capacity outcomes. |
| **New Capacity (MW)** | Generation capacity that can be connected to the network as a result of the stage's investment. |
| **Existing Capacity (MW)** | Constrained existing generation whose access is improved by the stage. |
| **Viability Tier** | A classification (High / Medium / Low) indicating how well-positioned a facility is to benefit from a CEL stage, based on proximity and capacity headroom. |
| **Viability Score** | The underlying numeric score used to assign viability tier. |

### Facility Status

| Term | Definition |
|------|------------|
| **Commissioned** | Facility is operational and connected to the network. |
| **Under Construction** | Facility is being built with high certainty of completion. |
| **Planned** | Facility has received approvals and/or financing commitment. |
| **Probable** | Facility is likely to proceed but lacks final commitment. |
| **Possible** | Facility is under consideration but has significant uncertainty. |
| **Proposed** | Facility is at the earliest stage of consideration. |

---

## Frequently Asked Questions

### General

**Q: What is the difference between a Terminal and a Grid Line?**
A: A terminal is a substation — a fixed node in the network where voltage transformation occurs. A grid line is the physical cable or overhead wire connecting two terminals (or a terminal to a facility). Terminals are points; grid lines are the connections between them.

**Q: Why does a terminal show zero utilisation?**
A: Utilisation is calculated from the facility capacities connected through the terminal relative to its transformer capacity (MVA). If no facilities have been connected to the terminal, or if the transformer capacity has not been entered, utilisation will be zero or cannot be calculated.

**Q: How are facilities linked to terminals?**
A: Through the **FacilityGridConnections** data — a facility is linked to a grid line, and that grid line has a "from terminal" and "to terminal". The Health Check will flag facilities or grid lines with missing endpoint data.

### CEL Viability

**Q: What determines a facility's CEL viability tier?**
A: The CEL Viability Service calculates a score based on: distance from the facility to the nearest CEL stage grid line or terminal; available capacity headroom at the relevant terminal; and the development status probability of the facility. High-tier facilities are close to planned infrastructure with sufficient capacity headroom.

**Q: Why is a facility not showing on the CEL Map?**
A: Facilities appear on the map only if they have location coordinates stored in the database. Check the facility record to ensure latitude and longitude are populated. Also verify the scenario and demand year selection matches the planning context you are interested in.

**Q: How often is viability recalculated?**
A: Viability scores are pre-computed and stored in the database. They are recalculated when the CEL programme or stage data is updated, or when the calculation is triggered manually.

### Data Management

**Q: Can I delete a terminal that has facilities connected to it?**
A: Deleting a terminal removes its endpoint associations from grid lines. However, the facilities themselves and their grid line connections are not deleted. Check the terminal's connections before deleting to avoid leaving grid lines without valid endpoints.

**Q: What does the Health Check look for?**
A: The Health Check identifies: terminals with no grid lines; terminals with no facilities; grid lines with no terminal endpoints; terminals with suspiciously low or missing capacity data. Use it regularly when adding or editing network data.

**Q: How do I record that a grid line is no longer in service?**
A: Edit the grid line and set its **Status** to Inactive. Inactive lines remain in the database for historical reference but are excluded from active network calculations.

---

## Support

For technical support or questions about the Transmission module:
- **Email**: modelling.lead@sen.asn.au

*Last updated: April 2026*
