from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
import json
from siren_web.database_operations import (
    fetch_technology_by_id, fetch_merit_order_technologies, compute_auto_sorted_merit_order,
    get_demand_scenario_context, resolve_demand_override, resolve_scenario_carbon_price,
    resolve_scenario_discount_rate, update_scenario_settings_data,
)
from siren_web.models import ScenariosTechnologies, Scenarios
from urllib.parse import urlencode

def _save_and_resolve_carbon_price(scenario, carbon_price_raw):
    """
    Persists carbon_price_raw as this scenario's carbon price (Merit Order is
    the only place it's ever written -- see resolve_scenario_carbon_price)
    when it parses to a number, and returns the value now in effect. Falls
    back to the saved/global value without writing anything if
    carbon_price_raw is blank or not a number, so a bad request doesn't
    clobber a previously-saved price.
    """
    if carbon_price_raw not in (None, ''):
        try:
            carbon_price = float(carbon_price_raw)
        except (TypeError, ValueError):
            carbon_price = None
        if carbon_price is not None:
            update_scenario_settings_data(scenario, 'Powermatch', 'carbon_price', carbon_price)
            return carbon_price
    return resolve_scenario_carbon_price(scenario)

def _save_and_resolve_discount_rate(scenario, discount_rate_raw, request=None):
    """
    Persists discount_rate_raw as this scenario's discount rate (Merit Order
    is the only place it's ever written -- see resolve_scenario_discount_rate)
    when it parses to a sane fraction, and returns the value now in effect.
    Falls back to the saved/global value without writing anything if
    discount_rate_raw is blank, not a number, or outside a sane range (a
    discount rate is always well under 1.0 -- e.g. 0.075 for 7.5%; a value
    >= 1 is almost always a units mistake, like typing a percentage or a
    stray extra digit, and previously corrupted this exact setting badly
    enough to overflow the annualised-cost calculation), so a bad request
    can't clobber a previously-saved rate. Mirrors _save_and_resolve_carbon_price.
    """
    if discount_rate_raw not in (None, ''):
        try:
            discount_rate = float(discount_rate_raw)
        except (TypeError, ValueError):
            discount_rate = None
        if discount_rate is not None:
            if 0 <= discount_rate < 1:
                update_scenario_settings_data(scenario, 'Powermatch', 'discount_rate', discount_rate)
                return discount_rate
            if request is not None:
                messages.error(
                    request,
                    f"Discount rate {discount_rate} looks wrong (expected a fraction like 0.075 "
                    "for 7.5%) -- not saved."
                )
    return resolve_scenario_discount_rate(scenario)

@login_required
def set_merit_order(request):
    if request.user.groups.filter(name='modellers').exists():
        pass
    else:
        messages.error(request, "Access not allowed.")
        return render(request, 'powermatchui_home.html')

    scenario = request.session.get('scenario')
    config_file = request.session.get('config_file')

    # Initialize with default values
    success_message = request.GET.get('success_message', '')
    merit_order = {}
    excluded_resources = {}

    if request.method == 'POST' and scenario:
        scenario_obj = Scenarios.objects.get(title=scenario)
        
        # Process form data
        try:
            data = {}
            if request.body:
                data = json.loads(request.body)
            
            merit_order_ids = data.get('meritOrderIds', [])
            excluded_resources_ids = data.get('excludedResourcesIds', [])
            carbon_price_raw = data.get('carbonPrice')
            discount_rate_raw = data.get('discountRate')
        except Exception as e:
            messages.error(request, f"Error processing request: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)})

        _save_and_resolve_carbon_price(scenario, carbon_price_raw)
        _save_and_resolve_discount_rate(scenario, discount_rate_raw, request=request)

        # Update the merit_order attribute for technologies in the 'Merit Order' column
        updated_count = 0
        for index, tech_id in enumerate(merit_order_ids, start=1):
            if tech_id:
                result = ScenariosTechnologies.objects.filter(
                    idtechnologies=tech_id, 
                    idscenarios=scenario_obj.pk
                ).update(merit_order=index)
                updated_count += result

        # Update the merit_order attribute for technologies in the 'Excluded Resources' column
        for index, tech_id in enumerate(excluded_resources_ids, start=800):
            if tech_id:
                technology = fetch_technology_by_id(tech_id)
                result = ScenariosTechnologies.objects.filter(
                    idtechnologies=tech_id, 
                    idscenarios=scenario_obj.pk
                ).update(merit_order=index)
                updated_count += result

        # Add success message using Django messages framework
        messages.success(request, f"Merit Order Updated. {updated_count} technologies updated.")
        
        # Return JSON response for AJAX
        return JsonResponse({'status': 'success', 'message': f'Merit Order Updated. {updated_count} technologies updated.'})
        
    demand_id = request.GET.get('demand_scenario_demand')
    demand_selected = bool(demand_id)
    carbon_price = None
    discount_rate = None

    # Technologies (Carbon Price and Discount Rate) are only shown once a
    # Demand Forecast Scenario is selected -- the cost year it implies is
    # what Auto Sort costs fossil technologies at, see
    # compute_auto_sorted_merit_order.
    if scenario and demand_selected:
        scenario_obj = Scenarios.objects.get(title=scenario)
        idscenarios = scenario_obj.pk
        merit_order, excluded_resources = fetch_merit_order_technologies(idscenarios)
        carbon_price = resolve_scenario_carbon_price(scenario)
        discount_rate = resolve_scenario_discount_rate(scenario)

        if not len(merit_order) and not len(excluded_resources):
            success_message = "Reload the technologies."
    elif scenario:
        success_message = "Select a Demand Forecast Scenario to view technologies."
    else:
        success_message = "Set a scenario and config first."

    context = {
        'merit_order': merit_order,
        'excluded_resources': excluded_resources,
        'success_message': success_message,
        'scenario': scenario,
        'config_file': config_file,
        'demand_selected': demand_selected,
        'carbon_price': carbon_price,
        'discount_rate': discount_rate,
        **get_demand_scenario_context(demand_id),
    }

    return render(request, 'merit_order.html', context)

@login_required
def auto_sort_merit_order(request):
    if not request.user.groups.filter(name='modellers').exists():
        return JsonResponse({'status': 'error', 'message': 'Access not allowed.'}, status=403)

    scenario = request.session.get('scenario')
    if not scenario:
        return JsonResponse({'status': 'error', 'message': 'Set a scenario and config first.'})

    try:
        data = json.loads(request.body) if request.body else {}
        demand_id = data.get('demandId')
        carbon_price_override = data.get('carbonPrice')

        scenario_obj = Scenarios.objects.get(title=scenario)
        demand_override = resolve_demand_override(demand_id)
        cost_year = demand_override.year if demand_override else None
        # Auto Sort saves whatever's currently typed in the Carbon Price box
        # (same as Save Merit Order), so the fossil ranking it shows and the
        # value a later baseline run uses are always the same number.
        carbon_price = _save_and_resolve_carbon_price(scenario, carbon_price_override)

        ordered_ids = compute_auto_sorted_merit_order(
            scenario_obj.pk, cost_year=cost_year, carbon_price=carbon_price
        )
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

    return JsonResponse({'status': 'success', 'orderedIds': ordered_ids})