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
print(f"Operational Consumption: {summary.operational_demand} GWh")
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
