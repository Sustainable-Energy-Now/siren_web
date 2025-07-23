from django.shortcuts import render
from docxtpl import DocxTemplate
import os
from siren_web.models import facilities
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.conf import settings
from datetime import datetime, timedelta
from io import BytesIO

TEMPLATE_MAPPING = {
    'modelling_report': 'modelling_report.docx',
    'sales_report': 'sales_report.docx',
    'invoice': 'invoice_template.docx',
}

REPORT_TYPES = [
    {'value': 'modelling_report', 'label': 'Modelling Report'},
    {'value': 'sales_report', 'label': 'Sales Report'},
    {'value': 'invoice', 'label': 'Invoice'},
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
            {'name': 'Modelling Report', 'type': 'report'},
        ]
    })

def get_document_context(doc_type, request):
    """Generate context data for different document types"""
    
    # Base context that all documents use
    base_context = {
        'company_name': 'Sustainable Energy Now',
        'company_address': '123 Green Energy Street',
        'company_city': 'Perth, WA 6000',
        'company_phone': '+61 8 1234 5678',
        'company_email': 'info@sustainableenergynow.com',
        'report_date': datetime.now().strftime('%B %d, %Y'),
        'generated_by': request.user.get_full_name() if request.user.is_authenticated else 'System',
        'generation_date': datetime.now().strftime('%B %d, %Y at %I:%M %p'),
    }
    
    # Document-specific context
    specific_context = {
    'facilities': facilities.objects.all(),  # This is a QuerySet
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

def index(request):
    """Main gendocs page"""
    return render(request, 'index.html', {
        'title': 'Document Generator',
        'available_templates': [
            {'name': 'Modelling Report', 'type': 'report'},
        ]
    })

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
        'modelling_report': ['system_capacity', 'panel_count', 'client_name'],
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
