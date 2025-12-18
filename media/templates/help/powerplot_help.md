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
