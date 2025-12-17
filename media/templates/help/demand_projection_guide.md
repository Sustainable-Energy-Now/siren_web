# Factor-Based Demand Projections - Quick Start Guide

## Overview

This system allows you to break down electricity demand into multiple independent growth factors (e.g., EV Adoption, Industrial Electrification, Hydrogen Production). Each factor:
- Starts with a base percentage of total demand
- Grows independently with its own formula
- Can use time-varying growth rates
- Supports multiple growth types (linear, exponential, S-curve, compound)

**Total Demand = Sum of All Factor Demands**

---
### 1. Create Your First Scenario

Navigate to: **Demand Projection → Manage Factors**

---

## Example Scenario: "High EV Adoption 2025-2050"

### Step 1: Configure Factors

| Factor | Operational % | Underlying % | Growth Rate | Growth Type |
|--------|---------------|--------------|-------------|-------------|
| EV Adoption | 15% | - | 8% | S-Curve |
| Industrial | 25% | - | 2% | Exponential |
| Data Centers | 8% | - | 5% | Exponential |
| HVAC | 10% | 10% | 1.5% | Linear |
| Residential | - | 20% | 1% | Linear |
| Commercial | - | 12% | 1.2% | Linear |

**Totals**: 58% Operational, 42% Underlying

### Step 2: Advanced Settings (Optional)

For EV Adoption (S-Curve):
- Saturation Multiplier: 3.0 (triples by 2050)
- Midpoint Year: 2035 (50% saturation point)

### Step 3: Generate Projection

1. Go to: **Demand Projection**
2. Select: "High EV Adoption 2025-2050" from **Factor-Based Scenarios**
3. Base Year: 2024
4. Project To: 2050
5. View Mode: **breakdown**
6. Click: **Generate Projection**

### Step 4: Interpret Results

**Chart Shows**:
- 6 colored areas stacking to show total demand
- Bottom to top: Commercial, Residential, HVAC (Und), Data Centers, Industrial, EV
- Hover over any area to see exact values

**Summary Stats**:
- Base Year: 15,000 GWh
- End Year: 25,400 GWh
- Total Growth: 69.3%
- Avg Annual Growth: 2.1%

**Factor Breakdown**:
- EV grows fastest (S-curve from 2,250 to 6,750 GWh)
- Industrial grows steadily (3,750 to 6,860 GWh)
- Data Centers grows rapidly (1,200 to 4,280 GWh)

---

## Common Use Cases

### Use Case 1: Compare EV Scenarios

Create 3 scenarios:
1. **Low EV**: 5% base, 3% growth
2. **Medium EV**: 10% base, 5% growth
3. **High EV**: 15% base, 8% growth (S-curve)

Generate projections for each and compare total demand in 2040.

### Use Case 2: Industrial Electrification Impact

1. Start with baseline scenario (no industrial factor)
2. Clone scenario, add Industrial factor at 20% with 3% growth
3. Compare 2050 demand difference
4. Result shows industrial electrification adds X GWh/year

### Use Case 3: Time-Varying EV Growth

Create EV factor with time-varying rates:
```json
{
  "2025": 0.03,
  "2030": 0.10,
  "2040": 0.02,
  "2050": 0.01
}
```

This models:
- Slow initial adoption (2024-2030: 3%)
- Rapid acceleration (2030-2040: 10%)
- Market saturation (2040-2050: 2% then 1%)

### Use Case 4: Hydrogen Economy Scenario

1. Create "Green Hydrogen Future" scenario
2. Hydrogen Production factor: 5% → 30% over 25 years
3. Use S-curve with late midpoint (2045)
4. Shows slow start, then rapid ramp-up post-2040

### Use Case 5: Net Zero by 2050

Configure factors to achieve specific target:
1. Set 2050 target: 30,000 GWh
2. Current demand: 15,000 GWh
3. Required growth: 100% over 26 years = 2.7% CAGR
4. Allocate across factors to sum to 2.7% weighted average

---

## Navigation Quick Reference

### Main Pages

| Page | URL | Purpose |
|------|-----|---------|
| **Demand Projection** | `/demand-projection/` | Generate and visualize projections |
| **Factor List** | `/demand-factors/` | Browse and manage factors |
| **Factor Types** | `/demand-factors/types/` | Manage factor categories |
| **Scenario Assignment** | `/demand-factors/scenario/<id>/assign/` | Bulk configure factors |

### Workflow

```
Factor Types List → Create/Edit Types
        ↓
Factor List → Create Individual Factors
        ↓
Scenario Assignment → Bulk Configure for Scenario
        ↓
Demand Projection → Visualize Results
```

---

## Growth Type Reference

### Linear Growth
```
Demand(year) = Base × (1 + rate × years)
```
**Use for**: Steady, predictable growth (population, baseline demand)
**Example**: 2% per year = adds constant 300 GWh each year

### Exponential Growth
```
Demand(year) = Base × (1 + rate)^years
```
**Use for**: Compounding growth (technology adoption, data centers)
**Example**: 5% per year = 15,000 → 51,000 GWh over 26 years

### S-Curve (Logistic)
```
Demand(year) = Base × saturation × sigmoid(years, midpoint)
```
**Use for**: Technology adoption with saturation (EVs, heat pumps)
**Example**: Fast growth 2030-2040, then plateaus at 3× initial

### Compound Growth
```
Demand(year) = Base × exp(rate × years)
```
**Use for**: Continuous compounding (similar to exponential but smoother)
**Example**: 3% continuous = 15,000 → 32,900 GWh over 26 years

---

## Tips for Accurate Projections

### ✅ DO:
- **Split demand logically**: Separate growing sectors (EV, industrial) from baseline
- **Use realistic percentages**: Sum to 90-100% of base demand
- **Choose appropriate growth types**: S-curve for tech adoption, linear for population
- **Consider saturation**: Use S-curves for factors that can't grow forever
- **Test sensitivity**: Try high/medium/low scenarios
- **Document assumptions**: Use Notes field to explain choices

### ❌ DON'T:
- **Allocate > 100%**: Factors overlap, leading to double-counting
- **Use extreme rates**: > 10% annual growth is rarely sustainable
- **Ignore efficiency**: Consider adding negative-growth efficiency factor
- **Forget inactive factors**: Inactive factors are excluded from projections
- **Mix timeframes**: Keep base year consistent across factors
- **Ignore data validation**: Check that percentages and rates are reasonable

---

## Troubleshooting

### Problem: Chart doesn't show factor breakdown
**Solution**:
1. Check view mode is set to "breakdown"
2. Verify scenario has active factors (check scenario dropdown shows count)
3. Open browser console (F12) and check for errors

### Problem: Factors don't sum to 100%
**Solution**:
1. Navigate to scenario assignment page
2. Check progress bars
3. Adjust percentages until bars are green (95-100%)

### Problem: Growth looks wrong
**Solution**:
1. Verify growth rate is correct (e.g., 0.05 = 5%, not 5)
2. Check growth type matches intent (exponential vs linear)
3. For S-curve, check midpoint year is reasonable

### Problem: "Scenario has no factors" warning
**Solution**:
1. The selected scenario doesn't have any configured factors
2. Go to Manage Factors → Create factors for this scenario
3. Or use Scenario Assignment page for bulk setup
4. Or switch to a factor-based scenario

---

## API Integration (Advanced)

### Calculate Factor-Based Projection

**Endpoint**: `POST /api/demand-projection/calculate/`

### Export Factor Breakdown (Planned)

Will add CSV/Excel export in future enhancement.

---

## Example Factor Configurations by Industry

### Energy-Intensive Industries
- **Aluminum Smelting**: 30% operational, 1% linear
- **Steel Production**: 25% operational, 1.5% linear
- **Chemical Plants**: 15% operational, 2% exponential

### Transportation Electrification
- **Light-Duty EVs**: 10% operational, 8% S-curve (midpoint 2032)
- **Heavy-Duty EVs**: 5% operational, 5% S-curve (midpoint 2038)
- **Public Transit**: 3% operational, 4% linear

### Building Electrification
- **Residential Heat Pumps**: 8% underlying, 6% S-curve
- **Commercial HVAC**: 12% operational, 4% S-curve
- **Cooking Electrification**: 2% underlying, 3% linear

### Emerging Technologies
- **Green Hydrogen**: 2% operational, 12% exponential (high uncertainty)
- **Carbon Capture**: 1% operational, 8% S-curve (post-2030)
- **Desalination**: 1% operational, 4% linear

---
