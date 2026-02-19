from django.contrib.auth.decorators import login_required
from common.decorators import settings_required
from django.shortcuts import render
from siren_web.forms import DemandScenarioSettings
from siren_web.models import facilities, Scenarios
from collections import defaultdict
import json


def _get_session_context(request):
    """Shared session/scenario handling for pipeline chart views."""
    weather_year = request.session.get('weather_year', '')
    demand_year = request.session.get('demand_year', '')
    scenario = request.session.get('scenario', '')
    config_file = request.session.get('config_file')
    success_message = ''

    if request.method == 'POST':
        form = DemandScenarioSettings(request.POST)
        if form.is_valid():
            demand_year = form.cleaned_data['demand_year']
            request.session['demand_year'] = demand_year
            scenario = form.cleaned_data['scenario']
            request.session['scenario'] = scenario
            success_message = "Settings updated."

    form = DemandScenarioSettings(initial={
        'demand_year': demand_year,
        'scenario': scenario
    })

    return {
        'demand_weather_scenario': form,
        'weather_year': weather_year,
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
        'success_message': success_message,
    }


def _get_pipeline_facilities(scenario):
    """Query facilities with lifecycle data for a given scenario title."""
    if not scenario:
        return []

    try:
        scenario_obj = Scenarios.objects.get(title=scenario)
    except Scenarios.DoesNotExist:
        return []

    result = []
    for f in facilities.objects.filter(
        scenarios=scenario_obj,
    ).select_related('idtechnologies'):
        status = f.status if f.status else 'commissioned'
        probability = f.commissioning_probability if f.commissioning_probability is not None else 1.0
        capacity = float(f.capacity) if f.capacity else 0
        tech_name = f.idtechnologies.technology_name if f.idtechnologies else 'Unknown'
        tech_category = (f.idtechnologies.category if f.idtechnologies and hasattr(f.idtechnologies, 'category') else 'Unknown') or 'Unknown'
        lifetime = float(f.idtechnologies.lifetime) if f.idtechnologies and f.idtechnologies.lifetime else None

        comm_year = f.commissioning_date.year if f.commissioning_date else None
        decomm_year = f.decommissioning_date.year if f.decommissioning_date else None
        retirement_year = None
        if comm_year and lifetime:
            retirement_year = comm_year + int(lifetime)
        # Explicit decommissioning date takes precedence
        end_year = decomm_year or retirement_year

        result.append({
            'idfacilities': f.idfacilities,
            'facility_name': f.facility_name,
            'capacity': capacity,
            'status': status,
            'commissioning_probability': probability,
            'commissioning_date': f.commissioning_date.isoformat() if f.commissioning_date else None,
            'decommissioning_date': f.decommissioning_date.isoformat() if f.decommissioning_date else None,
            'comm_year': comm_year,
            'end_year': end_year,
            'technology_name': tech_name,
            'technology_category': tech_category,
            'technology_lifetime': lifetime,
        })

    return result


@login_required
@settings_required(redirect_view='powermapui:powermapui_home')
def pipeline_gantt(request):
    """Timeline / Gantt chart of facility lifespans."""
    ctx = _get_session_context(request)
    facs = _get_pipeline_facilities(ctx['scenario'])

    # Sort: by category, then by commissioning date, then by name
    facs.sort(key=lambda f: (
        f['technology_category'],
        f['comm_year'] or 9999,
        f['facility_name']
    ))

    ctx['facilities_json'] = json.dumps(facs)
    ctx['facility_count'] = len(facs)
    return render(request, 'pipeline_gantt.html', ctx)


@login_required
@settings_required(redirect_view='powermapui:powermapui_home')
def pipeline_waterfall(request):
    """Capacity waterfall / stacked area chart over time."""
    ctx = _get_session_context(request)
    facs = _get_pipeline_facilities(ctx['scenario'])

    # Determine year range
    all_years = []
    for f in facs:
        if f['comm_year']:
            all_years.append(f['comm_year'])
        if f['end_year']:
            all_years.append(f['end_year'])

    if all_years:
        year_min = min(all_years)
        year_max = max(all_years) + 1
    else:
        year_min = 2020
        year_max = 2051

    # Build year-by-year capacity by category
    # For each year, sum capacity of facilities that are "online" in that year
    categories = sorted(set(f['technology_category'] for f in facs))
    years = list(range(year_min, year_max + 1))

    # committed_series: capacity of facilities with status=commissioned or under_construction
    # probable_series: probability-weighted capacity of proposed/planned facilities
    committed_by_cat = {cat: [] for cat in categories}
    probable_by_cat = {cat: [] for cat in categories}
    retirements_by_cat = {cat: [] for cat in categories}

    for year in years:
        cat_committed = defaultdict(float)
        cat_probable = defaultdict(float)
        cat_retiring = defaultdict(float)

        for f in facs:
            if not f['comm_year']:
                continue
            cat = f['technology_category']
            # Is this facility online in this year?
            online = f['comm_year'] <= year and (f['end_year'] is None or year < f['end_year'])
            # Is it retiring this exact year?
            retiring = f['end_year'] == year and f['comm_year'] <= year

            if online:
                if f['status'] in ('commissioned', 'under_construction', 'decommissioned'):
                    cat_committed[cat] += f['capacity']
                else:
                    # proposed/planned - weight by probability
                    cat_probable[cat] += f['capacity'] * f['commissioning_probability']

            if retiring:
                cat_retiring[cat] += f['capacity']

        for cat in categories:
            committed_by_cat[cat].append(round(cat_committed[cat], 1))
            probable_by_cat[cat].append(round(cat_probable[cat], 1))
            retirements_by_cat[cat].append(round(cat_retiring[cat], 1))

    waterfall_data = {
        'years': years,
        'categories': categories,
        'committed': committed_by_cat,
        'probable': probable_by_cat,
        'retirements': retirements_by_cat,
    }

    ctx['waterfall_json'] = json.dumps(waterfall_data)
    ctx['facilities_json'] = json.dumps(facs)
    ctx['year_min'] = year_min
    ctx['year_max'] = year_max
    return render(request, 'pipeline_waterfall.html', ctx)
