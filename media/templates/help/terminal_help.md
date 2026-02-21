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
#### Operational Consumption
**What it is**: Grid-visible demand measured at transmission level
**Data Source**: `supplyfactors` table, facility ID 144
**Characteristics**:
- Represents actual load on the grid
- Measured hourly (8760 data points per year)
- Includes commercial, industrial, and residential consumption
- Net of rooftop solar generation
**Typical Growth Rate**: 2-3% per year (moderate growth)
#### Underlying Consumption
**What it is**: Total electricity consumption including distributed generation
**Data Source**: `DPVGeneration` table (AEMO data)
**Characteristics**:
- Represents true consumption before distributed PV offset
- Based on distributed photovoltaic (DPV) generation estimates
- Converted from 30-minute intervals to hourly values
- Shows actual customer consumption patterns
**Typical Growth Rate**: 4-8% per year (higher due to electrification trends)
#### Total Demand
**Calculation**: Operational Consumption + Underlying Consumption
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
**Operational Consumption Growth Rate**
- Range: 0% to 10% per year
- Controls: Growth of grid-supplied electricity demand
- Default: Set by selected scenario
**Underlying Consumption Growth Rate**
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
**Operational Consumption Growth Rate Slider**
- **Range**: 0% (no growth) to 10% (very high growth)
- **Controls**: Grid-supplied electricity demand
- **Factors**: Economic growth, electrification, population
- **Display**: Shows current value as badge
**Underlying Consumption Growth Rate Slider**
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
**Operational Consumption**
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
**Underlying Consumption**
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

