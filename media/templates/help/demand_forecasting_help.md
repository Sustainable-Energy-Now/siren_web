# Demand Forecasting - Guide

## Overview

The **Demand Forecasting** menu covers everything to do with building,
adjusting, comparing and summarising a scenario's electricity demand
trace (`Demand` + its half-hourly `DemandMatrix` trace) before it's used
elsewhere in Powermatch. It has four groups of tools:

1. **ESOO-based demand** — build a demand trace from AEMO's published WEM
   ESOO forecasts, and manage bias corrections against those forecasts.
2. **EV load layering** — add an EV-uptake scenario's charging load on top
   of a base demand trace, or compare EV uptake scenarios side by side.
3. **Factor-based demand projection** — build a demand trace from
   independent growth factors (EV adoption, industrial electrification,
   etc.) instead of ESOO anchors.
4. **Scenario summary** — inspect and compare any built demand trace's
   statistics, regardless of which of the above built it.

**Total Demand = Sum of All Factor Demands** (factor-based path) *or* the
reconciled trace fitted to the ESOO peak/minimum/energy anchors (ESOO-based
path). The two are alternative ways of producing a `Demand`; EV Load
Scenario then layers on top of whichever one you used as the base.

---

## Menu Map

| Menu item | URL | Purpose |
|-----------|-----|---------|
| **Forecast Scenario Summary** | `/scenario-summary/` | Read-only stats/charts for any built Demand, optionally compared against a second one |
| **Create ESOO Demand Scenario** | `/esoo-scenario/` | Build a Demand trace from a WEM ESOO vintage/scenario/POE/year |
| **ESOO Forecast Adjustments** | `/esoo-adjustments/` | Manage bias corrections applied to ESOO anchor figures |
| **EV Load Scenario** | `/ev-scenario/` | Layer an EV uptake scenario's charging load onto a base Demand |
| **EV Sensitivity** | `/ev-scenario/compare/` | Compare Low/Medium/High EV uptake scenarios side by side (no save) |
| **List/Add Demand Factor Types** | `/demand-factors/types/` | Manage factor categories used by factor-based projection |
| **List/Add Demand Factors** | `/demand-factors/` | Manage individual growth factors |
| **Demand Projection** | `/demand-projection/` | Generate and visualise a factor-based projection |
| **Demand Forecasting Help / Help Edit** | `/help/demand_forecasting/` | This page / its markdown source |

---

## Forecast Scenario Summary

**Page**: `/scenario-summary/`

Read-only. Pick a Demand and a year (and optionally a second Demand to
compare against) and see:

- Annual energy, peak and minimum demand (with the date/time they occur)
- Load factor
- Monthly energy (bar chart)
- Mean daily profile and peak-day profile (line charts)
- Load-duration curve
- **Provenance**: a plain-English description of how the Demand was built
  (e.g. which ESOO vintage/scenario/POE, or which factor-based scenario, or
  which EV scenario it's layered on top of)

Nothing on this page writes to the database — it's purely for checking a
scenario before (or after) using it elsewhere, and for comparing two
scenarios (e.g. a base ESOO demand vs. the same demand with an EV layer
added).

---

## Create ESOO Demand Scenario

**Page**: `/esoo-scenario/`

Builds a half-hourly `Demand` trace directly from AEMO's published WEM ESOO
figures, rather than from user-defined growth factors.

**Steps**:
1. Select a **WEM ESOO vintage** (the ESOO publication year).
2. Select a **demand growth scenario** (Low / Expected / High).
3. Select a **POE level** (probability of exceedance).
4. Select a **forecast year** (the capacity year to build, e.g. 2034 means
   the 2034-35 capacity year).
5. Optionally tick **Apply ESOO bias correction** — see below.
6. Click through to build.

**What happens behind the scenes**:
- The three published anchors for that exact (vintage, scenario, POE,
  forecast year) combination are pulled from `EsooFigure`: **peak** demand
  (summer), **minimum** demand, and **annual energy**.
- A load-duration curve is fitted to those anchors against a real
  reference-year shape built from actual `FacilityScada` data (the most
  recent complete year available).
- A full half-hourly chronological trace is synthesised from that curve and
  reconciled back against the original peak/minimum/energy targets.
- The result is saved as a `Demand` record (created or updated) with a
  `DemandScenarios` "Demand Forecast" entry, ready to use as a base for EV
  layering or in Forecast Scenario Summary.

**Apply ESOO bias correction**: when ticked, each anchor is first adjusted
by its own metric's historical bias, as recorded on the **ESOO Forecast
Adjustments** page (e.g. if WEM ESOO peak-demand forecasts have
systematically run high for this scenario/POE, the peak anchor is nudged
down before fitting).

**Supply-adequacy figures**: the page also shows the selected vintage's
Reserve Capacity Target and capacity-outlook figures as read-only reference
data — these are shown for context only and never feed into the demand
trace that's built.

**If you get a "missing anchor" error**: that exact vintage/scenario/POE/
year combination wasn't published by AEMO (ESOO coverage is genuinely
uneven across vintages and years) — try a different vintage, scenario, POE
or year. The error message names exactly which anchor is missing and, when
relevant, which other ESOO vintages do cover that year.

---

## ESOO Forecast Adjustments

**Page**: `/esoo-adjustments/`

Manage bias corrections applied to individual ESOO anchor figures (used by
the "Apply ESOO bias correction" option above).

- **List/filter**: by vintage, metric, category, verdict and source
  (automatic vs. manual), and whether the adjustment has actually been
  applied to a built Demand.
- **Create**: manually enter an adjustment against a specific `EsooFigure`
  — the only route for a correction category that isn't computed
  automatically yet.
- **Edit**: change an adjustment's value/notes. Saving always sets its
  source to **manual**, so a later automatic recompute won't silently
  overwrite a person's override.
- **Recompute**: re-runs the automatic bias calculation (comparing past
  ESOO forecasts against actual outcomes) for a row whose source is still
  **automatic**, picking up newly-arrived actuals. Disabled for manual rows
  — delete and let it be recomputed instead if that's what you want.
- **Delete**: remove an adjustment.

---

## EV Load Scenario

**Page**: `/ev-scenario/`

Adds an EV-uptake scenario's charging load on top of an existing base
Demand trace (built either from ESOO or from factor-based projection), and
saves the combined result as a new **derived** Demand. The base Demand is
never modified — building an EV scenario just creates a second Demand
linked back to it, so you can always compare "with EV load" vs. "without"
on the Forecast Scenario Summary page.

**Steps**:
1. Select a **base scenario** — any half-hourly, non-derived Demand.
2. Select an **EV uptake scenario** (Low / Medium / High, from AEMO's 2025
   IASR WEM EV trajectory).
3. Select a **charging mode** (unmanaged, or managed where real
   time-of-use charging-shape data exists for this region).
4. Select the **forecast year**.
5. Optionally tick **net of ESOO's EV**.

**Net of ESOO's EV**: an ESOO demand forecast already includes some EV
charging load baked in, so simply adding a scenario's full EV load on top
would double-count it. Ticking this first estimates and removes the EV load
already embedded in the base ESOO Demand, then adds the selected scenario's
EV load — i.e. `base − embedded EV + scenario EV`. You can override the
estimated embedded EV energy (in GWh) by hand if you have a better figure.
This option only makes sense when the base Demand was built from ESOO; it's
not needed for a factor-based base.

**Result**: a new Demand named `"<base name> + EV <scenario> <year>"` (or
`"... + EV net <scenario> <year>"`), viewable on Forecast Scenario Summary.

---

## EV Sensitivity

**Page**: `/ev-scenario/compare/`

A read-only comparison view — it never creates or saves a Demand. Select a
base scenario, forecast year and charging mode, and see the **Low, Medium
and High** EV uptake scenarios side by side: a peak-day overlay chart
(base demand vs. base + each EV scenario) plus summary stats for each. Use
this to understand the range of outcomes before committing to build one
specific EV Load Scenario. Supports the same **net of ESOO's EV** option as
EV Load Scenario, with the same meaning.

---

## Factor-Based Demand Projection

This is the alternative way of building a demand trace: instead of fitting
to ESOO's published peak/minimum/energy anchors, you break down demand into
independent growth factors (e.g. EV Adoption, Industrial Electrification,
Hydrogen Production) that each grow on their own formula.

This system allows you to break down electricity demand into multiple independent growth factors (e.g., EV Adoption, Industrial Electrification, Hydrogen Production). Each factor:
- Starts with a base percentage of total demand
- Grows independently with its own formula
- Can use time-varying growth rates
- Supports multiple growth types (linear, exponential, S-curve, compound)

### 1. Create Your First Scenario

Navigate to: **List Demand Factors → Add Demand Factor** (and, if needed,
**List/Add Demand Factor Types** first to define a category).

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

## Factor-Based Navigation Quick Reference

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

### Problem: "Missing required anchor(s)" on Create ESOO Demand Scenario
**Solution**:
1. That vintage/scenario/POE/forecast-year combination wasn't published by AEMO
2. Try a different vintage, scenario, POE level or forecast year — the error names
   which other vintages (if any) cover that year
3. If an "underlying" energy figure exists but no "operational" one, the demand-basis
   crosswalk may not have been run yet for that vintage

### Problem: EV Load Scenario / EV Sensitivity says the base Demand has no usable trace
**Solution**:
1. The selected base Demand must be half-hourly (30-minute interval) — build or
   select one from Create ESOO Demand Scenario or Demand Projection first
2. If it was built before the ESOO trace was moved onto the AWST clock, rebuild it
   from Create ESOO Demand Scenario

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
