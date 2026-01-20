# SWIS Risk Analysis User Guide

## Overview

The SWIS Risk Analysis module provides a comprehensive framework for assessing and comparing risks across different energy transition scenarios for the South West Interconnected System (SWIS) in Western Australia. Based on the 2016 SWIS Risk Matrix methodology, this tool has been updated to include 2026 technology scenarios and new risk categories relevant to modern grid operations.

## Accessing the Module

Navigate to the Risk Analysis section from the Powerplot menu:

- **Risk Dashboard** (`/risk/`) - Overview of all scenarios and summary statistics
- **Manage Scenarios** (`/risk/scenarios/`) - Create, edit, and delete scenarios
- **Compare Scenarios** (`/risk/compare/`) - Side-by-side comparison of multiple scenarios

## Key Concepts

### Risk Matrix (6x6)

The risk assessment uses a 6x6 matrix combining **Likelihood** and **Consequence** scores:

| Likelihood Level | Score | Description |
|-----------------|-------|-------------|
| Rare | 1 | May occur only in exceptional circumstances |
| Unlikely | 2 | Could occur but not expected |
| Possible | 3 | Might occur at some time |
| Likely | 4 | Will probably occur |
| Almost Certain | 5 | Expected to occur in most circumstances |
| Expected | 6 | Will occur |

| Consequence Level | Score | Description |
|------------------|-------|-------------|
| Insignificant | 1 | No injuries, minimal financial impact |
| Minor | 2 | First aid treatment, <$100K impact |
| Moderate | 3 | Medical treatment, $100K-$1M impact |
| Major | 4 | Serious injury, $1M-$10M impact |
| Severe | 5 | Single fatality, $10M-$100M impact |
| Catastrophic | 6 | Multiple fatalities, >$100M impact |

### Risk Score Calculation

**Risk Score = Likelihood × Consequence**

| Risk Level | Score Range | Action Required |
|------------|-------------|-----------------|
| Low | 1-6 | Acceptable risk, routine monitoring |
| Moderate | 7-12 | Management attention required |
| High | 13-24 | Senior management attention required |
| Severe | 25-36 | Immediate action required |

### Inherent vs Residual Risk

- **Inherent Risk**: The risk level before any mitigation measures are applied
- **Residual Risk**: The risk level after mitigation strategies have been implemented
- **Risk Reduction**: The percentage decrease from inherent to residual risk

## Risk Categories

The module includes eight risk categories:

| Category | Description |
|----------|-------------|
| **Safety** | Risks to human health and safety |
| **Cost** | Financial and economic risks |
| **Environment** | Environmental impact and sustainability risks |
| **Production** | Energy production and reliability risks |
| **Grid Stability** | System inertia, frequency control, voltage stability |
| **Supply Chain** | Critical minerals, manufacturing, logistics risks |
| **Cyber Security** | SCADA vulnerabilities, DER coordination risks |
| **Climate Adaptation** | Extreme weather, bushfire, flooding, heat waves |

## Energy Scenarios

Seven pre-configured 2026 SWIS scenarios are included:

| Scenario | Description | Target Year |
|----------|-------------|-------------|
| **VRE + BESS + Gas** | Wind + Solar + Battery + Gas backup (baseline) | 2040 |
| **VRE + Pumped Hydro** | Wind + Solar + PHES + minimal Gas | 2040 |
| **VRE + Green Hydrogen** | Wind + Solar + H2 storage + H2 turbines | 2040 |
| **Nuclear SMR Hybrid** | SMR baseload + VRE complement | 2045 |
| **BAU Gas Transition** | Coal phase-out with gas expansion | 2035 |
| **High DPV + Storage** | Maximum rooftop solar + distributed storage | 2040 |
| **100% Renewable** | Full renewable, no fossil backup | 2045 |

---

## Using the Dashboard

### Summary Cards

The top of the dashboard displays key metrics:
- **Active Scenarios**: Number of scenarios in active status
- **Total Risk Events**: Sum of all risk events across scenarios
- **Severe Risks**: Count of risks with scores 25-36
- **Average Risk Reduction**: Mean percentage reduction across all events

### Scenario Comparison Chart

A grouped bar chart comparing average inherent and residual risk scores across all active scenarios.

### Risk Distribution Chart

A donut chart showing the distribution of risk events by level (Low, Moderate, High, Severe).

### Scenario Cards

Each active scenario is displayed as a card showing:
- Scenario name and status
- Target year
- Energy mix preview (color-coded progress bar)
- Risk event count
- Average inherent risk score

Click **View Details** to see the full scenario analysis.

---

## Managing Scenarios

### Creating a New Scenario

1. Click **New Scenario** from the dashboard or scenario list
2. Fill in the basic information:
   - **Scenario Name**: Full descriptive name
   - **Short Name**: Unique identifier (no spaces, use underscores)
   - **Description**: Detailed description of the scenario
   - **Target Year**: The year this scenario projects to
   - **Status**: Draft, Active, or Archived
3. Set the energy mix percentages (should total 100%):
   - Wind, Solar, Storage, Gas, Coal, Hydro, Hydrogen, Nuclear, Biomass, Other
4. Click **Create Scenario**

### Editing a Scenario

1. Navigate to the scenario detail page or scenario list
2. Click **Edit** or the pencil icon
3. Modify the fields as needed
4. Click **Update Scenario**

### Deleting a Scenario

1. From the scenario list, click the delete (trash) icon
2. Confirm the deletion in the modal dialog
3. Note: This will also delete all associated risk events

---

## Managing Risk Events

### Adding a Risk Event

1. Navigate to a scenario's detail page
2. Click **Add Risk Event**
3. Fill in the risk details:
   - **Category**: Select from the available risk categories
   - **Risk Title**: Short descriptive title
   - **Risk Description**: Detailed description of the risk
   - **Risk Cause**: What causes this risk (optional)
   - **Risk Source**: Reference source (optional)
4. Set the **Inherent Risk Assessment**:
   - **Likelihood**: 1-6 rating
   - **Consequence**: 1-6 rating
   - The risk score is calculated automatically
5. Add **Mitigation Strategies** (optional but recommended)
6. Set the **Residual Risk Assessment** (after mitigation):
   - **Likelihood**: 1-6 rating
   - **Consequence**: 1-6 rating
7. Add supporting information:
   - **Assumptions**: Key assumptions made
   - **Data Sources**: References and sources
8. Click **Add Risk Event**

### Viewing Risk Event Details

From the scenario detail page:
1. Find the risk event in the table
2. Click the eye icon to open the detail modal
3. View full risk description, mitigation strategies, and assessment details

### Editing a Risk Event

1. Click the pencil icon next to the risk event
2. Modify the fields as needed
3. Click **Update Risk Event**

### Deleting a Risk Event

1. Click the trash icon next to the risk event
2. Confirm the deletion in the modal dialog

---

## Scenario Detail Page

### Risk Matrix Heatmap

The 6x6 heatmap shows the distribution of risk events by likelihood and consequence:
- Toggle between **Inherent** and **Residual** views
- Cells are color-coded by risk level
- Hover to see the count of risks in each cell

### Risk Profile Radar Chart

A spider/radar chart showing the risk profile by category:
- Red line: Inherent risk scores
- Green line: Residual risk scores
- Helps identify which categories have the highest risk

### Risk Summary

Shows the count of risks at each level:
- Severe, High, Moderate, Low

### Risk Events Table

Lists all risk events with:
- Category (color-coded badge)
- Risk title and description preview
- Inherent and residual scores with risk level
- Risk reduction percentage
- Action buttons (view, edit, delete)

---

## Comparing Scenarios

### Selecting Scenarios

1. Navigate to **Compare Scenarios** (`/risk/compare/`)
2. Check the boxes next to scenarios you want to compare (minimum 2)
3. Click **Compare Selected**

### Comparison Charts

The comparison view includes:

1. **Risk Score Comparison**: Grouped bar chart of average inherent vs residual scores
2. **Risk Level Distribution**: Stacked bar chart showing count of risks by level
3. **Category Risk Profiles**: Overlaid radar charts for all selected scenarios
4. **Risk Reduction Effectiveness**: Bar chart showing average risk reduction percentage

### Detailed Comparison Table

A table comparing key metrics across scenarios:
- Total risk events
- Average inherent and residual scores
- Risk reduction percentage
- Count by risk level (Severe, High, Moderate, Low)
- Target year

### Energy Mix Comparison

A stacked bar chart comparing the energy mix percentages across scenarios.

---

## Importing Data from Excel

Risk data can be imported from an Excel spreadsheet using the management command:

```bash
python manage.py import_risk_data --file=risk_data.xlsx
```

### Expected Excel Format

**Sheet 1: "Categories"**
| Column | Description |
|--------|-------------|
| name | Category name (unique) |
| description | Category description |
| display_order | Sort order (integer) |
| color_code | Hex color code (e.g., #e74c3c) |
| icon | Bootstrap icon class (optional) |

**Sheet 2: "Scenarios"**
| Column | Description |
|--------|-------------|
| short_name | Unique identifier |
| name | Full name |
| description | Scenario description |
| target_year | Target year (integer) |
| status | draft, active, or archived |
| is_baseline | TRUE or FALSE |
| wind_pct | Wind percentage (0-100) |
| solar_pct | Solar percentage (0-100) |
| storage_pct | Storage percentage (0-100) |
| gas_pct | Gas percentage (0-100) |
| coal_pct | Coal percentage (0-100) |
| hydro_pct | Hydro percentage (0-100) |
| hydrogen_pct | Hydrogen percentage (0-100) |
| nuclear_pct | Nuclear percentage (0-100) |
| biomass_pct | Biomass percentage (0-100) |
| other_pct | Other percentage (0-100) |

**Sheet 3: "RiskEvents"**
| Column | Description |
|--------|-------------|
| scenario_short_name | Must match a scenario short_name |
| category_name | Must match a category name |
| risk_title | Risk title |
| risk_description | Full description |
| risk_cause | Cause of the risk (optional) |
| risk_source | Source reference (optional) |
| inherent_likelihood | 1-6 |
| inherent_consequence | 1-6 |
| mitigation_strategies | Mitigation text (optional) |
| residual_likelihood | 1-6 (optional) |
| residual_consequence | 1-6 (optional) |
| assumptions | Assumptions text (optional) |
| data_sources | Data sources text (optional) |

### Command Options

```bash
# Import from Excel file
python manage.py import_risk_data --file=risk_data.xlsx

# Dry run (preview without making changes)
python manage.py import_risk_data --file=risk_data.xlsx --dry-run

# Clear existing data before import
python manage.py import_risk_data --file=risk_data.xlsx --clear

# Seed default categories only
python manage.py import_risk_data --seed-categories

# Seed 2026 SWIS scenarios only
python manage.py import_risk_data --seed-scenarios
```

---

## Best Practices

### Risk Assessment

1. **Be consistent**: Use the same criteria for likelihood and consequence across all scenarios
2. **Document assumptions**: Record key assumptions in the assumptions field
3. **Cite sources**: Reference data sources for credibility
4. **Review regularly**: Risk assessments should be updated as circumstances change

### Mitigation Strategies

1. **Be specific**: Describe concrete actions, not vague intentions
2. **Assign ownership**: Note who is responsible for implementation
3. **Set timelines**: Include expected implementation timeframes
4. **Measure effectiveness**: Ensure residual risk reflects realistic mitigation outcomes

### Scenario Comparison

1. **Compare like with like**: Ensure scenarios have similar scope and assumptions
2. **Use consistent categories**: Apply the same risk categories across scenarios
3. **Consider trade-offs**: Lower risk in one category may increase risk in another
4. **Document rationale**: Explain why certain risks are rated differently across scenarios

---

## Troubleshooting

### Charts Not Loading

- Check browser console for JavaScript errors
- Ensure Plotly.js CDN is accessible
- Verify API endpoints are returning data

### Data Not Displaying

- Check that scenarios are in "active" status
- Verify risk events have been created
- Ensure inherent likelihood and consequence are both set

### Import Errors

- Verify Excel sheet names match exactly: "Categories", "Scenarios", "RiskEvents"
- Check that scenario_short_name values in RiskEvents match existing scenarios
- Ensure category_name values match existing categories
- Verify numeric fields contain valid numbers

---

## API Endpoints

For developers integrating with other systems:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/risk/summary/` | GET | Overall risk statistics |
| `/api/risk/scenarios/<id>/matrix/` | GET | Risk matrix data for heatmap |
| `/api/risk/scenarios/<id>/profile/` | GET | Category risk profile for radar chart |
| `/api/risk/scenarios/<id>/` | GET | Full scenario details with events |
| `/api/risk/comparison/?scenarios=1,2,3` | GET | Multi-scenario comparison data |

---

## Support

For issues or feature requests, please contact the system administrator or raise an issue in the project repository.
