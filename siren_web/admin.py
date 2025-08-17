from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms import ModelForm, FileField
from django.utils.html import format_html
from .models import Reference, SystemComponent, ComponentConnection
from siren_web.models import SystemComponent
from django.contrib import admin

@admin.register(SystemComponent)
class SystemComponentAdmin(admin.ModelAdmin):
    list_display = [
        'display_name', 
        'component_type', 
        'is_active', 
        'position_preview',
        'model_status',
        'updated_at'
    ]
    list_filter = ['component_type', 'is_active', 'color_scheme']
    search_fields = ['name', 'display_name', 'description']
    ordering = ['component_type', 'display_name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'display_name', 'component_type', 'description', 'is_active')
        }),
        ('Model Configuration', {
            'fields': ('model_class_name',),
            'classes': ('collapse',)
        }),
        ('Position & Appearance', {
            'fields': (
                ('position_x', 'position_y'),
                ('width', 'height'),
                'color_scheme'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def position_preview(self, obj):
        return format_html(
            '<span style="font-family: monospace;">({}, {}) {}×{}</span>',
            obj.position_x, obj.position_y, obj.width, obj.height
        )
    position_preview.short_description = 'Position & Size'
    
    def model_status(self, obj):
        if obj.component_type != 'model':
            return '-'
        
        model_class = obj.get_model_class()
        if model_class:
            try:
                count = model_class.objects.count()
                return format_html(
                    '<span style="color: green;">✓ {} records</span>',
                    count
                )
            except Exception as e:
                return format_html(
                    '<span style="color: red;">✗ Error: {}</span>',
                    str(e)[:50]
                )
        else:
            return format_html('<span style="color: orange;">⚠ Model not found</span>')
    
    model_status.short_description = 'Model Status'
    
    actions = ['test_model_connection', 'duplicate_component']
    
    def test_model_connection(self, request, queryset):
        """Test if model classes can be accessed"""
        results = []
        for component in queryset:
            if component.component_type == 'model':
                model_class = component.get_model_class()
                if model_class:
                    try:
                        count = model_class.objects.count()
                        results.append(f"✓ {component.name}: {count} records")
                    except Exception as e:
                        results.append(f"✗ {component.name}: {str(e)}")
                else:
                    results.append(f"⚠ {component.name}: Model class not found")
        
        self.message_user(request, "Model connection test results:\n" + "\n".join(results))
    
    test_model_connection.short_description = "Test model connections"
    
    def duplicate_component(self, request, queryset):
        """Create duplicates of selected components"""
        for component in queryset:
            component.pk = None
            component.name = f"{component.name}_copy"
            component.display_name = f"{component.display_name} (Copy)"
            component.position_x += 150  # Offset position
            component.save()
        
        self.message_user(request, f"Duplicated {queryset.count()} components")
    
    duplicate_component.short_description = "Duplicate selected components"

@admin.register(ComponentConnection)
class ComponentConnectionAdmin(admin.ModelAdmin):
    list_display = [
        'connection_preview',
        'connection_type',
        'is_active',
        'description_preview'
    ]
    list_filter = ['connection_type', 'is_active']
    search_fields = [
        'from_component__name',
        'to_component__name',
        'description'
    ]
    
    autocomplete_fields = ['from_component', 'to_component']
    
    def connection_preview(self, obj):
        return format_html(
            '<code>{}</code> → <code>{}</code>',
            obj.from_component.display_name,
            obj.to_component.display_name
        )
    connection_preview.short_description = 'Connection'
    
    def description_preview(self, obj):
        if obj.description:
            return obj.description[:50] + ('...' if len(obj.description) > 50 else '')
        return '-'
    description_preview.short_description = 'Description'

@admin.register(Reference)
class ReferenceAdmin(admin.ModelAdmin):
    list_display = [
        'source', 'title', 'author', 'reference_type', 
        'accessed_date', 'is_active'
    ]
    list_filter = ['reference_type', 'is_active', 'accessed_date']
    search_fields = ['source', 'title', 'author', 'notes', 'tags']
    readonly_fields = ['accessed_date', 'modified_date']
    list_per_page = 25
    date_hierarchy = 'accessed_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('source', 'title', 'author', 'reference_type')
        }),
        ('Dates', {
            'fields': ('publication_date', 'accessed_date', 'modified_date'),
            'classes': ('collapse',)
        }),
        ('Location & Details', {
            'fields': ('location', 'section', 'notes', 'tags')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )

    