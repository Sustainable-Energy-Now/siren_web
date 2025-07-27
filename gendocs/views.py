from django.shortcuts import render
from docxtpl import DocxTemplate
import os
from siren_web.models import facilities
from siren_web.database_operations import fetch_full_generator_storage_data
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.conf import settings
from datetime import datetime
from io import BytesIO

TEMPLATE_MAPPING = {
    'facilities_report': 'facilities_report.docx',
    'technologies_report': 'technologies_report.docx',
    'scenarios_report': 'scenarios_report.docx',
    'modelling_report': 'modelling_report.docx',
}

REPORT_TYPES = [
    {'value': 'facilities_report', 'label': 'Facilities Report'},
    {'value': 'technologies_report', 'label': 'Technologies Report'},
    {'value': 'scenarios_report', 'label': 'Scenarios Report'},
    {'value': 'modelling_report', 'label': 'Modelling Report'},
]

class DocumentGenerationError(Exception):
    """Custom exception for document generation errors"""
    pass

def get_template_path(doc_type):
    """Get the full path to a template file"""
    template_file = TEMPLATE_MAPPING.get(doc_type)
    if not template_file:
        raise DocumentGenerationError(f'Invalid document type: {doc_type}')
    
    template_path = os.path.join(settings.MEDIA_ROOT, 'templates', template_file)
    
    if not os.path.exists(template_path):
        raise DocumentGenerationError(f'Template file not found: {template_file}')
    
    return template_path

def index(request):
    """Main gendocs page"""
    return render(request, 'index.html', {
        'title': 'Document Generator',
        'available_templates': [
            {'name': 'Facilities Report', 'type': 'facilities_report'},
            {'name': 'Technologies Report', 'type': 'technologies_report'},
            {'name': 'Scenarios Report', 'type': 'scenarios_report'},
            {'name': 'Modelling Report', 'type': 'report'},
        ]
    })

def get_document_context(doc_type, request):
    """Generate context data for different document types"""
    
    # Get demand year from session or use default
    demand_year = request.session.get('demand_year', 2024)
    
    # Base context that all documents use
    base_context = {
        'company_name': 'Sustainable Energy Now',
        'company_address': '3 Dyer Sttreet',
        'company_city': 'West Perth, WA 6000',
        'company_phone': '+61 8 1234 5678',
        'company_email': 'contact@sen.asn.au',
        'report_date': datetime.now().strftime('%B %d, %Y'),
        'generated_by': request.user.get_full_name() if request.user.is_authenticated else 'System',
        'generation_date': datetime.now().strftime('%B %d, %Y at %I:%M %p'),
        'demand_year': demand_year,
    }
    
    # Get technologies data
    if doc_type == 'modelling_report':
        technology_queryset = fetch_full_generator_storage_data(demand_year)
        
        # Process technologies data for the template
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
        
        # Document-specific context
        specific_context = {
            'technologies': technologies_data,
    }
        
        # Merge base and specific context
        return {**base_context, **specific_context}

    elif doc_type == 'facilities_report':
        # Get all facilities
        facilities_data = facilities.objects.all()
        
        # Document-specific context
        specific_context = {
            'facilities': facilities_data,
        }
        
        # Merge base and specific context
        return {**base_context, **specific_context}
    elif doc_type == 'scenarios_report':
        # Get all scenarios
        scenarios_data = Scenarios.objects.all()
        
        # Document-specific context
        specific_context = {
            'scenarios': scenarios_data,
        }
        
        # Merge base and specific context
        return {**base_context, **specific_context}

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
    
    # Get context data
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
            'company_name': 'Sustainable Energy Now',
            'report_date': '2025-07-22',
            'customer_name': 'Sample Customer',
        }
    }
    
    return render(request, 'template_preview.html', context)
