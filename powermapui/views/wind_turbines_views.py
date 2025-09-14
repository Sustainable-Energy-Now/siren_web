from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.decorators.http import require_POST
from siren_web.models import WindTurbines, FacilityWindTurbines, TurbinePowerCurves, facilities

def wind_turbines_list(request):
    """List all wind turbines with search and pagination"""
    search_query = request.GET.get('search', '')
    manufacturer_filter = request.GET.get('manufacturer', '')
    application_filter = request.GET.get('application', '')
    
    turbines = WindTurbines.objects.all().order_by('manufacturer', 'turbine_model')
    
    # Apply search filter
    if search_query:
        turbines = turbines.filter(
            Q(turbine_model__icontains=search_query) |
            Q(manufacturer__icontains=search_query)
        )
    
    # Apply manufacturer filter
    if manufacturer_filter:
        turbines = turbines.filter(manufacturer__icontains=manufacturer_filter)
    
    # Apply application filter
    if application_filter:
        turbines = turbines.filter(application=application_filter)
    
    # Get unique manufacturers and applications for filter dropdowns
    manufacturers = WindTurbines.objects.values_list('manufacturer', flat=True).distinct().order_by('manufacturer')
    manufacturers = [m for m in manufacturers if m]  # Remove None values
    applications = WindTurbines.APPLICATION_CHOICES
    
    # Pagination
    paginator = Paginator(turbines, 25)  # Show 25 turbines per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'manufacturer_filter': manufacturer_filter,
        'application_filter': application_filter,
        'manufacturers': manufacturers,
        'applications': applications,
        'total_count': turbines.count()
    }
    
    return render(request, 'wind_turbines/list.html', context)

def wind_turbine_detail(request, pk):
    """Detail view for a specific wind turbine"""
    turbine = get_object_or_404(WindTurbines, pk=pk)
    
    # Get facilities using this turbine
    facility_installations = FacilityWindTurbines.objects.filter(
        idwindturbines=turbine,
        is_active=True
    ).select_related('idfacilities')
    
    # Get power curves
    power_curves = TurbinePowerCurves.objects.filter(
        idwindturbines=turbine
    ).order_by('-file_upload_date')
    
    # Calculate summary statistics
    total_installations = sum(inst.no_turbines for inst in facility_installations)
    total_capacity = sum(inst.total_capacity or 0 for inst in facility_installations)
    
    context = {
        'turbine': turbine,
        'facility_installations': facility_installations,
        'power_curves': power_curves,
        'total_installations': total_installations,
        'total_capacity': total_capacity,
    }
    
    return render(request, 'wind_turbines/detail.html', context)

def wind_turbine_create(request):
    """Create a new wind turbine"""
    if request.method == 'POST':
        try:
            # Extract form data
            turbine_model = request.POST.get('turbine_model', '').strip()
            manufacturer = request.POST.get('manufacturer', '').strip()
            application = request.POST.get('application')
            hub_height = request.POST.get('hub_height')
            rated_power = request.POST.get('rated_power')
            rotor_diameter = request.POST.get('rotor_diameter')
            cut_in_speed = request.POST.get('cut_in_speed')
            cut_out_speed = request.POST.get('cut_out_speed')
            
            # Validation
            if not turbine_model:
                messages.error(request, 'Turbine model is required.')
                return render(request, 'wind_turbines/create.html', {
                    'form_data': request.POST,
                    'applications': WindTurbines.APPLICATION_CHOICES
                })
            
            # Check for duplicate turbine model
            if WindTurbines.objects.filter(turbine_model=turbine_model).exists():
                messages.error(request, 'A turbine with this model already exists.')
                return render(request, 'wind_turbines/create.html', {
                    'form_data': request.POST,
                    'applications': WindTurbines.APPLICATION_CHOICES
                })
            
            # Create the turbine
            turbine = WindTurbines.objects.create(
                turbine_model=turbine_model,
                manufacturer=manufacturer if manufacturer else None,
                application=application if application else None,
                hub_height=float(hub_height) if hub_height else None,
                rated_power=float(rated_power) if rated_power else None,
                rotor_diameter=float(rotor_diameter) if rotor_diameter else None,
                cut_in_speed=float(cut_in_speed) if cut_in_speed else None,
                cut_out_speed=float(cut_out_speed) if cut_out_speed else None,
            )
            
            messages.success(request, f'Wind turbine "{turbine_model}" created successfully.')
            return redirect('wind_turbine_detail', pk=turbine.pk)
            
        except ValueError as e:
            messages.error(request, 'Invalid numeric value provided.')
            return render(request, 'wind_turbines/create.html', {
                'form_data': request.POST,
                'applications': WindTurbines.APPLICATION_CHOICES
            })
        except Exception as e:
            messages.error(request, f'Error creating turbine: {str(e)}')
            return render(request, 'wind_turbines/create.html', {
                'form_data': request.POST,
                'applications': WindTurbines.APPLICATION_CHOICES
            })
    
    context = {
        'applications': WindTurbines.APPLICATION_CHOICES
    }
    return render(request, 'wind_turbines/create.html', context)

def wind_turbine_edit(request, pk):
    """Edit an existing wind turbine"""
    turbine = get_object_or_404(WindTurbines, pk=pk)
    
    if request.method == 'POST':
        try:
            # Extract form data
            turbine_model = request.POST.get('turbine_model', '').strip()
            manufacturer = request.POST.get('manufacturer', '').strip()
            application = request.POST.get('application')
            hub_height = request.POST.get('hub_height')
            rated_power = request.POST.get('rated_power')
            rotor_diameter = request.POST.get('rotor_diameter')
            cut_in_speed = request.POST.get('cut_in_speed')
            cut_out_speed = request.POST.get('cut_out_speed')
            
            # Validation
            if not turbine_model:
                messages.error(request, 'Turbine model is required.')
                return render(request, 'wind_turbines/edit.html', {
                    'turbine': turbine,
                    'applications': WindTurbines.APPLICATION_CHOICES
                })
            
            # Check for duplicate turbine model (excluding current turbine)
            if WindTurbines.objects.filter(turbine_model=turbine_model).exclude(pk=pk).exists():
                messages.error(request, 'A turbine with this model already exists.')
                return render(request, 'wind_turbines/edit.html', {
                    'turbine': turbine,
                    'form_data': request.POST,
                    'applications': WindTurbines.APPLICATION_CHOICES
                })
            
            # Update the turbine
            turbine.turbine_model = turbine_model
            turbine.manufacturer = manufacturer if manufacturer else None
            turbine.application = application if application else None
            turbine.hub_height = float(hub_height) if hub_height else None
            turbine.rated_power = float(rated_power) if rated_power else None
            turbine.rotor_diameter = float(rotor_diameter) if rotor_diameter else None
            turbine.cut_in_speed = float(cut_in_speed) if cut_in_speed else None
            turbine.cut_out_speed = float(cut_out_speed) if cut_out_speed else None
            turbine.save()
            
            messages.success(request, f'Wind turbine "{turbine_model}" updated successfully.')
            return redirect('wind_turbine_detail', pk=turbine.pk)
            
        except ValueError as e:
            messages.error(request, 'Invalid numeric value provided.')
            return render(request, 'wind_turbines/edit.html', {
                'turbine': turbine,
                'applications': WindTurbines.APPLICATION_CHOICES
            })
        except Exception as e:
            messages.error(request, f'Error updating turbine: {str(e)}')
            return render(request, 'wind_turbines/edit.html', {
                'turbine': turbine,
                'applications': WindTurbines.APPLICATION_CHOICES
            })
    
    context = {
        'turbine': turbine,
        'applications': WindTurbines.APPLICATION_CHOICES
    }

    return render(request, 'wind_turbines/edit.html', context)

@require_POST
def wind_turbine_delete(request, pk):
    """Delete a wind turbine"""
    turbine = get_object_or_404(WindTurbines, pk=pk)
    
    # Check if turbine is being used in any facilities
    installations = FacilityWindTurbines.objects.filter(idwindturbines=turbine, is_active=True)
    if installations.exists():
        facility_names = [inst.idfacilities.facility_name for inst in installations[:3]]
        facility_list = ', '.join(facility_names)
        if len(installations) > 3:
            facility_list += f' and {len(installations) - 3} others'
        
        messages.error(request, f'Cannot delete turbine "{turbine.turbine_model}" as it is currently installed at: {facility_list}')
        return redirect('wind_turbine_detail', pk=pk)
    
    turbine_name = turbine.turbine_model
    turbine.delete()
    messages.success(request, f'Wind turbine "{turbine_name}" deleted successfully.')
    return redirect('wind_turbines_list')

def facility_wind_turbines_list(request):
    """List all facility wind turbine installations"""
    search_query = request.GET.get('search', '')
    facility_filter = request.GET.get('facility', '')
    turbine_filter = request.GET.get('turbine', '')
    active_only = request.GET.get('active_only', 'true') == 'true'
    
    installations = FacilityWindTurbines.objects.select_related(
        'idfacilities', 'idwindturbines'
    ).order_by('idfacilities__facility_name')
    
    # Apply filters
    if search_query:
        installations = installations.filter(
            Q(idfacilities__facility_name__icontains=search_query) |
            Q(idwindturbines__turbine_model__icontains=search_query) |
            Q(idwindturbines__manufacturer__icontains=search_query)
        )
    
    if facility_filter:
        installations = installations.filter(idfacilities__facility_name__icontains=facility_filter)
    
    if turbine_filter:
        installations = installations.filter(idwindturbines__turbine_model__icontains=turbine_filter)
    
    if active_only:
        installations = installations.filter(is_active=True)
    
    # Get filter options
    facilities_list = facilities.objects.values_list('facility_name', flat=True).distinct().order_by('facility_name')
    turbines_list = WindTurbines.objects.values_list('turbine_model', flat=True).distinct().order_by('turbine_model')
    
    # Pagination
    paginator = Paginator(installations, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'facility_filter': facility_filter,
        'turbine_filter': turbine_filter,
        'active_only': active_only,
        'facilities_list': facilities_list,
        'turbines_list': turbines_list,
        'total_count': installations.count(),
        'applications': WindTurbines.APPLICATION_CHOICES
    }

    return render(request, 'facility_wind_turbines/list.html', context)

def facility_wind_turbine_create(request):
    """Create a new facility wind turbine installation"""
    if request.method == 'POST':
        try:
            facility_id = request.POST.get('facility')
            turbine_id = request.POST.get('turbine')
            no_turbines = request.POST.get('no_turbines')
            tilt = request.POST.get('tilt')
            direction = request.POST.get('direction', '').strip()
            installation_date = request.POST.get('installation_date')
            notes = request.POST.get('notes', '').strip()
            
            # Validation
            if not facility_id or not turbine_id or not no_turbines:
                messages.error(request, 'Facility, turbine, and number of turbines are required.')
                return render(request, 'facility_wind_turbines/create.html', {
                    'facilities': facilities.objects.all().order_by('facility_name'),
                    'turbines': WindTurbines.objects.all().order_by('manufacturer', 'turbine_model'),
                    'form_data': request.POST
                })
            
            facility = get_object_or_404(facilities, pk=facility_id)
            turbine = get_object_or_404(WindTurbines, pk=turbine_id)
            
            # Check for duplicate installation
            if FacilityWindTurbines.objects.filter(idfacilities=facility, idwindturbines=turbine).exists():
                messages.error(request, 'This turbine model is already installed at this facility.')
                return render(request, 'facility_wind_turbines/create.html', {
                    'facilities': facilities.objects.all().order_by('facility_name'),
                    'turbines': WindTurbines.objects.all().order_by('manufacturer', 'turbine_model'),
                    'form_data': request.POST
                })
            
            # Create the installation
            installation = FacilityWindTurbines.objects.create(
                idfacilities=facility,
                idwindturbines=turbine,
                no_turbines=int(no_turbines),
                tilt=int(tilt) if tilt else None,
                direction=direction if direction else None,
                installation_date=installation_date if installation_date else None,
                notes=notes if notes else None,
                is_active=True
            )
            
            messages.success(request, f'Wind turbine installation created successfully for {facility.facility_name}.')
            return redirect('facility_wind_turbines_list')
            
        except ValueError as e:
            messages.error(request, 'Invalid numeric value provided.')
        except Exception as e:
            messages.error(request, f'Error creating installation: {str(e)}')
    
    context = {
        'facilities': facilities.objects.all().order_by('facility_name'),
        'turbines': WindTurbines.objects.all().order_by('manufacturer', 'turbine_model')
    }
    
    if request.method == 'POST':
        context['form_data'] = request.POST
    
    return render(request, 'facility_wind_turbines/create.html', context)

def facility_wind_turbine_edit(request, pk):
    """Edit an existing facility wind turbine installation"""
    installation = get_object_or_404(FacilityWindTurbines, pk=pk)
    
    if request.method == 'POST':
        try:
            no_turbines = request.POST.get('no_turbines')
            tilt = request.POST.get('tilt')
            direction = request.POST.get('direction', '').strip()
            installation_date = request.POST.get('installation_date')
            notes = request.POST.get('notes', '').strip()
            is_active = request.POST.get('is_active') == 'on'
            
            # Validation
            if not no_turbines:
                messages.error(request, 'Number of turbines is required.')
                return render(request, 'facility_wind_turbines/edit.html', {'installation': installation})
            
            # Update the installation
            installation.no_turbines = int(no_turbines)
            installation.tilt = int(tilt) if tilt else None
            installation.direction = direction if direction else None
            installation.installation_date = installation_date if installation_date else None
            installation.notes = notes if notes else None
            installation.is_active = is_active
            installation.save()
            
            messages.success(request, f'Wind turbine installation updated successfully.')
            return redirect('facility_wind_turbines_list')
            
        except ValueError as e:
            messages.error(request, 'Invalid numeric value provided.')
        except Exception as e:
            messages.error(request, f'Error updating installation: {str(e)}')
    
    context = {'installation': installation}
    return render(request, 'facility_wind_turbines/edit.html', context)

@require_POST
def facility_wind_turbine_delete(request, pk):
    """Delete a facility wind turbine installation"""
    installation = get_object_or_404(FacilityWindTurbines, pk=pk)
    
    facility_name = installation.idfacilities.facility_name
    turbine_model = installation.idwindturbines.turbine_model
    
    installation.delete()
    messages.success(request, f'Removed {turbine_model} installation from {facility_name}.')
    return redirect('facility_wind_turbines_list')
