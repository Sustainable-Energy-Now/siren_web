# Modular Help System - Implementation Guide

### After
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
- Much faster navigation and loading

## File Structure

```
media/
  templates/
    help/
      help_index.md                  # Main help index
      system_overview_help.md        # System overview
      powermap_help.md               # Powermap module
      powermatch_help.md             # Powermatch module
      powerplot_help.md              # Powerplot module
      terminal_help.md               # Terminal management
      aemo_scada_help.md             # AEMO SCADA data
      siren_web_manual.md            # Original (kept for reference)
      demand_projection_guide.md     # Existing guide
  help/
    help_index.html                  # Generated main help
    powermap_help.html               # Generated module help
    powermatch_help.html             # Generated module help
    powerplot_help.html              # Generated module help
    terminal_help.html               # Generated module help
    aemo_scada_help.html             # Generated module help
    system_overview_help.html        # Generated overview
```

## URL Structure

### Main Help
- `/help/` - Main help index page

### Module-Specific Help
- `/help/powermap/` - Powermap module help
- `/help/powermatch/` - Powermatch module help
- `/help/powerplot/` - Powerplot module help
- `/help/terminal/` - Terminal management help
- `/help/aemo_scada/` - AEMO SCADA help
- `/help/system_overview/` - System overview help

### Editing Help
- `/help/edit/` - Edit main help markdown
- `/help/<module>/edit/` - Edit module-specific markdown
  - Example: `/help/powermap/edit/`

### Generating Help HTML
- `/generate-help/` - Generate main help HTML
- `/help/<module>/generate/` - Generate module-specific HTML
  - Example: `/help/powermap/generate/`

## How to Use

### Accessing Help
1. **Main Help Index**: Go to `/help/`
   - Shows overview of all modules
   - Links to each module's help

2. **Module-Specific Help**: Go to `/help/<module>/`
   - Example: `/help/powermap/`
   - Shows only that module's documentation
   - Includes "Back to Main Help" link

### Editing Help

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
- This provides a seamless experience

## Adding Help Links to Module Menus

To add a help link to a module's menu (e.g., in Powermap, Powermatch, Powerplot):

### Example for Powermap
In your Powermap template, add:
```html
<a href="{% url 'display_module_help' 'powermap' %}" target="_blank">
  Help
</a>
```

### Example for Powermatch
```html
<a href="{% url 'display_module_help' 'powermatch' %}" target="_blank">
  Help
</a>
```

### Example for Powerplot
```html
<a href="{% url 'display_module_help' 'powerplot' %}" target="_blank">
  Help
</a>
```

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

### Auto-Calculation
- Duration auto-calculated in help generator
- Links preserved between sections
- Cross-module references supported

## Maintenance

### Updating Help Content

1. **Edit Markdown File**:
   - Go to `/help/<module>/edit/`
   - Make your changes
   - Save

2. **Regenerate HTML**:
   - Click "Save & Generate"
   - Or visit `/help/<module>/generate/`

3. **Verify Changes**:
   - Visit `/help/<module>/`
   - Check that changes appear correctly

### Adding New Modules

To add a new module help file:

1. **Create Markdown File**:
   ```bash
   media/templates/help/<new_module>_help.md
   ```

2. **Add Module Name to Generator**:
   Edit `help_generator.py`, add to `module_titles`:
   ```python
   'new_module': 'New Module Name',
   ```

3. **Create Help Link**:
   ```html
   <a href="{% url 'display_module_help' 'new_module' %}">Help</a>
   ```

4. **Update Main Index**:
   Edit `help_index.md` to add link to new module

## Benefits

1. **Smaller File Sizes**: Each module help is much smaller and faster to load
2. **Better Organization**: Related content grouped by module
3. **Easier Maintenance**: Update only the module you're working on
4. **Module-Specific Access**: Link directly to relevant help from each module
5. **Preserved History**: Original `siren_web_manual.md` kept for reference
6. **Auto-Generation**: HTML generated automatically when needed
7. **Responsive**: Works well on all devices

## Technical Details

### Modified Files
1. `siren_web/views/help_generator.py` - Added module support
2. `siren_web/views/help_views.py` - Added module-specific views
3. `siren_web/urls.py` - Added module URL patterns

### New Files Created
- `media/templates/help/help_index.md`
- `media/templates/help/system_overview_help.md`
- `media/templates/help/powermap_help.md`
- `media/templates/help/powermatch_help.md`
- `media/templates/help/powerplot_help.md`
- `media/templates/help/terminal_help.md`
- `media/templates/help/aemo_scada_help.md`

### Original File
- `media/templates/help/siren_web_manual.md` - Preserved for reference

## Testing

To test the new help system:

1. **Test Main Help Index**:
   ```
   Visit: http://localhost:8000/help/
   Verify: Links to all modules work
   ```

2. **Test Module Help**:
   ```
   Visit: http://localhost:8000/help/powermap/
   Verify: Powermap help displays correctly
   Verify: "Back to Main Help" link works
   ```

3. **Test Editing**:
   ```
   Visit: http://localhost:8000/help/powermap/edit/
   Make a small change
   Save & Generate
   Verify: Changes appear in help
   ```

4. **Test All Modules**:
   - `/help/powermap/`
   - `/help/powermatch/`
   - `/help/powerplot/`
   - `/help/terminal/`
   - `/help/aemo_scada/`
   - `/help/system_overview/`

## Migration Notes

The original `siren_web_manual.md` file has been preserved. You can:
- Keep it as a backup
- Use it for reference
- Eventually archive or delete it once you confirm the modular system works well

## Support

If you encounter issues:
1. Check that markdown files exist in `media/templates/help/`
2. Verify URLs are correctly configured in `siren_web/urls.py`
3. Check Django logs for any errors
4. Try manually regenerating help: `/help/<module>/generate/`
