"""
SWIS Risk Analysis Views

This module provides views for:
- Risk event assessment interface
- Scenario comparison (using existing Scenarios)
- Dashboard and summary views
- API endpoints for AJAX operations

Note: Scenarios are managed separately via the powermapui app.
This module uses existing Scenarios for risk analysis.
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
    RiskCategory, Scenarios, RiskEvent, TargetScenario,
    RISK_LIKELIHOOD_CHOICES, RISK_CONSEQUENCE_CHOICES
)

logger = logging.getLogger(__name__)


# =============================================================================
# Helper functions for risk calculations on Scenarios
# =============================================================================

def get_scenario_inherent_risk_score(scenario, category=None):
    """Calculate average inherent risk score for a scenario."""
    events = scenario.risk_events.all()
    if category:
        events = events.filter(category=category)
    if not events.exists():
        return None
    scores = [e.inherent_likelihood * e.inherent_consequence for e in events]
    return sum(scores) / len(scores) if scores else None


def get_scenario_residual_risk_score(scenario, category=None):
    """Calculate average residual risk score for a scenario."""
    events = scenario.risk_events.filter(
        residual_likelihood__isnull=False,
        residual_consequence__isnull=False
    )
    if category:
        events = events.filter(category=category)
    if not events.exists():
        return None
    scores = [e.residual_likelihood * e.residual_consequence for e in events]
    return sum(scores) / len(scores) if scores else None


def get_scenario_risk_counts_by_level(scenario):
    """Get count of risks by level for a scenario."""
    events = scenario.risk_events.all()
    counts = {'severe': 0, 'high': 0, 'medium': 0, 'low': 0}
    for event in events:
        score = event.inherent_likelihood * event.inherent_consequence
        if score >= 20:
            counts['severe'] += 1
        elif score >= 12:
            counts['high'] += 1
        elif score >= 6:
            counts['medium'] += 1
        else:
            counts['low'] += 1
    return counts


def get_scenario_energy_mix(scenario, target_year=None):
    """
    Get the energy mix from associated TargetScenario records.
    Returns the generation mix as percentages for a given year (or latest available).
    """
    target_scenarios = scenario.target_scenarios.filter(is_active=True)

    if not target_scenarios.exists():
        return None

    # If target_year specified, try to get that year
    if target_year:
        target = target_scenarios.filter(year=target_year).first()
    else:
        # Get the latest year's data
        target = target_scenarios.order_by('-year').first()

    if not target:
        return None

    total = target.total_generation
    if total == 0:
        return None

    return {
        'year': target.year,
        'scenario_type': target.get_scenario_type_display(),
        'target_re_percentage': target.target_re_percentage,
        'wind_pct': (target.wind_generation / total * 100) if total else 0,
        'solar_pct': (target.solar_generation / total * 100) if total else 0,
        'dpv_pct': (target.dpv_generation / total * 100) if total else 0,
        'biomass_pct': (target.biomass_generation / total * 100) if total else 0,
        'gas_pct': (target.gas_generation / total * 100) if total else 0,
        'wind_gwh': target.wind_generation,
        'solar_gwh': target.solar_generation,
        'dpv_gwh': target.dpv_generation,
        'biomass_gwh': target.biomass_generation,
        'gas_gwh': target.gas_generation,
        'total_gwh': total,
        'storage_mwh': target.storage,
    }


# =============================================================================
# Dashboard and Summary Views
# =============================================================================

def risk_dashboard(request):
    """
    Main dashboard view for SWIS risk analysis.
    Shows overview of all scenarios with risk profiles.
    """
    # Get scenarios that have risk events
    scenarios = Scenarios.objects.prefetch_related('risk_events').filter(
        risk_events__isnull=False
    ).distinct()
    categories = RiskCategory.objects.filter(is_active=True)

    # Calculate summary statistics
    total_scenarios = scenarios.count()
    total_events = RiskEvent.objects.count()

    # Get highest risk scenario
    highest_risk_scenario = None
    highest_score = 0
    for scenario in scenarios:
        score = get_scenario_inherent_risk_score(scenario)
        if score and score > highest_score:
            highest_score = score
            highest_risk_scenario = scenario

    # Count severe/high risks
    severe_count = RiskEvent.objects.annotate(
        score=F('inherent_likelihood') * F('inherent_consequence')
    ).filter(score__gte=20).count()

    high_count = RiskEvent.objects.annotate(
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
    scenario = get_object_or_404(Scenarios, idscenarios=scenario_id)
    categories = RiskCategory.objects.filter(is_active=True)
    events = scenario.risk_events.select_related('category').all()

    # Group events by category
    events_by_category = {}
    for category in categories:
        category_events = events.filter(category=category)
        if category_events.exists():
            events_by_category[category] = category_events

    # Calculate risk counts
    risk_counts = get_scenario_risk_counts_by_level(scenario)

    # Get energy mix from associated TargetScenario
    target_year = request.GET.get('year')
    energy_mix = get_scenario_energy_mix(scenario, target_year)

    # Get available years for this scenario
    available_years = list(
        scenario.target_scenarios.filter(is_active=True)
        .values_list('year', flat=True)
        .distinct()
        .order_by('year')
    )

    context = {
        'scenario': scenario,
        'categories': categories,
        'events': events,
        'events_by_category': events_by_category,
        'risk_counts': risk_counts,
        'energy_mix': energy_mix,
        'available_years': available_years,
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
    all_scenarios = Scenarios.objects.all()
    categories = RiskCategory.objects.filter(is_active=True)

    selected_scenarios = []
    if scenario_ids:
        selected_scenarios = Scenarios.objects.filter(
            idscenarios__in=scenario_ids
        ).prefetch_related('risk_events')

    context = {
        'all_scenarios': all_scenarios,
        'selected_scenarios': selected_scenarios,
        'categories': categories,
        'selected_ids': [int(id) for id in scenario_ids] if scenario_ids else [],
    }

    return render(request, 'risk_analysis/comparison.html', context)


# =============================================================================
# Scenario List View (Read-only - scenarios are managed elsewhere)
# =============================================================================

def scenario_list(request):
    """List all scenarios with their risk analysis status."""
    scenarios = Scenarios.objects.all().prefetch_related('risk_events')
    categories = RiskCategory.objects.filter(is_active=True)

    # Add risk event counts to each scenario for display
    scenario_data = []
    for scenario in scenarios:
        event_count = scenario.risk_events.count()
        inherent_score = get_scenario_inherent_risk_score(scenario)
        residual_score = get_scenario_residual_risk_score(scenario)
        scenario_data.append({
            'scenario': scenario,
            'event_count': event_count,
            'inherent_score': inherent_score,
            'residual_score': residual_score,
        })

    context = {
        'scenario_data': scenario_data,
        'scenarios': scenarios,
        'categories': categories,
        'likelihood_choices': RISK_LIKELIHOOD_CHOICES,
        'consequence_choices': RISK_CONSEQUENCE_CHOICES,
    }

    return render(request, 'risk_analysis/scenario_list.html', context)


# =============================================================================
# Risk Event CRUD Views
# =============================================================================

@require_http_methods(["GET", "POST"])
def risk_event_create(request, scenario_id):
    """Add a new risk event to a scenario."""
    scenario = get_object_or_404(Scenarios, idscenarios=scenario_id)
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
            return redirect('risk_scenario_detail', scenario_id=scenario.idscenarios)

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
    return render(request, 'risk_analysis/event_form.html', context)


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
            return redirect('risk_scenario_detail', scenario_id=event.scenario.idscenarios)

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
    return render(request, 'risk_analysis/event_form.html', context)


@require_POST
def risk_event_delete(request, event_id):
    """Delete a risk event."""
    event = get_object_or_404(RiskEvent, id=event_id)
    scenario_id = event.scenario.idscenarios
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
    scenario = get_object_or_404(Scenarios, idscenarios=scenario_id)
    events = scenario.risk_events.select_related('category').all()

    # Build 6x6 matrix data (likelihood x consequence)
    matrix_data = {
        'scenario_id': scenario.idscenarios,
        'scenario_name': scenario.title,
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

    scenarios = Scenarios.objects.filter(idscenarios__in=scenario_ids).prefetch_related('risk_events')
    categories = RiskCategory.objects.filter(is_active=True).order_by('display_order')

    comparison_data = {
        'categories': [c.name for c in categories],
        'category_colors': [c.color_code for c in categories],
        'scenarios': []
    }

    for scenario in scenarios:
        scenario_data = {
            'id': scenario.idscenarios,
            'name': scenario.title,
            'description': scenario.description or '',
            'inherent_scores': [],
            'residual_scores': [],
            'event_counts': [],
        }

        for category in categories:
            inherent = get_scenario_inherent_risk_score(scenario, category)
            residual = get_scenario_residual_risk_score(scenario, category)
            count = scenario.risk_events.filter(category=category).count()

            scenario_data['inherent_scores'].append(inherent if inherent else 0)
            scenario_data['residual_scores'].append(residual if residual else 0)
            scenario_data['event_counts'].append(count)

        # Overall scores
        scenario_data['overall_inherent'] = get_scenario_inherent_risk_score(scenario)
        scenario_data['overall_residual'] = get_scenario_residual_risk_score(scenario)
        scenario_data['total_events'] = scenario.risk_events.count()
        scenario_data['risk_counts'] = get_scenario_risk_counts_by_level(scenario)

        comparison_data['scenarios'].append(scenario_data)

    return JsonResponse(comparison_data)


def api_risk_summary(request):
    """
    API endpoint for overall risk summary across all scenarios with risk events.
    """
    scenarios = Scenarios.objects.prefetch_related('risk_events').filter(
        risk_events__isnull=False
    ).distinct()

    summary = {
        'total_scenarios': scenarios.count(),
        'total_risk_events': RiskEvent.objects.count(),
        'scenarios': []
    }

    for scenario in scenarios:
        events = scenario.risk_events.all()

        # Count by risk level
        risk_counts = get_scenario_risk_counts_by_level(scenario)

        summary['scenarios'].append({
            'id': scenario.idscenarios,
            'name': scenario.title,
            'description': scenario.description or '',
            'event_count': events.count(),
            'avg_inherent_score': get_scenario_inherent_risk_score(scenario),
            'avg_residual_score': get_scenario_residual_risk_score(scenario),
            'risk_counts': risk_counts,
        })

    return JsonResponse(summary)


def api_category_risk_profile(request, scenario_id):
    """
    API endpoint for risk profile by category (for radar chart).
    """
    scenario = get_object_or_404(Scenarios, idscenarios=scenario_id)
    categories = RiskCategory.objects.filter(is_active=True).order_by('display_order')

    profile = {
        'scenario_id': scenario.idscenarios,
        'scenario_name': scenario.title,
        'categories': [],
        'inherent_scores': [],
        'residual_scores': [],
        'event_counts': [],
        'max_score': 36,  # 6x6 matrix max
    }

    for category in categories:
        profile['categories'].append(category.name)

        inherent = get_scenario_inherent_risk_score(scenario, category)
        residual = get_scenario_residual_risk_score(scenario, category)
        count = scenario.risk_events.filter(category=category).count()

        profile['inherent_scores'].append(inherent if inherent else 0)
        profile['residual_scores'].append(residual if residual else 0)
        profile['event_counts'].append(count)

    return JsonResponse(profile)


def api_scenario_detail(request, scenario_id):
    """
    API endpoint for single scenario detail.
    """
    scenario = get_object_or_404(Scenarios, idscenarios=scenario_id)

    data = {
        'id': scenario.idscenarios,
        'name': scenario.title,
        'description': scenario.description or '',
    }

    return JsonResponse(data)