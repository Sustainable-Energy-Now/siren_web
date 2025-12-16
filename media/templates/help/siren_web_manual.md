# A Complete User Guide to Modelling the SWIS with Siren Web

## System Overview
Siren Web is a web-based Django application inspired on Siren, an open-source Python application, designed for modeling renewable energy systems within the South West Interconnected System (SWIS). Siren Web provides comprehensive tools for energy planning through three main modules: Powermap, Powermatch, and Powerplot.

### Core Modules
- **Powermap**: Interactive mapping tool for modeling renewable energy generation and infrastructure
- **Powermatch**: Power supply and demand matching algorithms and analysis
- **Powerplot**: Visualization and plotting tools for modeling results
---

### System Requirements
- Web browser with JavaScript enabled
- Internet connection
- Valid user credentials (membership-based access)
### Access Levels
Siren Web implements a membership-based access system with four tiers:
- **Modelling Team**: Full access to all features and data
- **Active Member**: Full read access to all features
- **Lapsed Member**: Limited access to system functionality  
- **Subscriber/Non-member**: Basic access with restricted features
Access is automatically granted based on membership status when accessing the system through the appropriate authentication flow.
### Initial Setup
1. **Login** to the Siren Web system
2. **Review** user access level and available modules
3. **Select** appropriate demand year and scenario settings
4. **Navigate** to desired module (Powermap, Powermatch, or Powerplot)
---
## Main Interface
### Home Page Layout
The main interface displays:
1. **System Information Panel**: Shows current configuration settings
   - **Demand Year**: The year being used for demand modeling
   - **Scenario**: Currently selected modeling scenari
   - **Config**: Active configuration file
2. **Interactive System Architecture Diagram**: A clickable diagram showing the Siren system components
3. **Module Navigation**: Quick access to the three main analysis modules
### Current Session Settings
The settings panel at the top of the page displays the current modeling parameters:
```
Demand Year: [Year]
Scenario: [Scenario Name]
Config: [Configuration File]
```

These settings persist throughout a session and affect how the system processes requests across all modules.
---
## System Navigation
### Interactive System Diagram

The main feature of Siren Web is an interactive diagram that illustrates the system architecture. This diagram contains clickable areas (hotspots) that provide detailed information about each component.
### Available Components
Click on any of the following components to view detailed information:
**Database Tables**

- **Demand**: Load demand data and forecasting information
- **Weather**: Meteorological data used for renewable energy calculations
- **Facilities**: Power generation and storage facility specifications
- **Scenarios**: Different modeling scenarios and assumptions
- **Technologies**: Technology specifications and parameters
- **SupplyFactors**: Resource availability and capacity factors
- **Variations**: Parameter variations for sensitivity analysis
**Analysis Modules**
- **Powermap**: Geographic mapping of power resources and infrastructure
- **Powermatch**: Power supply and demand matching algorithms
- **Powerplot**: Visualization and plotting tools for results
- **SAM**: System Advisor Model integration
- **MAP**: Geographic information system components
- **Optimisation**: Optimization algorithms and parameters
- **Analysis**: Results analysis and reporting tools
### Using the Interactive Diagram
1. **Click on any component** in the diagram to view its details
2. A **modal window** will appear displaying:
   - Component name and description
   - Database structure (for data tables)
   - Sample data (first 5 rows)
   - Column definitions
3. **Close the modal** by clicking the X button or clicking outside the modal area
### Component Information Display
When you click on a component, you'll see:
- **Model Name**: The technical name of the component
- **Description**: Detailed explanation of the component's purpose and function
- **Data Structure**: 
  - Column names and their purposes
  - Sample data showing the format and typical values
  - Up to 5 example rows from the database
---
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
# Terminal Management
A comprehensive Django application for managing electrical grid terminals, grid lines, and facility connections with advanced analytics, health monitoring, and intelligent recommendations.
## Overview
The system provides management for electrical grid infrastructure, including:
- **Terminals/Substations**: Manage connection points in the grid
- **Grid Lines**: Track transmission and distribution lines
- **Facilities**: Monitor power generation and consumption facilities
- **Connections**: Establish relationships between all components
- **Analytics**: Real-time monitoring and health checks
- **Recommendations**: AI-powered connection suggestions
## Features
### Core Features
- ✅ Full CRUD operations for terminals
- ✅ Grid line connection management (from/to relationships)
- ✅ Facility-to-grid-line connections
- ✅ Search, filter, and pagination on all views
facility_wind_turbines
- ✅ Validation and safety checks
### Advanced Features
- ✅ System-wide dashboard with charts
- ✅ Health monitoring with alerts (Critical/Warning/Info)
- ✅ Intelligent connection suggestions with scoring
- ✅ Node topology visualization (D3.js)
- ✅ Loss calculations and load profiling
- ✅ Path finding between terminals
### Terminal Management
### Creating a Terminal
1. Click "Add New Terminal"
2. Required fields:
   - Terminal Name (unique)
   - Terminal Code (unique)
   - Primary Voltage (kV)
   - Latitude & Longitude
3. Optional fields: secondary voltage, capacity, owner, etc.
4. Click "Create Terminal"
### Editing a Terminal
1. Navigate to terminal detail page
2. Click "Edit"
3. Modify fields as needed
4. Click "Update Terminal"
### Deleting a Terminal
1. Navigate to terminal detail page
2. Click "Delete Terminal"
3. Confirm deletion
4. Note: Cannot delete if grid lines are connected
### Connection Management
### Connecting Grid Lines
1. Open terminal detail page
2. Click "Manage Connections"
3. Select grid line from dropdown
4. Choose direction:
   - **Outgoing (From)**: Line originates from this terminal
   - **Incoming (To)**: Line terminates at this terminal
5. Click "Add Connection"
### Removing Connections
1. Navigate to "Manage Connections"
2. Find grid line in outgoing/incoming lists
3. Click "Remove"
4. Confirm removal
### Viewing Connected Facilities
1. Click "View Connected Facilities"
2. See all facilities connected through terminal's grid lines
3. View capacity, direction, and connection details
### Dashboard & Monitoring
### System Dashboard
- **Location**: `/terminals/dashboard/`
- **Shows**: Total terminals, capacity, alerts, charts
- **Charts**: Voltage distribution, terminal types
### Health Check
- **Location**: `/terminals/health-check/`
- **Critical Issues**: >95% utilization, no connections
- **Warnings**: 80-95% utilization, unbalanced connections
- **Information**: Notable configurations
### Connection Suggestions
- **Location**: Terminal detail → "Connection Suggestions"
- **Features**: Proximity-based recommendations
- **Scoring**: Voltage compatibility (50%), Distance (30%), Capacity (20%)
- **One-click**: Connect directly from suggestions
---
### Wind Turbine Management Overview
The Wind Turbine Management System allows you to manage wind turbine models and their installations at facilities within the SIREN web application. The system consists of two main components:
1. **Wind Turbine Models** - Master database of turbine specifications
2. **Facility Installations** - Tracking of which turbines are installed where
---
### Wind Turbine Models
### Viewing Turbine Models
**Access:** Navigate to `/wind-turbines/` or use the "Wind Turbines" menu option.
The turbine models list displays all wind turbine types in the system with the following information:
- **Model**: Turbine model designation
- **Manufacturer**: Company that makes the turbine
- **Application**: Deployment type (Onshore, Offshore, or Floating)
- **Rated Power**: Maximum power output in kW
- **Hub Height**: Height from ground to turbine hub in meters
- **Rotor Diameter**: Total rotor diameter in meters
- **Cut-in/Cut-out Speed**: Wind speeds for operation start/stop
- **Installations**: Number of active installations using this model
### Search and Filtering
Use the filters above the table to find specific turbines:
- **Search Box**: Enter model name or manufacturer
- **Manufacturer Filter**: Select specific manufacturer
- **Application Filter**: Filter by Onshore, Offshore, or Floating
- **Clear Button**: Reset all filters
### Pagination
Large lists are paginated with 25 turbines per page. Use the pagination controls at the bottom to navigate between pages.
### Adding New Turbine Models
**Access:** Click "Add New Wind Turbine" button on the turbine list page.
#### Required Information
- **Turbine Model** (Required): Unique identifier for the turbine
  - Example: "V90-2.0 MW", "GE 2.5-120"
  - Must be unique across all turbines in the system
#### Optional Information
- **Manufacturer**: Company name (e.g., Vestas, GE, Siemens Gamesa)
- **Application**: Select from:
  - Onshore
  - Offshore  
  - Floating
- **Rated Power**: Maximum power output in kW
- **Hub Height**: Standard hub height in meters
- **Rotor Diameter**: Total rotor diameter in meters
- **Cut-in Speed**: Minimum wind speed to start generating (m/s)
- **Cut-out Speed**: Maximum wind speed before shutdown (m/s)
#### Guidelines
- Use exact manufacturer designations for consistency
- Verify specifications with manufacturer datasheets
- Typical values:
  - Rated Power: 500-15,000 kW
  - Hub Height: 80-140m
  - Cut-in Speed: 3-4 m/s
  - Cut-out Speed: 20-25 m/s
### Editing Turbine Models
**Access:** Click "Edit" button next to any turbine in the list, or "Edit" from the detail view.
- All fields can be modified except the database ID
- Changes won't affect existing installations but apply to new installations
- The system prevents duplicate model names
- If turbines are already installed, you'll see a warning about the impact
### Deleting Turbine Models
**Access:** Click "Delete Turbine" from the detail view or edit page.
#### Important Notes
- **Safety Check**: Turbines currently installed at facilities cannot be deleted
- Remove all installations first before deleting the turbine model
- Deletion is permanent and cannot be undone
- The system will show which facilities are using the turbine if deletion is blocked
---
## Creating Power Curves
### Option 1: Upload .pow File
1. Navigate to turbine detail page
2. Click "Upload Power Curve"
3. Select "Upload .pow File" method
4. Choose a file
5. Optionally add IEC class, source, and notes
6. Check "Set as Active" if desired
7. Click "Create Power Curve"
### Option 2: Manual Entry
1. Navigate to turbine detail page
2. Click "Upload Power Curve"
3. Select "Manual Entry" method
4. Enter a **File Name** (e.g., "V90-2.0-HH80.pow")
5. Enter **Wind Speeds** (space or comma-separated):
   ```
   1.0 2.0 3.0 4.0 5.0 6.0 7.0 8.0 9.0 10.0 11.0 12.0
   ```
6. Enter **Power Outputs** (must have same count):
   ```
   0.0 0.0 0.004 0.035 0.072 0.113 0.151 0.184 0.21 0.23 0.244 0.246
   ```
7. Select **IEC Class** from dropdown (optional)
8. Enter **Source** (e.g., "Wind_Turbines_CSV", "Manufacturer Datasheet")
9. Add **Notes** if desired
10. Check "Set as Active" if this should be the active curve
11. Click "Create Power Curve"
**Note**: `data_points` is automatically calculated from the length of arrays.
## Editing Power Curves
**update modes**:
### Mode 1: Metadata Only (Default)
Update only the metadata without touching the data:
- IEC Class
- Source
- Notes
- Active status
**Use when**: To update classification or notes.
### Mode 2: Edit Data Manually
Edit the wind speeds and power outputs directly in text fields:
- Pre-filled with current values
- Can modify individual values
- Can change file name
- Updates all metadata fields
**Use when**: To correct specific data points or add/remove values.
### Mode 3: Replace with File
Upload a new `.pow` file to completely replace the dataset:
- Replaces all wind speeds and power outputs
- Updates file name to new file's name
- Can still update metadata
**Use when**: To upload a completely new dataset from a file.
## Field Details
### File Name
- Required for manual entry
- Must be unique per turbine
- Good format: `{Model}-{Variant}.pow`
- Examples: "V90-2.0-HH80.pow", "GE-2.5-120-Custom.pow"
### Wind Speeds
- Required array of numeric values in m/s
- Accepts space or comma-separated format
- Examples:
  ```
  1.0 2.0 3.0 4.0 5.0
  ```
  or
  ```
  1.0, 2.0, 3.0, 4.0, 5.0
  ```
- Typically ranges from 0-30 m/s
### Power Outputs  
- Required array of numeric values in kW
- Must have **exact same count** as wind speeds
- Accepts space or comma-separated format
- Can include 0.0 values for below cut-in and above cut-out speeds
### Data Points
- **Automatically calculated** 
- System counts the number of wind speed values
- Displayed in the summary but not editable
### IEC Class
- Optional dropdown selection
- Options: I, II, III, IV, S
- **Class I**: High wind sites (10 m/s avg)
- **Class II**: Medium wind sites (8.5 m/s avg)  
- **Class III**: Low wind sites (7.5 m/s avg)
- **Class IV**: Very low wind sites (6 m/s avg)
- **Class S**: Special/custom conditions
### Source
- Optional text field
- Indicates where the data came from
- Examples:
  - "Wind_Turbines_CSV" (from the bulk import)
  - "Manufacturer Datasheet"
  - "Measured Data 2024"
  - "Warranty Curve"
  - "Manual Entry" (default for manual entry)
  - "File Upload" (default for file uploads)
### Notes
- Optional long text field
- Use for any additional context:
  - Hub height variant info
  - Testing conditions
  - Version numbers
  - Quality notes
  - Source documentation references
## Validation Rules
The system validates input:
1. **File Name**: Required for manual entry, must be unique per turbine
2. **Array Matching**: Wind speeds and power outputs must have same count
3. **Numeric Values**: All values must be valid numbers (integers or decimals)
4. **At Least One Point**: Must have at least one data point
5. **Active Curve**: Only one curve can be active per turbine (others auto-deactivate)
## Tips & Best Practices
### For Manual Entry:
- **Copy from spreadsheet**: You can copy columns from Excel/CSV and paste them into the text fields
- **Use consistent decimals**: 1-3 decimal places is typical
- **Include full range**: From below cut-in to above cut-out speeds
- **Verify count**: Make sure wind speeds and power outputs have same number of values
### For Editing:
- **Use "Metadata Only"** when you just need to update IEC class or source
- **Use "Edit Data Manually"** when you need to fix a few data points
- **Use "Replace with File"** when you have a completely new dataset
### For Organization:
- Use descriptive file names that indicate hub height, variant, etc.
- Fill in IEC class when known - helps with analysis
- Always fill in source - crucial for traceability
- Use notes for version info and important context
## Examples
### Example 1: Creating from CSV data
You have data in a CSV like this:
```csv
wind_speed,power_output
3.0,0.0
4.0,0.004
5.0,0.035
6.0,0.072
...
```
**Steps**:
1. Copy the wind_speed column (without header): `3.0 4.0 5.0 6.0 ...`
2. Paste into Wind Speeds field
3. Copy the power_output column: `0.0 0.004 0.035 0.072 ...`
4. Paste into Power Outputs field
5. Fill in metadata and save!
### Example 2: Editing to fix one value
You notice power output at 8 m/s is wrong.
**Steps**:
1. Click "Edit" on the power curve
2. Select "Edit Data Manually"
3. Find the value at position 8 in the Power Outputs field
4. Change the incorrect value
5. Save!
### Example 3: Adding IEC class to existing curve
You want to add IEC classification to a curve.
**Steps**:
1. Click "Edit" on the power curve
2. Keep "Metadata Only" selected (default)
3. Select IEC class from dropdown
4. Save!

### Editing Installations
**Access:** Click "Edit" button next to any installation in the list.
#### Editable Fields
- Number of turbines
- Tilt angle
- Primary direction
- Installation date
- Installation notes
- Active/Inactive status
#### Read-Only Information
- Facility (cannot be changed after creation)
- Turbine model (cannot be changed after creation)
#### Status Management
- Uncheck "Installation is Active" to deactivate without deleting
- Inactive installations are shown with gray background
- Inactive installations don't count toward capacity totals
### Removing Installations
**Access:** Click "Remove" button next to any installation.
- Removes the association between facility and turbine model
- Does not delete the facility or turbine model
- Requires confirmation before deletion
- Action is permanent and cannot be undone
---
### Navigation
### Quick Access Links
- **Wind Turbines List** → **Facility Installations**: "View Facility Installations" button
- **Facility Installations** → **Wind Turbines List**: "View Wind Turbines" button  
- **Any List** → **Add New**: Prominent "Add" buttons on each list page
- **Detail View** → **Edit**: "Edit" button in header or quick actions sidebar
### Breadcrumb Navigation
- Always use the "Back to List" buttons to return to list views
- Detail pages show the current item in the page header
- Edit pages show both item name and "Edit" indicator
---
### Tips and Best Practices
### Data Management
1. **Consistent Naming**: Use manufacturer's exact model designations
2. **Complete Specifications**: Fill in all available technical data for better analysis
3. **Regular Updates**: Keep installation dates and status current
4. **Validation**: Double-check specifications against manufacturer datasheets
### Performance
1. **Search Efficiently**: Use specific terms rather than browsing long lists
2. **Filter Combinations**: Combine multiple filters to narrow results quickly
3. **Pagination**: Lists are capped at 25 items per page for optimal performance
### Workflow Recommendations
1. **Add Turbine Models First**: Create turbine specifications before installing at facilities
2. **Check for Duplicates**: Search existing turbines before adding new ones
3. **Document Installations**: Use the notes field for important installation details
4. **Regular Audits**: Periodically review and update installation status
### Error Prevention
1. **Unique Models**: Each turbine model name must be unique
2. **Installation Limits**: One turbine model per facility (create separate entries for different configurations)
3. **Delete Order**: Remove installations before deleting turbine models
4. **Backup Important Data**: Export or document critical specifications before major changes
---

### Facilities Management Overview

The Facilities Management System provides comprehensive tools for managing power generation and storage facilities within the SIREN web application. Facilities represent the infrastructure that comprises the grid, including power plants, renewable energy installations, and storage systems.

---
### Viewing Facilities

**Access:** Navigate to `/facilities/` or use the "Facilities" menu option.
The facilities list displays all infrastructure in the system with the following information:
- **Facility Name**: Unique identifier for the facility
- **Technology**: Type of generation or storage technology
- **Zone**: Geographic or administrative zone location
- **Capacity**: Rated capacity of the facility
- **Capacity Factor**: Ratio of actual to potential output
- **Generation**: Expected or actual generation output
- **Transmitted**: Energy transmitted from the facility
- **Latitude/Longitude**: Geographic coordinates
### Search and Filtering
Use the comprehensive filter system above the table to find specific facilities:
- **Search Box**: Enter facility name, technology type, or zone name
- **Scenario Filter**: Filter by specific scenario associations
- **Technology Filter**: Select specific technology types
- **Zone Filter**: Filter by geographic zones
- **Clear Button**: Reset all filters to show all facilities
### Pagination
Large facility lists are paginated with 25 facilities per page. Use the pagination controls at the bottom to navigate between pages.
---
### Adding New Facilities
**Access:** Click "Add New Facility" button on the facilities list page.
### Required Information
- **Facility Name** (Required): Unique identifier for the facility
  - Use descriptive, clear names that identify the facility
  - Must be unique across all facilities in the system
  - Example: "Collie Solar Farm", "Kwinana Battery Storage"
### Basic Configuration
**Technology Selection**
- Choose from available technology types
- Technologies define the facility's generation or storage type
- Examples: Solar PV, Wind, Battery Storage, Gas Turbine, Coal
**Zone Assignment**
- Select the geographic or administrative zone
- Zones are used for regional analysis and planning
- Proper zone assignment is important for accurate modeling
### Technical Specifications
**Capacity Settings**
- **Capacity**: Rated capacity of the facility
  - Enter in megawatts (MW) for generation facilities
  - Enter in megawatt-hours (MWh) for storage facilities
  - Leave blank if not yet determined
**Capacity Factor**
- Ratio of actual to potential output (value between 0 and 1)
- Typical values by technology:
  - Solar PV: 0.15-0.25
  - Wind: 0.25-0.45
  - Baseload (Coal/Gas): 0.50-0.90
  - Battery Storage: N/A (use for generation facilities only)
**Generation and Transmission**
- **Generation**: Expected or actual annual generation output
- **Transmitted**: Energy transmitted from this facility
- Both values are optional but useful for analysis
### Location Information
**Geographic Coordinates**
- **Latitude**: Decimal degrees format (-90 to 90)
  - Southern hemisphere latitudes are negative
  - Example: -32.0569 for Perth area
- **Longitude**: Decimal degrees format (-180 to 180)
  - Eastern hemisphere longitudes are positive
  - Example: 115.7439 for Perth area
- Accurate coordinates are essential for:
  - Mapping and visualization
  - Spatial analysis
  - Transmission planning
  - Resource assessment
### Scenario Associations
**Multiple Scenario Selection**
- Check boxes next to scenarios this facility should belong to
- Facilities can be associated with multiple scenarios
- Unassociated facilities won't appear in scenario-specific analyses
- You can modify scenario associations later
### Guidelines and Best Practices
**Naming Conventions**
- Use consistent, descriptive names
- Include location and technology type when helpful
- Avoid special characters that may cause issues
- Examples:
  - "Collie_Solar_100MW"
  - "Kwinana Battery 50MWh"
  - "Albany Wind Farm"
**Technology Selection**
- Choose the primary technology for the facility
- For co-located technologies (hybrid sites), create separate installations
- Ensure technology choice matches the actual installation
**Capacity and Performance**
- Verify specifications with technical documentation
- Use manufacturer ratings for equipment capacity
- Base capacity factors on local resource availability
- Consider derating factors for aging equipment
---
### Editing Facilities
**Access:** Click "Edit" button next to any facility in the list, or "Edit" from the detail view.
### Editable Fields
All facility parameters can be modified:
- Facility name (must remain unique)
- Technology type
- Zone assignment
- Capacity and capacity factor
- Generation and transmission values
- Geographic coordinates
- Scenario associations
### Important Notes
- **Name Changes**: Can be updated but must remain unique
- **Technology Changes**: Changes affect all associated scenarios
- **Impact Warning**: Updates are reflected across all scenario analyses
- **Scenario Associations**: Can add or remove scenarios freely
- **Validation**: System prevents duplicate names and invalid values
### Update Guidelines
**When to Edit vs. Create New**
- **Edit** when correcting data or updating specifications
- **Create New** when:
  - Changing technology type significantly (e.g., solar to wind)
  - Modeling major equipment upgrades
  - Creating alternative configurations for comparison
**Scenario Impact**
- Changes immediately affect all associated scenarios
- Consider creating a new scenario if testing major modifications
- Export existing results before making significant changes
**Data Validation**
- Double-check coordinates before saving
- Verify capacity factors are realistic for the technology
- Ensure zone assignment is correct for regional analysis
---
### Facility Details
**Access:** Click on any facility name in the list or the "View" button.
The facility detail page provides comprehensive information organized into sections:
### Facility Information Panel
**Basic Details**
- Complete facility name and identification
- Technology type with visual badge
- Zone assignment
- Full technical specifications
- Location coordinates
**Performance Metrics**
- Current capacity rating
- Capacity factor
- Generation values
- Transmission data
### Associated Scenarios
View all scenarios that include this facility:
- Scenario names and descriptions
- Quick reference for scenario planning
- Shows which analyses will include this facility
### Wind Turbine Installations (Wind Facilities Only)
For wind technology facilities, additional information displays:
- **Turbine Models**: Installed turbine types and specifications
- **Configuration**: Number of units, tilt angles, directions
- **Installation Dates**: When turbines were installed
- **Links**: Direct access to wind turbine details
- **Capacity Breakdown**: Detailed capacity calculations
### Quick Actions Sidebar
**Available Actions**
- **Edit Facility**: Modify facility parameters
- **Add Wind Turbine**: Add turbine installations (wind facilities only)
- **Delete Facility**: Remove facility from system
**Location Information**
- Visual display of coordinates
- Quick reference for mapping
- Verification of location accuracy
**Statistics Summary**
- Number of associated scenarios
- Total capacity information
- Installation counts (for wind facilities)
---
### Deleting Facilities
**Access:** Click "Delete Facility" button from the facility detail page.
### Delete Process
1. Click the delete button to open confirmation modal
2. Review the warning about permanent deletion
3. Confirm deletion to proceed
4. System removes facility and all associations
### Important Warnings
- **Permanent Action**: Deletion cannot be undone
- **Scenario Impact**: Facility is removed from all scenarios
- **Relationship Removal**: All scenario associations are deleted
- **Data Loss**: All facility-specific data is permanently removed
### Before Deleting
**Consider These Steps First**
- Export facility data for records
- Document the reason for deletion
- Check if facility is referenced in reports or analyses
- Consider deactivating instead if temporarily out of service
**Alternative: Scenario Removal**
- Instead of deleting, remove from specific scenarios
- Preserves facility data for other uses
- Allows reactivation in future scenarios
---
### Integration with Other Modules
### Powermap Integration
Facilities created in the Facilities Management system appear automatically in Powermap:
- Visual representation on interactive map
- Geographic distribution analysis
- Grid connection planning
- Transmission loss calculations
**Synchronization**
- Changes in Facilities Management immediately reflect in Powermap
- Location updates automatically adjust map markers
- Capacity changes affect power flow calculations
### Powermatch Integration
Facility data flows into Powermatch for analysis:
- Technology dispatch optimization
- Capacity factor utilization
- Generation profiles
- Economic analysis (LCOE calculations)

## Demand Forecast
---
### Overview
The Demand Forecast module provides tools for projecting future electricity demand for the South West Interconnected System (SWIS). It enables users to:
- Create demand forecasts based on historical hourly data
- Model different growth scenarios (operational and underlying demand)
- Compare multiple projection scenarios
- Export projections for use in RET dashboard and reporting functions
- Analyze peak demand and annual energy consumption trends
#### Key Features
- **Hourly Resolution**: Projects all 8760 hours of the year based on base year patterns
- **Dual Demand Streams**: Separate modeling of operational and underlying demand
- **Multiple Growth Models**: Linear, exponential, S-curve, and compound growth options
- **Scenario Comparison**: Visualize and compare different growth assumptions
- **Interactive Controls**: Adjust parameters in real-time with sliders
- **Integration Ready**: Outputs compatible with RET dashboard and reporting
- **Project demand** from a base year to future years
- **Adjust projections in real-time** with interactive controls
---
## Getting Started
### Accessing the Tool
1. Log in to the SIREN web interface
2. Ensure you have selected a valid configuration file (siren.ini)
3. Navigate to the Demand Projection page from the main menu
### Understanding Demand Types
The system models two distinct types of electricity demand:
#### Operational Demand
**What it is**: Grid-visible demand measured at transmission level
**Data Source**: `supplyfactors` table, facility ID 144
**Characteristics**:
- Represents actual load on the grid
- Measured hourly (8760 data points per year)
- Includes commercial, industrial, and residential consumption
- Net of rooftop solar generation
**Typical Growth Rate**: 2-3% per year (moderate growth)
#### Underlying Demand
**What it is**: Total electricity consumption including distributed generation
**Data Source**: `DPVGeneration` table (AEMO data)
**Characteristics**:
- Represents true consumption before distributed PV offset
- Based on distributed photovoltaic (DPV) generation estimates
- Converted from 30-minute intervals to hourly values
- Shows actual customer consumption patterns
**Typical Growth Rate**: 4-8% per year (higher due to electrification trends)
#### Total Demand
**Calculation**: Operational Demand + Underlying Demand
**Interpretation**: Comprehensive view of future grid requirements
---
### Configuration
#### Configuration File Location
Configuration is stored in:
```
siren_web/siren_files/preferences/siren.ini
```
#### Main Configuration Section
```ini
[demand projection]
base_year = 2024
operational_growth_rate = 0.025
operational_growth_type = exponential
operational_saturation = 2.0
operational_midpoint_year = 2035
underlying_growth_rate = 0.04
underlying_growth_type = s_curve
underlying_saturation = 3.5
underlying_midpoint_year = 2040
projection_start_year = 2024
projection_end_year = 2050
```
#### Parameter Descriptions
| Parameter | Description | Typical Range |
|-----------|-------------|---------------|
| `base_year` | Starting year for projections | 2024 |
| `operational_growth_rate` | Annual growth rate for operational demand | 0.015 - 0.04 (1.5% - 4%) |
| `operational_growth_type` | Growth model type | linear, exponential, s_curve, compound |
| `operational_saturation` | Maximum growth multiplier (S-curve only) | 1.5 - 2.5 |
| `operational_midpoint_year` | Inflection point year (S-curve only) | 2030 - 2040 |
| `underlying_growth_rate` | Annual growth rate for underlying demand | 0.02 - 0.08 (2% - 8%) |
| `underlying_growth_type` | Growth model type | linear, exponential, s_curve, compound |
| `underlying_saturation` | Maximum growth multiplier (S-curve only) | 2.5 - 5.0 |
| `underlying_midpoint_year` | Inflection point year (S-curve only) | 2035 - 2045 |
| `projection_start_year` | First year to project | Same as base_year |
| `projection_end_year` | Last year to project | 2050 - 2060 |
---
#### Initial View
When you first open the tool, you'll see:
- **Control Panel** (top) - Where you select parameters
- **Results Area** (middle) - Where charts are displayed
- **Summary Statistics** (bottom) - Key metrics and totals
---
## Demand Forecast Form
### Control Panel Components
The control panel contains all the settings for generating projections:
#### 1. Base Year Selector
- **What it does**: Selects the historical year to project from
- **Options**: Only years with complete operational data (8760 hours) are available
- **Default**: Most recent year with complete data
#### 2. Project To Year Selector
- **What it does**: Selects the final year of a projection
- **Options**: Years up to 2040
- **Default**: 2040
- **Recommendation**: Choose based on your planning horizon (10-30 years typical)
#### 3. View Mode Selector
Three viewing modes are available:
**Single Projection**
- Shows total demand over time
- Best for: Quick overview, presentations
- Display: Single line showing combined demand
**Operational vs Underlying**
- Shows stacked area chart of both demand components
- Visualizes contribution of each demand type
- Helps understand demand composition changes over time
**Compare Scenarios**
- Overlays multiple scenarios on one chart
- Best for: Scenario analysis, decision making
- Display: Multiple lines, one per scenario
#### 4. Scenario Selector
- **What it does**: Chooses pre-configured growth assumptions
- **Options**:Set by system configuration (e.g., "Low Growth", "High Growth", "DPV Revolution")
- **Default**: "Current Config"
#### 5. Generate Projection Button
- **What it does**: Calculates and displays the projection
- **Action**: Click to run the projection with current settings
#### Interactive Controls (Collapsible Panel)
Click **"Adjust Growth Rates"** to expand additional controls:
#### Interactive Growth Rate Sliders
Two sliders allow real-time adjustment:
**Operational Demand Growth Rate**
- Range: 0% to 10% per year
- Controls: Growth of grid-supplied electricity demand
- Default: Set by selected scenario
**Underlying Demand Growth Rate**
- Range: 0% to 15% per year
- Controls: Growth of behind-the-meter demand (e.g., distributed solar)
- Default: Set by selected scenario
**Slider Controls:**
- **Reset to Scenario Defaults**: Returns sliders to scenario values
- **Apply Custom Rates**: Recalculates projection with slider values
#### Results Display Area
Shows the interactive Plotly chart with:
- **Time axis (X)**: Years from base year to projection end
- **Demand axis (Y)**: Annual demand in GWh or peak demand in MW
- **Hover tooltips**: Show exact values when you mouse over
- **Zoom controls**: Top right corner of chart
- **Legend**: Identifies lines/areas (click to hide/show)
#### Summary Statistics Cards
Four key metrics displayed after projection:
1. **Base Year Demand** (GWh/year)
   - Total annual demand in base year
2. **End Year Demand** (GWh/year)
   - Projected total demand in final year
3. **Total Growth** (%)
   - Percentage increase from base to end year
4. **Average Annual Growth** (% per year)
   - Average compound annual growth rate
**Configuration Summary**
- Shows the growth rates and models used for the projection
---
### Basic Operations
#### Creating a Projection
**Step 1: Select Parameters**
1. Choose a **Base Year** (e.g., 2024)
2. Choose **Project To Year** (e.g., 2050)
3. Leave **View Mode** as "Single Projection"
4. Leave **Scenario** as "Current Config"
**Step 2: Generate**
1. Click **"Generate Projection"**
2. Wait for calculation (typically 1-2 seconds)
3. View results in chart and summary cards
**Step 3: Interpret**
1. Look at the demand curve - is it growing as expected?
2. Check summary statistics - what's the total growth?
3. Note the configuration used
#### Changing the Time Horizon
To see a shorter or longer projection:
1. Change **"Project To Year"**
   - Shorter horizon (e.g., 2035): More certain, near-term planning
   - Longer horizon (e.g., 2060): Less certain, strategic planning
2. Click **"Generate Projection"** again
3. Compare the results
**Use Cases:**
- **10-year horizon**: Operational planning, budgeting
- **20-year horizon**: Infrastructure investment decisions
- **30-year horizon**: Long-term strategic planning
- **40+ year horizon**: Policy analysis, climate scenarios
---
### View Modes
#### Single Projection Mode
**When to use:**
- Quick overview of total demand
- Presentations to executives or stakeholders
- Comparing single scenario changes
- Simple what-if analysis
**What you see:**
- Single line showing total demand (operational + underlying)
- Clean, simple visualization
- Summary stats show combined totals
**Example use:**
"Show me what demand will be in 2050 under current assumptions"
#### Operational vs Underlying Mode
**When to use:**
- Detailed analysis of demand components
- Understanding behind-the-meter vs grid demand
- Planning for distributed generation impacts
- Analyzing net load implications
**What you see:**
- Stacked area chart with two layers:
  - **Bottom layer (blue)**: Operational demand (grid-supplied)
  - **Top layer (green)**: Underlying demand (behind-the-meter, DPV)
- Total = sum of both layers
**Key insights:**
- How much is grid demand growing?
- How much is distributed generation growing?
- What's the relationship between the two?
**Example use:**
"Show me how rooftop solar growth affects total demand composition"
#### Compare Scenarios Mode
**When to use:**
- Evaluating different growth assumptions
- Risk analysis (best/worst case)
- Policy impact assessment
- Decision support
**What you see:**
- Multiple lines, one per scenario
- Different colors for each scenario
- All on same scale for easy comparison
- Legend shows which line is which scenario
**How to use:**
1. Change **View Mode** to "Compare Scenarios"
2. Check the boxes for scenarios you want to compare
3. Click **"Generate Projection"**
4. Compare the divergence of lines over time
**Example use:**
"Compare 'Low Growth', 'Medium Growth', and 'High Growth' scenarios to understand our range of possible futures"
---
---
### Growth Models
#### Linear Growth
**Formula**: `Demand(t) = Base × (1 + rate × years)`
**Characteristics**:
- Constant absolute increase each year
- Simple and conservative
- No acceleration or deceleration
**Best For**:
- Stable, mature markets
- Short-term projections (5-10 years)
- Pessimistic scenarios
**Example**: 2% linear growth
- Year 1: 100 GWh → Year 10: 120 GWh
- Adds 2 GWh each year
#### Exponential Growth
**Formula**: `Demand(t) = Base × (1 + rate)^years`
**Characteristics**:
- Compound growth each year
- Accelerating absolute increase
- Most common model for demand forecasting
**Best For**:
- Growing markets
- Standard economic growth assumptions
- Medium-term projections (10-20 years)
**Example**: 2% exponential growth
- Year 1: 100 GWh → Year 10: 121.9 GWh
- Growth accelerates over time
#### S-Curve (Logistic Growth)
**Formula**: `Growth Factor = 1 + (saturation - 1) / (1 + e^(-k × (year - midpoint)))`
**Characteristics**:
- Slow initial growth
- Rapid growth around midpoint year
- Levels off approaching saturation limit
- Models technology adoption curves
**Best For**:
- Electrification scenarios (EVs, heat pumps)
- Technology penetration
- Long-term projections with limits (20-30 years)
**Parameters**:
- **Saturation**: Maximum growth multiplier (e.g., 3.0 = 3× base demand)
- **Midpoint Year**: Year of maximum growth rate
- **Rate**: Steepness of the curve
**Example**: S-curve with saturation 3.0, midpoint 2035
- 2024-2030: Slow growth (~2% pa)
- 2030-2040: Rapid growth (5-8% pa)
- 2040-2050: Slowing growth, approaching 3× base
#### Compound Growth
**Formula**: `Demand(t) = Base × (1 + rate)^years`
**Characteristics**:
- Identical to exponential growth
- Continuous compounding
- Standard financial growth model
**Best For**:
- Economic growth alignment
- Consistency with financial models
- Similar to exponential in practice
---
### Working with Scenarios
#### What Are Scenarios?
Scenarios are pre-configured sets of growth assumptions. Each scenario represents a different possible future based on:
- Economic growth rates
- Technology adoption curves
- Policy impacts
- Behavioral changes
#### Defining Scenarios
Scenarios are defined in siren.ini using the format:
```ini
[Scenario: Scenario Name]
operational_growth_rate = 0.03
underlying_growth_rate = 0.05
operational_growth_type = exponential
underlying_growth_type = s_curve
underlying_saturation = 4.0
operational_midpoint_year = 2035
underlying_midpoint_year = 2038
```
### Example Scenarios
#### Low Growth (Conservative)
```ini
[Scenario: Low Growth]
operational_growth_rate = 0.015
underlying_growth_rate = 0.02
operational_growth_type = linear
underlying_growth_type = linear
```
**Use Case**: Economic stagnation, energy efficiency improvements, population decline
**Assumptions**:
- Minimal load growth
- Strong energy efficiency
- Limited electrification
- Stable population
#### High Growth (Aggressive Electrification)
```ini
[Scenario: High Growth]
operational_growth_rate = 0.04
underlying_growth_rate = 0.08
operational_growth_type = exponential
underlying_growth_type = s_curve
underlying_saturation = 5.0
operational_midpoint_year = 2033
underlying_midpoint_year = 2037
```
**Use Case**: Rapid EV adoption, industrial expansion, hydrogen production
**Assumptions**:
- High population growth
- Rapid EV penetration (50%+ by 2040)
- Heat pump adoption
- Industrial electrification
- Hydrogen electrolyzers
#### Moderate Electrification (Recommended Default)
```ini
[Scenario: Moderate Electrification]
operational_growth_rate = 0.025
underlying_growth_rate = 0.04
operational_growth_type = exponential
underlying_growth_type = s_curve
underlying_saturation = 3.5
operational_midpoint_year = 2035
underlying_midpoint_year = 2040
```
**Use Case**: Balanced outlook, aligns with AEMO forecasts
**Assumptions**:
- Moderate population growth (~2% pa)
- EV penetration reaches 30-40% by 2040
- Some electrification of heating/cooling
- Gradual industrial growth
### Available Scenarios
The system may include scenarios like:
#### Low Growth / Conservative / Business As Usual
- **Assumptions**: Minimal change from current trends
- **Growth Type**: Linear (steady, predictable)
- **Growth Rates**: 1.5-2% annually
- **Use for**: Conservative planning, worst-case for capacity
#### Medium Growth / Base Case
- **Assumptions**: Moderate economic and technology growth
- **Growth Type**: Exponential (compound growth)
- **Growth Rates**: 2.5-4% annually
- **Use for**: Most likely scenario, standard planning
#### High Growth / Electrification
- **Assumptions**: Aggressive electrification (EVs, heat pumps)
- **Growth Type**: Exponential (compound growth)
- **Growth Rates**: 4-8% annually
- **Use for**: High-demand planning, stress testing
#### DPV Revolution / Solar Boom
- **Assumptions**: Rapid distributed solar adoption
- **Growth Type**: S-curve (technology adoption curve)
- **Growth Rates**: Up to 12% peak growth
- **Use for**: Understanding solar impact, net load planning
#### Selecting a Scenario
**Single Projection Mode:**
1. Use the **Scenario** dropdown
2. Select desired scenario
3. Click **"Generate Projection"**
**Compare Mode:**
1. Change to **"Compare Scenarios"** view mode
2. Check boxes for scenarios to compare (2-4 recommended)
3. Click **"Generate Projection"**
#### Understanding Scenario Differences
Different scenarios vary in:
1. **Growth Rate**: How fast demand increases
2. **Growth Type**: Shape of the growth curve
3. **Saturation Level**: Maximum growth multiplier (for S-curve)
4. **Component Focus**: Which demand type grows faster
**Example Comparison:**
| Scenario | Operational Growth | Underlying Growth | Type |
|----------|-------------------|-------------------|------|
| Low Growth | 1.5% | 2.0% | Linear |
| Medium Growth | 2.5% | 4.0% | Exponential |
| High Growth | 4.0% | 8.0% | Exponential |
| DPV Revolution | 3.0% | 12.0% | S-curve |
---
### Using Interactive Controls
#### Growth Rate Sliders
The sliders let you override scenario assumptions and test custom growth rates.
#### Opening the Slider Panel
1. Click **"Adjust Growth Rates"** accordion
2. Panel expands showing two sliders
#### Understanding the Sliders
**Operational Demand Growth Rate Slider**
- **Range**: 0% (no growth) to 10% (very high growth)
- **Controls**: Grid-supplied electricity demand
- **Factors**: Economic growth, electrification, population
- **Display**: Shows current value as badge
**Underlying Demand Growth Rate Slider**
- **Range**: 0% (no growth) to 15% (extremely high growth)
- **Controls**: Behind-the-meter demand (distributed generation)
- **Factors**: Solar adoption, battery storage, prosumer behavior
- **Display**: Shows current value as badge
#### Using the Sliders
**Step 1: Select a Base Scenario**
1. Choose a scenario from dropdown (e.g., "Medium Growth")
2. Generate projection to see baseline
**Step 2: Adjust Sliders**
1. Click **"Adjust Growth Rates"** to expand
2. Move sliders to desired values
3. Watch badge update with new percentage
**Step 3: Apply Changes**
1. Click **"Apply Custom Rates"** button
2. New projection generates with custom rates
3. Compare with original scenario
**Step 4: Reset if Needed**
1. Click **"Reset to Scenario Defaults"** to return to scenario values
2. Sliders return to original positions
#### Slider Best Practices
**Testing Sensitivity:**
```
1. Start with base scenario projection
2. Move ONE slider at a time
3. Note how much the projection changes
4. This shows sensitivity to that parameter
```
**Creating Custom Scenarios:**
```
1. Start with closest existing scenario
2. Adjust both sliders according to assumptions
3. Apply and review results
4. Save screenshot or export data
```
**Bracketing Uncertainty:**
```
1. Run projection with sliders at minimum plausible values
2. Run again with sliders at maximum plausible values
3. This gives you a range of possible futures
```
---
### Interpreting Results
#### Understanding the Chart
#### Chart Types by View Mode
**Single Projection (Line Chart)**
- **X-axis**: Years (e.g., 2024, 2025, ..., 2050)
- **Y-axis**: Annual Demand (GWh/year)
- **Line**: Total demand trajectory
- **Interpretation**: How fast is demand growing?
**Operational vs Underlying (Stacked Area)**
- **X-axis**: Years
- **Y-axis**: Annual Demand (GWh/year)
- **Bottom area (blue)**: Operational demand
- **Top area (green)**: Underlying demand
- **Total height**: Combined demand
- **Interpretation**: What's driving growth - grid or distributed?
**Compare Scenarios (Multiple Lines)**
- **X-axis**: Years
- **Y-axis**: Annual Demand (GWh/year)
- **Multiple lines**: One per scenario
- **Spread**: Shows range of uncertainty
- **Interpretation**: How different might the future be?
#### Using Hover Tooltips
1. **Move mouse over chart**
2. **Tooltip appears** showing:
   - Exact year
   - Exact demand value(s)
   - Component breakdown (in stacked mode)
3. **Useful for**: Getting precise numbers for any year
#### Using Chart Controls
**Zoom In:**
1. Click and drag on chart to select area
2. Chart zooms to selected region
3. Double-click to reset zoom
**Pan:**
1. After zooming, click and drag to pan
2. Explore different parts of timeline
**Legend Interaction:**
1. Click legend item to hide/show that data series
2. Useful in compare mode to focus on specific scenarios
3. Click again to show hidden series
**Download Chart:**
1. Hover over chart
2. Click camera icon (top right)
3. Download as PNG image
#### Reading Summary Statistics
#### Base Year Demand
- **Shows**: Total demand in the selected base year
- **Unit**: GWh/year (gigawatt-hours per year)
- **Interpretation**: Starting point for projections
- **Typical values**: 5,000-50,000 GWh depending on region
#### End Year Demand
- **Shows**: Projected total demand in final year
- **Unit**: GWh/year
- **Interpretation**: Where demand is heading
- **Compare to**: Base year to see absolute growth
#### Total Growth
- **Shows**: Percentage increase from base to end year
- **Unit**: Percentage (%)
- **Formula**: ((End - Base) / Base) × 100
- **Interpretation**: Overall scale of change
- **Typical values**:
  - 10-30%: Low growth over 25 years
  - 30-70%: Moderate growth
  - 70-150%: High growth
  - 150%+: Very high growth (e.g., aggressive electrification)
#### Average Annual Growth
- **Shows**: Compound annual growth rate (CAGR)
- **Unit**: % per year
- **Formula**: (End/Base)^(1/years) - 1
- **Interpretation**: Sustained annual growth rate
- **Typical values**:
  - 0.5-1.5%: Low growth
  - 1.5-3.5%: Moderate growth
  - 3.5-5%: High growth
  - 5%+: Very high growth
#### Configuration Summary
Shows the parameters used:
- Operational growth rate and type
- Underlying growth rate and type
- Useful for: Documentation, reproducibility
#### Understanding Growth Patterns
#### Linear Growth
```
Demand curve: Straight line upward
Characteristics: Steady, predictable increase
Example: Adding 250 GWh every year
Use for: Conservative, stable demand
```
#### Exponential Growth
```
Demand curve: Upward curve (accelerating)
Characteristics: Compound growth, accelerates over time
Example: Growing 3% per year (compounds)
Use for: Economic growth, general demand
```
#### S-Curve (Logistic Growth)
```
Demand curve: S-shaped
  - Slow start
  - Rapid acceleration
  - Slowing as it saturates
Characteristics: Technology adoption pattern
Example: EV adoption, solar deployment
Use for: New technologies, market saturation
```
#### What Different Results Mean
**Scenario: Low base demand, high growth rate**
- **Pattern**: Steep upward curve
- **Meaning**: Starting small but growing fast
- **Example**: Emerging technology adoption
- **Action**: Plan for rapid infrastructure expansion
**Scenario: High base demand, low growth rate**
- **Pattern**: High but flat
- **Meaning**: Mature market, saturated
- **Example**: Established urban area
- **Action**: Focus on efficiency, replacement
**Scenario: Diverging scenarios**
- **Pattern**: Lines spread apart over time
- **Meaning**: High uncertainty in future
- **Example**: Policy-dependent outcomes
- **Action**: Plan for flexibility, multiple contingencies
**Scenario: Operational flat, underlying growing**
- **Pattern**: Top layer growing, bottom flat
- **Meaning**: Distributed generation offsetting demand
- **Example**: High solar adoption
- **Action**: Plan for net load management, duck curve
---
### Advanced Features
#### Peak Demand Analysis
In addition to annual totals, the system tracks peak demand:
**What is Peak Demand?**
- Maximum MW demanded in any single hour
- Critical for: Capacity planning, infrastructure sizing
- Shown in: Projection results data
**How to analyze:**
1. Generate projection
2. Note peak MW values in results
3. Compare peak growth to total growth
4. Plan capacity accordingly
**Typical pattern:**
- Peak often grows faster than total
- Due to: Increased air conditioning, charging concentration
- Important for: Generation capacity, transmission limits
#### Sensitivity Analysis
Test how results change with different assumptions:
**Method 1: Slider Sensitivity**
1. Generate base projection
2. Note key metrics (screenshot helpful)
3. Adjust ONE slider by +2%
4. Regenerate and compare change
5. Reset and adjust OTHER slider by +2%
6. Compare which has more impact
**Method 2: Scenario Range**
1. Use Compare mode
2. Select Low, Medium, High scenarios
3. Generate projection
4. Measure spread between lines at key years (e.g., 2040)
5. Spread = uncertainty / sensitivity
**Example output:**
```
2040 Projections:
Low Growth:     15,500 GWh
Medium Growth:  18,200 GWh  
High Growth:    22,800 GWh
Range:          7,300 GWh (47% variation)
Conclusion:     High uncertainty - plan for flexibility
```
### Time-Series Analysis
Understanding demand evolution over specific periods:
**Near-term (Base year + 5-10 years):**
- Most certain
- Use for: Immediate planning, budgets
- Typically: Close to current trends
**Mid-term (10-20 years):**
- Moderate certainty
- Use for: Infrastructure investment decisions
- Watch for: Policy impacts, technology inflection points
**Long-term (20-40 years):**
- High uncertainty
- Use for: Strategic planning, scenario planning
- Expect: Wide divergence between scenarios
**Analysis technique:**
1. Generate 2024-2050 projection
2. Note demand in 2030, 2040, 2050
3. Calculate growth rates for each decade:
   - 2024-2030: Early period
   - 2030-2040: Middle period
   - 2040-2050: Late period
4. Compare: Is growth accelerating or stabilizing?
### Exporting Results
**Screenshot Method:**
1. Generate projection
2. Use browser screenshot tool or:
3. Click camera icon on chart
4. Save image for reports
**Data Export (if enabled):**
1. Generate projection
2. Look for "Export" button (if available)
3. Download CSV with annual values
4. Use in Excel or other tools
---
## Glossary
### Terms
**Annual Demand**
- Total electricity consumed in one year
- Measured in: GWh (gigawatt-hours) or MWh (megawatt-hours)
- Example: 12,500 GWh/year
**Base Year**
- Historical year with actual data
- Starting point for projections
- Typically: Most recent complete year
**Behind-the-Meter**
- Electricity generation on customer side of meter
- Examples: Rooftop solar, battery storage
- Also called: Distributed generation, DPV
**CAGR (Compound Annual Growth Rate)**
- Average annual growth rate over period
- Accounts for compounding effect
- Formula: (End/Start)^(1/years) - 1
**Distributed Photovoltaic (DPV)**
- Solar panels on homes and businesses
- Behind-the-meter generation
- Offsets grid demand
**Duck Curve**
- Net load pattern with high solar penetration
- Shape: High morning, low midday, high evening
- Challenge: Steep evening ramp required
**Exponential Growth**
- Growth that compounds over time
- Gets faster each year
- Like: Bank interest compounding
**GWh (Gigawatt-hour)**
- Energy unit = 1,000 MWh = 1,000,000 kWh
- Typical: Annual regional demand
- Example: Small city uses ~1,000 GWh/year
**Growth Rate**
- Percentage increase per year
- Example: 3% means growing 3% annually
- Can be: Linear or compound
**Growth Type**
- Shape of growth curve
- Options: Linear, Exponential, S-curve
- Affects: How fast growth accelerates
**Linear Growth**
- Constant absolute increase each year
- Same amount added annually
- Like: Adding 100 GWh every year
**MW (Megawatt)**
- Power unit = 1,000 kW
- Typical: Peak demand measurement
- Example: Large city peaks at 2,000 MW
**MWh (Megawatt-hour)**
- Energy unit = 1,000 kWh
- Typical: Daily or monthly demand
- Example: Home uses ~10 MWh/year
**Net Load**
- Grid demand after subtracting DPV
- Formula: Operational demand - Underlying generation
- Important for: Grid planning
**Operational Demand**
- Electricity supplied by grid
- Measured at: Transmission level
- Does not include: Behind-the-meter generation
**Peak Demand**
- Maximum power demanded in any hour
- Critical for: Capacity planning
- Usually: Afternoon/evening in summer
**Projection**
- Forecast of future values
- Based on: Historical data + growth assumptions
- Not: Precise prediction
**Prosumer**
- Consumer who also produces electricity
- Example: Home with solar panels
- Both uses and generates power
**S-Curve (Logistic Growth)**
- Growth pattern: Slow → Fast → Saturate
- Typical for: Technology adoption
- Shape: Elongated S
**Saturation**
- Maximum penetration level
- When: Market becomes mature
- Example: 6x means grows to 6 times base
**Scenario**
- Set of growth assumptions
- Represents: Possible future
- Used for: Planning under uncertainty
**Sensitivity Analysis**
- Testing: How results change with assumptions
- Method: Vary one parameter at a time
- Purpose: Understand uncertainty
**Underlying Demand**
- Behind-the-meter demand (DPV)
- Not visible: To grid operators
- Important for: Total demand projections
---
## Quick Reference
### Keyboard Shortcuts
- **Ctrl/Cmd + R**: Refresh page
- **Ctrl/Cmd + '+'/'-'**: Zoom in/out
- **Escape**: Close dialogs
### Typical Workflow
```
1. Select Base Year (e.g., 2024)
2. Select End Year (e.g., 2050)
3. Choose View Mode (Single Projection)
4. Select Scenario (Medium Growth)
5. Click "Generate Projection"
6. Review Chart and Statistics
7. Try Other Scenarios or Adjust Sliders
8. Screenshot or Export Results
```
### Typical Growth Rates
| Context | Growth Rate | Annual Impact |
|---------|-------------|---------------|
| Mature market | 1-2% | Slow, steady |
| Normal economic growth | 2-3% | Moderate |
| Electrification (EVs) | 3-5% | Strong |
| Technology adoption peak | 8-12% | Rapid |
### When to Use Each View Mode
| Need | View Mode |
|------|-----------|
| Simple overview | Single Projection |
| Component analysis | Operational vs Underlying |
| Scenario comparison | Compare Scenarios |
| Presentations | Single Projection |
| Detailed planning | Operational vs Underlying |
| Risk analysis | Compare Scenarios |
---
## Appendix: Frequently Asked Questions
**Q: How often should I update projections?**
A: At least annually when new data is available, or when major policy/market changes occur.
**Q: Which scenario should I use for planning?**
A: Use Medium Growth as baseline. Plan for range between Low and High scenarios.
**Q: What time horizon is most reliable?**
A: Near-term (5-10 years) is most reliable. Use longer horizons for strategic planning only.
**Q: Can I create my own scenarios?**
A: Use sliders for custom growth rates. For permanent scenarios, contact system administrator.
**Q: Why doesn't my projection match other forecasts?**
A: Different assumptions, methodologies, and data sources. Compare assumptions carefully.
**Q: What's the difference between operational and underlying demand?**
A: Operational = grid-supplied. Underlying = behind-the-meter (DPV). Total = both combined.
**Q: How accurate are long-term projections?**
A: Projections are scenarios, not predictions. Accuracy decreases with time horizon. Use ranges.
**Q: Can I export data to Excel?**
A: Use screenshot for charts. Data export may be available (check for Export button).
**Q: What does the S-curve saturation parameter mean?**
A: Maximum growth multiplier. Example: 6.0 means demand grows to 6x base level at saturation.
**Q: How do I plan for uncertainty?**
A: Use multiple scenarios. Plan for flexibility. Monitor actual trends vs projections annually.
---
**Merit Order Considerations**
- Facility technologies populate merit order lists
- Capacity settings affect dispatch decisions
- Performance data influences optimization
### Powerplot Integration
Facilities data provides the foundation for visualizations:
- Technology-specific generation profiles
- Regional capacity distributions
- Performance comparisons
- Historical trend analysis
---
### Data Management Best Practices
### Consistent Data Entry
**Naming Standards**
- Establish facility naming conventions
- Use consistent abbreviations
- Include relevant identifiers (location, capacity, technology)
- Document naming scheme for team reference
**Data Quality**
- Validate coordinates using external mapping tools
- Cross-reference capacity ratings with technical specs
- Verify capacity factors against industry standards
- Keep generation data current
**Regular Maintenance**
- Periodically review facility data for accuracy
- Update capacity factors based on actual performance
- Remove or deactivate decommissioned facilities
- Document all major changes
### Scenario Planning
**Strategic Facility Assignment**
- Assign facilities to appropriate scenarios
- Use multiple scenarios to model alternatives
- Keep "Current" scenario as baseline reference
- Create planning scenarios for future buildout
**Version Control**
- Export facility lists regularly
- Document scenario-specific configurations
- Track changes over time
- Maintain backup of critical data
### Workflow Recommendations
**New Facility Setup**
1. Gather complete technical specifications
2. Verify location coordinates
3. Determine appropriate scenarios
4. Enter data with validation
5. Review in Powermap for accuracy
**Bulk Updates**
1. Export current facility data
2. Plan changes systematically
3. Update facilities individually with care
4. Verify changes across modules
5. Export updated data for records
**Facility Lifecycle Management**
1. Commission: Add with complete specifications
2. Operations: Update performance data regularly
3. Modifications: Edit rather than recreate
4. Decommission: Remove from future scenarios first
5. Archive: Export data before deletion
---
### Common Workflows
### Adding a New Solar Farm
1. Click "Add New Facility"
2. Enter facility name: "Example_Solar_100MW"
3. Select Technology: "Solar PV"
4. Select Zone: Appropriate region
5. Set Capacity: 100 MW
6. Set Capacity Factor: 0.22 (typical for location)
7. Enter coordinates using decimal degrees
8. Select relevant scenarios (e.g., "2030 High Renewables")
9. Click "Create Facility"
10. Verify appearance in Powermap
### Adding a Wind Farm with Turbines
1. Create facility as above with "Wind" technology
2. Save facility
3. From detail page, click "Add Wind Turbine"
4. Select turbine model from database
5. Enter number of turbines
6. Configure tilt and direction
7. Save installation
8. Verify total capacity calculation
### Creating a Battery Storage Facility
1. Click "Add New Facility"
2. Enter descriptive name
3. Select "Battery Storage" technology
4. Enter capacity in MWh (storage capacity)
5. Set location coordinates
6. Associate with planning scenarios
7. Note: Capacity factor not typically used for storage
8. Save and verify in system
### Updating Facility Specifications
1. Navigate to facility list
2. Search or filter to find facility
3. Click "Edit" button
4. Update required fields
5. Review impact on scenarios
6. Save changes
7. Verify updates in Powermap and Powermatch
---

# Powermatch Module

## Overview

PowerMatch is a web-based interface for matching and balancing Renewable Energy resources to the load on the South West Interconnected System (SWIS). The application quantifies and costs dispatchable energy generation, storage, and CO2-e emissions by taking input from Powermap load and generation data.

## Key Features
- **Renewable Energy Matching**: Balance renewable resources with system load
- **Cost Analysis**: Calculate levelised cost of energy (LCOE)
- **Emissions Tracking**: Quantify CO2-e emissions
- **Scenario Analysis**: Create and compare different energy scenarios
- **Real-time Progress**: Monitor analysis progress with live updates
## Navigation Overview
The PowerMatch interface consists of five main sections:
1. **Home**: Scenario and demand year selection
2. **Load Projection**: Project Load Growth into the Future
3. **Merit Order**: Configure technology dispatch priority
4. **Baseline Scenario**: Set parameters and run analysis
5. **Variations**: Create and analyze scenario variants
## Home Page - Scenario Selection
### Purpose
The home page allows you to select the demand year and scenario that will be used throughout a PowerMatch session. This selection is a prerequisite for all other functions.
### Steps to Configure
1. **Select Demand Year**: Choose from available demand years in the dropdown
2. **Select Scenario**: Choose the scenario you want to analyze
3. **Apply Settings**: Click the "Apply Settings" button to confirm selection
### Important Notes
- Both weather year, demand year and scenario must be specified before proceeding
- The selected scenario becomes the basis for all subsequent analysis
- Data availability depends on what has been imported from Powermap
## Merit Order Configuration
### Purpose
The merit order determines the dispatch priority of different energy technologies. Technologies higher in the list are dispatched first when demand needs to be met.
### Interface Components
**Merit Order Panel (Left Side)**
- **Active Technologies**: Technologies that will be used in the analysis
- **Drag and Drop**: Reorder technologies by dragging items up or down
- **Color Coding**: Each technology has a color based on emissions characteristics
**Excluded Resources Panel (Right Side)**
- **Excluded Technologies**: Technologies not included in the current analysis
- **Move Between Lists**: Drag technologies between merit order and excluded lists
### How to Configure Merit Order
1. **Reorder Technologies**:
   - Click and drag technology items within the Merit Order list
   - Higher position = higher dispatch priority
   - Lower emissions technologies typically go higher
2. **Include/Exclude Technologies**:
   - Drag technologies between "Merit Order" and "Excluded Resources" lists
   - Only technologies in the Merit Order list will be used in analysis
3. **Save Configuration**:
   - Click "Save Merit Order" button to save the configuration
   - Page will reload to confirm changes
### Best Practices
- Place renewable technologies (solar, wind) at the top
- Order by emissions intensity (lowest first)
- Consider economic dispatch order for conventional technologies
## Baseline Scenario Management
### Purpose
The baseline scenario establishes the foundation for an analysis by setting technology capacities, carbon pricing, and discount rates.
### Configuration Parameters
**Economic Settings**
- **Carbon Price**: Set the carbon price ($/tonne CO2-e) for emissions costing
- **Discount Rate**: Set the discount rate (%) for economic calculations
**Technology Capacity Settings**
For each technology, you can configure:
- **Capacity**: Base capacity in MW or MWh (read-only, from Powermap data)
- **Multiplier**: Factor to scale the base capacity (editable)
- **Effective Capacity**: Calculated result (Capacity × Multiplier)
### Setting Up a Baseline
1. **Configure Economic Parameters**:
   - Enter carbon price in the designated field
   - Set appropriate discount rate
2. **Adjust Technology Multipliers**:
   - Click in multiplier fields to edit values
   - Use multipliers to scale technologies up or down from base capacity
   - Effective capacity updates automatically
3. **Save Parameters**:
   - Click "Save Runtime Parameters" to store a configuration
### Running Analysis
**Standard Analysis**
- **Quick Run**: Click "Run Standard Analysis" for immediate results
- **No Progress Tracking**: Analysis runs in background
- **Direct Results**: Redirects to results page when complete
**Progress Tracking Analysis**
- **Real-time Updates**: Click "Run with Progress Tracking"
- **Live Progress Bar**: Shows completion percentage
- **Time Estimates**: Displays elapsed and remaining time
- **Connection Status**: Shows real-time connection status
**Level of Detail Options**
- Choose analysis detail level from dropdown
- Higher detail = more accurate results but longer processing time
- Select "Save baseline" checkbox to store results for future use
### Analysis Controls
- **Cancel**: Stop running analysis at any time
- **Progress Panel**: Shows real-time status and timing
- **Connection Status**: Monitors live data feed
## Variations and Analysis
### Purpose
Variations allow you to explore different scenarios by systematically changing technology parameters and comparing results.
### Creating Variations
**Prerequisites**
- Must have a baseline scenario established
- Select existing variant or choose "Create a new variant"
**Configuration Steps**
1. **Select Variant**: Choose existing variant or create new one
2. **Refresh Settings**: Click "Refresh" to load variant parameters
3. **Set Analysis Parameters**:
   - **Number of Stages**: How many analysis steps to run
   - **Step Value**: Increment for parameter changes
   - **Technology Selection**: Choose which technology to vary
**Technology Parameter Variation**
- **Expand Technology**: Click down arrow to show technology options
- **Set Step Change**: Enter the increment value for each stage
- **Submit Analysis**: Click "Submit" to run variation analysis
### Understanding Variations
- **Iterative Analysis**: PowerMatch runs multiple times with different parameters
- **Systematic Changes**: One technology parameter changes by step value each iteration
- **Comparative Results**: Results stored for plotting and comparison
- **Unique Naming**: Each variation gets automatically generated unique name
### Best Practices
- Start with small step changes to understand sensitivity
- Focus on technologies with significant impact on outcomes
- Use variations to optimize for specific goals (emissions, cost, reliability)
## Progress Tracking
### Real-time Monitoring Features
**Connection Status Indicators**
- **Connected** (Green): Receiving real-time updates
- **Connecting** (Orange): Establishing connection
- **Disconnected** (Red): No active connection
- **Error** (Red, Pulsing): Connection or analysis error
**Progress Information**
- **Progress Bar**: Visual completion percentage
- **Status Messages**: Current analysis step
- **Timing Data**:
  - Elapsed time since start
  - Estimated remaining time
- **Completion Percentage**: Numeric progress indicator
**Browser Features**
- **Background Processing**: Analysis continues if you switch tabs
- **Automatic Reconnection**: Reconnects if connection is lost
- **Download Integration**: Automatic file download when complete
### Managing Long-Running Analysis
- **Tab Switching**: Safe to switch browser tabs during analysis
- **Connection Recovery**: System attempts to reconnect automatically
- **Cancel Option**: Stop analysis at any time using Cancel button
- **Result Persistence**: Results saved even if connection is lost
---
# Powerplot Module
## Overview
PowerPlot UI is a Django-based data visualization module that enables users to generate various plots and charts to visualize analysis data. The system provides an interactive interface for selecting scenarios, variants, and data series to create customized visualizations and export data to Excel spreadsheets.
## Main Features
- **Supply Factors Visualization**: Generate various types of plots and charts for the generated output by facility and technology
- **Variant Visualization**: Generate various types of plots and charts for the selected statistics for variantsto a selected scenario baseline
## Accessing PowerPlot
Navigate to the PowerPlot landing page where you'll see selection fields the demand year and scenario.
## Overview Facility Supply Factors
The Renewable Facility Supply Factor Visualization tool allows you to analyze and compare renewable energy generation patterns from facilities in the portfolio. This tool helps you:
- Visualize hourly, weekly, or monthly supply patterns
- Compare facilities to identify complementary generation profiles
- Analyze technology-level aggregated performance
- Assess portfolio diversification through correlation metrics
- Filter data by seasonal periods or custom date ranges
### Key Features
- **Four visualization modes**: Single facility, facility comparison, technology aggregation, technology comparison
- **Four chart types**: Line, scatter, bar, and area charts
- **Three time aggregations**: Hourly, weekly, and monthly
- **Seasonal filtering**: Pre-defined seasonal ranges and custom date selections
- **Statistical analysis**: Correlation, complementarity, and variability metrics
- **Interactive charts**: Zoom, pan, hover for detailed values
### Basic Workflow
1. **Select a visualization mode** (Single Facility, Compare Two Facilities, Technology Aggregated, or Compare Technologies)
2. **Choose a facility or technology** from the dropdown menus
3. **Select a year** for analysis
4. **Choose time aggregation** (Hourly, Weekly, or Monthly)
5. **Select chart type** (Line, Scatter, Bar, or Area)
6. **(Optional)** Apply date range filters
7. **Click the Plot/Compare button** to generate a visualization
---
## Visualization Modes
### 1. Single Facility Mode
**Purpose**: Analyze supply patterns for an individual renewable energy facility.
**Use Cases**:
- Understand seasonal generation patterns
- Identify typical daily/weekly cycles
- Detect anomalies or maintenance periods
- Assess capacity factor variations
**How to Use**:
1. Select "Single Facility" mode
2. Choose a renewable facility from the dropdown
3. Select year, aggregation, and chart type
4. Click "Plot Supply"
**What You'll See**:
- Supply factor data over time
- Info panel showing facility name, technology, year, aggregation level, and data point count
- Interactive Plotly chart with zoom and pan capabilities
**Tip**: Use hourly aggregation for detailed analysis of short periods, and monthly aggregation for annual trends.
---
### 2. Compare Two Facilities Mode
**Purpose**: Compare generation patterns between two renewable facilities to identify complementarity.
**Use Cases**:
- Assess portfolio diversification
- Identify complementary generation profiles (e.g., solar + wind)
- Compare facilities of the same technology type
- Understand correlation between facilities
**How to Use**:
1. Select "Compare Two Facilities" mode
2. Choose Facility 1 and Facility 2 from dropdowns
3. Select year, aggregation, and chart type
4. Click "Compare"
**What You'll See**:
- Three traces: Facility 1, Facility 2, and Combined Total
- Correlation & Complementarity Analysis panel with key metrics:
  - **Correlation Coefficient**: -1 to +1 (how outputs move together)
  - **Complementarity Score**: 0 to 1 (portfolio diversification potential)
  - **Variability Reduction**: Percentage reduction in output variability when combined
  - **Complementary Periods**: Percentage of time when one is high and other is low
  - **Interpretation**: Plain-language explanation of metrics
**Understanding the Metrics**:
| Metric | Good Range | What It Means |
|--------|------------|---------------|
| Correlation | -0.3 to +0.3 | Outputs are independent (good for diversification) |
| Correlation | > 0.7 | Outputs move together (similar patterns) |
| Correlation | < -0.7 | Anti-correlated (opposite patterns) |
| Complementarity | > 0.7 | Excellent diversification potential |
| Complementarity | 0.4 - 0.7 | Moderate complementarity |
| Complementarity | < 0.4 | Similar patterns, limited diversification |
| Variability Reduction | > 10% | Combining significantly stabilizes output |
**Color Coding**:
- 🟢 Green badge: Good complementarity / low correlation
- 🟡 Yellow badge: Moderate values
- 🔴 Red badge: High correlation / poor complementarity
---
### 3. Technology Aggregated Mode
**Purpose**: View the combined output of all facilities using a specific technology.
**Use Cases**:
- Understand total technology capacity
- Analyze seasonal patterns at the portfolio level
- Compare technology performance across time periods
- Assess total renewable contribution by technology type
**How to Use**:
1. Select "Technology Aggregated" mode
2. Choose one or more technologies (e.g., Solar, Wind, Hydro)
3. Select year, aggregation, and chart type
4. Click "Plot Technology"
**What You'll See**:
- Aggregated supply (sum of all facilities with that technology)
- Info panel showing technology name, number of facilities included
- Combined total output over the selected time period
**Note**: The system automatically sums the output from all facilities using the selected technology. The chart title shows how many facilities are included in the aggregation.
---
### 4. Compare Technologies Mode
**Purpose**: Compare aggregated outputs between two technology types.
**Use Cases**:
- Compare solar vs wind generation patterns
- Assess complementarity between technology types
- Understand seasonal variations by technology
- Optimize technology mix for portfolio stability
**How to Use**:
1. Select "Compare Technologies" mode
2. Choose one or more Technologies for Group 1 and one or more Technologies for Group 2
3. Select year, aggregation, and chart type
4. Click "Compare"
**What You'll See**:
- Three traces: Technology 1 total, Technology 2 total, Combined Total
- Correlation & Complementarity Analysis panel
- Number of facilities included for each technology
- Statistical analysis of how the technologies complement each other
**Example Use Case**: 
Compare "Solar" vs "Wind" to see how well they complement each other seasonally. Typically, solar peaks during summer days while wind may be stronger at night or during winter, resulting in good complementarity scores.
---
## Chart Types
### Line Chart
**Best for**: Continuous data, time series analysis, identifying trends
**Features**:
- Smooth lines connecting data points
- Easy to see trends and patterns
- Works well for all aggregation levels
- Default chart type
**When to Use**: Hourly or weekly data where you want to see continuous patterns.
---
### Scatter Plot
**Best for**: Identifying outliers, seeing individual data points, correlation analysis
**Features**:
- Individual points without connecting lines
- Makes each data point visible
- Good for spotting anomalies
**When to Use**: When you need to see exact values or identify unusual data points.
---
### Bar Chart
**Best for**: Discrete time periods, comparing categories, monthly summaries
**Features**:
- Vertical bars for each time period
- Clear comparison between periods
- Good for discrete data
**When to Use**: Monthly or weekly aggregations where you're comparing distinct periods.
---
### Area Chart
**Best for**: Showing magnitude and volume, cumulative effects, emphasizing totals
**Features**:
- Filled area under the line
- Emphasizes the magnitude of values
- Good for stacked comparisons
**When to Use**: When you want to emphasize the volume or magnitude of generation, or when comparing cumulative totals.
---
## Time Aggregation
### Hourly Aggregation
- **Data Points**: 8,760 per year (365 days × 24 hours)
- **Best for**: Detailed analysis, short time periods (days to weeks)
- **Use when**: You need to see diurnal patterns, identify hourly variations
- **Performance**: May be slower with large datasets
- **Note**: Consider using date range filters for specific months when viewing hourly data
### Weekly Aggregation
- **Data Points**: 52 per year
- **Best for**: Medium-term trends, monthly to quarterly analysis
- **Use when**: You want to see weekly patterns without hourly detail
- **Performance**: Good balance between detail and performance
- **Calculation**: Averages all hours within each week
### Monthly Aggregation
- **Data Points**: 12 per year
- **Best for**: Annual trends, seasonal comparisons, long-term analysis
- **Use when**: Comparing across full years or multiple years
- **Performance**: Fast, handles large datasets well
- **Calculation**: Averages all hours within each month
---
## Date Range Filtering
Date range filtering allows you to focus on specific time periods without changing the base dataset.
### Quick Select Presets
**Southern Hemisphere Seasons**:
- **Summer** (Dec-Feb): Peak solar generation period
- **Autumn** (Mar-May): Transitional period
- **Winter** (Jun-Aug): Lower solar, potentially higher wind
- **Spring** (Sep-Nov): Transitional period
**Quarters**:
- **Q1** (Jan-Mar): First quarter
- **Q2** (Apr-Jun): Second quarter
- **Q3** (Jul-Sep): Third quarter
- **Q4** (Oct-Dec): Fourth quarter
### Custom Date Ranges
1. Click "Optional: Select Date Range" to expand the accordion
2. Use the **Quick Select** dropdown for preset ranges, OR
3. Manually select **Start Month** and **End Month**
4. Click "Plot Supply" or "Compare" to apply the filter
5. Use **Clear Range** button to reset to full year
### Use Cases for Date Filtering
| Scenario | Recommended Range |
|----------|-------------------|
| Compare summer solar performance | Summer (Dec-Feb) |
| Analyze winter wind patterns | Winter (Jun-Aug) |
| Review Q4 performance | Q4 (Oct-Dec) |
| Growing season analysis | Spring + Summer (Sep-Feb) |
| Year-end reporting | Full Year (no filter) |
**Note**: Date ranges work with all visualization modes and chart types. The system automatically filters the data to the selected months and adjusts aggregations accordingly.
---
## Correlation & Complementarity Analysis
This section appears when comparing two facilities or technologies and provides statistical insights into their relationship.
### Understanding the Metrics
#### Correlation Coefficient
**Range**: -1.0 to +1.0
- **+1.0**: Perfect positive correlation (outputs always move together)
- **+0.7 to +1.0**: Strong positive correlation
- **+0.3 to +0.7**: Moderate positive correlation
- **-0.3 to +0.3**: Weak or no correlation (independent outputs) ← **Best for diversification**
- **-0.7 to -0.3**: Moderate negative correlation
- **-1.0 to -0.7**: Strong negative correlation (anti-correlated)
- **-1.0**: Perfect negative correlation (outputs move in opposite directions)
#### Complementarity Score
**Range**: 0.0 to 1.0
Calculated as: `1 - |correlation|`
- **0.9 to 1.0**: Excellent complementarity (perfect for portfolio diversification)
- **0.7 to 0.9**: High complementarity (very good for diversification)
- **0.4 to 0.7**: Moderate complementarity (some diversification benefit)
- **0.0 to 0.4**: Low complementarity (limited diversification benefit)
#### Variability Reduction
**Range**: Can be negative or positive (expressed as percentage)
- **Positive values**: Combining the sources reduces output variability (desirable)
- **> 20%**: Significant reduction in variability
- **10-20%**: Moderate reduction
- **0-10%**: Small reduction
- **Negative values**: Combining actually increases variability (undesirable)
#### Complementary Periods Percentage
**Range**: 0% to 100%
Percentage of time when one facility is producing above 30% while the other is below 30%.
- **> 40%**: Frequently complementary
- **20-40%**: Sometimes complementary
- **< 20%**: Rarely complementary
## Interpretation Guide
The system provides an automatic interpretation combining all metrics. Here are some common patterns:
**Pattern 1: Ideal Complementarity (Solar + Wind)**
- Correlation: -0.2 to +0.2
- Complementarity: 0.8+
- Variability Reduction: 15%+
- Interpretation: "Weak correlation - outputs are largely independent | High complementarity - excellent for portfolio diversification | Combining reduces variability by 18%"
**Pattern 2: Similar Sources (Two Solar Farms)**
- Correlation: +0.8
- Complementarity: 0.2
- Variability Reduction: 2%
- Interpretation: "Strong positive correlation | Low complementarity - outputs follow similar patterns | Combining provides minimal variability reduction"
**Pattern 3: Anti-Correlated (Day Solar + Night Wind)**
- Correlation: -0.6
- Complementarity: 0.6
- Variability Reduction: 25%
- Interpretation: "Moderate negative correlation (anti-correlated - when one is high, other tends to be low) | Moderate complementarity | Combining significantly reduces output variability"
## Using Metrics for Decision-Making
**Portfolio Optimization**:
- Look for complementarity scores > 0.7
- Prefer negative correlations or near-zero correlations
- Prioritize combinations with high variability reduction
**Risk Management**:
- Avoid portfolios with all facilities showing correlation > 0.7
- Diversify across technologies with low correlation
- Use seasonal filtering to understand time-varying correlations
**Capacity Planning**:
- High complementarity suggests you need less total capacity
- Low complementarity means you need more backup capacity
- Variability reduction indicates firming requirements
---
## Best Practices
### Data Analysis Workflow
1. **Start with Overview**:
   - Use Technology Aggregated mode to see total capacity by type
   - Monthly aggregation for annual patterns
   - Full year (no date filter)
2. **Identify Patterns**:
   - Switch to Single Facility mode
   - Use hourly or weekly aggregation
   - Look for seasonal variations
3. **Deep Dive Analysis**:
   - Use date range filters for specific periods
   - Compare similar facilities to find best performers
   - Analyze complementarity for portfolio optimization
4. **Portfolio Optimization**:
   - Use Technology Comparison mode
   - Focus on complementarity scores
   - Apply seasonal filters to understand time-varying patterns
## Chart Selection Guide
| Analysis Type | Recommended Chart | Aggregation |
|--------------|-------------------|-------------|
| Daily patterns | Line | Hourly |
| Weekly trends | Line or Area | Weekly |
| Monthly comparison | Bar | Monthly |
| Outlier detection | Scatter | Hourly |
| Magnitude emphasis | Area | Any |
| Categorical comparison | Bar | Weekly/Monthly |
## Performance Tips
1. **For Large Datasets** (hourly, full year):
   - Apply date range filters to reduce data points
   - Use weekly or monthly aggregation
   - Consider scatter plots only for smaller datasets
2. **For Quick Analysis**:
   - Start with monthly aggregation
   - Use bar charts for clear comparisons
   - Apply quick select presets for seasons
3. **For Detailed Analysis**:
   - Use hourly aggregation with date ranges
   - Line or area charts work best
   - Focus on specific months or quarters
## Interpretation Tips
1. **Seasonal Patterns**:
   - Solar typically peaks in summer (Dec-Feb in Southern Hemisphere)
   - Wind patterns vary by location and season
   - Use date range filters to isolate seasons
2. **Complementarity**:
   - Solar + Wind often show good complementarity
   - Similar technologies (two solar farms) show high correlation
   - Geographic diversity can improve complementarity
3. **Variability**:
   - Higher variability reduction = better portfolio stability
   - Target > 10% for meaningful improvement
   - Seasonal analysis may show time-varying benefits
---
## Frequently Asked Questions
### General
**Q: What data sources are used?**  
A: The tool uses supply factor data from the `supplyfactors` table in the database, which contains hourly quantum and supply values for each facility.
**Q: Can I export the charts?**  
A: Yes, use Plotly's built-in download button in the chart toolbar to save as PNG or SVG.
**Q: Can I view multiple years?**  
A: Currently, you can select one year at a time. To compare years, you'll need to generate separate charts.
**Q: Why do some facilities not appear in the dropdown?**  
A: Only facilities with renewable technology (renewable flag = 1) are shown.
### Metrics and Calculations
**Q: How is the Combined Total calculated?**  
A: Combined Total = Facility 1 quantum + Facility 2 quantum at each time point.
**Q: What's the difference between Quantum and Supply?**  
A: Both are plotted if they differ. Quantum typically represents theoretical output, while Supply represents actual delivered output. If they're identical, only one trace is shown.
**Q: How is weekly aggregation calculated?**  
A: The year is divided into 52 weeks (168 hours each), and values are averaged within each week.
**Q: How is monthly aggregation calculated?**  
A: Data is grouped by calendar month, and values are averaged within each month.
**Q: What does "Complementary Periods" mean?**  
A: The percentage of time when one facility is producing above 30% of its maximum while the other is below 30%. Higher percentages indicate better complementarity.
## Date Ranges
**Q: Why do the seasons seem backwards?**  
A: The system uses Southern Hemisphere seasons (e.g., Summer = Dec-Feb). This is appropriate for Australian data.
**Q: Can I select non-contiguous months?**  
A: No, the system requires a continuous range from start month to end month.
**Q: Does date filtering affect correlation calculations?**  
A: Yes, all metrics are calculated only on the filtered data range.
### Technology Aggregation
**Q: How many facilities are included in technology aggregation?**  
A: The info panel shows the count. All facilities with the selected technology are automatically included.
**Q: Can I exclude specific facilities from technology aggregation?**  
A: Not currently. All facilities with the selected technology are included.
**Q: Why is my technology total different from my expectations?**  
A: Verify that all expected facilities are tagged with the correct technology in the database.
### Performance
**Q: Why is hourly data slow?**  
A: Hourly data for a full year contains 8,760 data points per facility. Use date range filters or switch to weekly/monthly aggregation for better performance.
**Q: Can I improve chart responsiveness?**  
A: Use modern browsers (Chrome, Firefox), close unnecessary tabs, and use lower aggregation levels (weekly/monthly) for faster rendering.
---
## Tips for Advanced Users
1. **Seasonal Complementarity Analysis**:
   - Run comparisons for each season separately
   - Compare correlation metrics across seasons
   - Identify which season shows best complementarity
2. **Portfolio Composition**:
   - Compare all technology pairs to create a correlation matrix
   - Target portfolio with average complementarity > 0.6
   - Balance high and low correlation pairs
3. **Capacity Factor Analysis**:
   - Use single facility mode with hourly data
   - Apply seasonal filters to understand seasonal capacity factors
   - Compare actual vs expected using scatter plots
4. **Custom Analysis**:
   - Export chart data (future feature)
   - Use scatter plots to identify outliers
   - Apply multiple date ranges to understand time-varying patterns
---
# AEMO SCADA Data Fetcher - Documentation
---
## Overview
The AEMO SCADA Data Fetcher is a Django application for downloading, storing, and analyzing facility SCADA (Supervisory Control and Data Acquisition) data from the Australian Energy Market Operator (AEMO) for the South West Interconnected System (SWIS) in Western Australia.
### Features
- **Automated daily data fetching** from current SCADA files
- **Historical data import** from ZIP archives
### Key Concepts
### Trading Intervals
- **Pre-reform** (before Oct 1, 2023): 30-minute intervals, 48 intervals/day
- **Post-reform** (from Oct 1, 2023): 5-minute intervals, 288 intervals/day
### Facility Quantities
- **Positive values**: Generation (facility supplying power to grid)
- **Negative values**: Consumption (facility drawing power from grid)
  - Battery charging
  - Pumped hydro pumping
  - Auxiliary loads
### Commands Reference
# Fetch yesterday's data (default)
* Syntax: *
python manage.py fetch_scada [OPTIONS]
Options:
--date YYYY-MM-DD - Specific date to fetch (default: yesterday)
--days-back N - Fetch last N days
--start-date YYYY-MM-DD - Start of date range
--end-date YYYY-MM-DD - End of date range
--verify - Verify data after fetching
--skip-existing - Skip dates with existing data
* Examples: *
# Fetch yesterday
python manage.py fetch_scada
# Fetch specific date with verification
python manage.py fetch_scada --date 2025-10-05 --verify
# Fetch last 7 days
python manage.py fetch_scada --days-back 7
# Fetch range, skipping existing
python manage.py fetch_scada \
    --start-date 2025-10-01 \
    --end-date 2025-10-07 \
    --skip-existing
### Fetch Historical Data
* Syntax: *
python manage.py fetch_historical_scada [OPTIONS]
* Options: *
--date YYYY-MM-DD - Single date to fetch
--month YYYY-MM - Entire month to fetch
--year YYYY - Entire year to fetch
--start-date YYYY-MM-DD - Start of date range
--end-date YYYY-MM-DD - End of date range
--output-summary FILE - Save summary to JSON file
* Examples: *
# Single day
python manage.py fetch_historical_scada --date 2024-01-15
# Entire month
python manage.py fetch_historical_scada --month 2024-01
# Multiple months (sequential commands)
for month in {01..12}; do
    python manage.py fetch_historical_scada --month 2024-$month
done
# Entire year with summary
python manage.py fetch_historical_scada --year 2024 \
    --output-summary scada_2024_summary.json
# Date range
python manage.py fetch_historical_scada \
    --start-date 2024-01-01 \
    --end-date 2024-03-31
## Verify Data
# Check for missing dates
* Syntax: *
python manage.py check_missing_scada_dates --start-date YYYY-MM-DD --end-date YYYY-MM-DD
* Eample: *
python manage.py check_missing_scada_dates \
    --start-date 2024-01-01 \
    --end-date 2024-12-31
### Analyze Facility
Analyze facility generation/consumption patterns.
*Syntax: *
python manage.py analyze_facility [OPTIONS]
* Options: *
--facility CODE - Specific facility to analyze
--all-batteries - Analyze all battery facilities
--start-date YYYY-MM-DD - Analysis start date
--end-date YYYY-MM-DD - Analysis end date
--output table|json - Output format
* Examples: *
# Analyze single facility
python manage.py analyze_facility \
    --facility KEMERTON_BESS \
    --start-date 2025-10-01 \
    --end-date 2025-10-31
# Analyze all batteries
python manage.py analyze_facility \
    --all-batteries \
    --start-date 2025-10-01 \
    --end-date 2025-10-31 \
    --output json > battery_analysis.json
### Scheduled Daily Updates
Set up cron job for daily updates:
# crontab -e
# Run daily at 12:30 PM AWST (after AEMO updates at 12:00 PM)
30 12 * * * cd /path/to/project && /path/to/venv/bin/python manage.py fetch_scada --verify
### Monthly Analysis Workflow
#!/bin/bash
# monthly_analysis.sh
YEAR=2025
MONTH=09
# Ensure data is complete
python manage.py fetch_historical_scada --month $YEAR-$MONTH
# Verify completeness
python manage.py check_missing_scada_dates \
    --start-date $YEAR-$MONTH-01 \
    --end-date $YEAR-$MONTH-30
# Run analysis
#!/bin/bash
# monthly_analysis.sh
YEAR=2025
MONTH=09
# Ensure data is complete
python manage.py fetch_historical_scada --month $YEAR-$MONTH
# Verify completeness
python manage.py check_missing_scada_dates \
    --start-date $YEAR-$MONTH-01 \
    --end-date $YEAR-$MONTH-30
# Run analysis
#!/bin/bash
# monthly_analysis.sh
YEAR=2025
MONTH=09
# Ensure data is complete
python manage.py fetch_historical_scada --month $YEAR-$MONTH
# Verify completeness
python manage.py check_missing_scada_dates \
    --start-date $YEAR-$MONTH-01 \
    --end-date $YEAR-$MONTH-30
# Run analysis
python manage.py shell <<EOF
from powerplot.services.load_analyzer import LoadAnalyzer
analyzer = LoadAnalyzer()
summary = analyzer.calculate_monthly_summary($YEAR, $MONTH)
print(f"Operational Demand: {summary.operational_demand} GWh")
print(f"RE %: {summary.re_percentage_operational}%")
EOF
---
### Overview Variants Statistics
- **Data Visualization**: Generate various types of plots and charts
- **Interactive Data Selection**: Dynamic filtering of scenarios, variants, and data series
- **Data Export**: Export selected scenarios/variants to Excel spreadsheets
- **Real-time Data Preview**: View analysis data in a scrollable table format
## Accessing PowerPlot
Navigate to the PowerPlot landing page where you'll see:
1. A data preview table showing analysis data
2. Interactive form controls for plot generation
3. Export functionality for data processing
## Understanding the Data Table
The top section displays analysis data in a scrollable table (300px height) with:
- **Headers**: Column names from the analysis data
- **Rows**: Data values organized in a striped, bordered table format
- **Scrolling**: Vertical scroll capability for large datasets
## Creating Plots and Charts
### Step 1: Select a Scenario
1. Use the **Scenario** dropdown to choose a scenario
2. The system will automatically update available variants based on a selection
3. If no scenario is selected, variant options will be cleared
### Step 2: Choose a Variant
1. After selecting a scenario, choose from the available **Variant** options
2. Variants are dynamically filtered based on the selected scenario
3. This selection will update the available data series options
### Step 3: Configure Data Series
The system supports up to two data series for comparison:
**Series 1 Configuration**
1. **Series 1 Heading**: Select the primary data category
2. **Series 1 Component**: Choose specific components within the selected heading
   - Components are automatically filtered based on the heading selection
**Series 2 Configuration (Optional)**
1. **Series 2 Heading**: Select the secondary data category for comparison
2. **Series 2 Component**: Choose specific components within the selected heading
   - Components are automatically filtered based on the heading selection
### Step 4: Generate a Plot
Once you've configured a selections:
1. Review choices in the form
2. Submit the form to generate a visualization
3. The system will create the appropriate plot based on a selections
## Data Export Functionality
### Excel Export Feature
When the download is ready:
1. A **Download** button will appear on the interface
2. Click the download button to save the data as an Excel file
3. The file will be automatically downloaded to the default download location
4. The exported file contains the selected scenario/variant data for further processing
### Export Process
The export functionality:
- Generates Excel files with base64 encoding for secure download
- Includes proper MIME type handling for Excel compatibility
- Provides automatic file naming for easy identification
### Interactive Features
### Dynamic Form Updates
The interface provides real-time updates:
- **Scenario Change**: Automatically updates variant options and clears series choices
- **Variant Change**: Refreshes series options based on new variant selection
- **Series Heading Change**: Filters component options for each series independently
### Error Handling
The system includes built-in error handling for:
- Failed AJAX requests when loading variants
- Component loading errors for series selections
- Network connectivity issues
### Visualization Types
Available chart and plot types include:
- Time series plots showing power generation and demand over time
- Capacity factor analysis charts
- Generation profiles by technology type
- Load duration curves
- Geographic visualizations integrated with Powermap data
- Economic analysis charts showing LCOE and costs
- Comparative scenario plots for variations analysis
- Emissions tracking and analysis charts
## User Interface Features
### Main Plotting Interface
- Clean, intuitive layout with logical workflow
- Form-based configuration with dropdown menus
- Real-time preview of selected data
- Responsive design for different screen sizes
### Chart Configuration Options
- Multiple data series support for comparisons
- Dynamic filtering based on selections
- Automatic chart type selection based on data
- Customizable time ranges and parameters
### Data Selection Tools
- Hierarchical selection (Scenario → Variant → Series → Component)
- Automatic filtering to show only relevant options
- Clear visual feedback for selections
- Easy reset and modification of choices
### Styling and Formatting
- Professional chart appearance with clear legends
- Consistent color schemes across different chart types
- Proper axis labeling and units
- Grid lines and annotations for clarity
### Export Options and Formats
- High-quality PNG and SVG export for charts
- Excel export for underlying data
- PDF export for reports
- Copy to clipboard functionality
## Creating Custom Visualizations
### Selecting and Filtering Data
1. **Choose Base Dataset**: Start with scenario selection
2. **Refine Scope**: Select specific variant for focused analysis
3. **Pick Metrics**: Choose relevant data series and components
4. **Preview Data**: Review the data table before plotting
### Configuring Chart Parameters
1. **Chart Type**: System automatically selects appropriate visualization
2. **Data Range**: Specify time periods or capacity ranges
3. **Comparison Series**: Add second series for comparative analysis
4. **Labels and Titles**: Charts automatically include descriptive labels
### Customizing Appearance
1. **Color Schemes**: Consistent colors based on technology types
2. **Scale and Units**: Automatic unit conversion and scaling
3. **Grid and Annotations**: Professional formatting applied automatically
4. **Legend Placement**: Optimal legend positioning for clarity
### Adding Annotations and Labels
- Automatic labeling based on data categories
- Technology-specific color coding
- Time series markers for significant events
- Capacity and generation unit labels
### Exporting High-Quality Graphics
1. **Chart Export**: High-resolution images for presentations
2. **Data Export**: Excel files for further analysis
3. **Report Integration**: Charts suitable for technical reports
4. **Multiple Formats**: PNG, SVG, PDF options available
### Creating Interactive Dashboards
- Multiple charts can be generated in sequence
- Consistent data selection across multiple visualizations
- Comparative analysis between different scenarios
- Progressive refinement of analysis through variations
## Integration with Other Modules
### Powermap Integration
- Visualize facility performance data
- Geographic distribution of generation
- Transmission loss analysis charts
- Capacity utilization across regions
### Powermatch Integration
- Display optimization results
- Show supply-demand matching over time
- Economic dispatch visualization
- Emissions tracking and analysis
### Data Flow
- Seamless access to results from both Powermap and Powermatch
- Consistent scenario and variant naming
- Real-time updates when new analysis results are available
- Cross-module data consistency checks
---
## Technical Features
### Responsive Design
The interface automatically adjusts to different screen sizes:
- **Desktop**: Full-featured interface with complete functionality
- **Mobile/Tablet**: Responsive layout with optimized touch controls
- **Zoom Support**: All components scale automatically with browser zoom
### Dynamic Content Loading
- Module information is loaded dynamically via AJAX
- No page refresh required when switching between modules
- Fast response times for data retrieval and analysis
- Real-time updates for collaborative scenarios
### Session Management
- Settings (Demand Year, Scenario, Config) persist throughout a session
- Automatic session handling for different access levels
- Secure authentication based on membership status
- Cross-module data consistency
### Integration Features
- Seamless data flow between Powermap, Powermatch, and Powerplot
- Shared scenario and configuration management
- Coordinated analysis workflows
- Unified results and reporting
---
## Troubleshooting
### Common Issues
**Modules not loading properly:**
- Ensure JavaScript is enabled in the browser
- Check internet connection stability
- Verify membership access level
- Try refreshing the page or clearing browser cache
**Powermap specific issues:**
*Facilities Not Loading*
- Ensure a valid scenario is selected
- Check that demand year is specified
- Refresh the page if data appears stale
*Cannot Add Facilities*
- Verify you're not using the "Current" scenario
- Ensure you have appropriate permissions
- Check that required fields are completed
*Map Performance Issues*
- Disable unnecessary layers to improve performance
- Zoom to specific regions rather than viewing entire system
- Clear browser cache if map tiles fail to load
*Grid Connection Problems*
- Verify grid lines exist in the selected scenario
- Check that connection distances are reasonable (<50km typically)
- Ensure grid line has sufficient available capacity
### Best Practices
- **Save work frequently** by applying settings after major changes
- **Use descriptive names** for facilities, grid lines, scenarios, and variations
- **Verify coordinates and parameters** before finalizing configurations
- **Consider system constraints** when planning facility clusters
- **Document assumptions** in facility or scenario descriptions
- **Test scenarios** across multiple modules for consistency
- **Export results regularly** for backup and reporting
- **Use variations systematically** to understand parameter sensitivity
- **Monitor progress** during long-running analyses
- **Validate results** by comparing with expected outcomes
---
*This comprehensive manual covers the complete Siren Web system including all three integrated modules: Powermap for infrastructure modeling, Powermatch for supply-demand optimization, and Powerplot for results visualization. The system provides a complete workflow for renewable energy planning and analysis within the South West Interconnected System (SWIS).*

*For specific technical questions, advanced feature requests, or system administration support, please contact the SEN Webmaster or refer to the online documentation portal.*
