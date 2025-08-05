from django.contrib import admin
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
        ('Administrative', {
            'fields': ['owner', 'commissioned_date', 'decommissioned_date']
        }),
        ('System Data', {
            'fields': ['kml_geometry', 'created_date', 'modified_date'],
            'classes': ['collapse']
        })
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


# Enhance the existing facilities admin to show grid connections
class FacilityGridConnectionsInline(admin.TabularInline):
    model = FacilityGridConnections
    extra = 0
    fields = [
        'idgridlines', 'connection_type', 'connection_voltage_kv', 
        'connection_capacity_mw', 'connection_distance_km', 'is_primary', 'active'
    ]
    raw_id_fields = ['idgridlines']


# If you have an existing FacilitiesAdmin, add this inline to it:
# class FacilitiesAdmin(admin.ModelAdmin):
#     inlines = [FacilityGridConnectionsInline]
#     # ... other existing configuration

# Or create a new one if it doesn't exist:
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
