from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from django.views.decorators.http import require_POST
from siren_web.models import facilities, Scenarios, ScenariosFacilities, Technologies, Zones

def facilities_list(request):
    """List all facilities with search and pagination"""
    search_query = request.GET.get('search', '')
    scenario_filter = request.GET.get('scenario', '')
    technology_filter = request.GET.get('technology', '')
    zone_filter = request.GET.get('zone', '')
    
    facs = facilities.objects.select_related(
        'idzones'
    ).prefetch_related(
        'solar_installations__idtechnologies',
        'storage_installations__idtechnologies',
        'facilitywindturbines_set__idtechnologies'
    ).all().order_by('facility_name')

    # Apply search filter
    if search_query:
        facs = facs.filter(
            Q(facility_name__icontains=search_query) |
            Q(solar_installations__idtechnologies__technology_name__icontains=search_query) |
            Q(storage_installations__idtechnologies__technology_name__icontains=search_query) |
            Q(facilitywindturbines_set__idtechnologies__technology_name__icontains=search_query) |
            Q(idzones__name__icontains=search_query)
        ).distinct()
    
    # Apply scenario filter
    if scenario_filter:
        scenario_obj = Scenarios.objects.get(idscenarios=scenario_filter)
        facility_ids = ScenariosFacilities.objects.filter(
            idscenarios=scenario_obj
        ).values_list('idfacilities', flat=True)
        facs = facs.filter(idfacilities__in=facility_ids)
    
    # Apply technology filter
    if technology_filter:
        facs = facs.filter(
            Q(solar_installations__idtechnologies__technology_name__icontains=technology_filter) |
            Q(storage_installations__idtechnologies__technology_name__icontains=technology_filter) |
            Q(facilitywindturbines_set__idtechnologies__technology_name__icontains=technology_filter)
        ).distinct()
    
    # Apply zone filter
    if zone_filter:
        facs = facs.filter(idzones__name__icontains=zone_filter)
    
    # Get filter options
    scenarios = Scenarios.objects.all().order_by('title')
    technologies = Technologies.objects.values_list('technology_name', flat=True).distinct().order_by('technology_name')
    technologies = [t for t in technologies if t]
    zones = Zones.objects.values_list('name', flat=True).distinct().order_by('name')
    zones = [z for z in zones if z]
    
    # Pagination
    paginator = Paginator(facs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Session variables for other pages
    weather_year = request.session.get('weather_year', '')
    demand_year = request.session.get('demand_year', '')
    scenario = request.session.get('scenario', '')
    config_file = request.session.get('config_file', '')
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'scenario_filter': scenario_filter,
        'technology_filter': technology_filter,
        'zone_filter': zone_filter,
        'scenarios': scenarios,
        'technologies': technologies,
        'zones': zones,
        'total_count': facs.count(),
        'weather_year': weather_year,
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
    }
    
    return render(request, 'facilities/list.html', context)

def facility_detail(request, pk):
    """Detail view for a specific facility"""
    from siren_web.models import FacilityWindTurbines, FacilitySolar, FacilityStorage, HybridSolarStorage

    facility = get_object_or_404(facilities, pk=pk)

    # Get scenarios this facility belongs to
    facility_scenarios = ScenariosFacilities.objects.filter(
        idfacilities=facility
    ).select_related('idscenarios')

    # Get all technology installations at this facility
    wind_installations = FacilityWindTurbines.objects.filter(
        idfacilities=facility,
        is_active=True
    ).select_related('idwindturbines', 'idtechnologies')

    solar_installations = FacilitySolar.objects.filter(
        idfacilities=facility,
        is_active=True
    ).select_related('idtechnologies')

    storage_installations = FacilityStorage.objects.filter(
        idfacilities=facility,
        is_active=True
    ).select_related('idtechnologies')

    hybrid_systems = HybridSolarStorage.objects.filter(
        solar_installation__idfacilities=facility,
        is_active=True
    ).select_related('solar_installation__idtechnologies', 'storage_installation__idtechnologies')

    # Get facility capacity summary
    capacity_summary = facility.get_installation_summary()

    context = {
        'facility': facility,
        'facility_scenarios': facility_scenarios,
        'wind_installations': wind_installations,
        'solar_installations': solar_installations,
        'storage_installations': storage_installations,
        'hybrid_systems': hybrid_systems,
        'capacity_summary': capacity_summary,
    }

    return render(request, 'facilities/detail.html', context)

def facility_create(request):
    """Create a new facility"""
    if request.method == 'POST':
        try:
            # Extract form data
            facility_name = request.POST.get('facility_name', '').strip()
            technology_id = request.POST.get('technology')
            zone_id = request.POST.get('zone')
            capacity = request.POST.get('capacity')
            capacity_factor = request.POST.get('capacity_factor')
            generation = request.POST.get('generation')
            transmitted = request.POST.get('transmitted')
            emission_intensity = request.POST.get('emission_intensity')
            latitude = request.POST.get('latitude')
            longitude = request.POST.get('longitude')
            scenario_ids = request.POST.getlist('scenarios')
            
            # Validation
            if not facility_name:
                messages.error(request, 'Facility name is required.')
                return render(request, 'facilities/create.html', {
                    'form_data': request.POST,
                    'technologies': Technologies.objects.all().order_by('technology_name'),
                    'zones': Zones.objects.all().order_by('name'),
                    'scenarios': Scenarios.objects.all().order_by('title')
                })
            
            # Check for duplicate facility name
            if facilities.objects.filter(facility_name=facility_name).exists():
                messages.error(request, 'A facility with this name already exists.')
                return render(request, 'facilities/create.html', {
                    'form_data': request.POST,
                    'technologies': Technologies.objects.all().order_by('technology_name'),
                    'zones': Zones.objects.all().order_by('name'),
                    'scenarios': Scenarios.objects.all().order_by('title')
                })
            
            # Get technology and zone objects
            technology = get_object_or_404(Technologies, pk=technology_id) if technology_id else None
            zone = get_object_or_404(Zones, pk=zone_id) if zone_id else None
            
            # Create the facility
            facility = facilities.objects.create(
                facility_name=facility_name,
                idtechnologies=technology,
                idzones=zone,
                capacity=float(capacity) if capacity else None,
                capacityfactor=float(capacity_factor) if capacity_factor else None,
                emission_intensity=float(emission_intensity) if emission_intensity else None,
                active=1,
                existing=1,
                latitude=float(latitude) if latitude else None,
                longitude=float(longitude) if longitude else None,
            )
            
            # Add to scenarios
            if scenario_ids:
                for scenario_id in scenario_ids:
                    scenario = Scenarios.objects.get(pk=scenario_id)
                    ScenariosFacilities.objects.create(
                        idscenarios=scenario,
                        idfacilities=facility
                    )
            
            messages.success(request, f'Facility "{facility_name}" created successfully.')
            return redirect('powermapui:facility_detail', pk=facility.pk)
            
        except ValueError as e:
            messages.error(request, 'Invalid numeric value provided.')
            return render(request, 'facilities/create.html', {
                'form_data': request.POST,
                'technologies': Technologies.objects.all().order_by('technology_name'),
                'zones': Zones.objects.all().order_by('name'),
                'scenarios': Scenarios.objects.all().order_by('title')
            })
        except Exception as e:
            messages.error(request, f'Error creating facility: {str(e)}')
            return render(request, 'facilities/create.html', {
                'form_data': request.POST,
                'technologies': Technologies.objects.all().order_by('technology_name'),
                'zones': Zones.objects.all().order_by('name'),
                'scenarios': Scenarios.objects.all().order_by('title')
            })
    
    context = {
        'technologies': Technologies.objects.all().order_by('technology_name'),
        'zones': Zones.objects.all().order_by('name'),
        'scenarios': Scenarios.objects.all().order_by('title')
    }
    return render(request, 'facilities/create.html', context)

def facility_edit(request, pk):
    """Edit an existing facility"""
    facility = get_object_or_404(facilities, pk=pk)
    
    # Get current scenarios
    current_scenario_ids = list(ScenariosFacilities.objects.filter(
        idfacilities=facility
    ).values_list('idscenarios__idscenarios', flat=True))
    
    if request.method == 'POST':
        try:
            # Extract form data
            facility_name = request.POST.get('facility_name', '').strip()
            technology_id = request.POST.get('technology')
            zone_id = request.POST.get('zone')
            capacity = request.POST.get('capacity')
            capacity_factor = request.POST.get('capacity_factor')
            generation = request.POST.get('generation')
            transmitted = request.POST.get('transmitted')
            emission_intensity = request.POST.get('emission_intensity')
            latitude = request.POST.get('latitude')
            longitude = request.POST.get('longitude')
            scenario_ids = request.POST.getlist('scenarios')
            
            # Validation
            if not facility_name:
                messages.error(request, 'Facility name is required.')
                return render(request, 'facilities/edit.html', {
                    'facility': facility,
                    'technologies': Technologies.objects.all().order_by('technology_name'),
                    'zones': Zones.objects.all().order_by('name'),
                    'scenarios': Scenarios.objects.all().order_by('title'),
                    'current_scenario_ids': current_scenario_ids
                })
            
            # Check for duplicate facility name (excluding current facility)
            if facilities.objects.filter(facility_name=facility_name).exclude(pk=pk).exists():
                messages.error(request, 'A facility with this name already exists.')
                return render(request, 'facilities/edit.html', {
                    'facility': facility,
                    'form_data': request.POST,
                    'technologies': Technologies.objects.all().order_by('technology_name'),
                    'zones': Zones.objects.all().order_by('name'),
                    'scenarios': Scenarios.objects.all().order_by('title'),
                    'current_scenario_ids': current_scenario_ids
                })
            
            # Get technology and zone objects
            technology = get_object_or_404(Technologies, pk=technology_id) if technology_id else None
            zone = get_object_or_404(Zones, pk=zone_id) if zone_id else None
            
            # Update the facility
            facility.facility_name = facility_name
            facility.idtechnologies = technology
            facility.idzones = zone
            facility.capacity = float(capacity) if capacity else None
            facility.capacityfactor = float(capacity_factor) if capacity_factor else None
            facility.generation = float(generation) if generation else None
            facility.transmitted = float(transmitted) if transmitted else None
            facility.emission_intensity = float(emission_intensity) if emission_intensity else None
            facility.latitude = float(latitude) if latitude else None
            facility.longitude = float(longitude) if longitude else None
            facility.save()
            
            # Update scenarios - remove old, add new
            ScenariosFacilities.objects.filter(idfacilities=facility).delete()
            if scenario_ids:
                for scenario_id in scenario_ids:
                    scenario = Scenarios.objects.get(pk=scenario_id)
                    ScenariosFacilities.objects.create(
                        idscenarios=scenario,
                        idfacilities=facility
                    )
            
            messages.success(request, f'Facility "{facility_name}" updated successfully.')
            return redirect('powermapui:facility_detail', pk=facility.pk)
            
        except ValueError as e:
            messages.error(request, 'Invalid numeric value provided.')
            return render(request, 'facilities/edit.html', {
                'facility': facility,
                'technologies': Technologies.objects.all().order_by('technology_name'),
                'zones': Zones.objects.all().order_by('name'),
                'scenarios': Scenarios.objects.all().order_by('title'),
                'current_scenario_ids': current_scenario_ids
            })
        except Exception as e:
            messages.error(request, f'Error updating facility: {str(e)}')
            return render(request, 'facilities/edit.html', {
                'facility': facility,
                'technologies': Technologies.objects.all().order_by('technology_name'),
                'zones': Zones.objects.all().order_by('name'),
                'scenarios': Scenarios.objects.all().order_by('title'),
                'current_scenario_ids': current_scenario_ids
            })
    
    context = {
        'facility': facility,
        'technologies': Technologies.objects.all().order_by('technology_name'),
        'zones': Zones.objects.all().order_by('name'),
        'scenarios': Scenarios.objects.all().order_by('title'),
        'current_scenario_ids': current_scenario_ids
    }
    
    return render(request, 'facilities/edit.html', context)

@require_POST
def facility_delete(request, pk):
    """Delete a facility"""
    facility = get_object_or_404(facilities, pk=pk)
    
    facility_name = facility.facility_name
    
    # Delete scenario associations first
    ScenariosFacilities.objects.filter(idfacilities=facility).delete()
    
    # Delete the facility
    facility.delete()
    
    messages.success(request, f'Facility "{facility_name}" deleted successfully.')
    return redirect('powermapui:facilities_list')