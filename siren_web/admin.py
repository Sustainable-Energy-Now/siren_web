from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms import ModelForm, FileField
from django.utils.html import format_html
from .models import Reference
from django.contrib import admin

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

    