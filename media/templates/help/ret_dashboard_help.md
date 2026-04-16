# Guide to the RET Dashboard Reports

## Overview

The Renewable Energy Target (RET) Dashboard is a comprehensive reporting system for tracking the South West Interconnected System's (SWIS) progress towards a renewable energy target. It provides monthly performance monitoring, quarterly analysis, annual reviews, and long-term scenario projections to support energy transition planning and stakeholder reporting.

---

## Available Reports

The RET Dashboard system includes four main report types:

| Report | Purpose | Frequency |
|--------|---------|-----------|
| **Monthly Dashboard** | Current month performance snapshot | Monthly |
| **Quarterly Report** | Detailed quarterly analysis with trends | Quarterly |
| **Annual Review** | Comprehensive yearly assessment | Annually |
| **Scenario Projections** | Long-term pathway analysis to 2040 | Ad-hoc |

---

## Monthly Dashboard

### Purpose
The Monthly Dashboard provides a snapshot of SWIS renewable energy performance for the selected reporting period, including year-to-date progress and comparison against targets.

### Navigation Bar
Links to recent quarterly reports, the annual review, published reports, a help page, and a print button appear at the top of the page. The **Select Period** dropdown lets you navigate to any available month.

### Key Sections

#### Visualizations
Two pie charts are displayed side by side showing the generation mix for the month:
- **Left chart** — operational generation mix (excludes rooftop solar)
- **Right chart** — underlying generation mix (includes rooftop solar/DPV)

Below the pie charts, the **Pathway to 2040 Target** line chart shows historical monthly RE% performance and the year-to-date cumulative line plotted against the target trajectory.

#### RE Performance
Displays the renewable energy percentage for both demand measures, each with a prior-year comparison:
- **RE% (Operational Demand)**: Renewable generation as a percentage of grid-sent electricity
- **RE% (Underlying Demand)**: Renewable generation as a percentage of total demand including rooftop solar

#### Understanding Demand Measures
An information box defines the two demand measures:
- **Operational Demand**: Total load required from the grid, excluding behind-the-meter rooftop solar and small, non-scheduled generation.
- **Underlying Demand**: Total electricity usage by consumers, including grid supply, behind-the-meter rooftop solar (PV), and battery storage.

#### Year to Date
Cumulative performance metrics from January to the current month:
- YTD RE% (Operational)
- YTD RE% (Underlying) — including rooftop solar
- Target status — shows the target percentage and whether performance is ahead of or behind the trajectory
- YTD Emissions (Kt CO₂-e) with year-on-year change indicator

#### Monthly Highlights — Generation Mix
A detailed table breaking down electricity generation for the month:

| Technology | Generation (GWh) | % of Operational Demand | % of Underlying Demand |
|---|---|---|---|
| Wind | | | |
| Solar (Utility) | | | |
| Solar (Rooftop) | | — | |
| Biomass | | | |
| Hydro | | | |
| Battery | | | |
| Gas | | | |
| Coal | | | |
| *Battery Charge* (if > 0) | | | |
| *Hydro Pumping* (if > 0) | | | |

The table footer shows the Total RE% for both demand measures.

Renewable rows are shown with a green background; fossil fuel rows in white; storage charge/pumping rows in blue italics.

#### Key Statistics
Notable performance indicators shown as metric cards:
- **Operational Demand** (GWh) with prior-year change
- **Underlying Demand** (GWh, includes rooftop solar) with prior-year change
- **Avg Grid Emissions Intensity** (kg CO₂-e/kWh)
- **Best Renewable Hour** — highest one-hour operational RE% and its date/time
- **Peak Instantaneous Operational RE%** — highest half-hourly RE% and its date/time
- **Peak Operational Demand** (MW and date/time)
- **Minimum Operational Demand** (MW and date/time)

#### Wholesale Price Statistics
Market price analysis for the period (shown only if price data is available):
- Average price ($/MWh) with prior-year comparison
- Maximum price ($/MWh) with date/time; card shows a warning colour if price exceeded $300/MWh
- Minimum price ($/MWh) with date/time; card shows positive colour if price was negative
- Price Volatility — standard deviation ($/MWh)
- **Negative Price Intervals** — count of trading intervals with price < $0/MWh, with prior-year comparison
- **Price Spike Intervals** — count of trading intervals with price > $300/MWh, with prior-year comparison

An information box explains negative prices, price spikes, and volatility.

#### New Capacity
Shown only when new capacity data exists for the period:
- List of facilities commissioned during the month with capacity (MW) and commissioning date
- Total new renewable capacity for the month
- Upcoming capacity (facilities expected to commission in the next 3 months)

#### Emissions Performance
A two-row table covering the current month and year-to-date:
- Total Emissions (Kt CO₂-e)
- Emissions Intensity (kg/kWh)
- Year-on-year change (%)

#### What This Means
Two information boxes providing contextual interpretation of the month's data:
- **For Consumers**: Emissions reduction, grid renewables percentage, underlying RE% including rooftop, and 2040 trajectory status
- **For the Grid**: Integration challenges, storage performance, negative pricing opportunities

#### Comments
Authenticated users can add, view, and manage comments for the monthly report.

---

## Quarterly Report

### Purpose
The Quarterly Report provides detailed analysis of performance over a three-month period, enabling trend identification and progress assessment against annual targets.

### Key Sections

#### Executive Summary
Auto-generated narrative showing quarterly RE% (both measures), year-to-date RE%, total quarterly emissions and the year-on-year change, and average wholesale price. Authenticated users can add additional commentary via the **Add to Summary** button. A demand definitions information box appears below the summary.

#### Key Findings
Summary metrics displayed as cards:
- Q[N] RE% (Operational) — grid-sent electricity
- Q[N] RE% (Underlying) — including rooftop solar
- YTD RE% (Operational) with prior-year comparison
- YTD RE% (Underlying) with prior-year comparison
- Year target status — shows shortfall in percentage points or "On track"
- Q[N] Emissions (tonnes CO₂-e) with year-on-year change
- YTD Emissions (tonnes CO₂-e) with year-on-year change
- Q[N] Average Wholesale Price ($/MWh) — shown only if price data is available

#### Wholesale Price Summary
Shown only if wholesale price data is available. Includes:
- Price stat cards: Average, Maximum, Minimum prices; Negative Price Intervals; Price Spike Intervals
- **Monthly Wholesale Price Breakdown** table with columns: Month, Avg Price, Max Price, Min Price, Negative Intervals, Spike Intervals
- Year-on-year wholesale price comparison

#### Monthly Performance Breakdown
Detailed table showing each month's performance:
- Underlying Demand (GWh)
- Renewable Generation (GWh)
- RE% (Operational)
- Variance from target (pp) — shown in green if ahead, red if behind
- RE% (Underlying)
- Emissions (tonnes CO₂-e)

The table includes a quarterly total row.

#### Cumulative Year-to-Date Performance
Comparison table with columns for Q[N] current year, YTD current year, YTD prior year, and change:
- RE% (Operational) — change shown in percentage points (pp)
- RE% (Underlying) — change shown in pp
- Total Emissions (tonnes CO₂-e) — change shown as %
- Emissions Intensity (kg CO₂-e/kWh) — change shown as absolute
- Average Wholesale Price ($/MWh) — shown if price data available

A status note below the table confirms whether YTD performance is ahead of or behind the annual target.

#### Generation by Technology for the Quarter
A detailed table with columns: Technology, Generation (GWh), % of Operational Demand, % of Underlying Demand, Emissions. Covers Wind, Solar (Utility), Solar (Rooftop), Biomass, Hydro, Battery, Gas, Coal, plus Battery Charge and Hydro Pumping rows (shown only when > 0). The table footer shows Total RE% for both demand measures.

#### Operational Generation Mix Analysis
Two interactive charts:
- **Monthly Generation Breakdown** — stacked bar chart of operational generation by technology (Wind, Solar, Biomass, Hydro, Battery, Gas, Coal) for each month of the quarter. Hover over columns to see exact generation values.
- **Year-over-Year RE% Comparison** — bar chart comparing both demand measures (Operational and Underlying) for the same quarter in the current and prior year (four bars total).

#### New Capacity Commissioned
Shown only when facilities were commissioned during the quarter. Lists each facility with name, capacity (MW), technology type, and commissioning date, plus the total new renewable capacity for the quarter.

#### Key Observations
Two analysis sections auto-populated with data-driven observations:
- **Positive Developments**: Year-on-year RE% improvement, emissions reduction, wind and solar contribution highlights, and negative pricing incidence.
- **Challenges and Risks**: RE% shortfall against target, price spike intervals, and general monitoring notes.

#### Comments
Authenticated users can add comments. Not shown in published versions of the report.

---

## Annual Review

### Purpose
The Annual Review provides a comprehensive assessment of the full calendar year's performance, including progress towards long-term targets and strategic recommendations.

### Key Sections

#### Executive Summary
Auto-generated narrative covering annual RE% (both measures), total emissions and year-on-year change, and average wholesale price. Authenticated users can add additional commentary via **Add to Summary**. A demand definitions information box appears below the summary.

#### Key Findings
Annual performance metrics shown as cards:
- RE% (Operational) — with target status colour
- RE% (Underlying) — with target status message
- Total Consumption (GWh, underlying) with year-on-year change
- Total Emissions (tonnes CO₂-e) with year-on-year change
- New Capacity (MW renewable) commissioned during the year

#### Wholesale Price Summary
Shown only if wholesale price data is available. Includes:
- Metric cards: Average Price (with YoY change), Maximum Price (with month and date/time), Minimum Price (with month and date/time), Negative Price Intervals (with prior-year comparison), Price Spike Intervals (with prior-year comparison)
- **Monthly Wholesale Price Breakdown** table with columns: Month, Avg ($/MWh), Max ($/MWh), Min ($/MWh), Std Dev, Negative intervals, Spike intervals. Includes an annual Total/Avg footer row.
- **Wholesale Price Insights** information box with auto-generated commentary on negative pricing, price spikes, and year-on-year price movement.

#### Performance Summary
Year-over-year comparison table (current year vs prior year with change column):
- Operational Demand (GWh)
- Underlying Demand (GWh)
- Renewable Generation (GWh)
- RE% (Operational) — change shown in pp
- RE% (Underlying) — change shown in pp

#### Generation Mix Analysis
Annual technology breakdown table with columns: Technology, Generation (GWh), % of Operational Demand, % of Underlying Demand, Emissions. Covers Wind, Solar (Utility), Solar (Rooftop), Biomass, Hydro, Battery, Gas, Coal, plus Battery Charge and Hydro Pumping rows. The table footer shows Total RE% for both demand measures.

#### Annual Trends
Two interactive Plotly charts:
- **Monthly Generation by Technology** — stacked bar chart showing monthly generation across the year by technology, illustrating seasonal patterns.
- **Multi-Year RE% Comparison** — line/trend chart overlaying historical annual performance for context.

#### New Capacity Commissioned
Shown only when facilities were commissioned during the year. A summary heading shows total MW, followed by a table with columns: Facility, Technology, Capacity (MW), Commissioned date.

#### Recommendations
Two information boxes:
- **Target Confirmation**: States the recommended 2040 target with supporting rationale and Monte Carlo probability.
- **Priority Actions**: Specific pipeline management, battery storage, grid investment, interim milestone, and price management actions.

#### Comments
Authenticated users can add comments. Not shown in published versions of the report.

---

## Scenario Projections

### Purpose
The Scenario Projections report provides long-term pathway analysis to assess the likelihood of achieving the 2040 renewable energy target under different assumptions.

### Scenario Types

| Scenario | Description |
|----------|-------------|
| **Base Case** | Planned and probable facilities commissioned on schedule with historical capacity factors and planned consumption growth (the most likely pathway) |
| **Accelerated Pipeline** | All possible facilities included, faster commissioning, optimistic capacity factors and additional unplanned consumption growth |
| **Delayed Pipeline** | Only planned facilities, 12-month average delay, conservative capacity factors, less than planned consumption growth |

A Scenario Type Definitions information box on the page summarises the assumptions for each scenario.

### Key Sections

#### Executive Summary
A brief narrative stating the three scenario types and the Base Case probability of achieving the 100% 2040 target based on Monte Carlo analysis.

#### Key Targets Overview
Four summary metric cards:
- 2040 RE Target (100%, underlying consumption basis)
- 2030 Interim Target (82%, underlying consumption basis)
- Current RE% — the latest annual result
- Achievement Probability — Base Case probability at the 100% target from Monte Carlo analysis

#### RE% Trajectory by Scenario
An interactive chart showing RE% pathways from the current year to 2040. Features:
- **Scenario selector dropdown** — switches which scenario's stacked area fill is shown (Base Case, Accelerated Pipeline, Delayed Pipeline)
- **Stacked area fill** — shows the energy mix breakdown (Wind, Solar Utility, DPV, Storage Discharge, Other RE) for the selected scenario
- **RE% lines** for all three scenarios simultaneously (solid, dashed, dotted) plus the Actual historical line and Target milestone line (2030: 82%, 2040: 100%)
- **Energy Mix hover panel** — appears to the right of the chart; hover over any year on the chart to see DPV, Solar (Utility), Wind, Storage (MWh), Other RE generation values, the RE%, and underlying demand for that year under the selected scenario

#### Scenario Projections Summary
A year-by-year projection table for the **Base Case (Step Change)** scenario showing: Year, RE%, Wind (GWh), Solar (GWh), DPV (GWh), Storage (MWh), Emissions (kt), Target Type (Ordinary / Interim Target / Major Target). Milestone years (2030, 2040) are highlighted.

#### Scenario Comparison — 2040 Target
A three-row table comparing all scenarios at 2040: Scenario name, 2040 RE%, variance from 100% target (pp), probability of achievement, total RE generation (GWh), Emissions (kt), and Status.

#### Projected Facility Pipeline
Summary capacity cards showing current MW by status (Commissioned, Under Construction, Planned, Probable), followed by a detailed table of upcoming facility commissioning (2025–2030) with columns: Facility, Technology, Capacity (MW), Status, Expected Commissioning, Probability.

#### Projected Generation Mix Transition
A stacked bar chart (Base Case) showing absolute generation (GWh) by technology — Wind, Solar (Utility), DPV (Rooftop Solar), Biomass/Other RE, Gas — for key years from 2025 to 2040, illustrating the shift from fossil fuels to renewables.

#### Cumulative Capacity by Technology
A table showing installed capacity (MW) for key years (2025, 2027, 2030, 2035, 2040): Wind, Solar Utility, DPV, Storage, Total RE.

#### Consumption Projections
An interactive line chart (Base Case) showing Underlying Demand and Operational Demand from 2025 to 2040, with actual historical demand overlaid. Followed by a table with columns: Year, Operational Consumption (GWh), DPV Generation (GWh), Underlying Consumption (GWh), Growth Rate.

#### Emissions Reduction Trajectory
An interactive line chart showing projected emissions (kt CO₂-e) under all three scenarios plus actual historical emissions. Followed by four metric cards: 2024 Baseline, 2030 Projected (Base), 2040 Projected (Base), and Cumulative Reduction (2025–2040).

#### Key Risks and Sensitivities
Two information boxes:
- **Downside Risks**: Project delays, grid constraints, financing challenges, resource variability
- **Upside Opportunities**: Technology improvements, policy support, storage cost decline, DPV growth

#### Monte Carlo Probability Analysis
Explains the simulation parameters (10,000 iterations, commissioning probability by status, commissioning delay distribution, capacity factor variance, consumption growth uncertainty), followed by an interactive bar chart and a table showing the probability of achieving each target RE% threshold (80%, 85%, 90%, 95%, 100%) under the Base Case.

#### Recommendations
Two information boxes:
- **Target Confirmation**: States the recommended 2040 target, achievement probability, and supporting rationale
- **Priority Actions**: Pipeline management, battery storage, grid investment, and interim milestone actions

---

## Glossary of Terms

### Demand Measures

| Term | Definition |
|------|------------|
| **Operational Demand** | The half-hourly average output from all large-scale grid connected generators. It doesn't include energy consumed by market scheduled loads e.g. pumped hydro and utility scale batteries. Represents electricity delivered through the transmission and distribution network. |
| **Underlying Demand** | Operational demand plus half-hourly estimates of rooftop solar generation, yielding an estimate of total supply from "both ends of the grid." |
| **Peak Demand** | Maximum instantaneous power demand (MW) during the reporting period. |
| **Minimum Demand** | Minimum instantaneous power demand (MW) during the reporting period. |

### Generation Technologies

| Term | Definition |
|------|------------|
| **Wind** | Utility-scale wind farm generation connected to the grid. |
| **Solar (Utility)** | Large-scale solar farms connected to the transmission network. |
| **Solar (Rooftop/DPV)** | Distributed Photovoltaic — residential and commercial rooftop solar systems. |
| **Biomass** | Generation from organic waste materials (e.g., landfill gas, wood waste). |
| **Hydro** | Pumped hydro electricity storage discharging to the grid. |
| **Battery** | Utility-scale storage batteries discharging to the grid. |
| **Gas** | Generation from natural gas-fired power stations (OCGT and CCGT). |
| **Coal** | Generation from coal-fired power stations. |
| **Battery Charge** | Electricity consumed by battery storage systems when charging. |
| **Hydro Pumping** | Electricity consumed by pumped hydro storage systems when pumping. |

### Performance Metrics

| Term | Definition |
|------|------------|
| **RE%** | Renewable Energy Percentage — the proportion of demand met by renewable generation. |
| **Capacity Factor** | Actual generation as a percentage of theoretical maximum output. |
| **Emissions Intensity** | CO₂-equivalent emissions per unit of electricity (kg CO₂-e/kWh). |
| **YTD** | Year-to-Date — cumulative performance from January to the current period. |
| **YoY** | Year-over-Year — comparison with the same period in the previous year. |
| **pp** | Percentage points — absolute change in percentage values. |

### Wholesale Market Terms

| Term | Definition |
|------|------------|
| **WEM** | The wholesale electricity market. The WEM system selects the lowest tender first, and others of increasing value until demand is satisfied. |
| **Balancing Price** | The price of the highest offer used during each interval. All selected generators receive the Balancing Price. There is a regulated ceiling for the offer price, currently $1000/MWh. |
| **Wholesale Price** | The price paid for electricity in the wholesale market ($/MWh). |
| **Trading Interval** | An interval is one of the 30-minute blocks of time used for controlling the electricity delivered to the grid. |
| **Negative Price** | When the wholesale price falls below $0/MWh. Generators are allowed to offer negative prices during intervals when generation exceeds demand, to avoid the costs of stopping and restarting generating plant. Coal and to a lesser extent gas plants have these costs. |
| **Price Spike** | A trading interval where the balancing price suddenly jumps from earlier prices, usually at or near the offer price ceiling. |
| **Price Volatility** | Standard deviation of wholesale prices, indicating price variability. |

### Facility Status Categories

| Term | Definition |
|------|------------|
| **Commissioned** | Facility is operational and generating electricity. |
| **Under Construction** | Facility is being built with high certainty of completion. |
| **Planned** | Facility has received approvals and/or financing commitment. |
| **Probable** | Facility is likely to proceed but lacks final commitment. |
| **Possible** | Facility is under consideration but has significant uncertainty. |

### Scenario Analysis Terms

| Term | Definition |
|------|------------|
| **Base Case** | Most likely outcome based on current plans and historical performance. |
| **Monte Carlo Analysis** | Statistical simulation using random sampling to model uncertainty. |
| **P10/P50/P90** | Probability percentiles (10%, 50%, 90% chance of achieving or exceeding). |
| **Probability of Achievement** | Likelihood of meeting a specific target based on simulation. |

---

## Formulae and Calculations

### Renewable Energy Percentage

**RE% (Operational)**
```
RE% (Operational) = (Renewable Generation / Operational Demand) x 100

Where:
  Renewable Generation = Wind + Solar (Utility) + Biomass + Hydro Discharge + Battery Discharge
  Operational Demand = Total demand from grid sources (excludes rooftop solar and storage charging)
```

**RE% (Underlying)**
```
RE% (Underlying) = (Total Renewable Generation / Underlying Demand) x 100

Where:
  Total Renewable Generation = Wind + Solar (Utility) + Solar (DPV) + Biomass + Hydro Discharge + Battery Discharge
  Underlying Demand = Operational Demand + Estimated Self-Consumed DPV Generation
```

### Emissions Calculations

**Total Emissions**
```
Total Emissions (tonnes CO₂-e) = Sum of (Generation by Fuel Type x Emissions Factor)

Emissions Factors:
  Gas:  380 kg CO₂-e/MWh (typical CCGT)
  Coal: 900 kg CO₂-e/MWh (typical black coal)
  Wind, Solar, Biomass, Hydro, Battery: 0 kg CO₂-e/MWh
```

**Emissions Intensity**
```
Emissions Intensity (kg CO₂-e/kWh) = Total Emissions (kg) / Operational Demand (kWh)
```

### Year-over-Year Change

**Percentage Change**
```
YoY Change (%) = ((Current Period Value - Previous Period Value) / Previous Period Value) x 100
```

**Percentage Point Change**
```
YoY Change (pp) = Current Period RE% - Previous Period RE%

Note: Use percentage points (pp) for comparing percentages, not percentage change.
Example: RE% increased from 35% to 40% = +5 pp (not +14.3%)
```

### Target Status

**Gap to Target**
```
Gap (pp) = Actual RE% - Target RE%

Status:
  Gap > 0:  "Ahead of target"
  Gap = 0:  "On target"
  Gap < 0:  "Behind target"
```

### Quarterly Aggregations

**Quarterly Summary**
```
Quarterly Demand = Sum of Monthly Demands (Jan–Mar, Apr–Jun, Jul–Sep, Oct–Dec)
Quarterly Generation = Sum of Monthly Generations
Quarterly RE% = (Quarterly Renewable Generation / Quarterly Demand) x 100
```

**Year-to-Date Summary**
```
YTD Demand = Sum of all monthly demand from January to current month
YTD Generation = Sum of all monthly generations from January to current month
YTD RE% = (YTD Renewable Generation / YTD Demand) x 100
```

### Wholesale Price Statistics

**Average Price (Volume-Weighted)**
```
Avg Price = Sum(Price x Volume) / Sum(Volume)
```

**Price Volatility (Standard Deviation)**
```
Std Dev = sqrt(Sum((Price - Avg Price)^2 x Volume) / Sum(Volume))
```

**Negative Price Count**
```
Negative Intervals = Count of trading intervals where Price < $0/MWh
```

**Price Spike Count**
```
Spike Intervals = Count of trading intervals where Price > $300/MWh
```

### Monte Carlo Simulation

**Achievement Probability**
```
Probability = (Count of simulations achieving target / Total simulations) x 100

Parameters:
  - Commissioning probability by status (Planned: 85%, Probable: 60%, Possible: 35%)
  - Commissioning delay distribution (Normal, mean 6 months, std dev 4 months)
  - Capacity factor variance (±10% based on historical data)
  - Consumption growth uncertainty (±0.5% annual variation)
```

---

## Report Usage Tips

### Report Actions
- **Print**: Use the Print button or browser print function (the period selector is hidden in print view)
- **Publish**: Authenticated users can publish quarterly and annual reports for external distribution; comments sections are hidden in published versions
- **Comment**: Add comments and observations to reports (authenticated users only)
- **Add to Summary**: Modify executive summaries for quarterly and annual reports (authenticated users only)

### Interactive Charts
- **Hover**: View exact values for data points
- **Zoom**: Click and drag to zoom into specific periods
- **Pan**: Use controls to move across the chart
- **Scenario selector**: On the Scenario Projections trajectory chart, use the dropdown to change which scenario's stacked area is displayed
- **Energy Mix panel**: On the Scenario Projections trajectory chart, hover over any year to see the full generation mix breakdown in the panel on the right

---

## Frequently Asked Questions

### General

**Q: What is the difference between Operational and Underlying Demand?**
A: Operational demand measures electricity delivered through the grid. Underlying demand includes operational demand plus rooftop solar generation consumed by households before export. Underlying demand represents total electricity consumption.

**Q: Why are there two RE% measures?**
A: RE% (Operational) shows renewables contribution to grid electricity, while RE% (Underlying) includes behind-the-meter solar, giving a complete picture of renewable energy in the system.

**Q: What is the 2040 target?**
A: The proposed SWIS target is for 100% renewable energy by 2040, measured on an underlying demand basis. An interim target of 82% applies for 2030.

### Data and Calculations

**Q: Where does the data come from?**
A: Generation data comes from AEMO SCADA systems, demand data from system operator reports, and DPV estimates from network operators. Wholesale prices are from WEM market data.

**Q: How often is data updated?**
A: Monthly performance data is typically available within 2–3 days of month end.

**Q: Why don't storage emissions show in the table?**
A: Storage (batteries, pumped hydro) doesn't generate emissions directly — it stores and releases electricity. The emissions are attributed to the original generation source.

**Q: What units are used for emissions intensity?**
A: Emissions intensity is displayed in kg CO₂-e/kWh on the dashboard cards and tables.

### Reports

**Q: Can I download reports?**
A: Yes, use the Print function to save as PDF, or published reports are available in the Published Reports section.

**Q: What does "Published" mean for a report?**
A: Published reports are frozen versions that have been reviewed and approved for external distribution. They cannot be edited and do not show the comments section.

**Q: What are the scenario projection numbers based on?**
A: When live scenario data exists in the database, the charts and tables reflect that data. When no database records are present, the page displays illustrative example data and shows a notice at the top of the page.

---

## Support

For technical support or questions about the RET Dashboard:
- **Email**: modelling.lead@sen.asn.au

*Last updated: April 2026*
