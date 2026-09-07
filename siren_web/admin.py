from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms import ModelForm, FileField
from django.utils.html import format_html
from .models import Reference
from django.contrib import admin
from .models import (
    EvVintage, SourceDocument, EvUptakePostcodeFigure, EvSuppressionFlag,
    EvChargingProfile, SwisBoundaryMembership, EvActualsRecord, EvLoadTrace,
    V2gInterfaceStub, SwisBoundary, PostcodeBoundary,
    EvActualsDocument, EvActualsQuarter, CommandRun,
)


@admin.register(CommandRun)
class CommandRunAdmin(admin.ModelAdmin):
    list_display = ['idcommandrun', 'label', 'status', 'trigger_source',
                    'triggered_by', 'return_code', 'created_at', 'finished_at']
    list_filter = ['status', 'trigger_source', 'command_key']
    search_fields = ['command_key', 'label', 'error_summary']
    readonly_fields = [f.name for f in CommandRun._meta.fields]
    list_per_page = 40

    def has_add_permission(self, request):
        return False

# EV Uptake & Charging Load Modelling (Phase 0 governance scaffold, GR-01)
@admin.register(EvVintage)
class EvVintageAdmin(admin.ModelAdmin):
    list_display = ['version', 'release_date', 'ingestion_status', 'updated_at']
    list_filter = ['ingestion_status']
    search_fields = ['version']


@admin.register(SourceDocument)
class SourceDocumentAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'domain', 'doc_type', 'retrieved_at']
    list_filter = ['doc_type']
    raw_id_fields = ['esoo_vintage', 'ev_vintage']


@admin.register(EvUptakePostcodeFigure)
class EvUptakePostcodeFigureAdmin(admin.ModelAdmin):
    list_display = ['vintage', 'postcode', 'forecast_year', 'csiro_scenario', 'consumption_kwh', 'validation_status']
    list_filter = ['csiro_scenario', 'validation_status', 'forecast_year']
    search_fields = ['postcode']


@admin.register(EvSuppressionFlag)
class EvSuppressionFlagAdmin(admin.ModelAdmin):
    list_display = ['vintage', 'postcode', 'forecast_year', 'csiro_scenario', 'reason']
    list_filter = ['reason', 'csiro_scenario']


@admin.register(EvChargingProfile)
class EvChargingProfileAdmin(admin.ModelAdmin):
    list_display = ['source_document', 'region', 'charging_type_label', 'charging_mode', 'share_of_charging']
    list_filter = ['region', 'charging_mode']


@admin.register(SwisBoundaryMembership)
class SwisBoundaryMembershipAdmin(admin.ModelAdmin):
    list_display = ['postcode', 'zone_name', 'membership_status', 'apportionment_fraction']
    list_filter = ['membership_status']
    search_fields = ['postcode', 'zone_name']


@admin.register(SwisBoundary)
class SwisBoundaryAdmin(admin.ModelAdmin):
    list_display = ['name', 'source', 'vertex_count', 'updated_at']


@admin.register(PostcodeBoundary)
class PostcodeBoundaryAdmin(admin.ModelAdmin):
    list_display = ['postcode', 'area_sqkm', 'source', 'updated_at']
    search_fields = ['postcode']


@admin.register(EvActualsDocument)
class EvActualsDocumentAdmin(admin.ModelAdmin):
    list_display = ['quarter_label', 'period_end', 'source', 'series_rows_extracted',
                    'report_prepared_date', 'retrieved_at']
    list_filter = ['source']
    date_hierarchy = 'period_end'


@admin.register(EvActualsQuarter)
class EvActualsQuarterAdmin(admin.ModelAdmin):
    list_display = ['period_end', 'region', 'source', 'bev_count', 'phev_count', 'total_count']
    list_filter = ['source', 'region']
    date_hierarchy = 'period_end'


@admin.register(EvActualsRecord)
class EvActualsRecordAdmin(admin.ModelAdmin):
    list_display = ['year', 'region', 'source', 'fleet_count', 'bev_count', 'phev_count', 'period_end']
    list_filter = ['source']


@admin.register(EvLoadTrace)
class EvLoadTraceAdmin(admin.ModelAdmin):
    list_display = ['csiro_scenario', 'year', 'charging_mode', 'n_intervals', 'annual_energy_mwh', 'integral_check_pct']
    list_filter = ['csiro_scenario', 'charging_mode']


@admin.register(V2gInterfaceStub)
class V2gInterfaceStubAdmin(admin.ModelAdmin):
    list_display = ['csiro_scenario', 'v2g_capable_fraction', 'exportable_capacity_kw']

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

    