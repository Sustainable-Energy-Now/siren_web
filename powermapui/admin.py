from django.contrib import admin
from django.urls import path
from django.utils.html import format_html
from siren_web.models import GridLines, FacilityGridConnections, facilities

@admin.register(GridLines)
class GridLinesAdmin(admin.ModelAdmin):
    list_display = [
        'line_name', 'line_code', 'line_type', 'voltage_level', 
        'thermal_capacity_mw', 'length_km', 'active', 'utilization_display'
    ]
    list_filter = ['line_type', 'voltage_level', 'active', 'commissioned_date']
    search_fields = ['line_name', 'line_code', 'owner']
    readonly_fields = ['created_date', 'modified_date', 'calculated_length']
    
    fieldsets = [
        ('Basic Information', {
            'fields': ['line_name', 'line_code', 'line_type', 'active']
        }),
        ('Technical Specifications', {
            'fields': [
                'voltage_level', 'thermal_capacity_mw', 'emergency_capacity_mw',
                'resistance_per_km', 'reactance_per_km', 'conductance_per_km', 'susceptance_per_km'
            ]
        }),
        ('Geographic Data', {
            'fields': [
                'from_latitude', 'from_longitude', 'to_latitude', 'to_longitude',
                'length_km', 'calculated_length'
            ]
        }),
        ('KML Integration', {
            'fields': ['kml_geometry'],
            'classes': ['collapse']
        }),
        ('Administrative', {
            'fields': ['owner', 'commissioned_date', 'decommissioned_date']
        }),
        ('System Data', {
            'fields': ['created_date', 'modified_date'],
            'classes': ['collapse']
        })
    ]
    
    actions = [
        'activate_lines', 'deactivate_lines', 'calculate_impedances',
        'sync_from_kml', 'export_to_kml', 'validate_coordinates'
    ]
    
    def calculated_length(self, obj):
        """Display calculated length based on coordinates"""
        import math
        
        if all([obj.from_latitude, obj.from_longitude, obj.to_latitude, obj.to_longitude]):
            # Haversine formula
            R = 6371  # Earth's radius in km
            lat1, lon1, lat2, lon2 = map(math.radians, [
                obj.from_latitude, obj.from_longitude, 
                obj.to_latitude, obj.to_longitude
            ])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
            c = 2 * math.asin(math.sqrt(a))
            distance = R * c
            
            if abs(distance - obj.length_km) > 0.1:  # If difference > 100m
                return format_html(
                    '<span style="color: orange;">{:.2f} km (differs from stored: {:.2f} km)</span>',
                    distance, obj.length_km
                )
            else:
                return f"{distance:.2f} km"
        return "Cannot calculate - missing coordinates"
    
    calculated_length.short_description = "Calculated Length"
    
    def utilization_display(self, obj):
        """Display current utilization if available"""
        # This would need to be connected to real-time data
        # For now, just show capacity info
        if obj.emergency_capacity_mw:
            return format_html(
                'Normal: {} MW<br>Emergency: {} MW',
                obj.thermal_capacity_mw,
                obj.emergency_capacity_mw
            )
        return f"{obj.thermal_capacity_mw} MW"
    
    utilization_display.short_description = "Capacity"
    utilization_display.allow_tags = True
    
    actions = ['activate_lines', 'deactivate_lines', 'calculate_impedances']
    
    def activate_lines(self, request, queryset):
        updated = queryset.update(active=True)
        self.message_user(request, f"{updated} grid lines activated.")
    activate_lines.short_description = "Activate selected grid lines"
    
    def deactivate_lines(self, request, queryset):
        updated = queryset.update(active=False)
        self.message_user(request, f"{updated} grid lines deactivated.")
    deactivate_lines.short_description = "Deactivate selected grid lines"
    
    def calculate_impedances(self, request, queryset):
        """Recalculate impedances for selected lines"""
        count = 0
        for line in queryset:
            # Perform any impedance calculations or validations
            line.save()  # Trigger any model save logic
            count += 1
        self.message_user(request, f"Recalculated impedances for {count} grid lines.")
    calculate_impedances.short_description = "Recalculate impedances"
    
    def sync_from_kml(self, request, queryset):
        """Sync selected grid lines from their KML source"""
        from django.core.management import call_command
        from io import StringIO
        
        try:
            out = StringIO()
            call_command('import_kml_gridlines', 
                        update_existing=True,
                        stdout=out)
            
            output = out.getvalue()
            self.message_user(request, f"KML sync completed: {output}")
            
        except Exception as e:
            self.message_user(request, f"KML sync failed: {str(e)}", level='ERROR')
    
    sync_from_kml.short_description = "Sync from KML source"
    
    def export_to_kml(self, request, queryset):
        """Export selected grid lines to KML format"""
        try:
            import tempfile
            import os
            from django.http import HttpResponse
            
            # Create KML content for selected lines
            kml_header = '''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Selected Grid Lines</name>
    <description>Exported from admin interface</description>
'''
            kml_footer = '''  </Document>
</kml>'''
            
            kml_content = kml_header
            for grid_line in queryset:
                kml_content += grid_line.export_to_kml() + '\n'
            kml_content += kml_footer
            
            response = HttpResponse(kml_content, content_type='application/vnd.google-earth.kml+xml')
            response['Content-Disposition'] = 'attachment; filename="selected_gridlines.kml"'
            
            return response
            
        except Exception as e:
            self.message_user(request, f"KML export failed: {str(e)}", level='ERROR')
    
    export_to_kml.short_description = "Export to KML"
    
    def validate_coordinates(self, request, queryset):
        """Validate coordinate data and KML geometry"""
        validated_count = 0
        error_count = 0
        
        for grid_line in queryset:
            try:
                # Check if coordinates are valid
                if not all([grid_line.from_latitude, grid_line.from_longitude,
                           grid_line.to_latitude, grid_line.to_longitude]):
                    error_count += 1
                    continue
                
                # Validate KML geometry if present
                kml_data = grid_line.get_kml_geometry_data()
                if kml_data and 'coordinates' in kml_data:
                    coords = kml_data['coordinates']
                    if len(coords) < 2:
                        error_count += 1
                        continue
                
                validated_count += 1
                
            except Exception:
                error_count += 1
        
        self.message_user(
            request, 
            f"Validation complete: {validated_count} valid, {error_count} errors"
        )
    
    validate_coordinates.short_description = "Validate coordinates"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('kml-import/', self.admin_site.admin_view(self.kml_import_view), 
                 name='gridlines-kml-import'),
            path('bulk-export/', self.admin_site.admin_view(self.bulk_export_view), 
                 name='gridlines-bulk-export'),
        ]
        return custom_urls + urls
    
    def kml_import_view(self, request):
        """Custom view for KML import with file upload"""
        if request.method == 'POST':
            # Handle file upload and import
            # This would include file upload handling
            pass
        
        from django.shortcuts import render
        return render(request, 'admin/kml_import.html', {
            'title': 'Import KML Grid Lines',
            'opts': self.model._meta,
        })
    
    def bulk_export_view(self, request):
        """Custom view for bulk export options"""
        from django.shortcuts import render
        return render(request, 'admin/bulk_export.html', {
            'title': 'Bulk Export Grid Lines',
            'opts': self.model._meta,
        })

@admin.register(FacilityGridConnections)
class FacilityGridConnectionsAdmin(admin.ModelAdmin):
    list_display = [
        'facility_name', 'grid_line_name', 'connection_type', 
        'connection_voltage_kv', 'connection_capacity_mw', 
        'connection_distance_km', 'is_primary', 'active'
    ]
    list_filter = ['connection_type', 'is_primary', 'active', 'connection_voltage_kv']
    search_fields = ['idfacilities__facility_name', 'idgridlines__line_name']
    raw_id_fields = ['idfacilities', 'idgridlines']
    
    fieldsets = [
        ('Connection Details', {
            'fields': ['idfacilities', 'idgridlines', 'connection_type', 'is_primary', 'active']
        }),
        ('Technical Specifications', {
            'fields': [
                'connection_voltage_kv', 'connection_capacity_mw', 'transformer_capacity_mva',
                'connection_distance_km'
            ]
        }),
        ('Geographic Data', {
            'fields': ['connection_point_latitude', 'connection_point_longitude']
        }),
        ('Administrative', {
            'fields': ['connection_date', 'created_date', 'modified_date'],
            'classes': ['collapse']
        })
    ]
    
    readonly_fields = ['created_date', 'modified_date']
    
    def facility_name(self, obj):
        return obj.idfacilities.facility_name
    facility_name.short_description = "Facility"
    facility_name.admin_order_field = 'idfacilities__facility_name'
    
    def grid_line_name(self, obj):
        return obj.idgridlines.line_name
    grid_line_name.short_description = "Grid Line"
    grid_line_name.admin_order_field = 'idgridlines__line_name'
    
    actions = ['make_primary', 'activate_connections', 'deactivate_connections']
    
    def make_primary(self, request, queryset):
        """Make selected connections primary (only one per facility-gridline pair)"""
        updated = 0
        for connection in queryset:
            # First, unset other primary connections for this facility-gridline pair
            FacilityGridConnections.objects.filter(
                idfacilities=connection.idfacilities,
                idgridlines=connection.idgridlines,
                is_primary=True
            ).update(is_primary=False)
            
            # Then set this one as primary
            connection.is_primary = True
            connection.save()
            updated += 1
        
        self.message_user(request, f"{updated} connections set as primary.")
    make_primary.short_description = "Set as primary connection"
    
    def activate_connections(self, request, queryset):
        updated = queryset.update(active=True)
        self.message_user(request, f"{updated} connections activated.")
    activate_connections.short_description = "Activate selected connections"
    
    def deactivate_connections(self, request, queryset):
        updated = queryset.update(active=False)
        self.message_user(request, f"{updated} connections deactivated.")
    deactivate_connections.short_description = "Deactivate selected connections"

class FacilityGridConnectionsInline(admin.TabularInline):
    model = FacilityGridConnections
    extra = 0
    fields = [
        'idgridlines', 'connection_type', 'connection_voltage_kv', 
        'connection_capacity_mw', 'connection_distance_km', 'is_primary', 'active'
    ]
    raw_id_fields = ['idgridlines']

@admin.register(facilities)
class FacilitiesAdmin(admin.ModelAdmin):
    list_display = [
        'facility_name', 'facility_code', 'technology_name', 'capacity', 
        'primary_grid_line', 'active', 'existing'
    ]
    list_filter = ['active', 'existing', 'idtechnologies', 'primary_grid_line']
    search_fields = ['facility_name', 'facility_code']
    inlines = [FacilityGridConnectionsInline]
    raw_id_fields = ['primary_grid_line']
    
    fieldsets = [
        ('Basic Information', {
            'fields': ['facility_name', 'facility_code', 'participant_code', 'active', 'existing']
        }),
        ('Technical Details', {
            'fields': ['idtechnologies', 'capacity', 'capacityfactor', 'generation', 'transmitted']
        }),
        ('Location', {
            'fields': ['latitude', 'longitude', 'idzones']
        }),
        ('Grid Connection', {
            'fields': ['primary_grid_line']
        }),
        ('Wind Turbine Details', {
            'fields': ['turbine', 'hub_height', 'no_turbines', 'tilt'],
            'classes': ['collapse']
        }),
        ('Additional Attributes', {
            'fields': ['storage_hours', 'power_file', 'grid_line', 'direction'],
            'classes': ['collapse']
        }),
        ('Administrative', {
            'fields': ['registered_from'],
            'classes': ['collapse']
        })
    ]
    
    def technology_name(self, obj):
        return obj.idtechnologies.technology_name if obj.idtechnologies else "Unknown"
    technology_name.short_description = "Technology"
    technology_name.admin_order_field = 'idtechnologies__technology_name'
