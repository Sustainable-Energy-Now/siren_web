"""
SWIS Risk Analysis Views

This module provides views for:
- Risk scenario management (CRUD)
- Risk event assessment interface
- Scenario comparison
- Dashboard and summary views
- API endpoints for AJAX operations
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST, require_http_methods
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Avg, Count, Q, F
from django.utils import timezone
from django.core.paginator import Paginator
import json
import logging

from siren_web.models import (
    RiskCategory, RiskScenario, RiskEvent,
    RISK_LIKELIHOOD_CHOICES, RISK_CONSEQUENCE_CHOICES
)

logger = logging.getLogger(__name__)


# =============================================================================
# Dashboard and Summary Views
# =============================================================================

def risk_dashboard(request):
    """
    Main dashboard view for SWIS risk analysis.
    Shows overview of all scenarios with risk profiles.
    """
    scenarios = RiskScenario.objects.filter(status='active').prefetch_related('risk_events')
    categories = RiskCategory.objects.filter(is_active=True)

    # Calculate summary statistics
    total_scenarios = scenarios.count()
    total_events = RiskEvent.objects.filter(scenario__status='active').count()

    # Get highest risk scenario
    highest_risk_scenario = None
    highest_score = 0
    for scenario in scenarios:
        score = scenario.get_inherent_risk_score()
        if score and score > highest_score:
            highest_score = score
            highest_risk_scenario = scenario

    # Count severe/high risks
    severe_count = RiskEvent.objects.filter(
        scenario__status='active'
    ).annotate(
        score=F('inherent_likelihood') * F('inherent_consequence')
    ).filter(score__gte=20).count()

    high_count = RiskEvent.objects.filter(
        scenario__status='active'
    ).annotate(
        score=F('inherent_likelihood') * F('inherent_consequence')
    ).filter(score__gte=12, score__lt=20).count()

    context = {
        'scenarios': scenarios,
        'categories': categories,
        'total_scenarios': total_scenarios,
        'total_events': total_events,
        'severe_count': severe_count,
        'high_count': high_count,
        'highest_risk_scenario': highest_risk_scenario,
        'likelihood_choices': RISK_LIKELIHOOD_CHOICES,
        'consequence_choices': RISK_CONSEQUENCE_CHOICES,
    }

    return render(request, 'risk_analysis/dashboard.html', context)


def risk_scenario_detail(request, scenario_id):
    """
    Detailed view of a single risk scenario.
    Shows all risk events by category with heatmap.
    """
    scenario = get_object_or_404(RiskScenario, id=scenario_id)
    categories = RiskCategory.objects.filter(is_active=True)
    events = scenario.risk_events.select_related('category').all()

    # Group events by category
    events_by_category = {}
    for category in categories:
        category_events = events.filter(category=category)
        if category_events.exists():
            events_by_category[category] = category_events

    # Calculate risk counts
    risk_counts = scenario.get_risk_counts_by_level()

    context = {
        'scenario': scenario,
        'categories': categories,
        'events': events,
        'events_by_category': events_by_category,
        'risk_counts': risk_counts,
        'likelihood_choices': RISK_LIKELIHOOD_CHOICES,
        'consequence_choices': RISK_CONSEQUENCE_CHOICES,
    }

    return render(request, 'risk_analysis/scenario_detail.html', context)


def risk_comparison_view(request):
    """
    Compare multiple scenarios side by side.
    Accepts scenario_ids as GET parameters.
    """
    scenario_ids = request.GET.getlist('scenarios')
    all_scenarios = RiskScenario.objects.filter(status__in=['active', 'draft'])
    categories = RiskCategory.objects.filter(is_active=True)

    selected_scenarios = []
    if scenario_ids:
        selected_scenarios = RiskScenario.objects.filter(
            id__in=scenario_ids
        ).prefetch_related('risk_events')

    context = {
        'all_scenarios': all_scenarios,
        'selected_scenarios': selected_scenarios,
        'categories': categories,
        'selected_ids': [int(id) for id in scenario_ids] if scenario_ids else [],
    }

    return render(request, 'risk_analysis/comparison.html', context)


# =============================================================================
# Scenario CRUD Views
# =============================================================================

def scenario_list(request):
    """List all risk scenarios with filtering options."""
    status_filter = request.GET.get('status', '')

    scenarios = RiskScenario.objects.all().prefetch_related('risk_events')

    if status_filter:
        scenarios = scenarios.filter(status=status_filter)

    categories = RiskCategory.objects.filter(is_active=True)

    context = {
        'scenarios': scenarios,
        'categories': categories,
        'status_filter': status_filter,
        'likelihood_choices': RISK_LIKELIHOOD_CHOICES,
        'consequence_choices': RISK_CONSEQUENCE_CHOICES,
    }

    return render(request, 'risk_analysis/scenario_list.html', context)


@require_http_methods(["GET", "POST"])
def scenario_create(request):
    """Create a new risk scenario."""
    categories = RiskCategory.objects.filter(is_active=True)

    if request.method == 'POST':
        try:
            name = request.POST.get('name', '').strip()
            short_name = request.POST.get('short_name', '').strip()
            description = request.POST.get('description', '').strip()

            if not name or not short_name:
                messages.error(request, 'Name and short name are required.')
                return redirect('risk_scenario_list')

            # Check for duplicate short_name
            if RiskScenario.objects.filter(short_name=short_name).exists():
                messages.error(request, f'A scenario with short name "{short_name}" already exists.')
                return redirect('risk_scenario_list')

            scenario = RiskScenario.objects.create(
                name=name,
                short_name=short_name,
                description=description,
                target_year=int(request.POST.get('target_year', 2040)),
                status=request.POST.get('status', 'draft'),
                is_baseline=request.POST.get('is_baseline') == 'on',
                wind_percentage=float(request.POST.get('wind_percentage', 0)),
                solar_percentage=float(request.POST.get('solar_percentage', 0)),
                storage_percentage=float(request.POST.get('storage_percentage', 0)),
                gas_percentage=float(request.POST.get('gas_percentage', 0)),
                coal_percentage=float(request.POST.get('coal_percentage', 0)),
                hydro_percentage=float(request.POST.get('hydro_percentage', 0)),
                hydrogen_percentage=float(request.POST.get('hydrogen_percentage', 0)),
                nuclear_percentage=float(request.POST.get('nuclear_percentage', 0)),
                biomass_percentage=float(request.POST.get('biomass_percentage', 0)),
                other_percentage=float(request.POST.get('other_percentage', 0)),
                created_by=request.user if request.user.is_authenticated else None,
            )

            messages.success(request, f'Scenario "{name}" created successfully.')
            return redirect('risk_scenario_detail', scenario_id=scenario.id)

        except ValueError as e:
            messages.error(request, f'Invalid value: {str(e)}')
        except Exception as e:
            logger.error(f"Error creating scenario: {str(e)}")
            messages.error(request, f'Error creating scenario: {str(e)}')

    context = {
        'categories': categories,
        'action': 'create',
    }
    return render(request, 'risk_analysis/scenario_form.html', context)


@require_http_methods(["GET", "POST"])
def scenario_update(request, scenario_id):
    """Update an existing risk scenario."""
    scenario = get_object_or_404(RiskScenario, id=scenario_id)
    categories = RiskCategory.objects.filter(is_active=True)

    if request.method == 'POST':
        try:
            scenario.name = request.POST.get('name', scenario.name).strip()
            scenario.short_name = request.POST.get('short_name', scenario.short_name).strip()
            scenario.description = request.POST.get('description', scenario.description).strip()
            scenario.target_year = int(request.POST.get('target_year', scenario.target_year))
            scenario.status = request.POST.get('status', scenario.status)
            scenario.is_baseline = request.POST.get('is_baseline') == 'on'
            scenario.wind_percentage = float(request.POST.get('wind_percentage', 0))
            scenario.solar_percentage = float(request.POST.get('solar_percentage', 0))
            scenario.storage_percentage = float(request.POST.get('storage_percentage', 0))
            scenario.gas_percentage = float(request.POST.get('gas_percentage', 0))
            scenario.coal_percentage = float(request.POST.get('coal_percentage', 0))
            scenario.hydro_percentage = float(request.POST.get('hydro_percentage', 0))
            scenario.hydrogen_percentage = float(request.POST.get('hydrogen_percentage', 0))
            scenario.nuclear_percentage = float(request.POST.get('nuclear_percentage', 0))
            scenario.biomass_percentage = float(request.POST.get('biomass_percentage', 0))
            scenario.other_percentage = float(request.POST.get('other_percentage', 0))
            scenario.save()

            messages.success(request, f'Scenario "{scenario.name}" updated successfully.')
            return redirect('risk_scenario_detail', scenario_id=scenario.id)

        except ValueError as e:
            messages.error(request, f'Invalid value: {str(e)}')
        except Exception as e:
            logger.error(f"Error updating scenario: {str(e)}")
            messages.error(request, f'Error updating scenario: {str(e)}')

    context = {
        'scenario': scenario,
        'categories': categories,
        'action': 'update',
    }
    return render(request, 'risk_analysis/scenario_form.html', context)


@require_POST
def scenario_delete(request, scenario_id):
    """Delete a risk scenario."""
    scenario = get_object_or_404(RiskScenario, id=scenario_id)
    name = scenario.name

    try:
        scenario.delete()
        messages.success(request, f'Scenario "{name}" deleted successfully.')
    except Exception as e:
        logger.error(f"Error deleting scenario: {str(e)}")
        messages.error(request, f'Error deleting scenario: {str(e)}')

    return redirect('risk_scenario_list')


# =============================================================================
# Risk Event CRUD Views
# =============================================================================

@require_http_methods(["GET", "POST"])
def risk_event_create(request, scenario_id):
    """Add a new risk event to a scenario."""
    scenario = get_object_or_404(RiskScenario, id=scenario_id)
    categories = RiskCategory.objects.filter(is_active=True)

    if request.method == 'POST':
        try:
            category_id = request.POST.get('category')
            category = get_object_or_404(RiskCategory, id=category_id)

            event = RiskEvent.objects.create(
                scenario=scenario,
                category=category,
                risk_title=request.POST.get('risk_title', '').strip(),
                risk_description=request.POST.get('risk_description', '').strip(),
                risk_cause=request.POST.get('risk_cause', '').strip(),
                risk_source=request.POST.get('risk_source', '').strip(),
                inherent_likelihood=int(request.POST.get('inherent_likelihood')),
                inherent_consequence=int(request.POST.get('inherent_consequence')),
                inherent_consequence_description=request.POST.get('inherent_consequence_description', '').strip(),
                inherent_likelihood_description=request.POST.get('inherent_likelihood_description', '').strip(),
                mitigation_strategies=request.POST.get('mitigation_strategies', '').strip(),
                residual_likelihood=int(request.POST.get('residual_likelihood')) if request.POST.get('residual_likelihood') else None,
                residual_consequence=int(request.POST.get('residual_consequence')) if request.POST.get('residual_consequence') else None,
                assumptions=request.POST.get('assumptions', '').strip(),
                data_sources=request.POST.get('data_sources', '').strip(),
                comments=request.POST.get('comments', '').strip(),
            )

            # Handle AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'event_id': event.id,
                    'message': f'Risk event "{event.risk_title}" created successfully.'
                })

            messages.success(request, f'Risk event "{event.risk_title}" created successfully.')
            return redirect('risk_scenario_detail', scenario_id=scenario.id)

        except Exception as e:
            logger.error(f"Error creating risk event: {str(e)}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': str(e)}, status=400)
            messages.error(request, f'Error creating risk event: {str(e)}')

    context = {
        'scenario': scenario,
        'categories': categories,
        'likelihood_choices': RISK_LIKELIHOOD_CHOICES,
        'consequence_choices': RISK_CONSEQUENCE_CHOICES,
        'action': 'create',
    }
    return render(request, 'risk_analysis/risk_event_form.html', context)


@require_http_methods(["GET", "POST"])
def risk_event_update(request, event_id):
    """Update a risk event assessment."""
    event = get_object_or_404(RiskEvent, id=event_id)
    categories = RiskCategory.objects.filter(is_active=True)

    if request.method == 'POST':
        try:
            category_id = request.POST.get('category')
            if category_id:
                event.category = get_object_or_404(RiskCategory, id=category_id)

            event.risk_title = request.POST.get('risk_title', event.risk_title).strip()
            event.risk_description = request.POST.get('risk_description', event.risk_description).strip()
            event.risk_cause = request.POST.get('risk_cause', '').strip()
            event.risk_source = request.POST.get('risk_source', '').strip()
            event.inherent_likelihood = int(request.POST.get('inherent_likelihood', event.inherent_likelihood))
            event.inherent_consequence = int(request.POST.get('inherent_consequence', event.inherent_consequence))
            event.inherent_consequence_description = request.POST.get('inherent_consequence_description', '').strip()
            event.inherent_likelihood_description = request.POST.get('inherent_likelihood_description', '').strip()
            event.mitigation_strategies = request.POST.get('mitigation_strategies', '').strip()
            event.residual_likelihood = int(request.POST.get('residual_likelihood')) if request.POST.get('residual_likelihood') else None
            event.residual_consequence = int(request.POST.get('residual_consequence')) if request.POST.get('residual_consequence') else None
            event.assumptions = request.POST.get('assumptions', '').strip()
            event.data_sources = request.POST.get('data_sources', '').strip()
            event.comments = request.POST.get('comments', '').strip()
            event.save()

            # Handle AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'event_id': event.id,
                    'message': f'Risk event "{event.risk_title}" updated successfully.'
                })

            messages.success(request, f'Risk event "{event.risk_title}" updated successfully.')
            return redirect('risk_scenario_detail', scenario_id=event.scenario.id)

        except Exception as e:
            logger.error(f"Error updating risk event: {str(e)}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': str(e)}, status=400)
            messages.error(request, f'Error updating risk event: {str(e)}')

    context = {
        'event': event,
        'scenario': event.scenario,
        'categories': categories,
        'likelihood_choices': RISK_LIKELIHOOD_CHOICES,
        'consequence_choices': RISK_CONSEQUENCE_CHOICES,
        'action': 'update',
    }
    return render(request, 'risk_analysis/risk_event_form.html', context)


@require_POST
def risk_event_delete(request, event_id):
    """Delete a risk event."""
    event = get_object_or_404(RiskEvent, id=event_id)
    scenario_id = event.scenario.id
    title = event.risk_title

    try:
        event.delete()

        # Handle AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Risk event "{title}" deleted successfully.'
            })

        messages.success(request, f'Risk event "{title}" deleted successfully.')
    except Exception as e:
        logger.error(f"Error deleting risk event: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
        messages.error(request, f'Error deleting risk event: {str(e)}')

    return redirect('risk_scenario_detail', scenario_id=scenario_id)


# =============================================================================
# API Endpoints (JSON)
# =============================================================================

def api_risk_matrix_data(request, scenario_id):
    """
    API endpoint for risk matrix heatmap data.
    Returns JSON for Plotly.js visualization.
    Uses 6x6 matrix based on 2016 SWIS methodology.
    """
    scenario = get_object_or_404(RiskScenario, id=scenario_id)
    events = scenario.risk_events.select_related('category').all()

    # Build 6x6 matrix data (likelihood x consequence)
    matrix_data = {
        'scenario_id': scenario.id,
        'scenario_name': scenario.name,
        'inherent': [[0 for _ in range(6)] for _ in range(6)],
        'residual': [[0 for _ in range(6)] for _ in range(6)],
        'events': []
    }

    for event in events:
        # Inherent matrix (0-indexed)
        li = event.inherent_likelihood - 1
        ci = event.inherent_consequence - 1
        matrix_data['inherent'][li][ci] += 1

        # Residual matrix
        if event.residual_likelihood and event.residual_consequence:
            lr = event.residual_likelihood - 1
            cr = event.residual_consequence - 1
            matrix_data['residual'][lr][cr] += 1

        matrix_data['events'].append({
            'id': event.id,
            'title': event.risk_title,
            'category': event.category.name,
            'category_color': event.category.color_code,
            'inherent_likelihood': event.inherent_likelihood,
            'inherent_consequence': event.inherent_consequence,
            'inherent_score': event.simple_inherent_score,
            'residual_likelihood': event.residual_likelihood,
            'residual_consequence': event.residual_consequence,
            'residual_score': event.simple_residual_score,
            'inherent_level': event.inherent_risk_level,
            'residual_level': event.residual_risk_level,
            'risk_reduction': event.risk_reduction_percentage,
        })

    return JsonResponse(matrix_data)


def api_scenario_comparison_data(request):
    """
    API endpoint for comparing multiple scenarios.
    Returns aggregated risk scores by category.
    """
    scenario_ids = request.GET.getlist('scenarios')
    if not scenario_ids:
        return JsonResponse({'error': 'No scenarios specified'}, status=400)

    scenarios = RiskScenario.objects.filter(id__in=scenario_ids).prefetch_related('risk_events')
    categories = RiskCategory.objects.filter(is_active=True).order_by('display_order')

    comparison_data = {
        'categories': [c.name for c in categories],
        'category_colors': [c.color_code for c in categories],
        'scenarios': []
    }

    for scenario in scenarios:
        scenario_data = {
            'id': scenario.id,
            'name': scenario.name,
            'short_name': scenario.short_name,
            'target_year': scenario.target_year,
            'is_baseline': scenario.is_baseline,
            'inherent_scores': [],
            'residual_scores': [],
            'event_counts': [],
        }

        for category in categories:
            inherent = scenario.get_inherent_risk_score(category)
            residual = scenario.get_residual_risk_score(category)
            count = scenario.risk_events.filter(category=category).count()

            scenario_data['inherent_scores'].append(inherent if inherent else 0)
            scenario_data['residual_scores'].append(residual if residual else 0)
            scenario_data['event_counts'].append(count)

        # Overall scores
        scenario_data['overall_inherent'] = scenario.get_inherent_risk_score()
        scenario_data['overall_residual'] = scenario.get_residual_risk_score()
        scenario_data['total_events'] = scenario.risk_events.count()
        scenario_data['risk_counts'] = scenario.get_risk_counts_by_level()

        comparison_data['scenarios'].append(scenario_data)

    return JsonResponse(comparison_data)


def api_risk_summary(request):
    """
    API endpoint for overall risk summary across all active scenarios.
    """
    scenarios = RiskScenario.objects.filter(status='active').prefetch_related('risk_events')

    summary = {
        'total_scenarios': scenarios.count(),
        'total_risk_events': RiskEvent.objects.filter(scenario__status='active').count(),
        'scenarios': []
    }

    for scenario in scenarios:
        events = scenario.risk_events.all()

        # Count by risk level
        risk_counts = scenario.get_risk_counts_by_level()

        summary['scenarios'].append({
            'id': scenario.id,
            'name': scenario.name,
            'short_name': scenario.short_name,
            'status': scenario.status,
            'target_year': scenario.target_year,
            'event_count': events.count(),
            'avg_inherent_score': scenario.get_inherent_risk_score(),
            'avg_residual_score': scenario.get_residual_risk_score(),
            'risk_counts': risk_counts,
            'energy_mix': scenario.energy_mix_dict,
        })

    return JsonResponse(summary)


def api_category_risk_profile(request, scenario_id):
    """
    API endpoint for risk profile by category (for radar chart).
    """
    scenario = get_object_or_404(RiskScenario, id=scenario_id)
    categories = RiskCategory.objects.filter(is_active=True).order_by('display_order')

    profile = {
        'scenario_id': scenario.id,
        'scenario_name': scenario.name,
        'categories': [],
        'inherent_scores': [],
        'residual_scores': [],
        'event_counts': [],
        'max_score': 36,  # 6x6 matrix max
    }

    for category in categories:
        profile['categories'].append(category.name)

        inherent = scenario.get_inherent_risk_score(category)
        residual = scenario.get_residual_risk_score(category)
        count = scenario.risk_events.filter(category=category).count()

        profile['inherent_scores'].append(inherent if inherent else 0)
        profile['residual_scores'].append(residual if residual else 0)
        profile['event_counts'].append(count)

    return JsonResponse(profile)


def api_scenario_detail(request, scenario_id):
    """
    API endpoint for single scenario detail.
    """
    scenario = get_object_or_404(RiskScenario, id=scenario_id)

    data = {
        'id': scenario.id,
        'name': scenario.name,
        'short_name': scenario.short_name,
        'description': scenario.description,
        'target_year': scenario.target_year,
        'status': scenario.status,
        'is_baseline': scenario.is_baseline,
        'energy_mix': scenario.energy_mix_dict,
        'total_percentage': scenario.total_percentage,
        'wind_percentage': scenario.wind_percentage,
        'solar_percentage': scenario.solar_percentage,
        'storage_percentage': scenario.storage_percentage,
        'gas_percentage': scenario.gas_percentage,
        'coal_percentage': scenario.coal_percentage,
        'hydro_percentage': scenario.hydro_percentage,
        'hydrogen_percentage': scenario.hydrogen_percentage,
        'nuclear_percentage': scenario.nuclear_percentage,
        'biomass_percentage': scenario.biomass_percentage,
        'other_percentage': scenario.other_percentage,
    }

    return JsonResponse(data)
