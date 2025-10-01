# Siren Web User Manual







## Complete Guide to Renewable Energy Modeling System







### System Overview







Siren Web is a web-based Django application modelled on Siren, an open-source Python application, designed for modeling renewable energy systems within the South West Interconnected System (SWIS). Siren Web provides comprehensive tools for energy planning through three main modules: Powermap, Powermatch, and Powerplot.







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







Siren Web implements a membership-based access system with three tiers:







- **Active Member**: Full access to all features and data



- **Lapsed Member**: Limited access to system functionality  



- **Subscriber/Non-member**: Basic access with restricted features







Access is automatically granted based on membership status when accessing the system through the appropriate authentication flow.







### Initial Setup







1. **Login** to the Siren Web system



2. **Review** your access level and available modules



3. **Select** appropriate demand year and scenario settings



4. **Navigate** to desired module (Powermap, Powermatch, or Powerplot)







---







## Main Interface







### Home Page Layout







The main interface displays:







1. **System Information Panel**: Shows current configuration settings



   - **Demand Year**: The year being used for demand modeling



   - **Scenario**: Currently selected modeling scenario



   - **Config**: Active configuration file







2. **Interactive System Architecture Diagram**: A clickable diagram showing the Siren system components







3. **Module Navigation**: Quick access to the three main analysis modules







### Current Session Settings







The settings panel at the top of the page displays your current modeling parameters:







```



Demand Year: [Year]



Scenario: [Scenario Name]



Config: [Configuration File]



```







These settings persist throughout your session and affect how the system processes your requests across all modules.







---







## System Navigation







### Interactive System Diagram







#### Overview







The main feature of Siren Web is an interactive diagram that illustrates the system architecture. This diagram contains clickable areas (hotspots) that provide detailed information about each component.







#### Available Components







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







#### Using the Interactive Diagram







1. **Click on any component** in the diagram to view its details



2. A **modal window** will appear displaying:



   - Component name and description



   - Database structure (for data tables)



   - Sample data (first 5 rows)



   - Column definitions







3. **Close the modal** by clicking the X button or clicking outside the modal area







#### Component Information Display







When you click on a component, you'll see:







- **Model Name**: The technical name of the component



- **Description**: Detailed explanation of the component's purpose and function



- **Data Structure**: 



  - Column names and their purposes



  - Sample data showing the format and typical values



  - Up to 5 example rows from the database







---







## Powermap Module







### Overview







Powermap is an interactive mapping tool for modeling renewable energy generation in the South West Interconnected System (SWIS). It integrates with the System Advisor Model (SAM) to provide comprehensive energy planning capabilities.







---







### Interface Components







The Powermap interface consists of:



- **Control Panel**: Top section for scenario selection and facility management



- **Interactive Map**: Central map showing facilities, grid lines, and infrastructure



- **Layer Controls**: Toggle different map layers (boundaries, zones, facilities, grid lines)







### Map Navigation







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



2. The button changes to "Cancel Add Facility" and your cursor becomes a crosshair



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







#### Starting the Process



1. Click **Add New Grid Line** button



2. The button changes to "Cancel Add Grid Line" and your cursor becomes a crosshair



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



Use the layer control to customize your view:



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



### Wind Turbine Management Overview







The Wind Turbine Management System allows you to manage wind turbine models and their installations at facilities within your SIREN web application. The system consists of two main components:







1. **Wind Turbine Models** - Master database of turbine specifications



2. **Facility Installations** - Tracking of which turbines are installed where







---







### Wind Turbine Models







#### Viewing Turbine Models







**Access:** Navigate to `/wind-turbines/` or use the "Wind Turbines" menu option.







The turbine models list displays all wind turbine types in your system with the following information:







- **Model**: Turbine model designation



- **Manufacturer**: Company that makes the turbine



- **Application**: Deployment type (Onshore, Offshore, or Floating)



- **Rated Power**: Maximum power output in kW



- **Hub Height**: Height from ground to turbine hub in meters



- **Rotor Diameter**: Total rotor diameter in meters



- **Cut-in/Cut-out Speed**: Wind speeds for operation start/stop



- **Installations**: Number of active installations using this model







#### Search and Filtering







Use the filters above the table to find specific turbines:







- **Search Box**: Enter model name or manufacturer



- **Manufacturer Filter**: Select specific manufacturer



- **Application Filter**: Filter by Onshore, Offshore, or Floating



- **Clear Button**: Reset all filters







#### Pagination







Large lists are paginated with 25 turbines per page. Use the pagination controls at the bottom to navigate between pages.







#### Adding New Turbine Models







**Access:** Click "Add New Wind Turbine" button on the turbine list page.







##### Required Information







- **Turbine Model** (Required): Unique identifier for the turbine



  - Example: "V90-2.0 MW", "GE 2.5-120"



  - Must be unique across all turbines in the system







##### Optional Information







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







##### Guidelines







- Use exact manufacturer designations for consistency



- Verify specifications with manufacturer datasheets



- Typical values:



  - Rated Power: 500-15,000 kW



  - Hub Height: 80-140m



  - Cut-in Speed: 3-4 m/s



  - Cut-out Speed: 20-25 m/s







#### Editing Turbine Models







**Access:** Click "Edit" button next to any turbine in the list, or "Edit" from the detail view.







- All fields can be modified except the database ID



- Changes won't affect existing installations but apply to new installations



- The system prevents duplicate model names



- If turbines are already installed, you'll see a warning about the impact







#### Deleting Turbine Models







**Access:** Click "Delete Turbine" from the detail view or edit page.







##### Important Notes







- **Safety Check**: Turbines currently installed at facilities cannot be deleted



- Remove all installations first before deleting the turbine model



- Deletion is permanent and cannot be undone



- The system will show which facilities are using the turbine if deletion is blocked







---







### Facility Wind Turbine Installations







#### Viewing Installations







**Access:** Navigate to `/facility-wind-turbines/` or click "View Facility Installations" from the turbine list.







The installations list shows:







- **Facility**: Where the turbines are installed



- **Zone**: Geographic zone of the facility



- **Turbine Model**: Which turbine type is installed



- **Manufacturer**: Turbine manufacturer



- **Units**: Number of turbines installed



- **Total Capacity**: Combined capacity of all units



- **Configuration**: Tilt angle and direction



- **Installation Date**: When installed



- **Status**: Active or Inactive







##### Filtering Options







- **Search**: Find by facility or turbine name



- **Facility Filter**: Specific facility name



- **Turbine Filter**: Specific turbine model



- **Active Only**: Show only active installations (checked by default)







#### Adding Installations







**Access:** Click "Add Installation" button on the installations list.







##### Required Information







- **Facility**: Select from dropdown of available facilities



- **Wind Turbine Model**: Select turbine type to install



- **Number of Turbines**: How many units to install (minimum 1)







##### Optional Configuration







- **Tilt Angle**: Turbine blade tilt in degrees (-90 to +90)



  - Typically 0° for horizontal axis turbines



  - Negative values = tilt backward, positive = tilt forward



- **Primary Direction**: Wind direction or turbine orientation



  - Examples: "North", "SW", "225°"



- **Installation Date**: When turbines were/will be installed



- **Notes**: Additional information about the installation







##### Automatic Calculations







The system automatically calculates:



- **Total Capacity**: Number of turbines × rated power



- Real-time capacity display updates as you change the quantity







##### Validation Rules







- Cannot install the same turbine model twice at the same facility



- Must select both facility and turbine model



- Number of turbines must be at least 1







#### Editing Installations







**Access:** Click "Edit" button next to any installation in the list.







##### Editable Fields







- Number of turbines



- Tilt angle



- Primary direction



- Installation date



- Installation notes



- Active/Inactive status







##### Read-Only Information







- Facility (cannot be changed after creation)



- Turbine model (cannot be changed after creation)







##### Status Management







- Uncheck "Installation is Active" to deactivate without deleting



- Inactive installations are shown with gray background



- Inactive installations don't count toward capacity totals







#### Removing Installations







**Access:** Click "Remove" button next to any installation.







- Removes the association between facility and turbine model



- Does not delete the facility or turbine model



- Requires confirmation before deletion



- Action is permanent and cannot be undone







---







### Navigation







#### Quick Access Links







- **Wind Turbines List** → **Facility Installations**: "View Facility Installations" button



- **Facility Installations** → **Wind Turbines List**: "View Wind Turbine Models" button  



- **Any List** → **Add New**: Prominent "Add" buttons on each list page



- **Detail View** → **Edit**: "Edit" button in header or quick actions sidebar







#### Breadcrumb Navigation







- Always use the "Back to List" buttons to return to list views



- Detail pages show the current item in the page header



- Edit pages show both item name and "Edit" indicator







---







### Tips and Best Practices







#### Data Management







1. **Consistent Naming**: Use manufacturer's exact model designations



2. **Complete Specifications**: Fill in all available technical data for better analysis



3. **Regular Updates**: Keep installation dates and status current



4. **Validation**: Double-check specifications against manufacturer datasheets







#### Performance







1. **Search Efficiently**: Use specific terms rather than browsing long lists



2. **Filter Combinations**: Combine multiple filters to narrow results quickly



3. **Pagination**: Lists are capped at 25 items per page for optimal performance







#### Workflow Recommendations







1. **Add Turbine Models First**: Create turbine specifications before installing at facilities



2. **Check for Duplicates**: Search existing turbines before adding new ones



3. **Document Installations**: Use the notes field for important installation details



4. **Regular Audits**: Periodically review and update installation status







#### Error Prevention







1. **Unique Models**: Each turbine model name must be unique



2. **Installation Limits**: One turbine model per facility (create separate entries for different configurations)



3. **Delete Order**: Remove installations before deleting turbine models



4. **Backup Important Data**: Export or document critical specifications before major changes







#### Common Issues







| Issue | Solution |



|-------|----------|



| Cannot delete turbine | Remove all installations first |



| Duplicate model error | Check existing turbines, use different model name |



| Missing capacity calculation | Ensure turbine has rated power specified |



| Filter not working | Clear all filters and try again |



| Installation not showing | Check "Active Only" filter setting |







---






### Facilities Management Overview

The Facilities Management System provides comprehensive tools for managing power generation and storage facilities within your SIREN web application. Facilities represent the infrastructure that comprises the grid, including power plants, renewable energy installations, and storage systems.

---

### Viewing Facilities

**Access:** Navigate to `/facilities/` or use the "Facilities" menu option.

The facilities list displays all infrastructure in your system with the following information:

- **Facility Name**: Unique identifier for the facility
- **Technology**: Type of generation or storage technology
- **Zone**: Geographic or administrative zone location
- **Capacity**: Rated capacity of the facility
- **Capacity Factor**: Ratio of actual to potential output
- **Generation**: Expected or actual generation output
- **Transmitted**: Energy transmitted from the facility
- **Latitude/Longitude**: Geographic coordinates

#### Search and Filtering

Use the comprehensive filter system above the table to find specific facilities:

- **Search Box**: Enter facility name, technology type, or zone name
- **Scenario Filter**: Filter by specific scenario associations
- **Technology Filter**: Select specific technology types
- **Zone Filter**: Filter by geographic zones
- **Clear Button**: Reset all filters to show all facilities

#### Pagination

Large facility lists are paginated with 25 facilities per page. Use the pagination controls at the bottom to navigate between pages.

---

### Adding New Facilities

**Access:** Click "Add New Facility" button on the facilities list page.

#### Required Information

- **Facility Name** (Required): Unique identifier for the facility
  - Use descriptive, clear names that identify the facility
  - Must be unique across all facilities in the system
  - Example: "Collie Solar Farm", "Kwinana Battery Storage"

#### Basic Configuration

**Technology Selection**
- Choose from available technology types
- Technologies define the facility's generation or storage type
- Examples: Solar PV, Wind, Battery Storage, Gas Turbine, Coal
- For hybrid facilities, create separate facility records for each technology

**Zone Assignment**
- Select the geographic or administrative zone
- Zones are used for regional analysis and planning
- Proper zone assignment is important for accurate modeling

#### Technical Specifications

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

#### Location Information

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

#### Scenario Associations

**Multiple Scenario Selection**
- Check boxes next to scenarios this facility should belong to
- Facilities can be associated with multiple scenarios
- Unassociated facilities won't appear in scenario-specific analyses
- You can modify scenario associations later

#### Guidelines and Best Practices

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
- For co-located technologies (hybrid sites), create separate facilities
- Ensure technology choice matches the actual installation

**Capacity and Performance**
- Verify specifications with technical documentation
- Use manufacturer ratings for equipment capacity
- Base capacity factors on local resource availability
- Consider derating factors for aging equipment

---

### Editing Facilities

**Access:** Click "Edit" button next to any facility in the list, or "Edit" from the detail view.

#### Editable Fields

All facility parameters can be modified:
- Facility name (must remain unique)
- Technology type
- Zone assignment
- Capacity and capacity factor
- Generation and transmission values
- Geographic coordinates
- Scenario associations

#### Important Notes

- **Name Changes**: Can be updated but must remain unique
- **Technology Changes**: Changes affect all associated scenarios
- **Impact Warning**: Updates are reflected across all scenario analyses
- **Scenario Associations**: Can add or remove scenarios freely
- **Validation**: System prevents duplicate names and invalid values

#### Update Guidelines

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

#### Facility Information Panel

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

#### Associated Scenarios

View all scenarios that include this facility:
- Scenario names and descriptions
- Quick reference for scenario planning
- Shows which analyses will include this facility

#### Wind Turbine Installations (Wind Facilities Only)

For wind technology facilities, additional information displays:
- **Turbine Models**: Installed turbine types and specifications
- **Configuration**: Number of units, tilt angles, directions
- **Installation Dates**: When turbines were installed
- **Links**: Direct access to wind turbine details
- **Capacity Breakdown**: Detailed capacity calculations

#### Quick Actions Sidebar

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

#### Delete Process

1. Click the delete button to open confirmation modal
2. Review the warning about permanent deletion
3. Confirm deletion to proceed
4. System removes facility and all associations

#### Important Warnings

- **Permanent Action**: Deletion cannot be undone
- **Scenario Impact**: Facility is removed from all scenarios
- **Relationship Removal**: All scenario associations are deleted
- **Data Loss**: All facility-specific data is permanently removed

#### Before Deleting

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

#### Powermap Integration

Facilities created in the Facilities Management system appear automatically in Powermap:
- Visual representation on interactive map
- Geographic distribution analysis
- Grid connection planning
- Transmission loss calculations

**Synchronization**
- Changes in Facilities Management immediately reflect in Powermap
- Location updates automatically adjust map markers
- Capacity changes affect power flow calculations

#### Powermatch Integration

Facility data flows into Powermatch for analysis:
- Technology dispatch optimization
- Capacity factor utilization
- Generation profiles
- Economic analysis (LCOE calculations)

**Merit Order Considerations**
- Facility technologies populate merit order lists
- Capacity settings affect dispatch decisions
- Performance data influences optimization

#### Powerplot Integration

Facilities data provides the foundation for visualizations:
- Technology-specific generation profiles
- Regional capacity distributions
- Performance comparisons
- Historical trend analysis

---

### Data Management Best Practices

#### Consistent Data Entry

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

#### Scenario Planning

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

#### Workflow Recommendations

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

#### Adding a New Solar Farm

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

#### Adding a Wind Farm with Turbines

1. Create facility as above with "Wind" technology
2. Save facility
3. From detail page, click "Add Wind Turbine"
4. Select turbine model from database
5. Enter number of turbines
6. Configure tilt and direction
7. Save installation
8. Verify total capacity calculation

#### Creating a Battery Storage Facility

1. Click "Add New Facility"
2. Enter descriptive name
3. Select "Battery Storage" technology
4. Enter capacity in MWh (storage capacity)
5. Set location coordinates
6. Associate with planning scenarios
7. Note: Capacity factor not typically used for storage
8. Save and verify in system

#### Updating Facility Specifications

1. Navigate to facility list
2. Search or filter to find facility
3. Click "Edit" button
4. Update required fields
5. Review impact on scenarios
6. Save changes
7. Verify updates in Powermap and Powermatch

---

### Troubleshooting

#### Common Issues

**"A facility with this name already exists"**
- Each facility must have a unique name
- Check existing facilities list
- Add distinguishing information to name
- Consider using location or capacity in name

**Facility Not Appearing in Powermap**
- Verify coordinates are correct format
- Check scenario selection in Powermap
- Ensure facility is associated with the selected scenario
- Refresh the Powermap view

**Capacity Calculations Incorrect**
- Verify capacity factor is between 0 and 1
- Check units (MW vs kW)
- Ensure numeric fields don't have text
- Review capacity vs generation relationship

**Cannot Delete Facility**
- Check for dependencies in other modules
- Verify you have appropriate permissions
- Try removing from scenarios first
- Contact administrator if issue persists

**Coordinate Entry Problems**
- Use decimal degrees format only
- Latitude: -90 to +90 (negative for south)
- Longitude: -180 to +180 (positive for east)
- Verify coordinates match intended location
- Use online tools to validate coordinates

#### Error Prevention

**Before Creating Facilities**
- Verify all required information is available
- Check for existing similar facilities
- Validate coordinates using mapping tools
- Confirm technology and zone selections

**During Data Entry**
- Double-check numeric values
- Ensure proper decimal placement
- Verify scenario selections
- Review all fields before saving

**After Saving**
- Check facility appears correctly in list
- Verify in Powermap visualization
- Confirm scenario associations
- Test in Powermatch if applicable

---

### Tips for Effective Facility Management

#### Planning and Organization

**Facility Hierarchy**
- Group facilities by technology type
- Organize by geographic region
- Use consistent naming for related facilities
- Document facility relationships

**Data Standards**
- Establish data entry guidelines
- Use standardized units consistently
- Create templates for common facility types
- Document assumptions and sources

#### Analysis Optimization

**Scenario Strategy**
- Use "Current" scenario as baseline
- Create planning scenarios for future years
- Group related facilities in scenarios
- Test alternatives with variations

**Performance Tracking**
- Update capacity factors based on actual data
- Track generation vs. predictions
- Document performance issues
- Use for planning future installations

#### Collaboration

**Team Coordination**
- Document facility changes
- Use clear naming conventions
- Communicate major updates
- Share scenario strategies

**Data Sharing**
- Export facility lists for stakeholders
- Create standardized reports
- Document assumptions clearly
- Version control important changes

---

### Advanced Features

#### Bulk Operations

**Export for External Analysis**
- Use search and filters to select facility subset
- Export filtered results
- Process in spreadsheet tools
- Import updated data (requires admin)

**Scenario Management**
- Efficiently assign facilities to multiple scenarios
- Use checkboxes for batch associations
- Create scenario-specific facility sets
- Manage facility lifecycle across scenarios

#### Integration with External Systems

**GIS Integration**
- Coordinate data compatible with GIS systems
- Export for spatial analysis
- Import validated coordinate data
- Overlay with other geographic data

**Technical Documentation**
- Link facilities to external documentation
- Reference manufacturer specifications
- Track equipment serial numbers (in notes)
- Maintain technical drawing references

---

*This Facilities Management system provides the foundation for all energy system modeling in SIREN Web. Accurate facility data ensures reliable analysis results across all modules.*

## Powermatch Module







### Overview







PowerMatch is a web-based interface for matching and balancing Renewable Energy resources to the load on the South West Interconnected System (SWIS). The application quantifies and costs dispatchable energy generation, storage, and CO2-e emissions by taking input from Powermap load and generation data.







### Key Features



- **Renewable Energy Matching**: Balance renewable resources with system load



- **Cost Analysis**: Calculate levelised cost of energy (LCOE)



- **Emissions Tracking**: Quantify CO2-e emissions



- **Scenario Analysis**: Create and compare different energy scenarios



- **Real-time Progress**: Monitor analysis progress with live updates







### Navigation Overview



The PowerMatch interface consists of four main sections:



1. **Home**: Scenario and demand year selection



2. **Merit Order**: Configure technology dispatch priority



3. **Baseline Scenario**: Set parameters and run analysis



4. **Variations**: Create and analyze scenario variants







### Home Page - Scenario Selection







#### Purpose



The home page allows you to select the demand year and scenario that will be used throughout your PowerMatch session. This selection is a prerequisite for all other functions.







#### Steps to Configure



1. **Select Demand Year**: Choose from available demand years in the dropdown



2. **Select Scenario**: Choose the scenario you want to analyze



3. **Apply Settings**: Click the "Apply Settings" button to confirm your selection







#### Important Notes



- Both demand year and scenario must be specified before proceeding



- The selected scenario becomes the basis for all subsequent analysis



- Data availability depends on what has been imported from Powermap







### Merit Order Configuration







#### Purpose



The merit order determines the dispatch priority of different energy technologies. Technologies higher in the list are dispatched first when demand needs to be met.







#### Interface Components







**Merit Order Panel (Left Side)**



- **Active Technologies**: Technologies that will be used in the analysis



- **Drag and Drop**: Reorder technologies by dragging items up or down



- **Color Coding**: Each technology has a color based on emissions characteristics







**Excluded Resources Panel (Right Side)**



- **Excluded Technologies**: Technologies not included in the current analysis



- **Move Between Lists**: Drag technologies between merit order and excluded lists







#### How to Configure Merit Order







1. **Reorder Technologies**:



   - Click and drag technology items within the Merit Order list



   - Higher position = higher dispatch priority



   - Lower emissions technologies typically go higher







2. **Include/Exclude Technologies**:



   - Drag technologies between "Merit Order" and "Excluded Resources" lists



   - Only technologies in the Merit Order list will be used in analysis







3. **Save Configuration**:



   - Click "Save Merit Order" button to save your configuration



   - Page will reload to confirm changes







#### Best Practices



- Place renewable technologies (solar, wind) at the top



- Order by emissions intensity (lowest first)



- Consider economic dispatch order for conventional technologies







### Baseline Scenario Management







#### Purpose



The baseline scenario establishes the foundation for your analysis by setting technology capacities, carbon pricing, and discount rates.







#### Configuration Parameters







**Economic Settings**



- **Carbon Price**: Set the carbon price ($/tonne CO2-e) for emissions costing



- **Discount Rate**: Set the discount rate (%) for economic calculations







**Technology Capacity Settings**



For each technology, you can configure:



- **Capacity**: Base capacity in MW or MWh (read-only, from Powermap data)



- **Multiplier**: Factor to scale the base capacity (editable)



- **Effective Capacity**: Calculated result (Capacity × Multiplier)







#### Setting Up a Baseline







1. **Configure Economic Parameters**:



   - Enter carbon price in the designated field



   - Set appropriate discount rate







2. **Adjust Technology Multipliers**:



   - Click in multiplier fields to edit values



   - Use multipliers to scale technologies up or down from base capacity



   - Effective capacity updates automatically







3. **Save Parameters**:



   - Click "Save Runtime Parameters" to store your configuration







#### Running Analysis







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







#### Analysis Controls



- **Cancel**: Stop running analysis at any time



- **Progress Panel**: Shows real-time status and timing



- **Connection Status**: Monitors live data feed







### Variations and Analysis







#### Purpose



Variations allow you to explore different scenarios by systematically changing technology parameters and comparing results.







#### Creating Variations







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







#### Understanding Variations



- **Iterative Analysis**: PowerMatch runs multiple times with different parameters



- **Systematic Changes**: One technology parameter changes by step value each iteration



- **Comparative Results**: Results stored for plotting and comparison



- **Unique Naming**: Each variation gets automatically generated unique name







#### Best Practices



- Start with small step changes to understand sensitivity



- Focus on technologies with significant impact on outcomes



- Use variations to optimize for specific goals (emissions, cost, reliability)







### Progress Tracking







#### Real-time Monitoring Features







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







#### Managing Long-Running Analysis



- **Tab Switching**: Safe to switch browser tabs during analysis



- **Connection Recovery**: System attempts to reconnect automatically



- **Cancel Option**: Stop analysis at any time using Cancel button



- **Result Persistence**: Results saved even if connection is lost







---







## Powerplot Module







### Overview







PowerPlot UI is a Django-based data visualization module that enables users to generate various plots and charts to visualize analysis data. The system provides an interactive interface for selecting scenarios, variants, and data series to create customized visualizations and export data to Excel spreadsheets.







### Main Features







- **Data Visualization**: Generate various types of plots and charts



- **Interactive Data Selection**: Dynamic filtering of scenarios, variants, and data series



- **Data Export**: Export selected scenarios/variants to Excel spreadsheets



- **Real-time Data Preview**: View analysis data in a scrollable table format







### Accessing the PowerPlot Interface







Navigate to the PowerPlot landing page where you'll see:



1. A data preview table showing your analysis data



2. Interactive form controls for plot generation



3. Export functionality for data processing







### Understanding the Data Table







The top section displays your analysis data in a scrollable table (300px height) with:



- **Headers**: Column names from your analysis data



- **Rows**: Data values organized in a striped, bordered table format



- **Scrolling**: Vertical scroll capability for large datasets







### Creating Plots and Charts







#### Step 1: Select a Scenario







1. Use the **Scenario** dropdown to choose your desired scenario



2. The system will automatically update available variants based on your selection



3. If no scenario is selected, variant options will be cleared







#### Step 2: Choose a Variant







1. After selecting a scenario, choose from the available **Variant** options



2. Variants are dynamically filtered based on the selected scenario



3. This selection will update the available data series options







#### Step 3: Configure Data Series







The system supports up to two data series for comparison:







**Series 1 Configuration**



1. **Series 1 Heading**: Select the primary data category



2. **Series 1 Component**: Choose specific components within the selected heading



   - Components are automatically filtered based on the heading selection







**Series 2 Configuration (Optional)**



1. **Series 2 Heading**: Select the secondary data category for comparison



2. **Series 2 Component**: Choose specific components within the selected heading



   - Components are automatically filtered based on the heading selection







#### Step 4: Generate Your Plot







Once you've configured your selections:



1. Review your choices in the form



2. Submit the form to generate your visualization



3. The system will create the appropriate plot based on your selections







### Data Export Functionality







#### Excel Export Feature







When the download is ready:



1. A **Download** button will appear on the interface



2. Click the download button to save your data as an Excel file



3. The file will be automatically downloaded to your default download location



4. The exported file contains the selected scenario/variant data for further processing







#### Export Process







The export functionality:



- Generates Excel files with base64 encoding for secure download



- Includes proper MIME type handling for Excel compatibility



- Provides automatic file naming for easy identification







### Interactive Features







#### Dynamic Form Updates







The interface provides real-time updates:







- **Scenario Change**: Automatically updates variant options and clears series choices



- **Variant Change**: Refreshes series options based on new variant selection



- **Series Heading Change**: Filters component options for each series independently







#### Error Handling







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







### User Interface Features







#### Main Plotting Interface



- Clean, intuitive layout with logical workflow



- Form-based configuration with dropdown menus



- Real-time preview of selected data



- Responsive design for different screen sizes







#### Chart Configuration Options



- Multiple data series support for comparisons



- Dynamic filtering based on selections



- Automatic chart type selection based on data



- Customizable time ranges and parameters







#### Data Selection Tools



- Hierarchical selection (Scenario → Variant → Series → Component)



- Automatic filtering to show only relevant options



- Clear visual feedback for selections



- Easy reset and modification of choices







#### Styling and Formatting



- Professional chart appearance with clear legends



- Consistent color schemes across different chart types



- Proper axis labeling and units



- Grid lines and annotations for clarity







#### Export Options and Formats



- High-quality PNG and SVG export for charts



- Excel export for underlying data



- PDF export for reports



- Copy to clipboard functionality







### Creating Custom Visualizations







#### Selecting and Filtering Data







1. **Choose Base Dataset**: Start with scenario selection



2. **Refine Scope**: Select specific variant for focused analysis



3. **Pick Metrics**: Choose relevant data series and components



4. **Preview Data**: Review the data table before plotting







#### Configuring Chart Parameters







1. **Chart Type**: System automatically selects appropriate visualization



2. **Data Range**: Specify time periods or capacity ranges



3. **Comparison Series**: Add second series for comparative analysis



4. **Labels and Titles**: Charts automatically include descriptive labels







#### Customizing Appearance







1. **Color Schemes**: Consistent colors based on technology types



2. **Scale and Units**: Automatic unit conversion and scaling



3. **Grid and Annotations**: Professional formatting applied automatically



4. **Legend Placement**: Optimal legend positioning for clarity







#### Adding Annotations and Labels







- Automatic labeling based on data categories



- Technology-specific color coding



- Time series markers for significant events



- Capacity and generation unit labels







#### Exporting High-Quality Graphics







1. **Chart Export**: High-resolution images for presentations



2. **Data Export**: Excel files for further analysis



3. **Report Integration**: Charts suitable for technical reports



4. **Multiple Formats**: PNG, SVG, PDF options available







#### Creating Interactive Dashboards







- Multiple charts can be generated in sequence



- Consistent data selection across multiple visualizations



- Comparative analysis between different scenarios



- Progressive refinement of analysis through variations







### Integration with Other Modules







#### Powermap Integration



- Visualize facility performance data



- Geographic distribution of generation



- Transmission loss analysis charts



- Capacity utilization across regions







#### Powermatch Integration



- Display optimization results



- Show supply-demand matching over time



- Economic dispatch visualization



- Emissions tracking and analysis







#### Data Flow



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



- Your settings (Demand Year, Scenario, Config) persist throughout your session



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



- Ensure JavaScript is enabled in your browser



- Check internet connection stability



- Verify your membership access level



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







**Powermatch specific issues:**







*Connection Problems*



- **Symptom**: Connection status shows "Disconnected" or "Error"



- **Solutions**:



  - Refresh the page and restart analysis



  - Check internet connection stability



  - Try using Standard Analysis mode instead







*Analysis Fails to Start*



- **Symptom**: No progress after clicking run button



- **Solutions**:



  - Verify all required parameters are set



  - Check that baseline scenario exists



  - Ensure merit order is configured



  - Try refreshing the page







*Slow Performance*



- **Symptom**: Analysis takes very long to complete



- **Solutions**:



  - Reduce level of detail setting



  - Decrease number of variation stages



  - Check system resource availability



  - Consider running during off-peak hours







*Results Not Displaying*



- **Symptom**: Analysis completes but no results shown



- **Solutions**:



  - Check if download was blocked by browser



  - Look for downloaded files in browser downloads



  - Try running analysis again



  - Contact system administrator







**Powerplot specific issues:**







*No Variants Available*



- Ensure a scenario is selected first



- Check that the scenario contains valid variants







*Series Components Not Loading*



- Verify that a heading is selected for the series



- Ensure the scenario and variant selections are valid







*Download Not Working*



- Check browser download settings



- Ensure pop-up blockers aren't preventing downloads



- Verify file permissions in download directory







### Error Messages







**"Cannot add facilities to the 'Current' scenario"**



- Switch to a modifiable planning scenario



- Current scenario is read-only for reference







**"No suitable grid line found within 50km"**



- Location is too remote for automatic connection



- Use "Create new grid line" option



- Consider relocating facility closer to existing infrastructure







**"Please fill in all required fields"**



- Complete facility name, technology, and capacity



- Ensure location is selected on map



- For wind facilities, include turbine specifications







**"Analysis is already running"**



- Wait for current analysis to complete



- Use Cancel button to stop current analysis



- Refresh page if analysis appears stuck







**"Failed to start analysis"**



- Check all required fields are completed



- Verify scenario selection on home page



- Ensure merit order is saved



- Try logging out and back in







**"Connection lost"**



- Analysis may still be running on server



- Try reconnecting by refreshing page



- Check results page directly



- Contact administrator if problem persists







**Access or authentication problems:**



- Verify your membership status with the system administrator



- Clear browser cookies and cache if experiencing login issues



- Contact support if access level seems incorrect







### Browser Compatibility



- Modern browsers (Chrome, Firefox, Safari, Edge) are fully supported



- Internet Explorer may have limited functionality



- Mobile browsers are supported with responsive design







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







## Support and Further Information







### Getting Help







For additional assistance with:







**Technical Issues**



- Contact your system administrator



- Check system status indicators for service availability



- Use the feedback system to report bugs or request features







**Powermap Module**



- Refer to facility and grid line troubleshooting sections above



- Check SWIS modeling guidelines for planning constraints



- Review transmission loss calculation methodologies







**Powermatch Module**



- Contact support for optimization algorithm questions



- Review supply-demand balancing documentation



- Check merit order configuration guidelines



- Refer to economic parameter setting best practices







**Powerplot Module**



- Check visualization best practices guide



- Contact support for custom chart requirements



- Review data export troubleshooting



- Refer to chart interpretation guidelines







**Siren Application**



- Refer to the main Siren documentation



- Consult renewable energy modeling best practices



- Review SWIS system specifications and constraints







**Data Interpretation**



- Review component descriptions and sample data in the interactive diagram



- Consult the technical specifications for each module



- Use help tooltips and modal information throughout the interface







### Documentation Updates







This manual covers Siren Web version 2.0 including:



- Powermap module (complete documentation)



- Powermatch module (complete documentation)



- Powerplot module (complete documentation)







For the latest updates and additional features, please refer to:



- Online documentation portal



- System administrator notifications



- Release notes and changelog



- Module-specific help systems







### Data Privacy and Security







- All data transmission is secured through standard web protocols



- Session data is managed securely on the server



- Access control is enforced based on membership levels



- No sensitive data is stored in browser localStorage



- Multi-module data consistency is maintained securely



- Scenario and configuration data is protected by user permissions







### System Requirements and Dependencies







**Browser Requirements**



- Modern web browsers with JavaScript enabled



- AJAX support for dynamic content loading



- Base64 download support for file exports



- WebSocket support for real-time progress tracking







**Network Requirements**



- Stable internet connection for real-time features



- Sufficient bandwidth for map tile loading



- WebSocket connectivity for progress monitoring



- File download capabilities







**Software Dependencies**



- jQuery library for dynamic interactions



- Django CSRF token support for secure form submissions



- Crispy Forms for enhanced form rendering



- Leaflet.js for interactive mapping



- Chart.js for data visualization







### Performance Optimization







**For Large Datasets**



- Use appropriate level of detail settings in Powermatch



- Filter data appropriately in Powerplot



- Disable unnecessary map layers in Powermap



- Close unused browser tabs during analysis







**For Long-Running Analysis**



- Use progress tracking for monitoring



- Ensure stable network connection



- Avoid browser sleep/hibernation during analysis



- Save intermediate results when possible







**Memory Management**



- Clear browser cache periodically



- Limit number of concurrent analyses



- Export and save results regularly



- Monitor system resource usage







### Advanced Features and Tips







**Cross-Module Workflows**



1. **Start with Powermap**: Design your system infrastructure



2. **Configure Powermatch**: Set up analysis parameters and run optimization



3. **Visualize with Powerplot**: Create charts and export results



4. **Iterate and Refine**: Use variations to optimize designs







**Scenario Management Best Practices**



- Use consistent naming conventions across modules



- Document scenario assumptions and parameters



- Save baseline scenarios before creating variations



- Export scenario data for backup and sharing







**Analysis Workflow Optimization**



- Run quick analyses first to validate setup



- Use variations systematically for sensitivity analysis



- Export intermediate results for later comparison



- Monitor progress and cancel if needed







**Data Management**



- Regular exports to Excel for external analysis



- Consistent file naming for organization



- Version control for important scenarios



- Backup critical analysis results







### Training and Learning Resources







**Getting Started Tutorials**



- New user orientation workflow



- Step-by-step scenario creation guides



- Basic analysis and visualization tutorials



- Common troubleshooting scenarios







**Advanced User Guides**



- Complex scenario modeling techniques



- Optimization strategy development



- Advanced visualization techniques



- Integration with external tools







**Best Practices Documentation**



- SWIS system modeling guidelines



- Renewable energy planning standards



- Economic analysis methodologies



- Technical parameter guidelines







**Community Resources**



- User forums and discussion groups



- Shared scenario repositories



- Template libraries for common analyses



- Case study examples and tutorials







---







*This comprehensive manual covers the complete Siren Web system including all three integrated modules: Powermap for infrastructure modeling, Powermatch for supply-demand optimization, and Powerplot for results visualization. The system provides a complete workflow for renewable energy planning and analysis within the South West Interconnected System (SWIS).*







*For specific technical questions, advanced feature requests, or system administration support, please contact your system administrator or refer to the online documentation portal.*