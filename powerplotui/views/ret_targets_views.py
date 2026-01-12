"""
SWIS Renewable Energy Target Management Views

This module provides views for managing the unified TargetScenario model,
which combines renewable energy targets and projection scenarios.

Views include list, create, update, and delete operations.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST, require_http_methods
from django.http import JsonResponse
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.utils import timezone

from siren_web.models import TargetScenario, Scenarios
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Unified Targets and Scenarios List View
# =============================================================================

def ret_targets_list(request):
    """
    Main view for displaying and managing RE targets and scenarios.
    Shows all target scenarios grouped by year and scenario type.
    Defaults to showing 'base_case' scenarios with option to select others.
    """
    # Get selected scenario_type from query param, default to 'base_case'
    selected_scenario_type = request.GET.get('scenario_type', 'base_case')

    # Get all scenarios ordered by year and type
    all_scenarios = TargetScenario.objects.all().order_by('year', 'scenario_type')

    # Filter by selected scenario_type for the main table
    filtered_scenarios = all_scenarios.filter(scenario_type=selected_scenario_type).order_by('year')

    # Separate targets (major/interim) from ordinary projections
    # targets = filtered_scenarios.filter(target_type__in=['major', 'interim'])
    targets = filtered_scenarios
    active_scenarios = filtered_scenarios.filter(is_active=True)

    # Get key milestone targets for base_case
    milestone_years = [2030, 2035, 2040]
    base_case_milestones = TargetScenario.objects.filter(
        scenario_type='base_case',
        target_type__in=['major', 'interim'],
        year__in=milestone_years
    ).order_by('year')

    # Get all SIREN scenarios for the dropdown
    siren_scenarios = Scenarios.objects.all().order_by('title')

    # Get years that have targets defined
    years_with_targets = list(targets.values_list('year', flat=True).distinct())

    # Get available scenario types for the selector
    available_scenario_types = list(
        all_scenarios.values_list('scenario_type', flat=True).distinct()
    )

    # Format scenario type for display (replace underscores with spaces)
    selected_scenario_type_display = selected_scenario_type.upper().replace('_', ' ')

    context = {
        'targets': targets,
        'active_scenarios': active_scenarios,
        'milestones': base_case_milestones,
        'years_with_targets': years_with_targets,
        'scenario_type_choices': TargetScenario._meta.get_field('scenario_type').choices,
        'target_type_choices': TargetScenario._meta.get_field('target_type').choices,
        'siren_scenarios': siren_scenarios,
        'now': timezone.now(),
        'selected_scenario_type': selected_scenario_type,
        'selected_scenario_type_display': selected_scenario_type_display,
        'available_scenario_types': available_scenario_types,
    }

    return render(request, 'ret_dashboard/targets.html', context)

# =============================================================================
# Unified Target/Scenario CRUD
# =============================================================================

@require_http_methods(["GET", "POST"])
def scenario_create(request):
    """Create a new target or projection scenario."""
    if request.method == 'POST':
        try:
            scenario_name = request.POST.get('scenario_name', '').strip()
            scenario_type = request.POST.get('scenario_type')
            year = int(request.POST.get('year', 2040))
            target_type = request.POST.get('target_type', 'ordinary')

            if not scenario_name:
                messages.error(request, 'Scenario name is required.')
                return redirect('ret_targets_list')

            # Validate year
            if year < 2020 or year > 2100:
                messages.error(request, 'Year must be between 2020 and 2100.')
                return redirect('ret_targets_list')

            # Get scenario FK if provided
            scenario_id = request.POST.get('scenario')
            scenario_obj = None
            if scenario_id:
                try:
                    scenario_obj = Scenarios.objects.get(idscenarios=scenario_id)
                except Scenarios.DoesNotExist:
                    pass

            # Get RE percentage
            target_re_percentage = float(request.POST.get('target_re_percentage', 0))
            if target_re_percentage < 0 or target_re_percentage > 100:
                messages.error(request, 'RE percentage must be between 0 and 100.')
                return redirect('ret_targets_list')

            # Create scenario with all fields
            scenario = TargetScenario.objects.create(
                scenario_name=scenario_name,
                scenario_type=scenario_type,
                scenario=scenario_obj,
                description=request.POST.get('description', '').strip(),
                year=year,
                target_type=target_type,
                operational_demand=float(request.POST.get('operational_demand')) if request.POST.get('operational_demand') else None,
                underlying_demand=float(request.POST.get('underlying_demand')) if request.POST.get('underlying_demand') else None,
                storage=float(request.POST.get('storage')) if request.POST.get('storage') else None,
                target_re_percentage=target_re_percentage,
                target_emissions_tonnes=float(request.POST.get('target_emissions_tonnes')) if request.POST.get('target_emissions_tonnes') else None,
                wind_generation=float(request.POST.get('wind_generation', 0)),
                solar_generation=float(request.POST.get('solar_generation', 0)),
                dpv_generation=float(request.POST.get('dpv_generation', 0)),
                biomass_generation=float(request.POST.get('biomass_generation', 0)),
                gas_generation=float(request.POST.get('gas_generation', 0)),
                probability_percentage=float(request.POST.get('probability_percentage')) if request.POST.get('probability_percentage') else None,
                is_active=request.POST.get('is_active') == 'on'
            )

            target_label = 'target' if target_type in ['major', 'interim'] else 'scenario'
            messages.success(request, f'Successfully created {target_label}: {scenario_name} ({year})')
            logger.info(f"Created {target_label}: {scenario_name} for {year}")

        except IntegrityError as e:
            messages.error(request, f'A scenario of type "{scenario_type}" for year {year} already exists.')
        except ValueError as e:
            messages.error(request, f'Invalid value: {str(e)}')
        except Exception as e:
            logger.error(f"Error creating scenario: {str(e)}", exc_info=True)
            messages.error(request, f'Error creating scenario: {str(e)}')

    return redirect('ret_targets_list')

@require_http_methods(["GET", "POST"])
def scenario_update(request, scenario_id):
    """Update an existing target or projection scenario."""
    scenario = get_object_or_404(TargetScenario, id=scenario_id)

    if request.method == 'POST':
        try:
            scenario.scenario_name = request.POST.get('scenario_name', '').strip()
            scenario.scenario_type = request.POST.get('scenario_type')

            if not scenario.scenario_name:
                messages.error(request, 'Scenario name is required.')
                return redirect('ret_targets_list')

            # Update scenario FK if provided
            siren_scenario_id = request.POST.get('scenario')
            if siren_scenario_id:
                try:
                    scenario.scenario = Scenarios.objects.get(idscenarios=siren_scenario_id)
                except Scenarios.DoesNotExist:
                    scenario.scenario = None
            else:
                scenario.scenario = None

            scenario.description = request.POST.get('description', '').strip()
            scenario.year = int(request.POST.get('year', 2040))
            scenario.target_type = request.POST.get('target_type', 'ordinary')
            scenario.operational_demand = float(request.POST.get('operational_demand')) if request.POST.get('operational_demand') else None
            scenario.underlying_demand = float(request.POST.get('underlying_demand')) if request.POST.get('underlying_demand') else None
            scenario.storage = float(request.POST.get('storage')) if request.POST.get('storage') else None

            # Validate and set RE percentage
            target_re_percentage = float(request.POST.get('target_re_percentage', 0))
            if target_re_percentage < 0 or target_re_percentage > 100:
                messages.error(request, 'RE percentage must be between 0 and 100.')
                return redirect('ret_targets_list')
            scenario.target_re_percentage = target_re_percentage

            scenario.target_emissions_tonnes = float(request.POST.get('target_emissions_tonnes')) if request.POST.get('target_emissions_tonnes') else None
            scenario.wind_generation = float(request.POST.get('wind_generation', 0))
            scenario.solar_generation = float(request.POST.get('solar_generation', 0))
            scenario.dpv_generation = float(request.POST.get('dpv_generation', 0))
            scenario.biomass_generation = float(request.POST.get('biomass_generation', 0))
            scenario.gas_generation = float(request.POST.get('gas_generation', 0))
            scenario.probability_percentage = float(request.POST.get('probability_percentage')) if request.POST.get('probability_percentage') else None
            scenario.is_active = request.POST.get('is_active') == 'on'

            scenario.save()
            target_label = 'target' if scenario.target_type in ['major', 'interim'] else 'scenario'
            messages.success(request, f'Successfully updated {target_label}: {scenario.scenario_name}')
            logger.info(f"Updated {target_label}: {scenario.scenario_name}")

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

def api_scenarios_list(request):
    """API endpoint to get all scenarios as JSON."""
    scenarios = TargetScenario.objects.all().order_by('year', 'scenario_type')

    data = [{
        'id': s.id,
        'scenario_name': s.scenario_name,
        'scenario_type': s.scenario_type,
        'scenario_id': s.scenario.idscenarios if s.scenario else None,
        'scenario_title': s.scenario.title if s.scenario else None,
        'description': s.description,
        'year': s.year,
        'target_type': s.target_type,
        'operational_demand': s.operational_demand,
        'underlying_demand': s.underlying_demand,
        'storage': s.storage,
        'target_re_percentage': s.target_re_percentage,
        'target_emissions_tonnes': s.target_emissions_tonnes,
        'wind_generation': s.wind_generation,
        'solar_generation': s.solar_generation,
        'dpv_generation': s.dpv_generation,
        'biomass_generation': s.biomass_generation,
        'gas_generation': s.gas_generation,
        'total_generation': s.total_generation,
        'probability_percentage': s.probability_percentage,
        'is_active': s.is_active,
        'is_major_target': s.is_major_target,
        'is_interim_target': s.is_interim_target,
        'status_vs_target': s.get_status_vs_target(),
        'created_at': s.created_at.isoformat() if s.created_at else None,
        'updated_at': s.updated_at.isoformat() if s.updated_at else None,
    } for s in scenarios]

    return JsonResponse({'scenarios': data})

def api_scenario_detail(request, scenario_id):
    """API endpoint to get a single scenario with full details."""
    scenario = get_object_or_404(TargetScenario, id=scenario_id)

    return JsonResponse({
        'id': scenario.id,
        'scenario_name': scenario.scenario_name,
        'scenario_type': scenario.scenario_type,
        'scenario_type_display': scenario.get_scenario_type_display(),
        'scenario_id': scenario.scenario.idscenarios if scenario.scenario else None,
        'scenario_title': scenario.scenario.title if scenario.scenario else None,
        'description': scenario.description,
        'year': scenario.year,
        'target_type': scenario.target_type,
        'target_type_display': scenario.get_target_type_display(),
        'operational_demand': scenario.operational_demand,
        'underlying_demand': scenario.underlying_demand,
        'storage': scenario.storage,
        'target_re_percentage': scenario.target_re_percentage,
        'target_emissions_tonnes': scenario.target_emissions_tonnes,
        'wind_generation': scenario.wind_generation,
        'solar_generation': scenario.solar_generation,
        'dpv_generation': scenario.dpv_generation,
        'biomass_generation': scenario.biomass_generation,
        'gas_generation': scenario.gas_generation,
        'total_generation': scenario.total_generation,
        'probability_percentage': scenario.probability_percentage,
        'is_active': scenario.is_active,
        'is_major_target': scenario.is_major_target,
        'is_interim_target': scenario.is_interim_target,
        'status_vs_target': scenario.get_status_vs_target(),
        'created_at': scenario.created_at.isoformat() if scenario.created_at else None,
        'updated_at': scenario.updated_at.isoformat() if scenario.updated_at else None,
    })
