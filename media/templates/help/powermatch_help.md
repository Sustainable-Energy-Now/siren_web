# Powermatch Module

## Overview

PowerMatch matches and balances Renewable Energy resources to the load on the South West
Interconnected System (SWIS). It takes generation capacity from Powermap's Facilities
scenarios and a demand trace built via the **Demand Forecasting** menu, then quantifies and
costs dispatchable generation, storage and CO2-e emissions for that combination.

**Access**: Merit Order, Baseline Scenario and Create Variants all require the logged-in
user to belong to the **modellers** group — anyone else sees an "Access not allowed" message
in place of the page.

## Menu Map

| Menu item | URL | Purpose |
|-----------|-----|---------|
| **Powermatch Home** | `/powermatchui/` | Landing page describing the workflow (no configuration here) |
| **Data Take-up → Data Pipelines** | `/data-pipelines/` | Run/monitor the background ESOO/EV/SCADA/GenCost ingest commands |
| **Data Take-up → GenCost Data** | `/gencost/upload/` | Upload, extract and apply CSIRO GenCost technology-cost vintages |
| **Demand Forecasting** | `/help/demand_forecasting/` | Build/manage the Demand traces this module runs against — see its own help page |
| **Set Merit Order** | `/merit_order/` | Order technologies for dispatch, and set carbon price / discount rate |
| **Baseline Scenario** | `/baseline_scenario/` | Pick a Facilities scenario + Demand forecast, adjust technology capacities, run PowerMatch |
| **Create Variants** | `/variation/` | Run PowerMatch repeatedly while stepping one technology's parameter |
| **Powermatch Help / Help Edit** | `/help/powermatch/` | This page / its markdown source |

**Workflow**: build or pick a Demand forecast (Demand Forecasting menu) → set the Merit
Order and economic settings for a Facilities scenario (Set Merit Order) → adjust technology
capacities and run PowerMatch (Baseline Scenario) → optionally explore sensitivity by
stepping a technology's parameters across several runs (Create Variants).

---

## Powermatch Home

`/powermatchui/` is a static landing page — it just describes the module's workflow in
prose. It doesn't select or store anything; there is no scenario/demand-year picker here
(that used to exist and has been removed — see Merit Order and Baseline Scenario below for
where each selection is actually made now).

---

## Data Take-up

Two tools for keeping the data PowerMatch depends on up to date.

### Data Pipelines (`/data-pipelines/`)

A dashboard for the background commands that ingest external data (WEM ESOO, EV uptake,
AEMO SCADA, CSIRO GenCost, etc.):

- **Freshness** cards at the top show one card per tracked dataset, each with a coloured
  dot indicating how stale it is.
- **Run a job**: each runnable command is listed with its parameters (choice fields, flags,
  free text) and a **Run** button. Only staff users can actually submit a run — everyone
  else sees the dashboard read-only. Only one run of a given command can be active at a
  time; submitting again while one is running is refused.
- **Recent runs**: the last 25 runs, each with status, duration and a "log" link
  (`pipeline_run_detail`) showing the command's full captured output.
- Runs execute in a background thread server-side; the dashboard page itself doesn't need
  to stay open, and `pipeline_run_status` is polled by the run-detail page for live status.

### GenCost Data (`/gencost/upload/`)

Manages CSIRO GenCost technology cost vintages, which feed the `TechnologyYears` cost data
used throughout PowerMatch (capex, FOM, VOM, lifetime). The primary way a new vintage
arrives is the automatic fetch command on the Data Pipelines dashboard; this page is the
manual fallback plus the review/apply workflow:

1. **Upload & register** (`/gencost/upload/`): upload a GenCost source document for an
   edition (e.g. "2024-25") and document type; it's archived to disk and registered as a
   `SourceDocument` against a `GencostVintage`.
2. **Vintage detail** (`/gencost/<id>/`): shows the vintage's registered documents, the
   number of extracted cost figures, and one row per cost case (e.g. "Current Policies",
   "Global NZE 2050") with how many technology labels in that case are still unmapped.
   - **Extract**: parses the uploaded document(s) into `GencostCostFigure` rows (runs the
     `extract_gencost_figures` pipeline command in the background).
   - **Apply** (per cost case): pushes that case's figures onto the live `TechnologyYears`
     table (`apply_gencost_cost_case`), with an optional capex premium percentage. Disabled
     until every raw technology label in that case has been mapped or explicitly ignored.
   - **Recent runs**: the extract/apply command runs for this vintage, same log-link
     pattern as Data Pipelines.
3. **Technology Mapping Review** (`/gencost/mapping/`): GenCost's raw technology labels
   don't match this project's `Technologies` names one-to-one, so each raw label is mapped
   by hand to a `Technologies` row, or marked "ignore" (not applicable to this project).
   Pending (unmapped, not ignored) rows are listed first since they're what blocks Apply.

---

## Demand Forecasting

Building and managing the `Demand` records (half-hourly demand traces) that Baseline
Scenario, Merit Order (for cost-year selection) and Create Variants all read from is a
separate menu with its own help page — see **Demand Forecasting → Demand Forecasting
Help** (`/help/demand_forecasting/`) for ESOO-based demand building, EV load layering,
factor-based projection and scenario summary/comparison.

Every page below that mentions "select a Demand Forecast" is choosing one of those `Demand`
records — you need at least one built before you can run a baseline.

---

## Set Merit Order (`/merit_order/`)

### Purpose
The merit order determines dispatch priority for the currently-selected Facilities
scenario, and this is also where the scenario's carbon price and discount rate are set.

### Prerequisites
A Facilities scenario must already be selected — this page reads it from the session,
which is set by choosing one on the **Baseline Scenario** page first. If none is set, the
page tells you to "Set a scenario and config first."

### Steps
1. **Select a Demand Forecast**: technologies, carbon price and discount rate are only
   shown once one is selected here, because Auto Sort needs a cost year (the Demand's
   forecast year) to compare fossil technologies' running costs.
2. **Carbon Price ($/tCO2e)** and **Discount Rate** (a fraction, e.g. `0.075` for 7.5%):
   entered here and saved with **Save Merit Order**. These are the *only* place either
   value is set for a scenario — Baseline Scenario just displays them read-only with a
   link back here. A discount rate outside `[0, 1)` is rejected (not saved) as almost
   certainly a units mistake (e.g. typing a percentage).
   - If nothing has ever been saved for this scenario, both fields fall back to the global
     Powermatch setting.
3. **Merit Order** (left list) / **Excluded Resources** (right list): drag technologies
   between the two lists and reorder within a list. Only technologies in the Merit Order
   list are dispatched; each item is colour-coded by its emissions intensity.
4. **Save Merit Order**: persists both lists' order (and whatever's currently in the
   Carbon Price / Discount Rate boxes) and reloads the page.
5. **Auto Sort**: reorders the Merit Order list only (Excluded Resources is left alone) —
   non-fossil technologies first (ascending emissions), then fossil technologies (Coal,
   Gas, Distillate) by ascending running cost (VOM + fuel cost) plus carbon cost
   (emissions × the carbon price currently in the box), at the selected Demand forecast's
   cost year. This also saves whatever's currently in the Carbon Price box, so the ranking
   shown and the price a later baseline run uses always agree.

---

## Baseline Scenario (`/baseline_scenario/`)

### Purpose
Model a dispatch engine matching demand with available generation and storage capacity for a future year.
Pick a Facilities scenario that provides the list of commissioned facilities and a Demand forecast scenario that provides the demand trace and the reference year that provided the weather year and demand shape used to create the demand trace.  The facilities' generation comes from the Supply Factors table previously generated based on the weather for the reference year. The user can adjust technology capacities by setting multipliers before running PowerMatch — either synchronously or with live progress tracking.

### Steps
1. **Facilities scenario**: select from the dropdown. This sets the session-wide scenario
   used by Merit Order and Create Variants too. Nothing else on the page shows until one is
   picked.
2. **Demand Forecast**: select the `Demand` record to run against (built via the Demand
   Forecasting menu). Unlike the Facilities scenario, this selection isn't stored in the
   session — it travels with each request as a form field, so Baseline Scenario, Create
   Variants and Merit Order can each have their own selection open at once.
3. **Carbon Price / Discount Rate**: shown read-only here, with a link to the Merit Order
   page where they're actually set.
4. **Technology Capacity table**: one row per technology in the scenario — read-only
   **Capacity** (from Powermap), an editable **Multiplier**, and a live-calculated
   **Effective Capacity** (Capacity × Multiplier). **Save Runtime Parameters** persists
   changed multipliers.
5. **Run PowerMatch Analysis**:
   - **Level of Detail**: **Summary** (a results table you can review in the browser) or
     **Detailed** (skips the browser table and downloads an `.xlsx` workbook — Summary,
     Metadata and Hourly_Data sheets — directly).
   - **Save Baseline**: when checked, results are written back as this scenario's stored
     baseline (used by Create Variants' "baseline must exist" check). If a baseline already
     exists, checking this and running asks you to confirm overwriting it first.
   - **Run Standard Analysis**: submits and waits — no progress bar; the page replaces
     itself with the results table (or triggers the .xlsx download) when PowerMatch
     finishes.
   - **Run with Progress Tracking**: same run, but via a background thread with a live
     Server-Sent-Events progress panel (see below), then redirects to the results page (or
     triggers the .xlsx download) on completion.
   - **Cancel**: stops a Progress-Tracking run in flight.

Running with no Demand Forecast selected is refused with an explicit error — a Facilities
scenario no longer carries an implicit demand trace of its own; a Demand must be chosen.

### How the dispatch algorithm works

PowerMatch dispatches every interval of the selected Demand forecast independently
(half-hourly or hourly, matching that Demand's own resolution), strictly in the order set
on the **Set Merit Order** page. A technology moved to Excluded Resources takes no part in
the run at all. Each interval goes through the same four passes:

1. **Storage self-discharge**: any battery/pumped-hydro storage first loses a small
   parasitic charge (its `parasitic_loss` daily rate, scaled to the interval length) before
   anything else happens.
2. **Must-run minimum generation**: any dispatchable generator configured with a
   `capacity_min` above zero (e.g. a coal plant that can't be switched off below some
   floor) is forced to produce that floor's worth of energy regardless of demand, before
   the merit-order pass proper. Whatever of that floor isn't needed to meet load becomes
   "minimum-generation surplus".
3. **Merit-order pass**: remaining demand for the interval is then offered to each
   technology in turn, top of the Merit Order list first:
   - **Non-dispatchable renewables** (solar, wind, etc.) generate whatever their trace
     says for that interval (scaled by the technology's Multiplier); as much as is needed
     to cover the demand still remaining is used, and any excess becomes "renewable
     surplus".
   - **Dispatchable generators** generate up to `capacity_max`, but never below
     `capacity_min` even if that's more than what's left to meet (again counted as
     surplus) — a generator that already supplied its must-run floor in pass 2 here only
     supplies the *additional* capacity above that floor.
   - **Storage** discharges to cover remaining demand, limited by its discharge rate,
     energy actually in store, discharge efficiency, and (if configured) minimum run-time
     and warm-up penalties.
   - Remaining demand shrinks after each technology's contribution; whatever demand is
     still unmet after the last technology in the list is that interval's **shortfall**.
4. **Storage charging**: any surplus left over from passes 2–3 (renewable + minimum-
   generation surplus) is offered to storage to charge, limited by each storage's spare
   capacity, charge rate and charge efficiency. Whatever storage can't absorb is
   **curtailment** (spilled, unused generation).

Once every interval has been dispatched this way, PowerMatch rolls the interval-by-interval
generation up into the per-technology and system-wide figures shown in the results:
- **Annual cost** = annualised capital cost (capital recovery factor from the Discount
  Rate and the technology's lifetime) + fixed O&M + variable O&M + fuel cost — or, for a
  technology defined by a flat reference LCOE instead of cost components, that LCOE times
  its generation.
- **LCOG** (cost per MWh generated) and **LCOE** (cost per MWh that actually met load) —
  LCOE allocates a renewable technology's share of storage's contribution to it, so
  storage's own cost doesn't show up as generation with no cost attached.
- **Emissions** = generation × the technology's emissions factor; **emissions cost** =
  emissions × the Carbon Price set on the Merit Order page; **LCOE with CO2** adds that
  cost into LCOE.
- **System-wide**: total load met %, curtailment %, renewable % (of both generation and of
  load met, crediting storage's renewable share by what fraction of the surplus it was
  charged from was renewable rather than must-run minimum generation), and a system-wide
  LCOE (total annual cost ÷ total load actually met).

### Progress Tracking (Run with Progress Tracking)
- **Connection status badge**: Connecting (orange) → Connected (green) while updates are
  flowing → Disconnected (grey) when closed → Error (red, pulsing) on a stream error.
- **Progress bar / status message**: percentage complete and the current processing step.
- **Elapsed / Remaining time**: live timing estimates.
- Safe to switch browser tabs — the analysis keeps running server-side regardless; the
  browser just reconnects to the SSE stream.

### Results & Downloads
- **Summary** results render as a "Modelling Results" page (`display_table.html`), described
  in full below.
- **Detailed** results are never shown in the browser — they download directly as an
  `.xlsx` workbook (`<scenario>-baseline detailed results.xlsx`).
- After a Progress-Tracking run, `download_results` lets you re-download a completed run's
  output (Summary as `.xlsx`, or the Detailed workbook) for as long as that session's result
  is still held in memory.

### The Summary results page ("Modelling Results")

A Summary-level run (Run Standard Analysis / Run with Progress Tracking, or a Create
Variants submission — variants always run at Summary level) lands on this page. It's built
from the same per-technology/system totals the dispatch algorithm above produces
(`metadata['system_totals']` etc.), grouped into sections:

- **Analysis Details**: what the run was actually dispatched against — the selected Demand
  Forecast's name and forecast year, the Facilities scenario, and the reference year (the
  real weather/SCADA year the Demand's shape was built from). If these results were
  reloaded from a previously *saved* baseline rather than a fresh run, a banner says so,
  because a saved baseline doesn't record which Demand Forecast it was run against — the
  details shown reflect your current page selection, not necessarily what the saved run
  actually used.
- **Load vs Supply**: Total Load (GWh), Load Met (%), Renewable Energy (%, of generation),
  Storage Contribution (%, of load met), Curtailment (%) and System LCOE ($/MWh — total
  annual cost ÷ load actually met). A warning banner appears if Load Met is below 95%
  ("consider adding more generation capacity"), and an info banner if Curtailment is above
  10%, which also says whether storage absorbed most of the surplus and, if most of the
  spilled surplus came from must-run minimum generation rather than renewables, suggests
  reviewing minimum-generation settings instead of just adding storage.
- **Surplus & Storage**: the breakdown behind the curtailment figure — total Surplus
  (GWh), how much of it came From Renewables vs. From Minimum Generation, how much was
  Charged to Storage (and what % of surplus that represents), and how much was ultimately
  Curtailed. Not shown for a baseline saved before this breakdown was recorded (an older
  saved baseline just says so instead).
- **Economic View**: Total Annual Cost, Total Capital Cost and Lifetime Cost (all
  annualised/rolled up across every technology — see "How the dispatch algorithm works"
  above for how each technology's own annual cost is computed), plus the Carbon Price and
  Discount Rate the run actually used (as saved on the Merit Order page at the time it ran).
- **Environmental View**: Annual Emissions (ktCO2e/year), Emissions Cost ($M/year, at the
  run's carbon price), Lifetime Emissions (MtCO2e, projected over the longest-lived
  technology's lifetime), and Total Land Use (km², for technologies with an area factor
  configured).
- **Technology Breakdown**: one row per technology — Capacity, Generation, Capacity
  Factor, LCOE, Emissions and Area — the same figures as Load vs Supply/Economic/
  Environmental but broken out per technology instead of summed.
- **Detailed Technology Data**: the full per-technology table underneath, with every field
  PowerMatch calculates (Capacity, Generation, To Meet Load, CF, Cost, LCOG Cost, LCOE Cost,
  Emissions, Emissions Cost, LCOE with CO2 Cost, Max Generation, Max Balance, Capital Cost,
  Lifetime Cost, Lifetime Emissions, Lifetime Emissions Cost, Area km², Reference LCOE,
  Reference CF) — this is the same data the Detailed level-of-detail's `.xlsx` download
  contains, shown in the browser instead.

---

## Create Variants (`/variation/`)

### Purpose
Run PowerMatch repeatedly while stepping one technology's parameter through several
values, to explore sensitivity of different technologies around the scenario's baseline.

### Prerequisites
- A Facilities scenario must be selected (via Baseline Scenario) and already have a saved
  baseline ("Baseline the scenario first" otherwise).
- A Demand Forecast must be selected on this page (its own selector, independent of
  Baseline Scenario's) before technology costs and the variation form appear.

### Steps
1. **Select Variation**: choose an existing variant (its saved parameters auto-populate
   the form below) or **Create a new variant**.
2. **Number of Stages**: how many PowerMatch runs to perform.
3. **Pick one technology**: expand its accordion row and set:
   - **Dimension**: which parameter to step — Multiplier, Capex, FOM, VOM or Lifetime.
   - **Step**: the increment applied each stage.
   Only one technology can be configured at a time — selecting a dimension/step on one
   disables the others until it's cleared, since a variation always varies a single
   technology's single dimension.
4. **Submit**: PowerMatch runs once per stage, stepping the chosen technology's chosen
   dimension by the step value each time, starting from that dimension's current value.
   Results are written to the `Analysis` table (tagged with the auto-generated variant
   name, e.g. `<tech signature>.mul0.5.5`) for later plotting/comparison, and re-running an
   existing variant clears and replaces its previous Analysis rows first.

Variant names and descriptions are generated automatically from the technology, dimension
and step values, and must be unique per scenario — the same combination can't exist twice.

---
