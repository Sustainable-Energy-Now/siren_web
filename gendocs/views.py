from django.shortcuts import render
from docxtpl import DocxTemplate
import os
from siren_web.models import facilities, Scenarios, Technologies
from siren_web.database_operations import fetch_full_generator_storage_data
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.conf import settings
from datetime import datetime
from io import BytesIO

# Document configuration
TEMPLATE_MAPPING = {
    'facilities_report': 'facilities_report.docx',
    'technologies_report': 'technologies_report.docx',
    'scenarios_report': 'scenarios_report.docx',
    'modelling_report': 'modelling_report.docx',
    'grid_balance_report': 'grid_balance_report.docx',
}

REPORT_TYPES = [
    {'value': 'facilities_report', 'label': 'Facilities Report'},
    {'value': 'technologies_report', 'label': 'Technologies Report'},
    {'value': 'scenarios_report', 'label': 'Scenarios Report'},
    {'value': 'modelling_report', 'label': 'Modelling Report'},
    {'value': 'grid_balance_report', 'label': 'Grid Balance Process'},
]

class DocumentGenerationError(Exception):
    """Custom exception for document generation errors"""
    pass

# Document handler classes for clean separation
class BaseDocumentHandler:
    """Base class for document handlers"""
    
    def __init__(self, request):
        self.request = request
        self.demand_year = request.session.get('demand_year', 2024)
    
    def get_base_context(self):
        """Common context data for all documents"""
        return {
            'organisation_name': 'Sustainable Energy Now',
            'organisation_address': '3 Dyer Street',
            'organisation_city': 'West Perth, WA 6000',
            'organisation_phone': '+61 8 1234 5678',
            'organisation_email': 'contact@sen.asn.au',
            'report_date': datetime.now().strftime('%B %d, %Y'),
            'generated_by': self.request.user.get_full_name() if self.request.user.is_authenticated else 'System',
            'generation_date': datetime.now().strftime('%B %d, %Y at %I:%M %p'),
            'demand_year': self.demand_year,
        }
    
    def get_context(self):
        """Override this method in subclasses"""
        return self.get_base_context()

class FacilitiesReportHandler(BaseDocumentHandler):
    """Handler for facilities reports"""
    
    def get_context(self):
        base_context = self.get_base_context()
        
        # Get facilities data
        facilities_data = facilities.objects.all()
        
        # Process facilities data if needed
        processed_facilities = []
        for facility in facilities_data:
            processed_facilities.append({
                'facility_name': facility.facility_name if hasattr(facility, 'facility_name') else 'Unknown',
                'facility_code': facility.facility_code if hasattr(facility, 'facility_code') else 'Unknown',
                'participant_code': facility.participant_code if hasattr(facility, 'participant_code') else 'Unknown',
                'registered_from': facility.registered_from if hasattr(facility, 'registered_from') else 'Unknown',
                'status': facility.active if hasattr(facility, 'active') else 'Unknown',
                'idtechnologies': facility.idtechnologies,
                'capacity': facility.capacity if facility.capacity is not None else 'N/A',
                'capacityfactor': facility.capacityfactor if facility.capacityfactor is not None else 'N/A',
                'storage_hours': facility.storage_hours if facility.storage_hours is not None else 'N/A',
                'grid_line': facility.grid_line if facility.grid_line else 'N/A',
                'direction': facility.direction if facility.direction else 'N/A',
                'latitude': facility.latitude if facility.latitude is not None else 'N/A',
                'longitude': facility.longitude if facility.longitude is not None else 'N/A',
            })
        specific_context = {
            'report_title': 'Facilities Report',
            'facilities': processed_facilities,
            'total_facilities': len(processed_facilities),
        }
        
        return {**base_context, **specific_context}

class TechnologiesReportHandler(BaseDocumentHandler):
    """Handler for technologies reports"""
    
    def get_context(self):
        base_context = self.get_base_context()
        
        # Get technologies data using your existing method
        technology_queryset = fetch_full_generator_storage_data(self.demand_year)
        
        # Process technologies data
        technologies_data = self._process_technologies(technology_queryset)
        
        specific_context = {
            'report_title': 'Technologies Report',
            'technologies': technologies_data,
            'total_technologies': len(technologies_data),
            'renewable_count': sum(1 for tech in technologies_data if tech['renewable'] == 'Yes'),
        }
        
        return {**base_context, **specific_context}
    
    def _process_technologies(self, technology_queryset):
        """Process technologies data for template"""
        technologies_data = []
        
        for technology in technology_queryset:
            # Get the first technology year data
            tech_year = technology.technologyyears_set.first()
            
            # Get generator or storage attributes
            generator_attrs = technology.generatorattributes_set.first()
            storage_attrs = technology.storageattributes_set.first()
            
            tech_data = {
                'name': technology.technology_name,
                'description': technology.description,
                'image_url': f"https://sen.asn.au/wp-content/uploads/{technology.image}" if technology.image else None,
                'renewable': 'Yes' if technology.renewable else 'No',
                'dispatchable': 'Yes' if technology.dispatchable else 'No',
                'lifetime': technology.lifetime,
                'discount_rate': technology.discount_rate,
                'emissions': technology.emissions,
                'area': technology.area,
                'capex': tech_year.capex if tech_year else None,
                'fom': tech_year.fom if tech_year else None,
                'vom': tech_year.vom if tech_year else None,
                'fuel': tech_year.fuel if tech_year else None,
                'is_generator': bool(generator_attrs),
                'is_storage': bool(storage_attrs),
            }
            
            # Add generator-specific attributes if applicable
            if generator_attrs:
                tech_data.update({
                    'capacity_max': generator_attrs.capacity_max,
                    'capacity_min': generator_attrs.capacity_min,
                    'rampdown_max': generator_attrs.rampdown_max,
                    'rampup_max': generator_attrs.rampup_max,
                })
            
            # Add storage-specific attributes if applicable
            if storage_attrs:
                tech_data.update({
                    'discharge_loss': storage_attrs.discharge_loss,
                    'discharge_max': storage_attrs.discharge_max,
                    'parasitic_loss': storage_attrs.parasitic_loss,
                    'recharge_loss': storage_attrs.recharge_loss,
                    'recharge_max': storage_attrs.recharge_max,
                })
            
            technologies_data.append(tech_data)
        
        return technologies_data

class ScenariosReportHandler(BaseDocumentHandler):
    """Handler for scenarios reports"""
    
    def get_context(self):
        base_context = self.get_base_context()
        
        # Get scenarios data
        scenarios_data = Scenarios.objects.all()
        
        # Process scenarios if needed
        processed_scenarios = []
        for scenario in scenarios_data:
            processed_scenarios.append({
                'name': getattr(scenario, 'name', 'Unknown'),
                'description': getattr(scenario, 'description', ''),
                'status': getattr(scenario, 'status', 'Unknown'),
                # Add more fields as needed
            })
        
        specific_context = {
            'report_title': 'Scenarios Report',
            'scenarios': processed_scenarios,
            'total_scenarios': len(processed_scenarios),
        }
        
        return {**base_context, **specific_context}

class ModellingReportHandler(BaseDocumentHandler):
    """Handler for modelling reports - uses same data as technologies but different template"""
    
    def get_context(self):
        base_context = self.get_base_context()
        
        # Reuse technologies processing
        tech_handler = TechnologiesReportHandler(self.request)
        tech_context = tech_handler.get_context()
        
        # Override title and add modelling-specific data
        specific_context = {
            'report_title': 'Energy Modelling Report',
            'technologies': tech_context['technologies'],
            'analysis_summary': self._get_analysis_summary(tech_context['technologies']),
            'recommendations': self._get_recommendations(tech_context['technologies']),
        }
        
        return {**base_context, **specific_context}
    
    def _get_analysis_summary(self, technologies):
        """Generate analysis summary"""
        total = len(technologies)
        renewable = sum(1 for tech in technologies if tech['renewable'] == 'Yes')
        
        return {
            'total_technologies': total,
            'renewable_percentage': (renewable / total * 100) if total > 0 else 0,
            'avg_lifetime': sum(tech['lifetime'] for tech in technologies if tech['lifetime']) / total if total > 0 else 0,
        }
    
    def _get_recommendations(self, technologies):
        """Generate recommendations based on data"""
        recommendations = []
        
        renewable_count = sum(1 for tech in technologies if tech['renewable'] == 'Yes')
        total_count = len(technologies)
        
        if renewable_count / total_count < 0.7:
            recommendations.append("Consider increasing renewable energy technology adoption")
        
        long_lifetime_techs = [tech for tech in technologies if tech['lifetime'] and tech['lifetime'] > 25]
        if long_lifetime_techs:
            recommendations.append(f"Focus on long-lifetime technologies like {', '.join([tech['name'] for tech in long_lifetime_techs[:3]])}")
        
        return recommendations

class GridBalanceReportHandler(BaseDocumentHandler):
    """Handler for grid balance reports"""
    
    def get_context(self):
        base_context = self.get_base_context()
        
        # Get grid balance specific data
        # This would be your grid balance logic
        grid_data = self._get_grid_balance_data()
        
        specific_context = {
            'report_title': 'Grid Balance Process Report',
            'grid_balance_data': grid_data,
            'balance_summary': self._get_balance_summary(grid_data),
        }
        
        return {**base_context, **specific_context}
    
    def _get_grid_balance_data(self):
        """Get grid balance specific data"""
        # Implement your grid balance data logic here
        return {
            'total_generation': 1000,  # Example data
            'total_demand': 950,
            'surplus': 50,
            'efficiency': 95.0,
        }
    
    def _get_balance_summary(self, grid_data):
        """Calculate balance summary"""
        return {
            'is_balanced': grid_data['surplus'] >= 0,
            'efficiency_rating': 'High' if grid_data['efficiency'] > 90 else 'Medium' if grid_data['efficiency'] > 80 else 'Low',
        }

# Document handler registry
DOCUMENT_HANDLERS = {
    'facilities_report': FacilitiesReportHandler,
    'technologies_report': TechnologiesReportHandler,
    'scenarios_report': ScenariosReportHandler,
    'modelling_report': ModellingReportHandler,
    'grid_balance_report': GridBalanceReportHandler,
}

# Utility functions
def get_template_path(doc_type):
    """Get the full path to a template file"""
    template_file = TEMPLATE_MAPPING.get(doc_type)
    if not template_file:
        raise DocumentGenerationError(f'Invalid document type: {doc_type}')
    
    template_path = os.path.join(settings.MEDIA_ROOT, 'templates', template_file)
    
    if not os.path.exists(template_path):
        raise DocumentGenerationError(f'Template file not found: {template_file}')
    
    return template_path

def get_document_context(doc_type, request):
    """Get context data for document generation using handlers"""
    handler_class = DOCUMENT_HANDLERS.get(doc_type)
    
    if not handler_class:
        raise DocumentGenerationError(f'No handler found for document type: {doc_type}')
    
    handler = handler_class(request)
    return handler.get_context()

def validate_document_request(doc_type):
    """Validate document generation request"""
    if not doc_type:
        raise DocumentGenerationError('Document type is required')
    
    if doc_type not in TEMPLATE_MAPPING:
        raise DocumentGenerationError(f'Invalid document type: {doc_type}')
    
    return True

def create_document(doc_type, request):
    """Core document creation logic - used by both functions"""
    # Validate request
    validate_document_request(doc_type)
    
    # Get template path
    template_path = get_template_path(doc_type)
    
    # Load template
    doc = DocxTemplate(template_path)
    
    # Get context data using appropriate handler
    context = get_document_context(doc_type, request)
    
    # Render document
    doc.render(context)
    
    return doc

@login_required
@require_http_methods(["GET", "POST"])
def generate_report(request):
    """Handle form submission and validation"""
    if request.method == 'GET':
        context = {
            'title': 'Generate Report',
            'report_types': REPORT_TYPES
        }
        return render(request, 'generate_form.html', context)
    
    elif request.method == 'POST':
        report_type = request.POST.get('report_type')
        
        try:
            # Validate the request (but don't generate document yet)
            validate_document_request(report_type)
            
            # Verify template exists
            get_template_path(report_type)
            
            # Return success with download link
            return JsonResponse({
                'success': True,
                'message': f'{report_type.replace("_", " ").title()} ready for generation',
                'download_url': f'/gendocs/download/{report_type}/'
            })
            
        except DocumentGenerationError as e:
            return JsonResponse({
                'error': str(e)
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'error': f'Unexpected error: {str(e)}'
            }, status=500)

def download_document(request, doc_type):
    """Generate and download document"""
    try:
        # Use shared document creation logic
        doc = create_document(doc_type, request)
        
        # Save to buffer
        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'{doc_type}_{timestamp}.docx'
        
        # Create response
        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except DocumentGenerationError as e:
        return HttpResponse(f'Document Generation Error: {str(e)}', status=400)
    except Exception as e:
        return HttpResponse(f'Error generating document: {str(e)}', status=500)

# API endpoints
@require_http_methods(["GET"])
def get_template_fields(request, template_name):
    """Return available fields for a specific template"""
    template_fields = {
        'modelling_report': ['system_capacity', 'client_name', 'technologies'],
        'facilities_report': ['location', 'status', 'capacity'],
        'scenarios_report': ['scenario_name', 'status'],
        'technologies_report': ['category', 'renewable', 'lifetime'],
        'grid_balance_report': ['generation', 'demand', 'efficiency'],
    }
    
    fields = template_fields.get(template_name, [])
    
    return JsonResponse({
        'fields': fields,
        'template_name': template_name
    })

@login_required
def template_preview(request, template_id):
    """Show preview of template with sample data"""
    
    context = {
        'template_id': template_id,
        'sample_data': {
            'organisation_name': 'Sustainable Energy Now',
            'report_date': '2025-07-22',
            'customer_name': 'Sample Customer',
        }
    }
    
    return render(request, 'template_preview.html', context)
