from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from siren_web.models import WindTurbines, FacilityWindTurbines, TurbinePowerCurves, facilities
import json
import csv
from io import StringIO

def wind_turbines_list(request):
    """List all wind turbines with search and pagination"""
    demand_year = request.session.get('demand_year', '')  # Get demand_year and scenario from session or default to empty string
    scenario= request.session.get('scenario', '')
    config_file = request.session.get('config_file')
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
    manufacturers = [m for m in manufacturers if m]
    applications = WindTurbines.APPLICATION_CHOICES
    
    # Pagination
    paginator = Paginator(turbines, 25)  # Show 25 turbines per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
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
    demand_year = request.session.get('demand_year', '')  # Get demand_year and scenario from session or default to empty string
    scenario= request.session.get('scenario', '')
    config_file = request.session.get('config_file')
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
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
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
            return redirect('powermapui:wind_turbine_detail', pk=turbine.pk)
            
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
            return redirect('powermapui:wind_turbine_detail', pk=turbine.pk)
            
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
        return redirect('powermapui:wind_turbine_detail', pk=pk)
    
    turbine_name = turbine.turbine_model
    turbine.delete()
    messages.success(request, f'Wind turbine "{turbine_name}" deleted successfully.')
    return redirect('wind_turbines_list')

# ========== POWER CURVE VIEWS ==========

def parse_pow_file(file_content):
    """Parse a .pow file and extract wind speed and power output data"""
    try:
        if isinstance(file_content, bytes):
            file_content = file_content.decode('utf-8')
        
        lines = file_content.strip().split('\n')
        wind_speeds = []
        power_outputs = []
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('Wind'):
                continue
            
            parts = line.split()
            if len(parts) >= 2:
                try:
                    wind_speed = float(parts[0])
                    power = float(parts[1])
                    wind_speeds.append(wind_speed)
                    power_outputs.append(power)
                except ValueError:
                    continue
        
        if not wind_speeds or not power_outputs:
            return None
        
        return {
            'wind_speeds': wind_speeds,
            'power_outputs': power_outputs,
            'data_points': len(wind_speeds),
            'iec_class': None,
            'source': 'File Upload'
        }
    except Exception as e:
        return None

def parse_manual_data(wind_speeds_text, power_outputs_text):
    """Parse manually entered wind speed and power output data"""
    try:
        # Parse wind speeds
        wind_speeds = []
        for value in wind_speeds_text.replace(',', ' ').split():
            wind_speeds.append(float(value))
        
        # Parse power outputs
        power_outputs = []
        for value in power_outputs_text.replace(',', ' ').split():
            power_outputs.append(float(value))
        
        if len(wind_speeds) != len(power_outputs):
            return None, "Number of wind speeds must match number of power outputs"
        
        if len(wind_speeds) == 0:
            return None, "At least one data point is required"
        
        return {
            'wind_speeds': wind_speeds,
            'power_outputs': power_outputs,
            'data_points': len(wind_speeds)
        }, None
        
    except ValueError as e:
        return None, "Invalid numeric values in data"

def power_curve_create(request, turbine_pk):
    """Create a new power curve for a wind turbine"""
    turbine = get_object_or_404(WindTurbines, pk=turbine_pk)
    
    if request.method == 'POST':
        try:
            entry_method = request.POST.get('entry_method', 'file')
            power_file_name = request.POST.get('power_file_name', '').strip()
            notes = request.POST.get('notes', '').strip()
            is_active = request.POST.get('is_active') == 'on'
            iec_class = request.POST.get('iec_class', '').strip()
            source = request.POST.get('source', '').strip()
            
            parsed_data = None
            error_message = None
            
            if entry_method == 'file':
                # File upload method
                power_file = request.FILES.get('power_file')
                
                if not power_file:
                    messages.error(request, 'Power curve file is required when using file upload method.')
                    return render(request, 'power_curves/create.html', {
                        'turbine': turbine,
                        'form_data': request.POST
                    })
                
                if not power_file.name.endswith('.pow'):
                    messages.error(request, 'Only .pow files are supported.')
                    return render(request, 'power_curves/create.html', {
                        'turbine': turbine,
                        'form_data': request.POST
                    })
                
                power_file_name = power_file.name
                file_content = power_file.read()
                parsed_data = parse_pow_file(file_content)
                
                if not parsed_data:
                    messages.error(request, 'Could not parse power curve file. Please check the file format.')
                    return render(request, 'power_curves/create.html', {
                        'turbine': turbine,
                        'form_data': request.POST
                    })
                
                # Update source if provided
                if source:
                    parsed_data['source'] = source
                    
            else:
                # Manual entry method
                wind_speeds_text = request.POST.get('wind_speeds', '').strip()
                power_outputs_text = request.POST.get('power_outputs', '').strip()
                
                if not power_file_name:
                    messages.error(request, 'File name is required.')
                    return render(request, 'power_curves/create.html', {
                        'turbine': turbine,
                        'form_data': request.POST
                    })
                
                if not wind_speeds_text or not power_outputs_text:
                    messages.error(request, 'Both wind speeds and power outputs are required.')
                    return render(request, 'power_curves/create.html', {
                        'turbine': turbine,
                        'form_data': request.POST
                    })
                
                parsed_data, error_message = parse_manual_data(wind_speeds_text, power_outputs_text)
                
                if error_message:
                    messages.error(request, error_message)
                    return render(request, 'power_curves/create.html', {
                        'turbine': turbine,
                        'form_data': request.POST
                    })
                
                # Add metadata
                parsed_data['iec_class'] = iec_class if iec_class else None
                parsed_data['source'] = source if source else 'Manual Entry'
            
            # Check for duplicate file name
            if TurbinePowerCurves.objects.filter(
                idwindturbines=turbine, 
                power_file_name=power_file_name
            ).exists():
                messages.error(request, f'A power curve with file name "{power_file_name}" already exists for this turbine.')
                return render(request, 'power_curves/create.html', {
                    'turbine': turbine,
                    'form_data': request.POST
                })
            
            # If setting as active, deactivate other curves
            if is_active:
                TurbinePowerCurves.objects.filter(
                    idwindturbines=turbine, 
                    is_active=True
                ).update(is_active=False)
            
            # Update IEC class if provided
            if iec_class:
                parsed_data['iec_class'] = iec_class
            
            # Create the power curve
            power_curve = TurbinePowerCurves.objects.create(
                idwindturbines=turbine,
                power_file_name=power_file_name,
                power_curve_data=parsed_data,
                is_active=is_active,
                notes=notes if notes else None
            )
            
            messages.success(request, f'Power curve "{power_file_name}" created successfully.')
            return redirect('powermapui:wind_turbine_detail', pk=turbine.pk)
            
        except Exception as e:
            messages.error(request, f'Error creating power curve: {str(e)}')
            return render(request, 'power_curves/create.html', {
                'turbine': turbine,
                'form_data': request.POST
            })
    
    context = {
        'turbine': turbine
    }
    return render(request, 'power_curves/create.html', context)

def power_curve_edit(request, pk):
    """Edit an existing power curve"""
    power_curve = get_object_or_404(TurbinePowerCurves, pk=pk)
    turbine = power_curve.idwindturbines
    
    if request.method == 'POST':
        try:
            entry_method = request.POST.get('entry_method', 'metadata')
            power_file_name = request.POST.get('power_file_name', '').strip()
            notes = request.POST.get('notes', '').strip()
            is_active = request.POST.get('is_active') == 'on'
            iec_class = request.POST.get('iec_class', '').strip()
            source = request.POST.get('source', '').strip()
            
            parsed_data = None
            
            if entry_method == 'file':
                # File upload - replace entire data
                power_file = request.FILES.get('power_file')
                if power_file:
                    if not power_file.name.endswith('.pow'):
                        messages.error(request, 'Only .pow files are supported.')
                        return render(request, 'power_curves/edit.html', {
                            'power_curve': power_curve,
                            'turbine': turbine
                        })
                    
                    file_content = power_file.read()
                    parsed_data = parse_pow_file(file_content)
                    
                    if not parsed_data:
                        messages.error(request, 'Could not parse power curve file. Please check the file format.')
                        return render(request, 'power_curves/edit.html', {
                            'power_curve': power_curve,
                            'turbine': turbine
                        })
                    
                    power_curve.power_file_name = power_file.name if power_file else power_file_name
                    
            elif entry_method == 'manual':
                # Manual data entry - replace data
                wind_speeds_text = request.POST.get('wind_speeds', '').strip()
                power_outputs_text = request.POST.get('power_outputs', '').strip()
                
                if not wind_speeds_text or not power_outputs_text:
                    messages.error(request, 'Both wind speeds and power outputs are required.')
                    return render(request, 'power_curves/edit.html', {
                        'power_curve': power_curve,
                        'turbine': turbine
                    })
                
                parsed_data, error_message = parse_manual_data(wind_speeds_text, power_outputs_text)
                
                if error_message:
                    messages.error(request, error_message)
                    return render(request, 'power_curves/edit.html', {
                        'power_curve': power_curve,
                        'turbine': turbine
                    })
                
                if power_file_name:
                    power_curve.power_file_name = power_file_name
            
            # Update or preserve existing data
            if parsed_data:
                power_curve.power_curve_data = parsed_data
            else:
                # Just updating metadata
                parsed_data = power_curve.power_curve_data
            
            # Update metadata fields
            if iec_class or 'iec_class' in parsed_data:
                parsed_data['iec_class'] = iec_class if iec_class else None
            
            if source or 'source' in parsed_data:
                parsed_data['source'] = source if source else parsed_data.get('source', 'Manual Entry')
            
            power_curve.power_curve_data = parsed_data
            
            # If setting as active, deactivate other curves
            if is_active and not power_curve.is_active:
                TurbinePowerCurves.objects.filter(
                    idwindturbines=turbine, 
                    is_active=True
                ).exclude(pk=pk).update(is_active=False)
            
            power_curve.notes = notes if notes else None
            power_curve.is_active = is_active
            power_curve.save()
            
            messages.success(request, 'Power curve updated successfully.')
            return redirect('powermapui:wind_turbine_detail', pk=turbine.pk)
            
        except Exception as e:
            messages.error(request, f'Error updating power curve: {str(e)}')
            return render(request, 'power_curves/edit.html', {
                'power_curve': power_curve,
                'turbine': turbine
            })
    
    # Prepare data for template
    curve_data = power_curve.power_curve_data
    wind_speeds_text = ' '.join(str(ws) for ws in curve_data.get('wind_speeds', []))
    power_outputs_text = ' '.join(str(po) for po in curve_data.get('power_outputs', []))
    
    context = {
        'power_curve': power_curve,
        'turbine': turbine,
        'wind_speeds_text': wind_speeds_text,
        'power_outputs_text': power_outputs_text,
        'iec_class': curve_data.get('iec_class', ''),
        'source': curve_data.get('source', '')
    }
    return render(request, 'power_curves/edit.html', context)

@require_POST
def power_curve_delete(request, pk):
    """Delete a power curve"""
    power_curve = get_object_or_404(TurbinePowerCurves, pk=pk)
    turbine_pk = power_curve.idwindturbines.pk
    file_name = power_curve.power_file_name
    
    power_curve.delete()
    messages.success(request, f'Power curve "{file_name}" deleted successfully.')
    return redirect('powermapui:wind_turbine_detail', pk=turbine_pk)

@require_POST
def power_curve_toggle_active(request, pk):
    """Toggle active status of a power curve"""
    power_curve = get_object_or_404(TurbinePowerCurves, pk=pk)
    turbine = power_curve.idwindturbines
    
    if not power_curve.is_active:
        TurbinePowerCurves.objects.filter(
            idwindturbines=turbine, 
            is_active=True
        ).update(is_active=False)
        
        power_curve.is_active = True
        power_curve.save()
        messages.success(request, f'Power curve "{power_curve.power_file_name}" set as active.')
    else:
        power_curve.is_active = False
        power_curve.save()
        messages.success(request, f'Power curve "{power_curve.power_file_name}" deactivated.')
    
    return redirect('powermapui:wind_turbine_detail', pk=turbine.pk)

def power_curve_data_json(request, pk):
    """Return power curve data as JSON for charting"""
    power_curve = get_object_or_404(TurbinePowerCurves, pk=pk)
    
    curve_data = power_curve.power_curve_data
    
    return JsonResponse({
        'file_name': power_curve.power_file_name,
        'wind_speeds': curve_data.get('wind_speeds', []),
        'power_outputs': curve_data.get('power_outputs', []),
        'data_points': curve_data.get('data_points', 0),
        'iec_class': curve_data.get('iec_class'),
        'source': curve_data.get('source'),
        'is_active': power_curve.is_active
    })

# ========== FACILITY WIND TURBINE VIEWS ==========

def facility_wind_turbines_list(request):
    """List all facility wind turbine installations"""
    demand_year = request.session.get('demand_year', '')
    scenario = request.session.get('scenario', '')
    config_file = request.session.get('config_file')
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
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
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
            return redirect('powermapui:facility_wind_turbines_list')
            
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
            return redirect('powermapui:facility_wind_turbines_list')
            
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
    return redirect('powermapui:facility_wind_turbines_list')

def get_turbines_json(request):
    """Return wind turbines data as JSON for frontend consumption"""
    turbines = WindTurbines.objects.all().values(
        'idwindturbines',
        'turbine_model',
        'manufacturer',
        'application',
        'hub_height',
        'rated_power',
        'rotor_diameter'
    )
    
    # Group turbines by application for easier frontend consumption
    turbines_by_app = {
        'onshore': [],
        'offshore': [],
        'floating': []
    }
    
    for turbine in turbines:
        if turbine['application'] in turbines_by_app:
            turbines_by_app[turbine['application']].append({
                'id': turbine['idwindturbines'],
                'model': turbine['turbine_model'],
                'manufacturer': turbine['manufacturer'],
                'capacity': turbine['rated_power'],
                'hub_height': turbine['hub_height'],
                'rotor_diameter': turbine['rotor_diameter']
            })
    
    return JsonResponse({
        'turbines': list(turbines),
        'turbines_by_application': turbines_by_app
    })
