# Powerplot Module
## Overview
Powerplot is the charting and reporting module of Siren. It turns the outputs of the Powermap (Facilities scenarios) and Powermatch (Baselines and Variants) processes into interactive charts, compares them with actual performance of the South West Interconnected System (SWIS), and tracks progress against the Renewable Energy Targets. Charts are drawn with Plotly: hover for values, drag to zoom, double-click to reset, and use the toolbar camera icon to save a chart as a PNG.
## Main Features
- **Variants Statistics**: plot and export the statistics of a Powermatch Baseline and one of its Variants
- **Renewable Energy Target**: RET Dashboard with monthly, quarterly and annual reports; Scenario Projections to 2040; target management; RET Replacement Scenarios analysis
- **Facility Generation**: actual (SCADA) and simulated (SAM) generation by facility and technology, SCADA load analysis, and actual-versus-simulated comparison
- **Risk Analysis**: risk events, 6x6 risk matrix and scenario risk comparison
- **Transport Electrification**: EV uptake tracking and EV charging profiles
- **WEM Prices** and **SWIS Demand**: 3D history charts
- **ESOO Bias Tracking**: how well AEMO's demand forecasts have matched reality
## Accessing Powerplot
Select **Powerplot** from the main menu to reach the Powerplot home page. The menu bar across the top gives access to every function below. Working left to right:

| Menu item | Purpose |
|-----------|---------|
| Powerplot Home | Overview and menu |
| Variants Statistics | Chart and export Baseline/Variant statistics |
| Renewable Energy Target | RET Dashboard, Scenario Projections, Manage Targets, RET Replacement Scenarios, RET Analysis Config |
| Facility Generation | Actual (Scada), Scada Analysis, Simulated (SAM), Comparison |
| Risk Analysis | Risk Dashboard, Manage Scenarios, Compare Scenarios |
| Transport Electrification | EV Uptake Tracking, EV Charging Profiles |
| WEM Prices | 3D history of wholesale prices |
| SWIS Demand | 3D history of operational and underlying demand |
| ESOO Bias Tracking | Forecast-versus-actual bias analysis |
| Powerplot Help / Help Edit | This document and its editor |

Some menu items (RET Dashboard, EV pages) open in a new browser tab.

### What data each page needs
| Page | Needs |
|------|-------|
| Variants Statistics | A Baseline and Variants run in Powermatch |
| Simulated (SAM) | *Run Power* completed for the scenario/year in Powermatch |
| Actual (Scada), Scada Analysis, RET Dashboard | SCADA data and monthly performance records kept up to date by the Data Pipelines (Powermap > Data Take-up) |
| Comparison | Facilities with **both** SCADA and simulated data for the same year |
| Risk Analysis | Facilities scenarios created in Powermap |
| EV pages, ESOO Bias | The EV and ESOO data loaded through the Data Pipelines |

If a page shows a "No data" message, the data it depends on has not been loaded yet.

---
## Variants Statistics
**Menu**: Variants Statistics (`/variants/`)

Use this page to plot any two statistics from a Powermatch Baseline and one of its Variants against each other, stage by stage, or to export everything to Excel.

### Selecting data
1. **Choose a Baseline**: the scenario/demand-forecast combination that Powermatch was run for. The Variant list is filled in from the Baseline you choose.
2. **Choose a Variant**: the sensitivity run created in Powermatch (*Create Variants*). If a Baseline has no Variants, the list says so.
3. **Series 1**: choose a *component* (e.g. a technology or system total) and then a *statistic* (heading) for that component, such as capacity, generation, cost or emissions.
4. **Series 2**: choose a second component and statistic in the same way. The two series can have different units; unless a *Stacked* option is chosen, Series 2 is drawn against a second (right-hand) axis.
5. **Chart type**: *Line* or *Bar*.
6. **Chart specialization**: Basic Line, Stacked Line, Area Chart, Smoothed Line, Step Line, Basic Bar or Stacked Bar.

The component and statistic lists only offer combinations that exist for the selected Variant, so the lists change as you make choices.

### Plot
Click **Plot**. The chart shows the value of each series at every stage of the Variant (the Baseline's value and each step of the sensitivity run). Use it to see, for example, how emissions fall as wind capacity is stepped up, or where cost per MWh is lowest. Stages for which one of the two series has no value are omitted.

Use the **back** button on the chart page to return to the form with your selections restored.

### Export
Click **Export** to download a spreadsheet of the selected Baseline/Variant for further processing in Excel. Series and chart selections are not needed for an export.

**Tips**
- Use *Stacked* options only for series that are parts of a whole (e.g. generation by technology).
- Pick the same units for both series where you want to compare magnitudes directly.

---
## Renewable Energy Target (RET)
The RET pages track how the SWIS is progressing towards its renewable energy targets, using actual SCADA data, and project future pathways.

RE% definitions used throughout:
- **Operational RE%** = renewable generation (wind, solar, biomass incl. waste-to-energy) as a share of grid generation, excluding storage.
- **Underlying RE%** = (renewable generation + rooftop solar, DPV) as a share of (grid generation excluding storage + DPV). Targets are compared on this underlying basis.
- Storage (battery, pumped hydro) is excluded from both numerator and denominator, consistent with the AEMO Quarterly Energy Dynamics (QED) method.
- Months are Australian Western Standard Time (AWST).

### RET Dashboard
**Menu**: Renewable Energy Target > RET Dashboard

A monthly report of how the grid performed.

1. Use **Select Period** to choose a month and click **View**.
2. Read the sections down the page:
   - **RE Performance** for the month, with the operational and underlying RE%
   - **Year to Date** performance against the target pathway
   - **Highlights and Generation Mix**: pie charts of the mix, with and without rooftop solar
   - **Key Statistics**: demand, peaks and renewable records
   - **Wholesale Prices**: statistics for the month, including negative-price periods
   - **New Capacity**: facilities commissioned in the month and those under construction
   - **Emissions Performance**
   - **What This Means**: plain-language summary for consumers, the grid and WA
3. The bar of links above the period selector opens the **recent quarterly reports**, the **Annual Review**, the **Published Reports** archive, this help, and **Print**.

### Quarterly Reports and Annual Review
Open from the links at the top of the RET Dashboard.

- The **Quarterly Report** summarises the quarter, compares it with the same quarter last year and with the previous quarter, and charts the generation mix.
- The **Annual Review** summarises the full year, shows annual trends, and compares progress with the target scenarios.
- Both contain an **Executive Summary** and a **Comments** section. Logged-in users can add, edit, pin, resolve and delete comments and edit the executive summary. Comments can be categorised.
- **Publish** (logged-in users): generates HTML and PDF versions of the report and stores them in the archive. Review the report first - published copies are a snapshot and do not change if the data is later revised.
- **Print** uses your browser's print dialog.

### Published Reports
**Menu**: *Published Reports* link on the RET Dashboard

Archive of every published quarterly and annual report. For each you can **view** the PDF, **download** it, or **view the HTML** version.

### Scenario Projections
**Menu**: Renewable Energy Target > Scenario Projections

The SWIS 2040 pathway analysis, built from the *active* target scenarios held in Manage Targets. It contains:
- Executive summary and the scenario type definitions
- Key targets overview
- RE% trajectory by scenario (Base Case, Accelerated Pipeline, Delayed Pipeline) with an **Energy Mix for** selector to show the mix for one scenario
- Scenario comparison table for 2040
- Facility pipeline by status and technology, and upcoming commissioning
- Generation mix transition, cumulative capacity, consumption projections and emissions trajectory
- Key risks and sensitivities, and a Monte Carlo probability analysis
- Recommendations

Use **Print** to produce a copy.

### Manage Targets
**Menu**: Renewable Energy Target > Manage Targets

Maintains the target and projection records that drive the Dashboard and Scenario Projections pages.

- Use the **scenario type** selector (default Base Case) and optionally a **SIREN scenario** to filter the table, which lists records by year.
- **Add Scenario**: enter the scenario type, target year, target type and, if relevant, the SIREN Facilities scenario it is linked to, plus a description. Then fill in:
  - *Consumption*: operational and underlying consumption (GWh) and storage (MWh)
  - *Target/projected RE%* and *emissions (t)*
  - *Generation (GWh)* by wind, utility solar, rooftop solar, biomass and gas
  - *Probability (%)* of the projection being achieved
- Row buttons let you **view**, **edit** or **delete** a record, and **toggle active/inactive**. Only active records are used in the Projections and Risk pages.

### RET Replacement Scenarios
**Menu**: Renewable Energy Target > RET Replacement Scenarios

Assesses how different RET levels (55% to 85%) would displace coal and gas generation by 2030. Two tabs give a forecast for the **expected** demand and the **high** demand. For each RET level the page shows the additional renewable energy needed, the wind and solar capacity required, and how the displacement is shared across the fossil sources in priority order.

### RET Analysis Config
**Menu**: Renewable Energy Target > RET Analysis Config

Edits the assumptions behind RET Replacement Scenarios:
- **Demand forecasts** (TWh) for expected and high 2030 demand
- **Capacity factors** assumed for wind and solar (0 to 1)
- **Current RE baseline** (GWh) and the **pipeline** wind and solar additions by 2030 (GW), with a **curtailment rate** (0 to 1)
- **Fossil fuelled generation and displacement priorities**: add or remove sources and set the order in which they are displaced

Click **Save Configuration**; the settings are kept in the active preferences (.ini) file.

---
## Facility Generation
Three tools share the same layout and controls as the Supply Factor visualisation described in the next section.

### Actual (Scada)
**Menu**: Facility Generation > Actual (Scada)

Plots the **actual** half-hourly output of facilities as recorded by SCADA, aggregated to hourly, weekly or monthly.

- Same four modes as Supply Factors: *Single Facility*, *Compare Two Facilities* (each side can be a group of facilities), *Technology Aggregated*, and *Compare Technologies*.
- Choose the year, **Time Period**, **Chart Type** and optional date range, then click the plot or compare button.
- **Export** creates an Excel file of the plotted data.

Any facility can be plotted, whether or not it is renewable. Only years with SCADA data are offered.

### Scada Analysis
**Menu**: Facility Generation > Scada Analysis

A monthly report of average SWIS load, with three tabs:
- **Load Analysis**: key metrics for the month, energy mix, average diurnal (24 hour) profiles, daily renewable variation, a detailed breakdown, renewable performance highlights and year-to-date figures including battery (BESS) metrics.
- **Historical Data**: demand, RE penetration and generation mix trends over a chosen range of years, a period comparison table, summary statistics and annual comparison. **Export CSV** downloads the data.
- **Facility Overview**: installed capacity by fuel type and top performers for the month.

Pick the month in **Select Period** and click **View**.

### Simulated (SAM)
**Menu**: Facility Generation > Simulated (SAM)

The Supply Factors visualisation - see *Facility Supply Factors* below. It plots the output simulated with the System Advisor Model in Powermatch *Run Power*, not actual output.

### Comparison (Actual vs Simulated)
**Menu**: Facility Generation > Comparison

Overlays actual SCADA output and simulated output so you can judge how well the simulation reproduces reality.

**Modes**: Single Facility, Facility Group, Technology Aggregated, Compare Technology Groups. Only facilities and years that have **both** SCADA and simulated data are offered.

**Controls**: year, time period (hourly, weekly, monthly), chart type, optional date range, and a **Peak Hours** filter:

| Filter | Hours |
|--------|-------|
| All Hours | All |
| Peak | 4pm to 9pm |
| Shoulder | 7am to 4pm |
| Off-Peak | 9pm to 7am |
| Daytime | 6am to 8pm |
| Solar Peak | 10am to 3pm |

**Statistics shown**: correlation between actual and simulated, and error measures (MAE and RMSE). A high correlation with a large error means the shape is right but the magnitude is off (for example the simulated weather year differs from the actual year).

**Export** creates an Excel file with the series and the metrics.

---
## Risk Analysis
Records and compares risks against Facilities scenarios (scenarios themselves are created in Powermap).

### Risk Dashboard
**Menu**: Risk Analysis > Risk Dashboard

Overview cards (scenarios with risks, total events, severe and high risks), a scenario risk comparison chart, a risk distribution chart, a card per scenario with its risk events, and the legend for the 6x6 risk matrix.

### Manage Scenarios
**Menu**: Risk Analysis > Manage Scenarios

Lists scenarios. Open one to see its **detail page**: scenario details, risk summary, risk profile by category, the **6x6 risk matrix** (switch between **Inherent** and **Residual**), and the list of risk events with view and delete buttons.

### Adding and editing risk events
From a scenario's detail page choose **Add Risk Event**. Complete:
- **Risk Details**: category, title, description, cause, source and mitigation strategies
- **Inherent Risk Assessment**: likelihood and consequence *before* mitigation
- **Residual Risk Assessment**: likelihood and consequence *after* mitigation
- **Supporting Information**: assumptions and data sources

Likelihood and consequence are each scored 1 to 6:

| Score | Likelihood | Consequence |
|-------|-----------|-------------|
| 1 | Remote (once in 10,000-100,000 yrs) | Slight |
| 2 | Highly unlikely | Minor |
| 3 | Unlikely | Moderate |
| 4 | Possible (once in 10-100 yrs) | Major |
| 5 | Quite likely (once in 1-10 yrs) | Massive |
| 6 | Likely (more than once a year) | Catastrophic |

The risk score is likelihood multiplied by consequence and is placed in a level on the matrix. The gap between inherent and residual shows how effective the mitigations are.

### Compare Scenarios
**Menu**: Risk Analysis > Compare Scenarios

Tick two or more scenarios and click **Compare**. Charts show risk score, risk level distribution, category risk profiles and risk reduction effectiveness; tables give a detailed comparison and the energy mix of each scenario.

---
## Transport Electrification
### EV Uptake Tracking
**Menu**: Transport Electrification > EV Uptake Tracking

Compares actual electric vehicle registrations in WA (Department of Transport quarterly data) with the CSIRO Low, Medium and High projections. The chart plots the projection curves (each year-end point) and the actuals. A flag states whether actual uptake is tracking above, within or below the projection range, as an early warning for the EV load assumptions in Powermatch.

### EV Charging Profiles
**Menu**: Transport Electrification > EV Charging Profiles

Displays the AEMO charging shapes that drive the half-hourly EV load model: the weekday and weekend shape for each charging type, and the composite *unmanaged* versus *managed* shapes. It explains how the profiles are used and their caveats. Read-only.

---
## WEM Prices and SWIS Demand
### WEM Prices
**Menu**: WEM Prices

A 3D chart of the average wholesale energy price in the WEM by month and period of day, with commentary on negative prices and where they are heading. Rotate and zoom the chart with the mouse.

### SWIS Demand
**Menu**: SWIS Demand

A 3D chart of underlying consumption showing how operational demand has moderated despite rising underlying demand, due mainly to rooftop solar growth, with commentary on future trends.

---
## ESOO Bias Tracking
**Menu**: ESOO Bias Tracking

Tests whether AEMO's WEM Electricity Statement of Opportunities (ESOO) demand forecasts have been systematically high or low. The page works in a strict order:

1. **Validation-first backcast**: reproduces the forecast-versus-actual gaps AEMO itself published (Table 11 of the 2026 WEM ESOO) using this system's own calculations, and reports whether they match. If this check fails, treat the later results with caution.
2. **Extended bias tracking (full archive)**: uses every ESOO vintage loaded. Shows central-estimate bias by metric and year-ahead horizon, and a band calibration chart (how often actuals fell inside the POE10 to POE90 range).
3. **Applied to Powermatch scenarios**: shows which demand-forecast scenarios the findings affect.

Terms: **operational demand** is the demand drawn from the grid (excluding rooftop solar and other on-site generation); **POE10/50/90** are the probabilities that a forecast is exceeded; **horizon** is how many years ahead a forecast was made. Pairs whose demand basis differs are refused rather than compared. Where there is too little data, the page says "Insufficient evidence" instead of guessing.

---
## Facility Supply Factors (Simulated, SAM)
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
A: The tool uses the simulated supply factor data stored per facility and year by Powermatch *Run Power*, which contains hourly quantum and supply values for each facility.
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
