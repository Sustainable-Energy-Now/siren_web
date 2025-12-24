"""
Django views for demand factor management
CRUD operations for DemandFactorType and DemandFactor models
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.db.models import Q, Count
from siren_web.models import (
    DemandFactorType, DemandFactor,
    Scenarios
)
from common.decorators import settings_required
import json


# ============================================================================
# DEMAND FACTOR TYPE VIEWS
# ============================================================================

@login_required
def factor_type_list(request):
    """List all demand factor types"""
    search_query = request.GET.get('search', '')

    factor_types = DemandFactorType.objects.annotate(
        instance_count=Count('factor_instances')
    ).all()

    if search_query:
        factor_types = factor_types.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    context = {
        'factor_types': factor_types,
        'search_query': search_query
    }

    return render(request, 'demand_factors/factor_type_list.html', context)

@login_required
def factor_type_create(request):
    """Create a new demand factor type"""
    if request.method == 'POST':
        try:
            name = request.POST.get('name', '').strip()
            description = request.POST.get('description', '').strip()
            category = request.POST.get('category', 'both')
            display_order = int(request.POST.get('display_order', 0))

            if not name:
                messages.error(request, 'Factor type name is required.')
                return redirect('powermatchui:factor_type_create')

            # Check for duplicate
            if DemandFactorType.objects.filter(name=name).exists():
                messages.error(request, f'A factor type named "{name}" already exists.')
                return redirect('powermatchui:factor_type_create')

            factor_type = DemandFactorType.objects.create(
                name=name,
                description=description,
                category=category,
                display_order=display_order,
                is_system_default=False
            )

            messages.success(request, f'Factor type "{name}" created successfully.')
            return redirect('powermatchui:factor_type_list')

        except Exception as e:
            messages.error(request, f'Error creating factor type: {str(e)}')
            return redirect('powermatchui:factor_type_create')

    context = {
        'categories': DemandFactorType.CATEGORY_CHOICES
    }
    return render(request, 'demand_factors/factor_type_form.html', context)

@login_required
def factor_type_edit(request, pk):
    """Edit an existing demand factor type"""
    factor_type = get_object_or_404(DemandFactorType, pk=pk)

    if request.method == 'POST':
        try:
            name = request.POST.get('name', '').strip()
            description = request.POST.get('description', '').strip()
            category = request.POST.get('category', 'both')
            display_order = int(request.POST.get('display_order', 0))

            if not name:
                messages.error(request, 'Factor type name is required.')
                return redirect('powermatchui:factor_type_edit', pk=pk)

            # Check for duplicate (excluding current)
            if DemandFactorType.objects.filter(name=name).exclude(pk=pk).exists():
                messages.error(request, f'A factor type named "{name}" already exists.')
                return redirect('powermatchui:factor_type_edit', pk=pk)

            factor_type.name = name
            factor_type.description = description
            factor_type.category = category
            factor_type.display_order = display_order
            factor_type.save()

            messages.success(request, f'Factor type "{name}" updated successfully.')
            return redirect('powermatchui:factor_type_list')

        except Exception as e:
            messages.error(request, f'Error updating factor type: {str(e)}')
            return redirect('powermatchui:factor_type_edit', pk=pk)

    context = {
        'factor_type': factor_type,
        'categories': DemandFactorType.CATEGORY_CHOICES,
        'editing': True
    }
    return render(request, 'demand_factors/factor_type_form.html', context)

@require_POST
@login_required
def factor_type_delete(request, pk):
    """Delete a demand factor type"""
    factor_type = get_object_or_404(DemandFactorType, pk=pk)

    # Check if it has associated instances
    instance_count = factor_type.factor_instances.count()
    if instance_count > 0:
        messages.error(
            request,
            f'Cannot delete "{factor_type.name}" - it has {instance_count} factor instance(s). '
            f'Delete those first.'
        )
        return redirect('powermatchui:factor_type_list')

    name = factor_type.name
    factor_type.delete()

    messages.success(request, f'Factor type "{name}" deleted successfully.')
    return redirect('powermatchui:factor_type_list')

# ============================================================================
# DEMAND FACTOR INSTANCE VIEWS
# ============================================================================

@login_required
def factor_list(request):
    """List demand factor instances with filtering"""
    scenario_filter = request.GET.get('scenario', '')
    factor_type_filter = request.GET.get('factor_type', '')
    active_only = request.GET.get('active_only', 'false') == 'true'

    factors = DemandFactor.objects.select_related(
        'factor_type', 'scenario'
    ).all().order_by('scenario__title', 'factor_type__display_order')

    if scenario_filter:
        if scenario_filter == 'null':
            factors = factors.filter(scenario__isnull=True)
        else:
            factors = factors.filter(scenario__idscenarios=scenario_filter)

    if factor_type_filter:
        factors = factors.filter(factor_type__iddemandfactortype=factor_type_filter)

    if active_only:
        factors = factors.filter(is_active=True)

    # Pagination
    paginator = Paginator(factors, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'scenarios': Scenarios.objects.all().order_by('title'),
        'factor_types': DemandFactorType.objects.all().order_by('display_order', 'name'),
        'scenario_filter': scenario_filter,
        'factor_type_filter': factor_type_filter,
        'active_only': active_only
    }

    return render(request, 'demand_factors/factor_list.html', context)

@login_required
def factor_create(request):
    """Create a new demand factor instance"""
    if request.method == 'POST':
        try:
            factor_type_id = request.POST.get('factor_type')
            scenario_id = request.POST.get('scenario')
            base_year = int(request.POST.get('base_year', 2024))

            # Percentages
            base_pct_op = float(request.POST.get('base_percentage_operational', 0.0))
            base_pct_und = float(request.POST.get('base_percentage_underlying', 0.0))

            # Growth parameters
            growth_rate = float(request.POST.get('growth_rate', 0.02))
            growth_type = request.POST.get('growth_type', 'exponential')
            saturation_multiplier = float(request.POST.get('saturation_multiplier', 2.0))
            midpoint_year = int(request.POST.get('midpoint_year', 2035))

            # Time-varying config (JSON)
            time_varying_str = request.POST.get('time_varying_config', '').strip()
            time_varying_config = None
            if time_varying_str:
                try:
                    time_varying_config = json.loads(time_varying_str)
                except json.JSONDecodeError:
                    messages.error(request, 'Invalid JSON format for time-varying configuration.')
                    return redirect('powermatchui:factor_create')

            # Notes
            notes = request.POST.get('notes', '').strip()
            is_active = request.POST.get('is_active') == 'on'

            # Validation
            factor_type = get_object_or_404(DemandFactorType, pk=factor_type_id)
            scenario = get_object_or_404(Scenarios, pk=scenario_id) if scenario_id else None

            # Check for duplicate
            if DemandFactor.objects.filter(factor_type=factor_type, scenario=scenario).exists():
                messages.error(
                    request,
                    f'A factor for "{factor_type.name}" already exists in this scenario.'
                )
                return redirect('powermatchui:factor_create')

            factor = DemandFactor.objects.create(
                factor_type=factor_type,
                scenario=scenario,
                base_year=base_year,
                base_percentage_operational=base_pct_op,
                base_percentage_underlying=base_pct_und,
                growth_rate=growth_rate,
                growth_type=growth_type,
                saturation_multiplier=saturation_multiplier,
                midpoint_year=midpoint_year,
                time_varying_config=time_varying_config,
                notes=notes,
                is_active=is_active
            )

            messages.success(request, f'Demand factor "{factor_type.name}" created successfully.')
            return redirect('powermatchui:factor_list')

        except Exception as e:
            messages.error(request, f'Error creating demand factor: {str(e)}')
            return redirect('powermatchui:factor_create')

    context = {
        'factor_types': DemandFactorType.objects.all().order_by('display_order', 'name'),
        'scenarios': Scenarios.objects.all().order_by('title'),
        'growth_types': DemandFactor.GROWTH_TYPE_CHOICES
    }
    return render(request, 'demand_factors/factor_form.html', context)

@login_required
def factor_edit(request, pk):
    """Edit an existing demand factor instance"""
    factor = get_object_or_404(DemandFactor.objects.select_related('factor_type', 'scenario'), pk=pk)

    if request.method == 'POST':
        try:
            # Update fields
            factor.base_year = int(request.POST.get('base_year', 2024))
            factor.base_percentage_operational = float(request.POST.get('base_percentage_operational', 0.0))
            factor.base_percentage_underlying = float(request.POST.get('base_percentage_underlying', 0.0))
            factor.growth_rate = float(request.POST.get('growth_rate', 0.02))
            factor.growth_type = request.POST.get('growth_type', 'exponential')
            factor.saturation_multiplier = float(request.POST.get('saturation_multiplier', 2.0))
            factor.midpoint_year = int(request.POST.get('midpoint_year', 2035))
            factor.notes = request.POST.get('notes', '').strip()
            factor.is_active = request.POST.get('is_active') == 'on'

            # Time-varying config
            time_varying_str = request.POST.get('time_varying_config', '').strip()
            if time_varying_str:
                try:
                    factor.time_varying_config = json.loads(time_varying_str)
                except json.JSONDecodeError:
                    messages.error(request, 'Invalid JSON format for time-varying configuration.')
                    return redirect('powermatchui:factor_edit', pk=pk)
            else:
                factor.time_varying_config = None

            factor.save()

            messages.success(request, f'Demand factor "{factor.factor_type.name}" updated successfully.')
            return redirect('powermatchui:factor_list')

        except Exception as e:
            messages.error(request, f'Error updating demand factor: {str(e)}')
            return redirect('powermatchui:factor_edit', pk=pk)

    # Convert time_varying_config to JSON string for display
    time_varying_str = ''
    if factor.time_varying_config:
        time_varying_str = json.dumps(factor.time_varying_config, indent=2)

    context = {
        'factor': factor,
        'growth_types': DemandFactor.GROWTH_TYPE_CHOICES,
        'time_varying_str': time_varying_str,
        'editing': True
    }
    return render(request, 'demand_factors/factor_form.html', context)

@require_POST
@login_required
def factor_delete(request, pk):
    """Delete a demand factor instance"""
    factor = get_object_or_404(DemandFactor, pk=pk)

    factor_name = f"{factor.factor_type.name}"
    scenario_name = factor.scenario.title if factor.scenario else "Default"

    factor.delete()

    messages.success(request, f'Demand factor "{factor_name}" ({scenario_name}) deleted successfully.')
    return redirect('powermatchui:factor_list')

@require_POST
@login_required
def factor_toggle_active(request, pk):
    """Toggle active status of a demand factor"""
    factor = get_object_or_404(DemandFactor, pk=pk)

    factor.is_active = not factor.is_active
    factor.save()

    status = "activated" if factor.is_active else "deactivated"
    messages.success(request, f'Demand factor "{factor.factor_type.name}" {status}.')

    return redirect('powermatchui:factor_list')

# ============================================================================
# SCENARIO FACTOR ASSIGNMENT VIEWS
# ============================================================================

@login_required
def scenario_factor_assignment(request, scenario_id):
    """Assign/configure factors for a specific scenario"""
    scenario = get_object_or_404(Scenarios, pk=scenario_id)

    # Get all factor types
    factor_types = DemandFactorType.objects.all().order_by('display_order', 'name')

    # Get existing factors for this scenario
    existing_factors = {
        f.factor_type.iddemandfactortype: f
        for f in DemandFactor.objects.filter(scenario=scenario).select_related('factor_type')
    }

    # Calculate totals
    total_op_pct = sum(f.base_percentage_operational for f in existing_factors.values() if f.is_active)
    total_und_pct = sum(f.base_percentage_underlying for f in existing_factors.values() if f.is_active)

    context = {
        'scenario': scenario,
        'factor_types': factor_types,
        'existing_factors': existing_factors,
        'total_operational_pct': total_op_pct,
        'total_underlying_pct': total_und_pct
    }

    return render(request, 'demand_factors/scenario_assignment.html', context)

@require_http_methods(["POST"])
@login_required
def bulk_update_scenario_factors(request, scenario_id):
    """Bulk update all factors for a scenario"""
    scenario = get_object_or_404(Scenarios, pk=scenario_id)

    try:
        data = json.loads(request.body)
        factors_data = data.get('factors', [])

        for factor_data in factors_data:
            factor_type_id = factor_data.get('factor_type_id')

            # Get or create factor
            factor, created = DemandFactor.objects.get_or_create(
                factor_type_id=factor_type_id,
                scenario=scenario,
                defaults={
                    'base_year': 2024,
                    'growth_rate': 0.02,
                    'growth_type': 'exponential'
                }
            )

            # Update values
            factor.base_percentage_operational = float(factor_data.get('base_pct_op', 0.0))
            factor.base_percentage_underlying = float(factor_data.get('base_pct_und', 0.0))
            factor.growth_rate = float(factor_data.get('growth_rate', 0.02))
            factor.growth_type = factor_data.get('growth_type', 'exponential')
            factor.is_active = factor_data.get('is_active', True)

            factor.save()

        return JsonResponse({'success': True, 'message': 'Factors updated successfully'})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


# ============================================================================
# API ENDPOINTS FOR AJAX
# ============================================================================

@require_http_methods(["GET"])
@login_required
def api_get_factor_details(request, pk):
    """Get detailed information about a demand factor (for AJAX)"""
    factor = get_object_or_404(
        DemandFactor.objects.select_related('factor_type', 'scenario'),
        pk=pk
    )

    data = {
        'id': factor.iddemandfactor,
        'factor_type': {
            'id': factor.factor_type.iddemandfactortype,
            'name': factor.factor_type.name,
            'category': factor.factor_type.category
        },
        'scenario': {
            'id': factor.scenario.idscenarios if factor.scenario else None,
            'title': factor.scenario.title if factor.scenario else 'Default'
        },
        'base_year': factor.base_year,
        'base_percentage_operational': factor.base_percentage_operational,
        'base_percentage_underlying': factor.base_percentage_underlying,
        'growth_rate': factor.growth_rate,
        'growth_type': factor.growth_type,
        'saturation_multiplier': factor.saturation_multiplier,
        'midpoint_year': factor.midpoint_year,
        'time_varying_config': factor.time_varying_config,
        'is_active': factor.is_active,
        'notes': factor.notes
    }

    return JsonResponse(data)


@require_http_methods(["GET"])
@login_required
def api_scenario_factor_summary(request, scenario_id):
    """Get summary of all factors for a scenario (for AJAX)"""
    scenario = get_object_or_404(Scenarios, pk=scenario_id)

    factors = DemandFactor.objects.filter(
        scenario=scenario,
        is_active=True
    ).select_related('factor_type')

    factor_list = []
    total_op = 0.0
    total_und = 0.0

    for factor in factors:
        factor_list.append({
            'name': factor.factor_type.name,
            'operational_pct': factor.base_percentage_operational,
            'underlying_pct': factor.base_percentage_underlying,
            'growth_rate': factor.growth_rate,
            'growth_type': factor.growth_type
        })
        total_op += factor.base_percentage_operational
        total_und += factor.base_percentage_underlying

    data = {
        'scenario': {
            'id': scenario.idscenarios,
            'title': scenario.title
        },
        'factors': factor_list,
        'totals': {
            'operational_pct': total_op,
            'underlying_pct': total_und
        },
        'warnings': []
    }

    # Add warnings
    if total_op > 100.0:
        data['warnings'].append(f'Operational percentages sum to {total_op:.1f}% (> 100%)')
    if total_und > 100.0:
        data['warnings'].append(f'Underlying percentages sum to {total_und:.1f}% (> 100%)')

    return JsonResponse(data)
