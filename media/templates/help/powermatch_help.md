# Powermatch Module

## Overview

PowerMatch is a web-based interface for matching and balancing Renewable Energy resources to the load on the South West Interconnected System (SWIS). The application quantifies and costs dispatchable energy generation, storage, and CO2-e emissions by taking input from Powermap load and generation data.

## Key Features
- **Renewable Energy Matching**: Balance renewable resources with system load
- **Cost Analysis**: Calculate levelised cost of energy (LCOE)
- **Emissions Tracking**: Quantify CO2-e emissions
- **Scenario Analysis**: Create and compare different energy scenarios
- **Real-time Progress**: Monitor analysis progress with live updates
## Navigation Overview
The PowerMatch interface consists of five main sections:
1. **Home**: Scenario and demand year selection
2. **Load Projection**: Project Load Growth into the Future
3. **Merit Order**: Configure technology dispatch priority
4. **Baseline Scenario**: Set parameters and run analysis
5. **Variations**: Create and analyze scenario variants
## Home Page - Scenario Selection
### Purpose
The home page allows you to select the demand year and scenario that will be used throughout a PowerMatch session. This selection is a prerequisite for all other functions.
### Steps to Configure
1. **Select Demand Year**: Choose from available demand years in the dropdown
2. **Select Scenario**: Choose the scenario you want to analyze
3. **Apply Settings**: Click the "Apply Settings" button to confirm selection
### Important Notes
- Both weather year, demand year and scenario must be specified before proceeding
- The selected scenario becomes the basis for all subsequent analysis
- Data availability depends on what has been imported from Powermap
## Merit Order Configuration
### Purpose
The merit order determines the dispatch priority of different energy technologies. Technologies higher in the list are dispatched first when demand needs to be met.
### Interface Components
**Merit Order Panel (Left Side)**
- **Active Technologies**: Technologies that will be used in the analysis
- **Drag and Drop**: Reorder technologies by dragging items up or down
- **Color Coding**: Each technology has a color based on emissions characteristics
**Excluded Resources Panel (Right Side)**
- **Excluded Technologies**: Technologies not included in the current analysis
- **Move Between Lists**: Drag technologies between merit order and excluded lists
### How to Configure Merit Order
1. **Reorder Technologies**:
   - Click and drag technology items within the Merit Order list
   - Higher position = higher dispatch priority
   - Lower emissions technologies typically go higher
2. **Include/Exclude Technologies**:
   - Drag technologies between "Merit Order" and "Excluded Resources" lists
   - Only technologies in the Merit Order list will be used in analysis
3. **Save Configuration**:
   - Click "Save Merit Order" button to save the configuration
   - Page will reload to confirm changes
### Best Practices
- Place renewable technologies (solar, wind) at the top
- Order by emissions intensity (lowest first)
- Consider economic dispatch order for conventional technologies
## Baseline Scenario Management
### Purpose
The baseline scenario establishes the foundation for an analysis by setting technology capacities, carbon pricing, and discount rates.
### Configuration Parameters
**Economic Settings**
- **Carbon Price**: Set the carbon price ($/tonne CO2-e) for emissions costing
- **Discount Rate**: Set the discount rate (%) for economic calculations
**Technology Capacity Settings**
For each technology, you can configure:
- **Capacity**: Base capacity in MW or MWh (read-only, from Powermap data)
- **Multiplier**: Factor to scale the base capacity (editable)
- **Effective Capacity**: Calculated result (Capacity × Multiplier)
### Setting Up a Baseline
1. **Configure Economic Parameters**:
   - Enter carbon price in the designated field
   - Set appropriate discount rate
2. **Adjust Technology Multipliers**:
   - Click in multiplier fields to edit values
   - Use multipliers to scale technologies up or down from base capacity
   - Effective capacity updates automatically
3. **Save Parameters**:
   - Click "Save Runtime Parameters" to store a configuration
### Running Analysis
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
### Analysis Controls
- **Cancel**: Stop running analysis at any time
- **Progress Panel**: Shows real-time status and timing
- **Connection Status**: Monitors live data feed
## Variations and Analysis
### Purpose
Variations allow you to explore different scenarios by systematically changing technology parameters and comparing results.
### Creating Variations
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
### Understanding Variations
- **Iterative Analysis**: PowerMatch runs multiple times with different parameters
- **Systematic Changes**: One technology parameter changes by step value each iteration
- **Comparative Results**: Results stored for plotting and comparison
- **Unique Naming**: Each variation gets automatically generated unique name
### Best Practices
- Start with small step changes to understand sensitivity
- Focus on technologies with significant impact on outcomes
- Use variations to optimize for specific goals (emissions, cost, reliability)
## Progress Tracking
### Real-time Monitoring Features
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
### Managing Long-Running Analysis
- **Tab Switching**: Safe to switch browser tabs during analysis
- **Connection Recovery**: System attempts to reconnect automatically
- **Cancel Option**: Stop analysis at any time using Cancel button
- **Result Persistence**: Results saved even if connection is lost
---
