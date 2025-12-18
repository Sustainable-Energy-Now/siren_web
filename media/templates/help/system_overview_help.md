# System Overview

## Introduction

Siren Web is a web-based Django application inspired on Siren, an open-source Python application, designed for modeling renewable energy systems within the South West Interconnected System (SWIS). Siren Web provides comprehensive tools for energy planning through three main modules: Powermap, Powermatch, and Powerplot.

## Core Modules
- **[Powermap](/help/powermap/)**: Interactive mapping tool for modeling renewable energy generation and infrastructure
- **[Powermatch](/help/powermatch/)**: Power supply and demand matching algorithms and analysis
- **[Powerplot](/help/powerplot/)**: Visualization and plotting tools for modeling results

## System Requirements
- Web browser with JavaScript enabled
- Internet connection
- Valid user credentials (membership-based access)

## Access Levels
Siren Web implements a membership-based access system with four tiers:
- **Modelling Team**: Full access to all features and data
- **Active Member**: Full read access to all features
- **Lapsed Member**: Limited access to system functionality
- **Subscriber/Non-member**: Basic access with restricted features

Access is automatically granted based on membership status when accessing the system through the appropriate authentication flow.

## Initial Setup
1. **Login** to the Siren Web system
2. **Review** user access level and available modules
3. **Select** appropriate demand year and scenario settings
4. **Navigate** to desired module (Powermap, Powermatch, or Powerplot)

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
The settings panel at the top of the page displays the current modeling parameters:
```
Demand Year: [Year]
Scenario: [Scenario Name]
Config: [Configuration File]
```

These settings persist throughout a session and affect how the system processes requests across all modules.

## System Navigation

### Interactive System Diagram

The main feature of Siren Web is an interactive diagram that illustrates the system architecture. This diagram contains clickable areas (hotspots) that provide detailed information about each component.

### Available Components
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

### Using the Interactive Diagram
1. **Click on any component** in the diagram to view its details
2. A **modal window** will appear displaying:
   - Component name and description
   - Database structure (for data tables)
   - Sample data (first 5 rows)
   - Column definitions
3. **Close the modal** by clicking the X button or clicking outside the modal area

### Component Information Display
When you click on a component, you'll see:
- **Model Name**: The technical name of the component
- **Description**: Detailed explanation of the component's purpose and function
- **Data Structure**:
  - Column names and their purposes
  - Sample data showing the format and typical values
  - Up to 5 example rows from the database

## Related Modules

- [Powermap Module](/help/powermap/) - Interactive facility mapping
- [Powermatch Module](/help/powermatch/) - Energy modeling and analysis
- [Powerplot Module](/help/powerplot/) - Data visualization
- [Terminal Management](/help/terminal/) - Facility management
- [AEMO SCADA Data](/help/aemo_scada/) - Data fetcher documentation
