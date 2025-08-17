# home_views.py - Updated for database-driven component system

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.db.models import Model
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.http import HttpResponse, JsonResponse
from django.apps import apps
from django.core.cache import cache
from django.views.decorators.cache import cache_page
import logging

# Import your existing models
from siren_web.models import Analysis, facilities, Generatorattributes, \
    Genetics, Optimisations, sirensystem, Scenarios, Settings, Storageattributes, \
    supplyfactors, Technologies, Zones

# Import the new component models
from siren_web.models import SystemComponent, ComponentConnection

logger = logging.getLogger(__name__)

def get_description(name, sirensystem_model):
    """Legacy function - kept for backward compatibility"""
    try:
        sirensystem_obj = get_object_or_404(sirensystem_model, name=name)
        description = sirensystem_obj.description
    except sirensystem_model.DoesNotExist:
        description = "No description available."
    return description

def home_view(request):
    """
    Enhanced home view with database-driven components.
    Maintains backward compatibility with existing functionality.
    """
    # Get session data (existing functionality)
    demand_year = request.session.get('demand_year')
    scenario = request.session.get('scenario')
    config_file = request.session.get('config_file')
    
    # Handle scenario validation (existing functionality)
    try:
        if scenario:
            scenario_obj: Scenarios = Scenarios.objects.get(title=scenario)
    except Scenarios.DoesNotExist:
        scenario = None
        request.session['scenario'] = scenario
        demand_year = None
        request.session['demand_year'] = demand_year
    
    # Handle authentication (existing functionality - unchanged)
    success_message = ""
    member_name = request.GET.get('member_name', '')
    email_address = request.GET.get('email_address', '')
    membership_status = request.GET.get('membership_status', '')
    
    if not request.user.is_authenticated:
        if membership_status:
            user_name = None
            if membership_status == 'Active':
                user_name = 'member'
                user_password = settings.USER_PASS['member_pass']
            elif membership_status == 'Lapsed':
                user_name = 'lapsed'
                user_password = settings.USER_PASS['lapsed_pass']
            elif membership_status == 'Non member':
                user_name = 'subscriber'
                user_password = settings.USER_PASS['subscriber_pass']
            
            try:
                if user_name is not None:
                    user = authenticate(request, username=user_name, password=user_password)
                    if user is not None:
                        login(request, user)
            except UnboundLocalError:
                user = None

    # NEW: Get component information for the diagram
    components = SystemComponent.objects.filter(is_active=True).select_related().order_by('component_type', 'name')
    connections = ComponentConnection.objects.filter(is_active=True).select_related('from_component', 'to_component')

    # Base context (existing + new)
    context = {
        'home_view_url': reverse('home_view'),
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
        'success_message': success_message,
        'components': components,
        'connections': connections,
    }

    # Handle AJAX requests for component details
    component_name = request.GET.get('component')  # NEW parameter name
    table = request.GET.get('table')  # Legacy parameter name
    
    # Support both new 'component' and legacy 'table' parameters
    requested_component = component_name or table
    
    if requested_component:
        return handle_component_request(request, requested_component, context)
    
    # Render the main template
    return render(request, 'home_alt.html', context)

def handle_component_request(request, component_name, base_context):
    """
    Handle AJAX requests for component details.
    Supports both new database-driven components and legacy hard-coded components.
    """
    try:
        # Try to get component from database first (NEW WAY)
        component = SystemComponent.objects.get(name=component_name, is_active=True)
        return get_database_component_details(component)
        
    except SystemComponent.DoesNotExist:
        # Fall back to legacy method (BACKWARD COMPATIBILITY)
        logger.info(f"Component '{component_name}' not found in database, trying legacy method")
        return get_legacy_component_details(component_name, base_context)

def get_database_component_details(component):
    """
    Get component details from the new database-driven system.
    """
    try:
        # Get column names and sample data
        column_names, sample_data = component.get_sample_data(limit=5)
        
        return JsonResponse({
            'status': 'success',
            'component_name': component.display_name,
            'component_description': component.description,
            'component_type': component.component_type,
            'column_names': column_names,
            'sample_data': sample_data,
        })
        
    except Exception as e:
        logger.error(f"Error getting database component details for {component.name}: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Error loading component data: {str(e)}'
        })

def get_legacy_component_details(table_name, context):
    """
    Legacy method for getting component details.
    Maintains backward compatibility with existing hard-coded components.
    """
    # Legacy dictionary mapping table names to their respective model classes
    legacy_models = {
        'Analysis': Analysis,
        'Facilities': facilities,
        'Generatorattributes': Generatorattributes,
        'Genetics': Genetics,
        'Optimisations': Optimisations,
        'Scenarios': Scenarios,
        'Settings': Settings,
        'Storageattributes': Storageattributes,
        'SupplyFactors': supplyfactors,
        'Technologies': Technologies,
        'Zones': Zones,
        # Add legacy module mappings
        'Powermap': None,
        'Powermatch': None,
        'Powerplot': None,
        'SAM': None,
        'MAP': None,
        'Weather': None,
        'Demand': None,
        'Variations': None,
    }

    model_class = legacy_models.get(table_name)

    if model_class and issubclass(model_class, Model):
        try:
            # Get sample data from the model
            sample_data = [list(row) for row in model_class.objects.all()[:5].values_list()]
            column_names = [field.name for field in model_class._meta.fields]
            
            # Get description from legacy sirensystem model
            description = get_description(table_name, sirensystem)
            
            return JsonResponse({
                'status': 'success',
                'model_name': table_name,  # Legacy field name
                'component_name': table_name,  # New field name
                'model_description': str(description),  # Legacy field name
                'component_description': str(description),  # New field name
                'component_type': 'model',  # Assume model for legacy items
                'sample_data': sample_data,
                'column_names': column_names,
            })
            
        except Exception as e:
            logger.error(f"Error getting legacy component details for {table_name}: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': f'Error loading legacy component data: {str(e)}'
            })
    else:
        # Handle legacy modules (non-model components)
        legacy_module_descriptions = {
            'Powermap': 'Power generation mapping and visualization module',
            'Powermatch': 'Power supply and demand matching analysis module',
            'Powerplot': 'Power generation plotting and charting module',
            'SAM': 'System Advisor Model integration module',
            'MAP': 'Geographic mapping and spatial analysis module',
            'Weather': 'Weather data processing and forecasting module',
            'Demand': 'Energy demand analysis and forecasting module',
            'Variations': 'Scenario variations and sensitivity analysis module',
        }
        
        description = legacy_module_descriptions.get(table_name, f'{table_name} processing module')
        
        return JsonResponse({
            'status': 'success',
            'model_name': table_name,
            'component_name': table_name,
            'model_description': description,
            'component_description': description,
            'component_type': 'module',
            'sample_data': [],
            'column_names': [],
        })

@cache_page(60 * 15)  # Cache for 15 minutes
def get_component_config(request):
    """
    NEW: API endpoint to get component configuration for frontend.
    Returns all active components and their connections as JSON.
    """
    try:
        components = SystemComponent.objects.filter(is_active=True).select_related()
        connections = ComponentConnection.objects.filter(is_active=True).select_related(
            'from_component', 'to_component'
        )
        
        component_data = []
        for component in components:
            component_data.append({
                'name': component.name,
                'display_name': component.display_name,
                'type': component.component_type,
                'description': component.description,
                'position': {
                    'x': component.position_x,
                    'y': component.position_y,
                    'width': component.width,
                    'height': component.height,
                },
                'color_scheme': component.color_scheme,
                'model_class': component.model_class_name,
            })
        
        connection_data = []
        for connection in connections:
            connection_data.append({
                'from': connection.from_component.name,
                'to': connection.to_component.name,
                'type': connection.connection_type,
                'description': connection.description,
            })
        
        return JsonResponse({
            'status': 'success',
            'components': component_data,
            'connections': connection_data,
        })
        
    except Exception as e:
        logger.error(f"Error getting component configuration: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Error loading component configuration: {str(e)}'
        })

def get_component_details(request, component_name):
    """
    NEW: Dedicated API endpoint for getting detailed component information.
    """
    try:
        component = get_object_or_404(SystemComponent, name=component_name, is_active=True)
        column_names, sample_data = component.get_sample_data(limit=10)
        
        # Get additional metadata if it's a model component
        model_info = {}
        if component.component_type == 'model' and component.model_class_name:
            model_class = component.get_model_class()
            if model_class:
                try:
                    model_info = {
                        'total_records': model_class.objects.count(),
                        'model_fields': [
                            {
                                'name': field.name,
                                'type': field.get_internal_type(),
                                'verbose_name': str(field.verbose_name),
                                'help_text': field.help_text,
                            }
                            for field in model_class._meta.fields
                        ]
                    }
                except Exception as e:
                    logger.warning(f"Could not get model info for {component.name}: {str(e)}")
        
        return JsonResponse({
            'status': 'success',
            'component': {
                'name': component.name,
                'display_name': component.display_name,
                'type': component.component_type,
                'description': component.description,
                'position': {
                    'x': component.position_x,
                    'y': component.position_y,
                    'width': component.width,
                    'height': component.height,
                },
                'is_active': component.is_active,
                'created_at': component.created_at.isoformat(),
                'updated_at': component.updated_at.isoformat(),
            },
            'data': {
                'column_names': column_names,
                'sample_data': sample_data,
            },
            'model_info': model_info,
            'connections': {
                'incoming': [
                    {
                        'from': conn.from_component.name,
                        'from_display': conn.from_component.display_name,
                        'type': conn.connection_type,
                        'description': conn.description,
                    }
                    for conn in component.incoming_connections.filter(is_active=True)
                ],
                'outgoing': [
                    {
                        'to': conn.to_component.name,
                        'to_display': conn.to_component.display_name,
                        'type': conn.connection_type,
                        'description': conn.description,
                    }
                    for conn in component.outgoing_connections.filter(is_active=True)
                ]
            }
        })
        
    except SystemComponent.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': f'Component "{component_name}" not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error getting component details for {component_name}: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Error loading component details: {str(e)}'
        }, status=500)

# NEW: Utility functions for component management

def refresh_component_cache(request):
    """
    API endpoint to refresh component configuration cache.
    Useful for admin users after making changes.
    """
    if not request.user.is_staff:
        return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
    
    try:
        # Clear relevant caches
        cache.delete_many([
            'component_config',
            'component_list',
            'connection_list'
        ])
        
        return JsonResponse({
            'status': 'success',
            'message': 'Component configuration cache refreshed'
        })
    except Exception as e:
        logger.error(f"Error refreshing component cache: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Error refreshing cache: {str(e)}'
        })

def validate_component_models(request):
    """
    API endpoint to validate that all component model classes exist and are accessible.
    Useful for debugging after code changes.
    """
    if not request.user.is_staff:
        return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
    
    results = []
    components = SystemComponent.objects.filter(component_type='model', is_active=True)
    
    for component in components:
        result = {
            'name': component.name,
            'model_class_name': component.model_class_name,
            'status': 'unknown'
        }
        
        try:
            model_class = component.get_model_class()
            if model_class:
                # Try to access the model
                count = model_class.objects.count()
                result['status'] = 'success'
                result['record_count'] = count
                result['message'] = f'Model accessible with {count} records'
            else:
                result['status'] = 'error'
                result['message'] = 'Model class not found'
        except Exception as e:
            result['status'] = 'error'
            result['message'] = str(e)
        
        results.append(result)
    
    return JsonResponse({
        'status': 'success',
        'validation_results': results,
        'summary': {
            'total_components': len(results),
            'successful': len([r for r in results if r['status'] == 'success']),
            'failed': len([r for r in results if r['status'] == 'error']),
        }
    })
    