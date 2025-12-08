from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q, Sum, Count
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from siren_web.models import Technologies, FacilitySolar, facilities

def facility_solar_list(request):
    """List all facility solar installations with search and pagination"""
    demand_year = request.session.get('demand_year', '')
    scenario = request.session.get('scenario', '')
    config_file = request.session.get('config_file')
    
    search_query = request.GET.get('search', '')
    facility_filter = request.GET.get('facility', '')
    technology_filter = request.GET.get('technology', '')
    active_only = request.GET.get('active_only', '') == 'on'
    
    # Get all facility solar installations
    installations = FacilitySolar.objects.select_related(
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
    technologies_list = Technologies.objects.filter(fuel_type = 'SOLAR').values_list('technology_name', flat=True).distinct().order_by('technology_name')
    
    # Calculate summary statistics
    total_dc_capacity = installations.filter(is_active=True).aggregate(Sum('nameplate_capacity'))['nameplate_capacity__sum'] or 0
    total_ac_capacity = installations.filter(is_active=True).aggregate(Sum('ac_capacity'))['ac_capacity__sum'] or 0
    
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
        'total_dc_capacity': total_dc_capacity,
        'total_ac_capacity': total_ac_capacity,
    }
    
    return render(request, 'facility_solar/list.html', context)

def facility_solar_detail(request, pk):
    """Detail view for a specific facility solar installation"""
    demand_year = request.session.get('demand_year', '')
    scenario = request.session.get('scenario', '')
    config_file = request.session.get('config_file')
    
    installation = get_object_or_404(
        FacilitySolar.objects.select_related('idfacilities', 'idtechnologies'),
        pk=pk
    )
    
    # Get solar attributes from technology
    solar_attrs = installation.solar_attrs
    
    # Calculate derived values
    derived_values = {
        'calculated_dc_ac_ratio': installation.get_calculated_dc_ac_ratio(),
        'calculated_panel_count': installation.get_calculated_panel_count(),
        'calculated_array_area': installation.get_calculated_array_area(),
        'panel_efficiency': installation.get_panel_efficiency(),
        'performance_ratio': installation.get_performance_ratio(),
    }
    
    # Calculate total inverter capacity
    if installation.inverter_count and installation.inverter_capacity_each:
        derived_values['total_inverter_capacity'] = (
            installation.inverter_count * installation.inverter_capacity_each / 1000  # Convert kW to MW
        )
    else:
        derived_values['total_inverter_capacity'] = None
    
    context = {
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
        'installation': installation,
        'solar_attrs': solar_attrs,
        'derived_values': derived_values,
    }
    
    return render(request, 'facility_solar/detail.html', context)

def facility_solar_create(request):
    """Create a new facility solar installation"""
    # Filter to facilities with solar technology
    solar_facilities = facilities.objects.filter(
        idtechnologies__fuel_type='SOLAR'
    ).select_related('idtechnologies').order_by('facility_name')
    
    if request.method == 'POST':
        try:
            # Extract form data
            facility_id = request.POST.get('facility')
            installation_name = request.POST.get('installation_name', '').strip()
            nameplate_capacity = request.POST.get('nameplate_capacity')
            ac_capacity = request.POST.get('ac_capacity')
            panel_count = request.POST.get('panel_count')
            panel_wattage = request.POST.get('panel_wattage')
            tilt_angle = request.POST.get('tilt_angle')
            azimuth_angle = request.POST.get('azimuth_angle')
            array_area = request.POST.get('array_area')
            inverter_count = request.POST.get('inverter_count')
            inverter_capacity_each = request.POST.get('inverter_capacity_each')
            installation_date = request.POST.get('installation_date')
            commissioning_date = request.POST.get('commissioning_date')
            notes = request.POST.get('notes', '').strip()
            
            # Validation
            if not facility_id:
                messages.error(request, 'Facility is required.')
                return render(request, 'facility_solar/create.html', {
                    'facilities': solar_facilities,
                    'form_data': request.POST
                })
            
            # At least one capacity field should be provided
            if not any([nameplate_capacity, ac_capacity]):
                messages.error(request, 'At least one capacity field (DC or AC) must be provided.')
                return render(request, 'facility_solar/create.html', {
                    'facilities': solar_facilities,
                    'form_data': request.POST
                })
            
            # Get facility and its associated technology
            facility = get_object_or_404(
                facilities.objects.select_related('idtechnologies'), 
                pk=facility_id,
                idtechnologies__fuel_type='SOLAR'
            )
            technology = facility.idtechnologies
            
            # Check for duplicate installation
            if FacilitySolar.objects.filter(
                idfacilities=facility, 
                idtechnologies=technology,
                installation_name=installation_name or None
            ).exists():
                messages.error(request, 'This solar installation already exists at this facility.')
                return render(request, 'facility_solar/create.html', {
                    'facilities': solar_facilities,
                    'form_data': request.POST
                })
            
            # Create the installation
            installation = FacilitySolar.objects.create(
                idfacilities=facility,
                idtechnologies=technology,
                installation_name=installation_name if installation_name else None,
                nameplate_capacity=float(nameplate_capacity) if nameplate_capacity else None,
                ac_capacity=float(ac_capacity) if ac_capacity else None,
                panel_count=int(panel_count) if panel_count else None,
                panel_wattage=float(panel_wattage) if panel_wattage else None,
                tilt_angle=float(tilt_angle) if tilt_angle else None,
                azimuth_angle=float(azimuth_angle) if azimuth_angle else None,
                array_area=float(array_area) if array_area else None,
                inverter_count=int(inverter_count) if inverter_count else None,
                inverter_capacity_each=float(inverter_capacity_each) if inverter_capacity_each else None,
                installation_date=installation_date if installation_date else None,
                commissioning_date=commissioning_date if commissioning_date else None,
                notes=notes if notes else None,
                is_active=True
            )
            
            messages.success(request, f'Solar installation created successfully at {facility.facility_name}.')
            return redirect('powermapui:facility_solar_detail', pk=installation.pk)
            
        except ValueError as e:
            messages.error(request, f'Invalid numeric value provided: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error creating solar installation: {str(e)}')
    
    context = {
        'facilities': solar_facilities,
    }
    
    if request.method == 'POST':
        context['form_data'] = request.POST
    
    return render(request, 'facility_solar/create.html', context)

def facility_solar_edit(request, pk):
    """Edit an existing facility solar installation"""
    installation = get_object_or_404(FacilitySolar, pk=pk)
    
    if request.method == 'POST':
        try:
            # Extract form data
            installation_name = request.POST.get('installation_name', '').strip()
            nameplate_capacity = request.POST.get('nameplate_capacity')
            ac_capacity = request.POST.get('ac_capacity')
            panel_count = request.POST.get('panel_count')
            panel_wattage = request.POST.get('panel_wattage')
            tilt_angle = request.POST.get('tilt_angle')
            azimuth_angle = request.POST.get('azimuth_angle')
            array_area = request.POST.get('array_area')
            inverter_count = request.POST.get('inverter_count')
            inverter_capacity_each = request.POST.get('inverter_capacity_each')
            installation_date = request.POST.get('installation_date')
            commissioning_date = request.POST.get('commissioning_date')
            notes = request.POST.get('notes', '').strip()
            is_active = request.POST.get('is_active') == 'on'
            
            # Validation
            if not any([nameplate_capacity, ac_capacity]):
                messages.error(request, 'At least one capacity field must be provided.')
                return render(request, 'facility_solar/edit.html', {
                    'installation': installation,
                    'form_data': request.POST
                })
            
            # Update the installation
            installation.installation_name = installation_name if installation_name else None
            installation.nameplate_capacity = float(nameplate_capacity) if nameplate_capacity else None
            installation.ac_capacity = float(ac_capacity) if ac_capacity else None
            installation.panel_count = int(panel_count) if panel_count else None
            installation.panel_wattage = float(panel_wattage) if panel_wattage else None
            installation.tilt_angle = float(tilt_angle) if tilt_angle else None
            installation.azimuth_angle = float(azimuth_angle) if azimuth_angle else None
            installation.array_area = float(array_area) if array_area else None
            installation.inverter_count = int(inverter_count) if inverter_count else None
            installation.inverter_capacity_each = float(inverter_capacity_each) if inverter_capacity_each else None
            installation.installation_date = installation_date if installation_date else None
            installation.commissioning_date = commissioning_date if commissioning_date else None
            installation.notes = notes if notes else None
            installation.is_active = is_active
            installation.save()
            
            messages.success(request, 'Solar installation updated successfully.')
            return redirect('powermapui:facility_solar_detail', pk=installation.pk)
            
        except ValueError as e:
            messages.error(request, f'Invalid numeric value provided: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error updating installation: {str(e)}')
    
    context = {
        'installation': installation,
        'solar_attrs': installation.solar_attrs
    }
    return render(request, 'facility_solar/edit.html', context)

@require_POST
def facility_solar_delete(request, pk):
    """Delete a facility solar installation"""
    installation = get_object_or_404(FacilitySolar, pk=pk)
    
    facility_name = installation.facility.facility_name
    technology_name = installation.technology.technology_name
    
    installation.delete()
    messages.success(request, f'Removed {technology_name} installation from {facility_name}.')
    return redirect('powermapui:facility_solar_list')

def get_facility_solar_json(request):
    """Return facility solar installations as JSON"""
    installations = FacilitySolar.objects.select_related(
        'idfacilities',
        'idtechnologies'
    ).filter(is_active=True)
    
    data = []
    for install in installations:
        solar_attrs = install.solar_attrs
        data.append({
            'id': install.idfacilitysolar,
            'facility_id': install.idfacilities.idfacilities,
            'facility_name': install.idfacilities.facility_name,
            'technology_id': install.idtechnologies.idtechnologies,
            'technology_name': install.idtechnologies.technology_name,
            'installation_name': install.installation_name,
            'nameplate_capacity': install.nameplate_capacity,
            'ac_capacity': install.ac_capacity,
            'panel_count': install.panel_count,
            'dc_ac_ratio': install.get_calculated_dc_ac_ratio(),
            'panel_efficiency': solar_attrs.module_efficiency if solar_attrs else None,
            'performance_ratio': solar_attrs.performance_ratio if solar_attrs else None,
            'is_active': install.is_active,
        })
    
    return JsonResponse({
        'installations': data,
        'count': len(data),
        'total_dc_capacity_mw': sum(d['nameplate_capacity'] or 0 for d in data),
        'total_ac_capacity_mw': sum(d['ac_capacity'] or 0 for d in data),
    })
