# Grid Map

## Overview

The Grid Map is an interactive map of the South West Interconnected System (SWIS). It shows generation and storage **facilities**, **grid lines** and **terminals** (substations), together with the SWIS boundary and planning zones.

From the Grid Map you can:

- Filter facilities by **scenario**, **status**, **technology** and **year**
- View details of any facility, grid line or terminal
- Add new facilities, terminals and grid lines by clicking on the map
- Move facilities and terminals, and manage facility grid connections
- Draw zone boundaries and edit the SWIS boundary
- Review grid line utilisation

Open the map from **Powermap → Grid Map → Display Map**. The **❓ Help** button at the top of the map opens this guide in a new tab.

---

## Map Interface

The map uses **Leaflet.js** over a vector basemap.

### Navigation
- **Pan**: click and drag
- **Zoom**: mouse wheel or the **+ / −** controls
- **Find on Map**: click **Find on Map**, choose a type (Facility, Terminal or Grid Line), type part of the name and pick an entry to zoom to it

### Map Layers
Use the layer control at the top right of the map to show or hide each layer:

| Layer | Description |
|---|---|
| SWIS Boundary | Outer boundary of the interconnected system |
| Zones | Geographic planning zones within the SWIS |
| Grid Facilities | Generation and storage facilities |
| Terminals | Substations and switching stations |
| Grid Lines | Transmission and distribution lines |

### Facility Icons
Each facility icon shows its technology: Wind, Solar PV, Battery Storage (BESS), Pumped Hydro (PHES), Gas (CCGT/OCGT), Reciprocating Engine, Coal, Biomass, Solar Thermal (CST) and Nuclear. Other technologies use a default icon.

---

## Filtering Facilities

All facilities are loaded when the page opens, and the filters are applied straight away in the browser. A facility is shown only if it passes **every** filter. The **Summary** panel always reflects the facilities currently visible.

### Scenario
The **Scenario** dropdown above the map limits the map to the facilities in that scenario. **All Facilities** shows every facility. Changing scenario is instant; the page doesn't reload.

Adding facilities, terminals and grid lines requires a scenario to be selected. New facilities are added to that scenario.

### Status Filter
Tick or untick each development status:

| Status | Legend colour |
|---|---|
| Proposed | Grey |
| Planned | Blue |
| Under Construction | Orange |
| Commissioned | Green |
| Decommissioned | Red |

### Timeline
Tick **Enable timeline** and drag the year slider to see the fleet as it would stand in that year:

- A facility counts as **Commissioned** from its commissioning year.
- It becomes **Decommissioned** once the year reaches its commissioning year plus its technology's lifetime.
- Facilities with no commissioning date keep their recorded status.

With the timeline off, each facility's recorded status is used.

### Technology
The **Technology** panel lists every facility technology on the map (for example *Onshore Wind*, *Single Axis PV*, *Battery*, *Gas OCGT*). Technologies are grouped under their category (Generator / Storage), and each shows its number of facilities in brackets.

- Untick a technology to hide those facilities.
- **All** / **None** in the panel header tick or untick every technology at once.
- Your selections are kept when the map refreshes after an edit. Any new technology is ticked by default.

### Summary
The **Summary** panel shows the number of visible facilities (**N**) and their total capacity (**MW**) for each status, with an overall total.

---

## Viewing Details

### Facilities
- **Hover** over a facility for a tooltip showing its name, technology, capacity and number of grid connections.
- **Click** a facility to open a popup with its technology, capacity, grid connection status and primary line, plus these buttons:
  - **Details**: opens the facility detail page in a new tab
  - **Edit**: opens the facility edit page in a new tab
  - **Connections**: manage the facility's grid connections (see *Grid Connections*)
  - **Move**: drag the facility to a new location (see *Editing on the Map*)

### Grid Lines
Click a grid line to see its name, voltage, thermal capacity and number of connected facilities, with **Details** and **Edit** buttons that open in a new tab. Hover over a line to see its connected capacity and utilisation.

Grid lines are coloured by voltage, and thicker lines are higher voltage:

| Voltage | Colour |
|---|---|
| ≥ 330 kV | Dark Red |
| ≥ 220 kV | Orange-Red |
| ≥ 132 kV | Orange |
| ≥ 66 kV | Gold |
| < 66 kV | Yellow |

The colour changes to show heavily loaded lines (connected capacity ÷ thermal capacity):

| Utilisation | Display |
|---|---|
| > 80% | Red, thicker |
| > 60% | Orange, slightly thicker |
| > 30% | Yellow |

### Terminals
Click a terminal to see its type, primary voltage and number of connected lines, with **Details** and **Edit** buttons (opening in a new tab) and a **Move** button. Hover over a terminal to see its utilisation. Terminals that are not yet commissioned are shown faded.

### Grid Utilisation
**Show Grid Utilization** opens a summary of how many grid lines have high (> 80%), medium (50–80%) and low utilisation. **Connections Overview** opens the infrastructure network diagram in a new tab.

---

## Adding Infrastructure

> **Prerequisite**: select a scenario first.

### Adding a Facility
1. Click **Add New Facility**. The cursor changes to a crosshair and the form opens.
2. Click on the map to set the location.
3. Enter the **Facility Name**, **Technology** and **Capacity (MW)**.
4. Choose a **Grid Connection Strategy**:
   - *Auto-connect to optimal grid line*: picks the best nearby line by distance, capacity and utilisation, within the **Minimum Voltage** and **Max Distance** you set
   - *Select specific grid line*: choose a line from the list. Recommended nearby lines are shown.
   - *Create new dedicated grid line*: creates a new line for this facility
5. Click **Save Facility**. A notice links to the facility page, where you can add installations (turbines, panels, storage).

Click **Cancel** (or the button again) to stop.

### Adding a Terminal
1. Click **Add New Terminal** and click on the map to set the location.
2. Enter the name, code, type, primary and secondary voltage, transformer capacity, number of bays, owner and description.
3. Click **Save Terminal**.

### Adding a Grid Line
1. Click **Add New Grid Line**.
2. Click on the map to set the start point, then click again for each waypoint along the route. At least two points are needed.
3. **Undo Last Point** removes the last click. The running length is shown as you go.
4. Click **Continue to Full Form →** to finish the line details (voltage, capacity, impedance, terminals) on the grid line form.

---

## Editing on the Map

### Moving Facilities and Terminals
1. Click the marker, then **Move**.
2. Drag the marker to the new position. A banner shows the coordinates.
3. Click **Save** on the banner to store the new location, or **Cancel** to put it back.

### Grid Connections
**Connections** in a facility popup opens the connection manager. There you can:

- add a connection to another grid line
- set the **primary** connection
- remove a connection

The map refreshes after each change.

### Zones
**Draw Zone Boundary** lets you click waypoints to outline a zone, then **Continue to Zone Form →** to name and save it. The **Zones** button lists the existing zones.

### SWIS Boundary
**Edit SWIS Boundary** (shown once the boundary has loaded) lets you change the boundary polygon:

- **Drag** a vertex to move it
- **Click** a line segment to insert a vertex
- **Right-click** a vertex to delete it

Zoom in first, because handles are only shown for the visible part of the boundary. Click **Save Boundary** to store the changes, or **Cancel** to discard them.

---

## Calculations

### Grid Line Utilisation

```
Utilisation (%) = (total connected facility capacity MW / thermal capacity MW) × 100
```

### Line Losses

Power losses on a transmission line are calculated using:

```
P_loss = (P² × R) / (V² × cos²φ)
```

Where:
- `P` = power flow (MW)
- `R` = total line resistance = `resistance_per_km × length_km` (Ω)
- `V` = operating voltage (kV)
- `cos(φ)` = power factor = 0.95 (assumed)

Losses on the spur connection between a facility and its grid connection point are calculated the same way, using the connection distance as the line length and standard cable specifications for the voltage class.

### Impedance

```
R_total = resistance_per_km × length_km   (Ω)
X_total = reactance_per_km × length_km    (Ω)
Z_total = √(R_total² + X_total²)          (Ω)
```

### Grid Line Length

When you draw a grid line, its length is the sum of the great-circle (Haversine) distances between consecutive points:

```
a = sin²(Δlat/2) + cos(lat1) × cos(lat2) × sin²(Δlon/2)
distance_km = 2 × R_earth × arcsin(√a)       [R_earth ≈ 6371 km]
```

### Terminal Bottlenecks

A terminal is a **bottleneck** when the total capacity of its connected facilities exceeds its transformer capacity (MVA). Bottlenecks are highlighted in red in the Network Overview.

---

## Related Help

- <a href="/help/powermap/" target="_blank" rel="noopener noreferrer">Powermap Help</a>: the rest of the Powermap module
- <a href="/help/transmission/" target="_blank" rel="noopener noreferrer">Transmission Help</a>: terminals, grid lines, losses and the Clean Energy Link (CEL)
