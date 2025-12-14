from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q, Sum, Count
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from siren_web.models import Technologies, FacilityStorage, facilities

def facility_storage_list(request):
    """List all facility storage installations with search and pagination"""
    demand_year = request.session.get('demand_year', '')
    scenario = request.session.get('scenario', '')
    config_file = request.session.get('config_file')
    
    search_query = request.GET.get('search', '')
    facility_filter = request.GET.get('facility', '')
    technology_filter = request.GET.get('technology', '')
    active_only = request.GET.get('active_only', '') == 'on'
    
    # Get all facility storage installations
    installations = FacilityStorage.objects.select_related(
        'idfacilities', 
        'idtechnologies'
    ).order_by('-is_active', 'idfacilities__facility_name', 'idtechnologies__technology_name')
    
    # Apply search filter
    if search_query:
        installations = installations.filter(
            Q(idfacilities__facility_name__icontains=search_query) |
            Q(idtechnologies__technology_name__icontains=search_query) |
            Q(installation_name__icontains=search_query)
        )
    
    # Apply facility filter
    if facility_filter:
        installations = installations.filter(idfacilities__facility_name__icontains=facility_filter)
    
    # Apply technology filter
    if technology_filter:
        installations = installations.filter(idtechnologies__technology_name__icontains=technology_filter)
    
    # Apply active filter
    if active_only:
        installations = installations.filter(is_active=True)
    
    # Get filter options
    facilities_list = facilities.objects.values_list('facility_name', flat=True).distinct().order_by('facility_name')
    technologies_list = Technologies.objects.filter(category='Storage').values_list('technology_name', flat=True).distinct().order_by('technology_name')
    
    # Calculate summary statistics
    total_power = installations.filter(is_active=True).aggregate(Sum('power_capacity'))['power_capacity__sum'] or 0
    total_energy = installations.filter(is_active=True).aggregate(Sum('energy_capacity'))['energy_capacity__sum'] or 0
    
    # Pagination
    paginator = Paginator(installations, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
        'page_obj': page_obj,
        'search_query': search_query,
        'facility_filter': facility_filter,
        'technology_filter': technology_filter,
        'active_only': active_only,
        'facilities_list': facilities_list,
        'technologies_list': technologies_list,
        'total_count': installations.count(),
        'total_power': total_power,
        'total_energy': total_energy,
    }
    
    return render(request, 'facility_storage/list.html', context)

def facility_storage_detail(request, pk):
    """Detail view for a specific facility storage installation"""
    demand_year = request.session.get('demand_year', '')
    scenario = request.session.get('scenario', '')
    config_file = request.session.get('config_file')
    
    installation = get_object_or_404(
        FacilityStorage.objects.select_related('idfacilities', 'idtechnologies'),
        pk=pk
    )
    
    # Get storage attributes from technology
    storage_attrs = installation.storage_attrs
    
    # Calculate derived values
    derived_values = {
        'calculated_duration': installation.get_calculated_duration(),
        'usable_capacity': installation.get_usable_capacity(),
        'round_trip_efficiency': installation.get_round_trip_efficiency(),
        'cycle_life': installation.get_cycle_life(),
    }
    
    context = {
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
        'installation': installation,
        'storage_attrs': storage_attrs,
        'derived_values': derived_values,
    }
    
    return render(request, 'facility_storage/detail.html', context)

def facility_storage_create(request, facility_id):
    """Create a new storage installation for a specific facility"""
    facility = get_object_or_404(facilities, pk=facility_id)

    if request.method == 'POST':
        try:
            # Extract form data
            technology_id = request.POST.get('technology')
            installation_name = request.POST.get('installation_name', '').strip()
            power_capacity = request.POST.get('power_capacity')
            energy_capacity = request.POST.get('energy_capacity')
            duration = request.POST.get('duration')
            initial_soc = request.POST.get('initial_state_of_charge')
            installation_date = request.POST.get('installation_date')
            commissioning_date = request.POST.get('commissioning_date')
            notes = request.POST.get('notes', '').strip()
            
            # Validation
            if not technology_id:
                messages.error(request, 'Storage technology is required.')
                return render(request, 'facility_storage/create.html', {
                    'facility': facility,
                    'technologies': Technologies.objects.filter(category='Storage').order_by('technology_name'),
                    'form_data': request.POST
                })

            # At least one capacity field should be provided
            if not any([power_capacity, energy_capacity, duration]):
                messages.error(request, 'At least one capacity field (Power, Energy, or Duration) must be provided.')
                return render(request, 'facility_storage/create.html', {
                    'facility': facility,
                    'technologies': Technologies.objects.filter(category='Storage').order_by('technology_name'),
                    'form_data': request.POST
                })

            # Get technology
            technology = get_object_or_404(Technologies, pk=technology_id, category='Storage')
            
            # Check for duplicate installation (same facility, technology, and name)
            if FacilityStorage.objects.filter(
                idfacilities=facility, 
                idtechnologies=technology,
                installation_name=installation_name or None
            ).exists():
                messages.error(request, 'This storage installation already exists at this facility.')
                return render(request, 'facility_storage/create.html', {
                    'facility': facility,
                    'technologies': Technologies.objects.filter(category='Storage').order_by('technology_name'),
                    'form_data': request.POST
                })
            
            # Create the installation
            installation = FacilityStorage.objects.create(
                idfacilities=facility,
                idtechnologies=technology,
                installation_name=installation_name if installation_name else None,
                power_capacity=float(power_capacity) if power_capacity else None,
                energy_capacity=float(energy_capacity) if energy_capacity else None,
                duration=float(duration) if duration else None,
                initial_state_of_charge=float(initial_soc) if initial_soc else None,
                installation_date=installation_date if installation_date else None,
                commissioning_date=commissioning_date if commissioning_date else None,
                notes=notes if notes else None,
                is_active=True
            )
            
            messages.success(request, f'Storage installation created successfully at {facility.facility_name}.')
            return redirect('powermapui:facility_storage_detail', pk=installation.pk)
            
        except ValueError as e:
            messages.error(request, f'Invalid numeric value provided: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error creating storage installation: {str(e)}')
    
    context = {
        'facility': facility,
        'technologies': Technologies.objects.filter(category='Storage').order_by('technology_name')
    }

    if request.method == 'POST':
        context['form_data'] = request.POST

    return render(request, 'facility_storage/create.html', context)

def facility_storage_edit(request, pk):
    """Edit an existing facility storage installation"""
    installation = get_object_or_404(FacilityStorage, pk=pk)
    
    if request.method == 'POST':
        try:
            # Extract form data
            installation_name = request.POST.get('installation_name', '').strip()
            power_capacity = request.POST.get('power_capacity')
            energy_capacity = request.POST.get('energy_capacity')
            duration = request.POST.get('duration')
            initial_soc = request.POST.get('initial_state_of_charge')
            installation_date = request.POST.get('installation_date')
            commissioning_date = request.POST.get('commissioning_date')
            notes = request.POST.get('notes', '').strip()
            is_active = request.POST.get('is_active') == 'on'
            
            # Validation
            if not any([power_capacity, energy_capacity, duration]):
                messages.error(request, 'At least one capacity field must be provided.')
                return render(request, 'facility_storage/edit.html', {
                    'installation': installation,
                    'form_data': request.POST
                })
            
            # Update the installation
            installation.installation_name = installation_name if installation_name else None
            installation.power_capacity = float(power_capacity) if power_capacity else None
            installation.energy_capacity = float(energy_capacity) if energy_capacity else None
            installation.duration = float(duration) if duration else None
            installation.initial_state_of_charge = float(initial_soc) if initial_soc else None
            installation.installation_date = installation_date if installation_date else None
            installation.commissioning_date = commissioning_date if commissioning_date else None
            installation.notes = notes if notes else None
            installation.is_active = is_active
            installation.save()

            messages.success(request, 'Storage installation updated successfully.')
            return redirect('powermapui:facility_detail', pk=installation.facility.idfacilities)
            
        except ValueError as e:
            messages.error(request, f'Invalid numeric value provided: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error updating installation: {str(e)}')
    
    context = {
        'installation': installation,
        'storage_attrs': installation.storage_attrs
    }
    return render(request, 'facility_storage/edit.html', context)

@require_POST
def facility_storage_delete(request, pk):
    """Delete a facility storage installation"""
    installation = get_object_or_404(FacilityStorage, pk=pk)

    facility_id = installation.facility.idfacilities
    facility_name = installation.facility.facility_name
    technology_name = installation.technology.technology_name

    installation.delete()
    messages.success(request, f'Removed {technology_name} installation from {facility_name}.')
    return redirect('powermapui:facility_detail', pk=facility_id)

def get_facility_storage_json(request):
    """Return facility storage installations as JSON"""
    installations = FacilityStorage.objects.select_related(
        'idfacilities',
        'idtechnologies'
    ).filter(is_active=True)
    
    data = []
    for install in installations:
        storage_attrs = install.storage_attrs
        data.append({
            'id': install.idfacilitystorage,
            'facility_id': install.idfacilities.idfacilities,
            'facility_name': install.idfacilities.facility_name,
            'technology_id': install.idtechnologies.idtechnologies,
            'technology_name': install.idtechnologies.technology_name,
            'installation_name': install.installation_name,
            'power_capacity': install.power_capacity,
            'energy_capacity': install.energy_capacity,
            'duration': install.get_calculated_duration(),
            'usable_capacity': install.get_usable_capacity(),
            'round_trip_efficiency': storage_attrs.round_trip_efficiency if storage_attrs else None,
            'is_active': install.is_active,
        })
    
    return JsonResponse({
        'installations': data,
        'count': len(data),
        'total_power_mw': sum(d['power_capacity'] or 0 for d in data),
        'total_energy_mwh': sum(d['energy_capacity'] or 0 for d in data),
    })