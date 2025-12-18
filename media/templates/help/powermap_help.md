# Powermap Module

## Overview
---
Powermap is an interactive mapping tool for modeling renewable energy generation in the South West Interconnected System (SWIS). It integrates with the System Advisor Model (SAM) to provide comprehensive energy planning capabilities.
---

### Scenario Management
#### Selecting a Scenario
1. Use the **Demand Year** dropdown to select the planning year
2. Choose a **Scenario** from the available options
3. Click **Apply Settings** to load the scenario data

#### Scenario Types
- **Current**: Existing infrastructure (read-only, no additions allowed)
- **Planning Scenarios**: Modifiable scenarios for future planning
- **Custom Scenarios**: User-created scenarios for specific studies
> **Note**: You cannot add facilities or grid lines to the "Current" scenario. Select a different scenario to add new infrastructure.

### Grid Map
The Powermap interface consists of:

- **Control Panel**: Top section for scenario selection and facility management
- **Interactive Map**: Central map showing facilities, grid lines, and infrastructure
- **Layer Controls**: Toggle different map layers (boundaries, zones, facilities, grid lines)

#### Basic Navigation
- **Pan**: Click and drag to move around the map
- **Zoom**: Use mouse wheel or zoom controls (+/-) 
- **Reset View**: Double-click to reset to default zoom level

#### Map Layers
Use the layer control panel (top-right of map) to toggle:

- ✅ **SWIS Boundary**: Regional boundary overlay
- ✅ **Zones**: Planning zones within SWIS
- ✅ **Grid Facilities**: Power generation facilities
- ✅ **Grid Lines**: Transmission and distribution infrastructure
- ✅ **Terminals**: Terminals and Sub-stations

#### Visual Elements
**Facility Icons**: Different colored icons represent various technologies:

- ⚫ Coal (coal.png)
- 🌞 Solar PV (solar.png)
- 💨 Wind (wind.png) 
- 🔋 Battery Storage (bess.png)
- 🏭 Reciprocating Engine (RECIP.png)
- ⚡ Combined Cycle Gas Turbine (CCGT.png)
- 🌱 Biomass (biomass.png)
- 💧 Pumped Hydro Storage (PHES.png)
- ⚙️ Default/Other (power_technology.png)
**Grid Lines**: Color-coded by voltage level:
- **Red**: 330kV+ (High voltage transmission)
- **Cyan**: 220kV (Sub-transmission)
- **Orange**: 132kV (Distribution)
- **Yellow**: <66kV (Local distribution)

### Viewing Facilities
#### Basic Facility Information
- **Hover** over any facility icon to see basic information in a tooltip
- **Click** on a facility icon to open detailed information

#### Facility Details Modal
When you click on a facility, a detailed modal window opens showing:

**Basic Information**
- Facility name and code
- Technology type and capacity (MW)
- Operational status (Active/Inactive)
- Commission and decommission dates
- Location coordinates
**Technical Specifications**
*For Wind Facilities:*
- Turbine model and specifications
- Hub height and number of turbines
- Rotor tilt angle and diameter
- Capacity per turbine
*For Solar Facilities:*
- Panel tilt and azimuth angles
- Tracking system type
- Inverter efficiency ratings
*For Battery Storage:*
- Storage capacity (MWh)
- Round-trip efficiency
- Charge/discharge rates
- State of charge limits
*For Thermal Plants:*
- Heat rate and fuel type
- Emission factors
- Minimum load factors
**Grid Connections**
- Connected transmission lines
- Connection voltage levels
- Distance to grid connection points
- Primary vs. secondary connections
- Calculated transmission losses
**Economic Data**
- Capital expenditure (CAPEX)
- Operating expenditure (OPEX) 
- Project lifetime and discount rates
**Performance Metrics**
- Capacity factor and annual output
- System availability
- Performance ratios

#### Facility Actions
From the facility details modal, you can:
- **Show on Map**: Center the map on the facility with highlighting
- **Calculate Losses**: View detailed transmission loss calculations
- **Edit Facility**: Modify facility parameters (if permissions allow)

### Grid Line Management
#### Viewing Grid Lines
- Grid lines appear as colored lines based on voltage level
- **Click** on any grid line to view detailed information
- Use **Toggle Grid Line Labels** button to show/hide line names
#### Grid Line Details Modal
Clicking on a grid line opens a detailed modal showing:
**Technical Specifications**
- Line name, code, and voltage level
- Line type (transmission, sub-transmission, distribution)
- Length and thermal capacity
- Electrical characteristics (resistance, reactance, impedance)
**Connected Facilities**
- List of all facilities connected to the line
- Connection distances and capacity allocations
- Primary vs. secondary connection indicators
**Performance Data**
- Current utilization levels
- Transmission losses at full capacity
- Emergency capacity ratings
**Operational Information**
- Owner and commissioning date
- Maintenance status and operational history

### Adding New Facilities
> **Prerequisites**: Select a modifiable scenario (not "Current")
#### Starting the Process
1. Click **Add New Facility** button
2. The button changes to "Cancel Add Facility" and the cursor becomes a crosshair
3. Click on the map to select the facility location
#### Facility Configuration
**Basic Settings**
1. **Facility Name**: Enter a descriptive name
2. **Technology**: Select from available technology types
3. **Capacity**: Enter capacity in megawatts (MW)
**Location Selection**
- Click anywhere on the map to set facility coordinates
- Coordinates are displayed and can be verified
- A temporary marker shows the selected location
**Grid Connection Options**
Choose one of three connection methods:
*Auto-connect to nearest grid line* (Recommended)
- System automatically finds the closest suitable grid line
- Shows nearby grid lines with distances and capacities
*Select existing grid line*
- Choose from a dropdown of available grid lines
- View technical specifications before selection
*Create new grid line*
- System creates a basic connection line
- Useful for remote locations without nearby infrastructure
**Wind Turbine Specific Settings**
For wind facilities, additional fields appear:
- **Turbine Model**: Select from available turbine types
- **Hub Height**: Height from ground to hub (meters)
- **Number of Turbines**: Total turbine count
- **Tilt**: Rotor tilt angle (typically 5° onshore, 0° offshore)
#### Completing the Process
1. Fill in all required fields
2. Click **Save Facility** to create the facility
3. The new facility appears immediately on the map
4. Success message confirms creation and grid connection details
#### Canceling
- Click **Cancel Add Facility** to exit without saving
- This removes temporary markers and resets the form
### Adding New Grid Lines
> **Prerequisites**: Select a modifiable scenario (not "Current")
### Starting the Process
1. Click **Add New Grid Line** button
2. The button changes to "Cancel Add Grid Line" and the cursor becomes a crosshair
3. Click two points on the map to define the line endpoints
#### Grid Line Configuration
**Basic Information**
- **Line Name**: Descriptive name for the transmission line
- **Line Code**: Short code identifier
- **Line Type**: Choose from transmission, sub-transmission, or distribution
**Technical Specifications**
- **Voltage Level**: Operating voltage in kilovolts (kV)
- **Thermal Capacity**: Maximum power transfer capacity (MW)
- **Resistance**: Electrical resistance per kilometer (Ω/km)
**Endpoint Definition**
1. **First Click**: Sets the starting point of the line
2. **Second Click**: Sets the ending point of the line
3. **Automatic Calculation**: System calculates line length and displays coordinates
#### Visual Feedback
- First endpoint shows a marker labeled "Grid Line Start Point"
- Second endpoint shows a marker labeled "Grid Line End Point"  
- A dashed red line connects the two points
- Length is automatically calculated and displayed
#### Completing the Process
1. Define both endpoints by clicking on the map
2. Fill in all technical specifications
3. Click **Save Grid Line** to create the line
4. The new grid line appears on the map with appropriate styling
5. Grid line becomes available for facility connections
#### Canceling
- Click **Cancel Add Grid Line** to exit without saving
- This removes all temporary markers and lines
### Advanced Powermap Features
#### Grid Line Labels
- Click **Toggle Grid Line Labels** to show/hide line names on the map
- Labels appear at the midpoint of each grid line
- Useful for identifying specific transmission corridors
#### Layer Management
Use the layer control to customize the view:
- Toggle facility visibility to focus on grid infrastructure
- Hide boundary layers for cleaner facility views
- Combine different layers for comprehensive planning views
#### Loss Calculations
Access detailed transmission loss analysis:
1. Click on any facility to open details modal
2. Click **Calculate Losses** button
3. View breakdown of connection losses vs. line losses
4. See percentage losses relative to facility capacity
#### Nearby Infrastructure Analysis
When placing new facilities:
- System automatically identifies nearby grid lines
- Distance and capacity information helps with siting decisions
- Transmission constraints are highlighted
#### Performance Metrics
For existing facilities, view:
- Historical capacity factors
- Annual energy output projections
- Grid connection utilization rates
- Environmental impact assessments
---
## Facilities Management

#### Facility Storage Installation
**What it is:** A *specific deployment* of a storage technology at a facility
**Examples:**
- "100 MW / 400 MWh BESS at Solar Farm A"
- "200 MW / 800 MWh BESS at Wind Farm B"
- Both using the same "Lithium-Ion BESS" technology
**Contains:**
- Power capacity (MW)
- Energy capacity (MWh)
- Duration (hours)
- Installation dates
- Active/inactive status
- Installation-specific notes
#### Why This Separation?
**Flexibility:** You can install the same battery technology at different facilities with different capacities
- Site A might need 100 MW
- Site B might need 200 MW
- Both use the same technology with the same efficiency
**Accuracy:** Technology characteristics (like 85% efficiency) don't change based on installation size
**Tracking:** You can track when each installation was commissioned, deactivate old installations, and add new ones
---
### Creating a New Installation
**Navigation:** Facility Installations → Add Storage Installation
#### Step 1: Select Facility and Technology
**Facility:** Choose where the storage will be located
- Dropdown shows all available facilities
- Required field
**Storage Technology:** Choose the type of storage
- Dropdown shows all storage technologies
- Required field
- Must select technology before entering capacity
**Installation Name:** Optional identifier for this installation
- Use if facility has multiple installations of same technology
- Examples: "Main Battery Bank", "North Array", "Phase 1"
- Leave blank if facility has only one installation
**Example:**
```
Facility: Solar Farm A
Technology: Lithium-Ion BESS
Installation Name: Main Battery Bank
```
#### Step 2: Specify Capacity
**Important:** This is where you define the actual size of this installation!
**Power Capacity (MW):** Maximum charge/discharge rate
- How fast the battery can charge or discharge
- Example: 100 MW
**Energy Capacity (MWh):** Total energy storage
- How much total energy the battery holds
- Example: 400 MWh
**Duration (hours):** How long battery can discharge at rated power
- Optional - automatically calculated if you provide power and energy
- Formula: Duration = Energy ÷ Power
- Example: 400 MWh ÷ 100 MW = 4 hours
**Auto-Calculation:** As you enter power and energy, the form shows calculated duration
**Example:**
```
Power: 100 MW (enter)
Energy: 400 MWh (enter)
Duration: 4.0 hours (automatically calculated)
```
**At Least One Required:** You must provide at least one capacity value (power, energy, or duration)
#### Step 3: Enter Installation Details
**Installation Date:** When physical installation occurred
- Optional
- Format: YYYY-MM-DD
- Example: 2024-03-15
**Commissioning Date:** When system began operations
- Optional
- Usually after installation date
- Format: YYYY-MM-DD
- Example: 2024-04-01
**Initial State of Charge:** Starting charge level for simulations
- Optional (uses technology default if not specified)
- Range: 0.0 to 1.0 (0% to 100%)
- Example: 0.5 (50%)
**Notes:** Free-form text field
- Additional information about this installation
- Examples:
  - "Phase 1 of planned expansion"
  - "Integrated with solar array"
  - "Primary frequency regulation unit"
**Example:**
```
Installation Date: 2024-03-15
Commissioning Date: 2024-04-01
Initial SOC: 0.5
Notes: Main battery bank integrated with 50 MW solar array
```
#### Step 4: Create Installation
Click **Create Installation**. The system will:
- Validate all inputs
- Check for duplicates
- Auto-calculate duration if possible
- Create the installation record
- Redirect to installation detail page
**Validation Rules:**
- At least one capacity value required
- If all three capacities provided, they must be consistent
- Power and energy must be positive numbers
- SOC must be between 0.0 and 1.0
#### Viewing Installation Details
**Navigation:** Click any installation name or "View" button
**What You'll See:**
#### Installation Information
- Facility name (with link)
- Storage technology (with link to tech details)
- Installation name
- Status (Active/Inactive badge)
- Installation date
- Commissioning date
- Created and last updated timestamps
#### Capacity Specifications (Primary Card)
- **Power Capacity:** MW rating
- **Energy Capacity:** MWh capacity
- **Duration:** Hours at rated power
- **Usable Capacity:** Accounting for SOC limits
- **Initial SOC:** For this installation
- **Capacity Summary:** One-line description
**Example:**
```
Power Capacity: 100 MW
Energy Capacity: 400 MWh
Duration: 4.0 hours
Usable Capacity: 320 MWh (based on 10-90% SOC limits)
Initial SOC: 0.5 (50%)
Capacity Summary: 100 MW / 400 MWh (4.0h)
```
#### Technology Characteristics
- Inherited from the storage technology
- Efficiency values (round-trip, charge, discharge)
- Operational limits (min/max SOC)
- Degradation data (cycle life, calendar life, self-discharge)
- **Link** to view full technology details
**Why Shown Here:** You can see the technology specs without leaving the installation view
#### Performance Metrics
Calculated values specific to this installation:
**Energy Metrics:**
- Usable energy after SOC limits
- Effective delivered energy per cycle (accounting for efficiency)
- Lifetime energy throughput (capacity × cycle life)
**Cycling Capability:**
- Total cycle life
- Suitability for daily cycling
- Expected years of operation
**Example:**
```
Usable Energy: 320 MWh (80% of 400 MWh, based on SOC limits)
Effective Energy per Cycle: ~400 MWh × 85% RTE
Lifetime Throughput: ~400 MWh × 5,000 cycles
Cycling Capability: 5,000 full cycles
  → Suitable for daily cycling (13+ years at 1 cycle/day)
```
### Notes Section
Displays any notes entered for this installation
#### Action Buttons
- **Edit Installation:** Modify capacity and settings
- **Back to List:** Return to installations list
- **Delete Installation:** Remove this installation (with confirmation)
#### Editing an Installation
**Navigation:** Installation Detail → Edit Installation
**What You Can Edit:**
- Installation name
- All capacity values (power, energy, duration)
- Installation dates
- Initial SOC override
- Active/inactive status
- Notes
**What You CANNOT Edit:**
- Facility (permanent after creation)
- Storage technology (permanent after creation)
**Why Fixed?** Facility and technology define the installation. If you need to change these, create a new installation.
#### Edit Form Sections
**Read-Only Fields:**
- Facility name (shown but grayed out)
- Storage technology (shown but grayed out)
**Editable Fields:**
- Installation name
- Power capacity (MW)
- Energy capacity (MWh)
- Duration (hours)
- Installation date
- Commissioning date
- Initial SOC
- Active checkbox
- Notes
**Auto-Calculation:** Duration updates as you modify power/energy
**Current Values Sidebar:**
- Shows current values for reference
- Links to technology details
**Saving Changes:**
1. Modify desired fields
2. Click **Update Installation**
3. System validates inputs
4. Redirects to installation detail page
**Validation:**
- At least one capacity value required
- Capacity values must be consistent if all three provided
- SOC must be between 0.0 and 1.0
### Deactivating an Installation
**Why Deactivate?** When storage is temporarily offline or permanently retired but you want to keep the record.
**How:**
1. Navigate to installation edit page
2. Uncheck "Installation is Active"
3. Add note explaining why (optional)
4. Click **Update Installation**
**Effect:**
- Installation marked as inactive
- **Excluded from simulations**
- Shown with gray background in list view
- **Not deleted** - data preserved for history
**Reactivating:** Simply check the "Active" box again
#### Deleting an Installation
**Warning:** This permanently removes the installation record!
**How:**
1. Navigate to installation detail page
2. Click **Delete Installation** button (red)
3. Confirm deletion in popup dialog
4. Installation is permanently deleted
**When to Delete vs. Deactivate:**
- **Deactivate:** Temporarily offline, might return, want to keep history
- **Delete:** Data entry error, duplicate entry, no longer needed
---
## Best Practices
### Creating Technologies
### Do:
- ✅ Use descriptive, consistent names
- ✅ Use manufacturer data sheets for specifications
- ✅ Document assumptions in the description field
- ✅ Enter all available data - more is better for modeling
- ✅ Verify efficiency values with manufacturer
### Don't:
- ❌ Create duplicate technologies with slightly different names
- ❌ Put capacity values in technology (they belong in installations!)
- ❌ Leave efficiency fields blank if data is available
- ❌ Use generic names like "Battery 1", "Battery 2"
- ❌ Mix different chemistries in one technology
### Creating Installations
### Do:
- ✅ Provide all three capacities (power, energy, duration) when known
- ✅ Use descriptive installation names at multi-battery facilities
- ✅ Enter installation and commissioning dates
- ✅ Add notes about unique characteristics or constraints
- ✅ Verify capacity values match purchase orders
- ✅ Set initial SOC based on operational practice
### Don't:
- ❌ Create installation before creating technology
- ❌ Guess at capacity values - verify with facility manager
- ❌ Leave installation unnamed at facilities with multiple batteries
- ❌ Forget to update status when storage is offline

### Signatures (Short Codes)
**Technologies:**
```
Good: "BESS4" (BESS)
Good: "PHES" (Pumped Hydro)
Good: "VRFB" (Vanadium Redox Flow Battery)
Bad: "B1" (not descriptive)
Bad: "Battery" (too generic)
Bad: "StorageTech1" (too long)
```
### Consistency Rules
- Use same units everywhere (MW, MWh, hours)
- SOC as decimal (0.0-1.0) not percentage
- Efficiency as percentage (85%) not decimal (0.85)
- Dates in ISO format (YYYY-MM-DD)
### Workflow Best Practices
### Before Creating Installation
1. ✅ Verify technology exists (or create it first)
2. ✅ Confirm facility exists in system
3. ✅ Gather all capacity specifications
4. ✅ Have installation dates ready
5. ✅ Know operational constraints
---
## Glossary
**AC/DC Conversion:** Converting alternating current to direct current (or vice versa). Most storage uses DC internally but connects to AC grid, so efficiency includes conversion losses.
**Active Installation:** Storage installation currently operational and included in simulations.
**Arbitrage:** Buying electricity when cheap (charging storage) and selling when expensive (discharging storage).
**Auxiliary Load:** Power consumed by storage system itself (cooling, controls, monitoring).
**BESS:** Battery Energy Storage System. Usually refers to lithium-ion batteries.
**Calendar Life:** Expected operational life in years, independent of usage.
**Capacity (Energy):** Total amount of energy that can be stored, measured in megawatt-hours (MWh).
**Capacity (Power):** Maximum rate of charging or discharging, measured in megawatts (MW).
**Commissioning:** Process of testing and activating a newly installed system.
**Cycle:** One complete charge and discharge sequence.
**Cycle Life:** Number of full charge-discharge cycles before significant degradation.
**Degradation:** Gradual loss of capacity over time due to aging and use.
**Depth of Discharge (DoD):** How much capacity is used. DoD = 1.0 - SOC.
**Dispatch:** Instruction to charge or discharge storage at specified rate.
**Duration:** How long storage can discharge at rated power. Duration = Energy ÷ Power.
**Efficiency:** Ratio of energy out to energy in. Never 100% due to losses.
**Energy Throughput:** Total amount of energy cycled through storage over its lifetime.
**Facility:** Physical location where storage is installed.
**Firming:** Using storage to smooth variable renewable generation.
**Flow Battery:** Storage technology where energy stored in liquid electrolyte tanks.
**Frequency Regulation:** Rapid adjustment of power to maintain grid frequency at 50/60 Hz.
**Installation:** Specific deployment of a storage technology at a facility.
**Lithium-Ion:** Common battery chemistry used in BESS.
**MW (Megawatt):** Unit of power. 1 MW = 1,000 kilowatts.
**MWh (Megawatt-hour):** Unit of energy. 1 MWh = 1 MW for 1 hour.
**Peak Shaving:** Reducing peak demand by discharging storage.
**Pumped Hydro Storage (PHES):** Storage by pumping water uphill, then releasing through turbines.
**Round-Trip Efficiency (RTE):** Energy recovered as percentage of energy stored.
**Self-Discharge:** Gradual loss of stored energy over time when idle.
**SOC:** State of Charge. Percentage of capacity currently stored (0-100%).
**Technology:** Type of storage system with defined characteristics.
**Time-Shifting:** Moving energy from one time period to another via storage.
**Usable Capacity:** Energy capacity accounting for SOC limits. = Energy × (Max SOC - Min SOC).

---
### Facility Installations List Screen
**What you see:**
- Three summary cards at top (total installations, power, energy)
- Filter/search panel
- Table of all installations
- Columns: Facility, Technology, Name, Power, Energy, Duration, Status
**What you can do:**
- Filter by facility, technology, or active status
- Search installations
- View installation details
- Edit installations
- Create new installation
- See aggregate statistics
### Facility Installation Detail Screen
**What you see:**
- Installation header with facility and technology
- Four main cards:
  1. Installation Information
  2. Capacity Specifications (highlighted)
  3. Technology Characteristics (inherited)
  4. Performance Metrics (calculated)
- Notes section if present
- Action buttons at bottom
**What you can do:**
- View complete installation details
- See capacity and calculated metrics
- Check technology characteristics
- Review performance analysis
- Edit installation
- Delete installation (with confirmation)
### Facility Installation Create/Edit Screen
**What you see:**
- Form with sections:
  1. Facility and Technology selection (or read-only in edit)
  2. Installation Name
  3. Capacity Specifications
  4. Installation Details
  5. Notes
- Sidebar with help and current values (in edit mode)
- Save/Cancel buttons
**What you can do:**
- Select facility and technology (create only)
- Enter installation name
- Specify capacities (auto-calculates duration)
- Set dates and initial SOC
- Toggle active status (edit only)
- Add notes
- Save or cancel
---
