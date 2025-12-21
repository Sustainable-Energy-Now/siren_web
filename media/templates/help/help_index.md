# Siren Web User Manual

## Welcome

Welcome to Siren Web - your comprehensive renewable energy modeling platform for the South West Interconnected System (SWIS).

## Quick Navigation

### Core Modules

#### [Powermap Module](/help/powermap/)
Visualize and manage facilities on an interactive map. Create, edit, and analyze renewable energy facilities including wind, solar, and battery storage systems.

**Key Features:**
- Interactive facility mapping
- Facility creation and editing
- Power curve management
- Spatial analysis tools

#### [Powermatch Module](/help/powermatch/)
Perform sophisticated energy modeling and scenario analysis. Model different renewable energy configurations and analyze their performance.

**Key Features:**
- Scenario creation and management
- Merit order configuration
- Demand forecasting and projection
- Variation analysis
- Progress tracking

#### [Powerplot Module](/help/powerplot/)
Visualize energy data through comprehensive charts and graphs. Analyze facility performance, correlations, and temporal patterns.

**Key Features:**
- Multiple chart types (line, bar, scatter, heatmap)
- Time-based aggregation
- Correlation analysis
- Data export functionality
- Custom visualizations

### Supporting Documentation

#### [Terminal Management](/help/terminal/)
Learn about facilities management, including creating, editing, and configuring renewable energy facilities and their technical specifications.

#### [AEMO SCADA Data Fetcher](/help/aemo_scada/)
Instructions for fetching and managing SCADA data from the Australian Energy Market Operator (AEMO) for analysis and modeling.

#### [System Overview](/help/system_overview/)
General system navigation, configuration, and best practices for using Siren Web effectively.

## Getting Started

1. **Login** to your Siren Web account
2. **Select or create a scenario** to work with
3. **Choose a module** from the main menu based on your task:
   - Use **Powermap** for facility visualization and management
   - Use **Powermatch** for energy modeling and scenario analysis
   - Use **Powerplot** for data visualization and analysis
4. **Access module-specific help** from each module's menu

## System Requirements

- Modern web browser (Chrome, Firefox, Edge, Safari)
- Active internet connection
- Login credentials provided by your administrator

# Help System

## Features

### Navigation
- Each module help has a "Back to Main Help" link
- Main help index links to all modules
- Breadcrumb-style navigation

### Responsive Design
- Works on desktop and mobile
- Sidebar navigation
- Keyboard shortcuts (Arrow keys, Page Up/Down)

### Pagination
- Sections broken into pages
- Table of contents sidebar
- Page indicators
- Previous/Next buttons

### Accessing Help
1. **Main Help Index**: Go to `/help/`
   - Shows overview of all modules
   - Links to each module's help

2. **Module-Specific Help**: Go to `/help/<module>/`
   - Example: `/help/powermap/`
   - Shows only that module's documentation
   - Includes "Back to Main Help" link

### Editing Help

## Mardown Files
- Modular markdown files organized by module:
  - `help_index.md` - Main help index with links to all modules
  - `system_overview_help.md` - System overview and navigation
  - `powermap_help.md` - Powermap module documentation
  - `powermatch_help.md` - Powermatch module documentation
  - `powerplot_help.md` - Powerplot module documentation
  - `terminal_help.md` - Terminal/Facilities management
  - `aemo_scada_help.md` - AEMO SCADA data fetcher
- Module-specific HTML files auto-generated on demand
- Each module can link to its specific help

1. **Edit Markdown**: Go to `/help/<module>/edit/`
   - Edit the markdown content
   - Preview changes
   - Save changes

2. **Generate HTML**: After editing
   - Click "Save & Generate" to automatically generate HTML
   - Or manually visit `/help/<module>/generate/`

### Auto-Generation
The system automatically generates HTML from markdown when:
- You visit a help page and the HTML doesn't exist
- The markdown file exists for that module

## Release Notes

For information about the latest features and updates, visit the [Release Notes](/release-notes/) page.

---

*Last Updated: December 2024*
