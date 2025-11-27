"""
SWIS Renewable Energy Target Management Views

This module provides views for managing:
- RenewableEnergyTarget: Annual RE percentage targets
- TargetScenario: 2040 projection scenarios

Views include list, create, update, and delete operations for both models.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST, require_http_methods
from django.http import JsonResponse
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.utils import timezone

from siren_web.models import RenewableEnergyTarget, TargetScenario
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Renewable Energy Targets List View
# =============================================================================

def ret_targets_list(request):
    """
    Main view for displaying and managing RE targets and scenarios.
    Shows all targets chronologically and active scenarios.
    """
    # Get all targets ordered by year
    targets = RenewableEnergyTarget.objects.all().order_by('target_year')
    
    # Get all scenarios
    scenarios = TargetScenario.objects.all().order_by('scenario_type', 'scenario_name')
    active_scenarios = scenarios.filter(is_active=True)
    
    # Calculate scenario status vs 2040 target
    target_2040 = targets.filter(target_year=2040).first()
    scenarios_with_status = []
    for scenario in scenarios:
        status = scenario.get_status_vs_target(2040)
        scenarios_with_status.append({
            'scenario': scenario,
            'status': status,
            'total_generation': scenario.total_generation_2040
        })
    
    # Get key milestone targets
    milestone_years = [2030, 2035, 2040]
    milestones = targets.filter(target_year__in=milestone_years)
    
    context = {
        'targets': targets,
        'scenarios': scenarios,
        'scenarios_with_status': scenarios_with_status,
        'active_scenarios': active_scenarios,
        'target_2040': target_2040,
        'milestones': milestones,
        'scenario_type_choices': TargetScenario._meta.get_field('scenario_type').choices,
        'now': timezone.now(),
    }
    
    return render(request, 'ret_dashboard/targets.html', context)


# =============================================================================
# Renewable Energy Target CRUD
# =============================================================================

@require_http_methods(["GET", "POST"])
def ret_target_create(request):
    """Create a new Renewable Energy Target."""
    if request.method == 'POST':
        try:
            target_year = int(request.POST.get('target_year'))
            target_percentage = float(request.POST.get('target_percentage'))
            target_emissions = request.POST.get('target_emissions_tonnes')
            description = request.POST.get('description', '').strip()
            is_interim = request.POST.get('is_interim_target') == 'on'
            
            # Validate
            if target_year < 2020 or target_year > 2100:
                messages.error(request, 'Target year must be between 2020 and 2100.')
                return redirect('ret_targets_list')
            
            if target_percentage < 0 or target_percentage > 100:
                messages.error(request, 'Target percentage must be between 0 and 100.')
                return redirect('ret_targets_list')
            
            # Create target
            target = RenewableEnergyTarget.objects.create(
                target_year=target_year,
                target_percentage=target_percentage,
                target_emissions_tonnes=float(target_emissions) if target_emissions else None,
                description=description if description else None,
                is_interim_target=is_interim
            )
            
            messages.success(request, f'Successfully created target for {target_year}.')
            logger.info(f"Created RE target for {target_year}: {target_percentage}%")
            
        except IntegrityError:
            messages.error(request, f'A target for year {target_year} already exists.')
        except ValueError as e:
            messages.error(request, f'Invalid value: {str(e)}')
        except Exception as e:
            logger.error(f"Error creating RE target: {str(e)}", exc_info=True)
            messages.error(request, f'Error creating target: {str(e)}')
    
    return redirect('ret_targets_list')

@require_http_methods(["GET", "POST"])
def ret_target_update(request, target_id):
    """Update an existing Renewable Energy Target."""
    target = get_object_or_404(RenewableEnergyTarget, id=target_id)
    
    if request.method == 'POST':
        try:
            target.target_percentage = float(request.POST.get('target_percentage'))
            target_emissions = request.POST.get('target_emissions_tonnes')
            target.target_emissions_tonnes = float(target_emissions) if target_emissions else None
            target.description = request.POST.get('description', '').strip() or None
            target.is_interim_target = request.POST.get('is_interim_target') == 'on'
            
            # Validate
            if target.target_percentage < 0 or target.target_percentage > 100:
                messages.error(request, 'Target percentage must be between 0 and 100.')
                return redirect('ret_targets_list')
            
            target.save()
            messages.success(request, f'Successfully updated target for {target.target_year}.')
            logger.info(f"Updated RE target for {target.target_year}: {target.target_percentage}%")
            
        except ValueError as e:
            messages.error(request, f'Invalid value: {str(e)}')
        except Exception as e:
            logger.error(f"Error updating RE target: {str(e)}", exc_info=True)
            messages.error(request, f'Error updating target: {str(e)}')
    
    return redirect('ret_targets_list')

@require_POST
def ret_target_delete(request, target_id):
    """Delete a Renewable Energy Target."""
    target = get_object_or_404(RenewableEnergyTarget, id=target_id)
    year = target.target_year
    
    try:
        target.delete()
        messages.success(request, f'Successfully deleted target for {year}.')
        logger.info(f"Deleted RE target for {year}")
    except Exception as e:
        logger.error(f"Error deleting RE target: {str(e)}", exc_info=True)
        messages.error(request, f'Error deleting target: {str(e)}')
    
    return redirect('ret_targets_list')

# =============================================================================
# Target Scenario CRUD
# =============================================================================

@require_http_methods(["GET", "POST"])
def scenario_create(request):
    """Create a new Target Scenario."""
    if request.method == 'POST':
        try:
            scenario_name = request.POST.get('scenario_name', '').strip()
            scenario_type = request.POST.get('scenario_type')
            
            if not scenario_name:
                messages.error(request, 'Scenario name is required.')
                return redirect('ret_targets_list')
            
            # Create scenario with all fields
            scenario = TargetScenario.objects.create(
                scenario_name=scenario_name,
                scenario_type=scenario_type,
                description=request.POST.get('description', '').strip(),
                projected_re_percentage_2040=float(request.POST.get('projected_re_percentage_2040', 0)),
                projected_emissions_2040_tonnes=float(request.POST.get('projected_emissions_2040_tonnes', 0)),
                wind_generation_2040=float(request.POST.get('wind_generation_2040', 0)),
                solar_generation_2040=float(request.POST.get('solar_generation_2040', 0)),
                dpv_generation_2040=float(request.POST.get('dpv_generation_2040', 0)),
                biomass_generation_2040=float(request.POST.get('biomass_generation_2040', 0)),
                gas_generation_2040=float(request.POST.get('gas_generation_2040', 0)),
                probability_percentage=float(request.POST.get('probability_percentage')) if request.POST.get('probability_percentage') else None,
                is_active=request.POST.get('is_active') == 'on'
            )
            
            messages.success(request, f'Successfully created scenario: {scenario_name}')
            logger.info(f"Created scenario: {scenario_name}")
            
        except IntegrityError:
            messages.error(request, f'A scenario named "{scenario_name}" already exists.')
        except ValueError as e:
            messages.error(request, f'Invalid value: {str(e)}')
        except Exception as e:
            logger.error(f"Error creating scenario: {str(e)}", exc_info=True)
            messages.error(request, f'Error creating scenario: {str(e)}')
    
    return redirect('ret_targets_list')


@require_http_methods(["GET", "POST"])
def scenario_update(request, scenario_id):
    """Update an existing Target Scenario."""
    scenario = get_object_or_404(TargetScenario, id=scenario_id)
    
    if request.method == 'POST':
        try:
            scenario.scenario_name = request.POST.get('scenario_name', '').strip()
            scenario.scenario_type = request.POST.get('scenario_type')
            scenario.description = request.POST.get('description', '').strip()
            scenario.projected_re_percentage_2040 = float(request.POST.get('projected_re_percentage_2040', 0))
            scenario.projected_emissions_2040_tonnes = float(request.POST.get('projected_emissions_2040_tonnes', 0))
            scenario.wind_generation_2040 = float(request.POST.get('wind_generation_2040', 0))
            scenario.solar_generation_2040 = float(request.POST.get('solar_generation_2040', 0))
            scenario.dpv_generation_2040 = float(request.POST.get('dpv_generation_2040', 0))
            scenario.biomass_generation_2040 = float(request.POST.get('biomass_generation_2040', 0))
            scenario.gas_generation_2040 = float(request.POST.get('gas_generation_2040', 0))
            scenario.probability_percentage = float(request.POST.get('probability_percentage')) if request.POST.get('probability_percentage') else None
            scenario.is_active = request.POST.get('is_active') == 'on'
            
            if not scenario.scenario_name:
                messages.error(request, 'Scenario name is required.')
                return redirect('ret_targets_list')
            
            scenario.save()
            messages.success(request, f'Successfully updated scenario: {scenario.scenario_name}')
            logger.info(f"Updated scenario: {scenario.scenario_name}")
            
        except ValueError as e:
            messages.error(request, f'Invalid value: {str(e)}')
        except Exception as e:
            logger.error(f"Error updating scenario: {str(e)}", exc_info=True)
            messages.error(request, f'Error updating scenario: {str(e)}')
    
    return redirect('ret_targets_list')

@require_POST
def scenario_delete(request, scenario_id):
    """Delete a Target Scenario."""
    scenario = get_object_or_404(TargetScenario, id=scenario_id)
    name = scenario.scenario_name
    
    try:
        scenario.delete()
        messages.success(request, f'Successfully deleted scenario: {name}')
        logger.info(f"Deleted scenario: {name}")
    except Exception as e:
        logger.error(f"Error deleting scenario: {str(e)}", exc_info=True)
        messages.error(request, f'Error deleting scenario: {str(e)}')
    
    return redirect('ret_targets_list')

@require_POST
def scenario_toggle_active(request, scenario_id):
    """Toggle active status of a scenario."""
    scenario = get_object_or_404(TargetScenario, id=scenario_id)
    
    try:
        scenario.is_active = not scenario.is_active
        scenario.save()
        status = 'activated' if scenario.is_active else 'deactivated'
        messages.success(request, f'Successfully {status} scenario: {scenario.scenario_name}')
    except Exception as e:
        logger.error(f"Error toggling scenario: {str(e)}", exc_info=True)
        messages.error(request, f'Error toggling scenario: {str(e)}')
    
    return redirect('ret_targets_list')

# =============================================================================
# API Endpoints (JSON)
# =============================================================================

def api_targets_list(request):
    """API endpoint to get all targets as JSON."""
    targets = RenewableEnergyTarget.objects.all().order_by('target_year')
    
    data = [{
        'id': t.id,
        'target_year': t.target_year,
        'target_percentage': t.target_percentage,
        'target_emissions_tonnes': t.target_emissions_tonnes,
        'description': t.description,
        'is_interim_target': t.is_interim_target,
        'created_at': t.created_at.isoformat() if t.created_at else None,
        'updated_at': t.updated_at.isoformat() if t.updated_at else None,
    } for t in targets]
    
    return JsonResponse({'targets': data})

def api_scenarios_list(request):
    """API endpoint to get all scenarios as JSON."""
    scenarios = TargetScenario.objects.all().order_by('scenario_type')
    
    data = [{
        'id': s.id,
        'scenario_name': s.scenario_name,
        'scenario_type': s.scenario_type,
        'description': s.description,
        'projected_re_percentage_2040': s.projected_re_percentage_2040,
        'projected_emissions_2040_tonnes': s.projected_emissions_2040_tonnes,
        'wind_generation_2040': s.wind_generation_2040,
        'solar_generation_2040': s.solar_generation_2040,
        'dpv_generation_2040': s.dpv_generation_2040,
        'biomass_generation_2040': s.biomass_generation_2040,
        'gas_generation_2040': s.gas_generation_2040,
        'total_generation_2040': s.total_generation_2040,
        'probability_percentage': s.probability_percentage,
        'is_active': s.is_active,
        'status_vs_target': s.get_status_vs_target(2040),
        'created_at': s.created_at.isoformat() if s.created_at else None,
        'updated_at': s.updated_at.isoformat() if s.updated_at else None,
    } for s in scenarios]
    
    return JsonResponse({'scenarios': data})

def api_target_detail(request, target_id):
    """API endpoint to get a single target."""
    target = get_object_or_404(RenewableEnergyTarget, id=target_id)
    
    return JsonResponse({
        'id': target.id,
        'target_year': target.target_year,
        'target_percentage': target.target_percentage,
        'target_emissions_tonnes': target.target_emissions_tonnes,
        'description': target.description,
        'is_interim_target': target.is_interim_target,
        'created_at': target.created_at.isoformat() if target.created_at else None,
        'updated_at': target.updated_at.isoformat() if target.updated_at else None,
    })

def api_scenario_detail(request, scenario_id):
    """API endpoint to get a single scenario."""
    scenario = get_object_or_404(TargetScenario, id=scenario_id)
    
    return JsonResponse({
        'id': scenario.id,
        'scenario_name': scenario.scenario_name,
        'scenario_type': scenario.scenario_type,
        'description': scenario.description,
        'projected_re_percentage_2040': scenario.projected_re_percentage_2040,
        'projected_emissions_2040_tonnes': scenario.projected_emissions_2040_tonnes,
        'wind_generation_2040': scenario.wind_generation_2040,
        'solar_generation_2040': scenario.solar_generation_2040,
        'dpv_generation_2040': scenario.dpv_generation_2040,
        'biomass_generation_2040': scenario.biomass_generation_2040,
        'gas_generation_2040': scenario.gas_generation_2040,
        'total_generation_2040': scenario.total_generation_2040,
        'probability_percentage': scenario.probability_percentage,
        'is_active': scenario.is_active,
        'status_vs_target': scenario.get_status_vs_target(2040),
        'created_at': scenario.created_at.isoformat() if scenario.created_at else None,
        'updated_at': scenario.updated_at.isoformat() if scenario.updated_at else None,
    })
