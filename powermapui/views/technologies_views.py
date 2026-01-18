# powermapui/views/technologies_views.py
from datetime import datetime
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from siren_web.models import Technologies, TechnologyYears
from siren_web.forms import DemandYearForm
from siren_web.database_operations import fetch_full_generator_storage_data
from powermapui.forms import TechnologyForm, TechnologyYearsForm


def technologies(request):
    """Original technologies view - displays read-only table"""
    weather_year = request.session.get('weather_year', 2024)
    demand_year = request.session.get('demand_year', 2024)
    scenario = request.session.get('scenario')
    config_file = request.session.get('config_file')
    success_message = ""
    technology_name = request.GET.get('technology_name', '')

    # Handle form submission
    if request.method == 'POST':
        demand_year_form = DemandYearForm(request.POST)
        if demand_year_form.is_valid():
            demand_year = demand_year_form.cleaned_data['demand_year']
            request.session['demand_year'] = demand_year
    else:
        url_demand_year = request.GET.get('demand_year')
        if url_demand_year:
            try:
                demand_year = int(url_demand_year)
                request.session['demand_year'] = demand_year
            except ValueError:
                pass

    technology_queryset = fetch_full_generator_storage_data(demand_year)

    attribute_explain = {
        'area': 'The area occupied by a technology.',
        'capacity': 'The capacity of the technology in mW (generation) or MWhs (storage).',
        'capacity_max': 'The maximum capacity of the technology in mW (generation) or MWhs (storage).',
        'capacity_min': 'The minimum capacity of the technology in mW (generation) or MWhs (storage).',
        'function': 'The role it plays in the grid.',
        'capex': 'The initial capital expenditure for the technology.',
        'discharge_loss': 'The percentage capacity that is lost in discharging.',
        'discharge_max': 'The maxiumum percentage of storage capacity that can be discharged.',
        'discount_rate': 'The discount rate applied to the technology.',
        'dispatchable': 'The technology can be dispatched at any time when required.',
        'emissions': 'CO2 emmissions in kg/mWh',
        'fuel': 'The cost of fuel consumed by the technology.',
        'fom': 'The fixed operating cost of the technology.',
        'lifetime': 'The operational lifetime of the technology.',
        'parasitic_loss': 'The percentage of storage capacity lost other than by charging or discharging.',
        'rampdown_max': 'The maximum rampdown rate of the technology.',
        'rampup_max': 'The maximum rampup rate of the technology.',
        'recharge_loss': 'The percentage capacity that is lost in recharging.',
        'recharge_max': 'The maximum recharge rate of the technology.',
        'renewable': 'Whether the technology can be renewed.',
        'vom': 'The variable operating cost of the technology.',
        'year': 'The year of reference.',
    }

    demand_year_form = DemandYearForm(initial={'demand_year': demand_year})

    context = {
        'demand_year_form': demand_year_form,
        'technology_queryset': technology_queryset,
        'attribute_explain': attribute_explain,
        'weather_year': weather_year,
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
        'success_message': success_message
    }

    return render(request, 'technologies.html', context)


# ============================================================================
# Technologies CRUD Views
# ============================================================================

@login_required
def technology_list(request):
    """List all technologies with search and filtering"""
    weather_year = request.session.get('weather_year', '')
    demand_year = request.session.get('demand_year', '')
    scenario = request.session.get('scenario', '')
    config_file = request.session.get('config_file')

    technologies = Technologies.objects.all().annotate(
        year_count=Count('technologyyears')
    )

    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        technologies = technologies.filter(
            Q(technology_name__icontains=search_query) |
            Q(technology_signature__icontains=search_query) |
            Q(category__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    # Filter by category
    category = request.GET.get('category', '')
    if category:
        technologies = technologies.filter(category=category)

    # Filter by fuel type
    fuel_type = request.GET.get('fuel_type', '')
    if fuel_type:
        technologies = technologies.filter(fuel_type=fuel_type)

    # Get distinct categories and fuel types for filters
    categories = Technologies.objects.values_list('category', flat=True).distinct().order_by('category')
    categories = [c for c in categories if c]

    fuel_types = [
        ('WIND', 'Wind'), ('SOLAR', 'Solar'), ('GAS', 'Gas'),
        ('COAL', 'Coal'), ('HYDRO', 'Hydro'), ('BIOMASS', 'Biomass'), ('OTHER', 'Other')
    ]

    # Pagination
    paginator = Paginator(technologies.order_by('technology_name'), 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'category': category,
        'fuel_type': fuel_type,
        'categories': categories,
        'fuel_types': fuel_types,
        'weather_year': weather_year,
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
    }
    return render(request, 'technologies/list.html', context)


@login_required
def technology_detail(request, pk):
    """Show detailed view of a technology with its year data"""
    weather_year = request.session.get('weather_year', '')
    demand_year = request.session.get('demand_year', '')
    scenario = request.session.get('scenario', '')
    config_file = request.session.get('config_file')

    technology = get_object_or_404(Technologies, pk=pk)
    technology_years = TechnologyYears.objects.filter(
        idtechnologies=technology
    ).order_by('year')

    context = {
        'technology': technology,
        'technology_years': technology_years,
        'weather_year': weather_year,
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
    }
    return render(request, 'technologies/detail.html', context)


@login_required
def technology_create(request):
    """Create a new technology"""
    weather_year = request.session.get('weather_year', '')
    demand_year = request.session.get('demand_year', '')
    scenario = request.session.get('scenario', '')
    config_file = request.session.get('config_file')

    if request.method == 'POST':
        form = TechnologyForm(request.POST)
        if form.is_valid():
            technology = form.save()
            messages.success(request, f'Technology "{technology.technology_name}" created successfully.')
            return redirect('powermapui:technology_detail', pk=technology.pk)
        else:
            for field_name, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field_name}: {error}")
    else:
        form = TechnologyForm()

    return render(request, 'technologies/form.html', {
        'form': form,
        'title': 'Add New Technology',
        'weather_year': weather_year,
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
    })


@login_required
def technology_edit(request, pk):
    """Update an existing technology"""
    weather_year = request.session.get('weather_year', '')
    demand_year = request.session.get('demand_year', '')
    scenario = request.session.get('scenario', '')
    config_file = request.session.get('config_file')

    technology = get_object_or_404(Technologies, pk=pk)

    if request.method == 'POST':
        form = TechnologyForm(request.POST, instance=technology)
        if form.is_valid():
            form.save()
            messages.success(request, f'Technology "{technology.technology_name}" updated successfully.')
            return redirect('powermapui:technology_detail', pk=technology.pk)
    else:
        form = TechnologyForm(instance=technology)

    return render(request, 'technologies/form.html', {
        'form': form,
        'technology': technology,
        'title': 'Edit Technology',
        'weather_year': weather_year,
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
    })


@login_required
@require_POST
def technology_delete(request, pk):
    """Delete a technology"""
    technology = get_object_or_404(Technologies, pk=pk)
    technology_name = technology.technology_name

    # Check for related records
    year_count = TechnologyYears.objects.filter(idtechnologies=technology).count()
    if year_count > 0:
        messages.error(
            request,
            f'Cannot delete "{technology_name}". It has {year_count} year record(s). '
            f'Delete the year records first.'
        )
        return redirect('powermapui:technology_detail', pk=pk)

    technology.delete()
    messages.success(request, f'Technology "{technology_name}" has been deleted.')
    return redirect('powermapui:technology_list')


@login_required
def technology_search_api(request):
    """API endpoint for AJAX search"""
    query = request.GET.get('q', '')
    if len(query) < 2:
        return JsonResponse({'results': []})

    technologies = Technologies.objects.filter(
        Q(technology_name__icontains=query) |
        Q(technology_signature__icontains=query) |
        Q(category__icontains=query)
    )[:10]

    results = [{
        'id': tech.idtechnologies,
        'name': tech.technology_name,
        'signature': tech.technology_signature,
        'category': tech.category,
    } for tech in technologies]

    return JsonResponse({'results': results})


# ============================================================================
# TechnologyYears CRUD Views
# ============================================================================

@login_required
def technology_years_create(request, technology_pk=None):
    """Create a new technology year record"""
    weather_year = request.session.get('weather_year', '')
    demand_year = request.session.get('demand_year', '')
    scenario = request.session.get('scenario', '')
    config_file = request.session.get('config_file')

    initial = {}
    technology = None
    if technology_pk:
        technology = get_object_or_404(Technologies, pk=technology_pk)
        initial['idtechnologies'] = technology
        # Get the greatest existing year for this technology and add 1
        # If no existing years, default to next year after current year
        max_year = TechnologyYears.objects.filter(
            idtechnologies=technology
        ).order_by('-year').values_list('year', flat=True).first()
        if max_year:
            initial['year'] = max_year + 1
        else:
            initial['year'] = datetime.now().year + 1

    if request.method == 'POST':
        form = TechnologyYearsForm(request.POST)
        if form.is_valid():
            tech_year = form.save()
            messages.success(
                request,
                f'Year {tech_year.year} data for "{tech_year.idtechnologies.technology_name}" created successfully.'
            )
            return redirect('powermapui:technology_detail', pk=tech_year.idtechnologies.pk)
        else:
            for field_name, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field_name}: {error}")
    else:
        form = TechnologyYearsForm(initial=initial)

    context = {
        'form': form,
        'title': 'Add Technology Year Data',
        'technology': technology,
        'weather_year': weather_year,
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
    }

    return render(request, 'technologies/years_form.html', context)


@login_required
def technology_years_edit(request, pk):
    """Update an existing technology year record"""
    weather_year = request.session.get('weather_year', '')
    demand_year = request.session.get('demand_year', '')
    scenario = request.session.get('scenario', '')
    config_file = request.session.get('config_file')

    tech_year = get_object_or_404(TechnologyYears, pk=pk)

    if request.method == 'POST':
        form = TechnologyYearsForm(request.POST, instance=tech_year)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f'Year {tech_year.year} data for "{tech_year.idtechnologies.technology_name}" updated successfully.'
            )
            return redirect('powermapui:technology_detail', pk=tech_year.idtechnologies.pk)
    else:
        form = TechnologyYearsForm(instance=tech_year)

    return render(request, 'technologies/years_form.html', {
        'form': form,
        'tech_year': tech_year,
        'title': 'Edit Technology Year Data',
        'weather_year': weather_year,
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
    })


@login_required
@require_POST
def technology_years_delete(request, pk):
    """Delete a technology year record"""
    tech_year = get_object_or_404(TechnologyYears, pk=pk)
    technology_pk = tech_year.idtechnologies.pk
    year = tech_year.year
    tech_name = tech_year.idtechnologies.technology_name

    tech_year.delete()
    messages.success(request, f'Year {year} data for "{tech_name}" has been deleted.')
    return redirect('powermapui:technology_detail', pk=technology_pk)
