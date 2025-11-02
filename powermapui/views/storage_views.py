from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from django.http import JsonResponse
from siren_web.models import Technologies, Storageattributes

def storage_list(request):
    """List all storage technologies with search and pagination"""
    demand_year = request.session.get('demand_year', '')
    scenario = request.session.get('scenario', '')
    config_file = request.session.get('config_file')
    
    search_query = request.GET.get('search', '')
    technology_filter = request.GET.get('technology', '')
    
    # Get all storage technologies - simply filter by category='Storage'
    storage_techs = Technologies.objects.filter(
        category='Storage'
    ).prefetch_related('storageattributes_set').order_by('technology_name')
    
    # Apply search filter
    if search_query:
        storage_techs = storage_techs.filter(
            Q(technology_name__icontains=search_query) |
            Q(technology_signature__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Apply technology name filter
    if technology_filter:
        storage_techs = storage_techs.filter(technology_name=technology_filter)
    
    # Get all unique technology names for filter dropdown
    technology_names = Technologies.objects.filter(
        category='Storage'
    ).values_list('technology_name', flat=True).distinct().order_by('technology_name')
    
    # Pagination
    paginator = Paginator(storage_techs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
        'page_obj': page_obj,
        'search_query': search_query,
        'technology_filter': technology_filter,
        'technology_names': technology_names,
        'total_count': storage_techs.count()
    }
    
    return render(request, 'storage/list.html', context)

def storage_detail(request, pk):
    """Detail view for a specific storage technology"""
    demand_year = request.session.get('demand_year', '')
    scenario = request.session.get('scenario', '')
    config_file = request.session.get('config_file')
    
    technology = get_object_or_404(Technologies, pk=pk)
    
    # Get storage attributes
    try:
        storage_attrs = Storageattributes.objects.get(idtechnologies=technology)
    except Storageattributes.DoesNotExist:
        storage_attrs = None
    
    # Get facility installations using this technology
    try:
        from siren_web.models import FacilityStorage
        facility_installations = FacilityStorage.objects.filter(
            idtechnologies=technology,
            is_active=True
        ).select_related('idfacilities')
        
        # Calculate summary statistics
        total_installations = facility_installations.count()
        total_power = sum(inst.power_capacity or 0 for inst in facility_installations)
        total_energy = sum(inst.energy_capacity or 0 for inst in facility_installations)
    except:
        # FacilityStorage model might not exist yet
        facility_installations = []
        total_installations = 0
        total_power = 0
        total_energy = 0
    
    # Calculate derived values if storage attributes exist
    derived_values = {}
    if storage_attrs:
        if storage_attrs.charge_efficiency and storage_attrs.discharge_efficiency:
            derived_values['round_trip_calc'] = storage_attrs.charge_efficiency * storage_attrs.discharge_efficiency
        
        # Calculate SOC percentages for progress bar
        min_soc = storage_attrs.min_state_of_charge or 0.0
        max_soc = storage_attrs.max_state_of_charge or 1.0
        derived_values['min_soc_pct'] = min_soc * 100
        derived_values['max_soc_pct'] = max_soc * 100
        derived_values['usable_soc_pct'] = (max_soc - min_soc) * 100
        derived_values['reserved_soc_pct'] = (1.0 - max_soc) * 100
    
    context = {
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
        'technology': technology,
        'storage_attrs': storage_attrs,
        'derived_values': derived_values,
        'facility_installations': facility_installations,
        'total_installations': total_installations,
        'total_power': total_power,
        'total_energy': total_energy,
    }
    
    return render(request, 'storage/detail.html', context)

def storage_create(request):
    """Create a new storage technology"""
    if request.method == 'POST':
        try:
            # Extract Technology form data
            technology_name = request.POST.get('technology_name', '').strip()
            technology_signature = request.POST.get('technology_signature', '').strip()
            description = request.POST.get('description', '').strip()
            lifetime = request.POST.get('lifetime')
            discount_rate = request.POST.get('discount_rate')
            emissions = request.POST.get('emissions')
            
            # Validation
            if not technology_name:
                messages.error(request, 'Technology name is required.')
                return render(request, 'storage/create.html', {
                    'form_data': request.POST
                })
            
            if not technology_signature:
                messages.error(request, 'Technology signature is required.')
                return render(request, 'storage/create.html', {
                    'form_data': request.POST
                })
            
            # Check for duplicates
            if Technologies.objects.filter(technology_name=technology_name).exists():
                messages.error(request, 'A technology with this name already exists.')
                return render(request, 'storage/create.html', {
                    'form_data': request.POST
                })
            
            if Technologies.objects.filter(technology_signature=technology_signature).exists():
                messages.error(request, 'A technology with this signature already exists.')
                return render(request, 'storage/create.html', {
                    'form_data': request.POST
                })
            
            # Create the technology with category='Storage'
            technology = Technologies.objects.create(
                technology_name=technology_name,
                technology_signature=technology_signature,
                category='Storage',
                description=description if description else None,
                lifetime=float(lifetime) if lifetime else None,
                discount_rate=float(discount_rate) if discount_rate else None,
                emissions=float(emissions) if emissions else None,
                renewable=0,  # Storage is not renewable generation
                dispatchable=1,  # Storage is dispatchable
            )
            
            # Extract Storage Attributes form data (NO capacity fields - those are in FacilityStorage)
            round_trip_efficiency = request.POST.get('round_trip_efficiency')
            charge_efficiency = request.POST.get('charge_efficiency')
            discharge_efficiency = request.POST.get('discharge_efficiency')
            min_state_of_charge = request.POST.get('min_state_of_charge')
            max_state_of_charge = request.POST.get('max_state_of_charge')
            initial_state_of_charge = request.POST.get('initial_state_of_charge')
            cycle_life = request.POST.get('cycle_life')
            calendar_life = request.POST.get('calendar_life')
            degradation_rate = request.POST.get('degradation_rate')
            self_discharge_rate = request.POST.get('self_discharge_rate')
            auxiliary_load = request.POST.get('auxiliary_load')
            
            # Create storage attributes (technology characteristics only)
            Storageattributes.objects.create(
                idtechnologies=technology,
                round_trip_efficiency=float(round_trip_efficiency) if round_trip_efficiency else None,
                charge_efficiency=float(charge_efficiency) if charge_efficiency else None,
                discharge_efficiency=float(discharge_efficiency) if discharge_efficiency else None,
                min_state_of_charge=float(min_state_of_charge) if min_state_of_charge else 0.0,
                max_state_of_charge=float(max_state_of_charge) if max_state_of_charge else 1.0,
                initial_state_of_charge=float(initial_state_of_charge) if initial_state_of_charge else 0.5,
                cycle_life=int(cycle_life) if cycle_life else None,
                calendar_life=float(calendar_life) if calendar_life else None,
                degradation_rate=float(degradation_rate) if degradation_rate else None,
                self_discharge_rate=float(self_discharge_rate) if self_discharge_rate else None,
                auxiliary_load=float(auxiliary_load) if auxiliary_load else None,
            )
            
            messages.success(request, f'Storage technology "{technology_name}" created successfully.')
            return redirect('powermapui:storage_detail', pk=technology.pk)
            
        except ValueError as e:
            messages.error(request, f'Invalid numeric value provided: {str(e)}')
            return render(request, 'storage/create.html', {
                'form_data': request.POST
            })
        except Exception as e:
            messages.error(request, f'Error creating storage technology: {str(e)}')
            return render(request, 'storage/create.html', {
                'form_data': request.POST
            })
    
    return render(request, 'storage/create.html')

def storage_edit(request, pk):
    """Edit an existing storage technology"""
    technology = get_object_or_404(Technologies, pk=pk)
    
    try:
        storage_attrs = Storageattributes.objects.get(idtechnologies=technology)
    except Storageattributes.DoesNotExist:
        storage_attrs = None
    
    if request.method == 'POST':
        try:
            # Extract Technology form data
            technology_name = request.POST.get('technology_name', '').strip()
            technology_signature = request.POST.get('technology_signature', '').strip()
            description = request.POST.get('description', '').strip()
            lifetime = request.POST.get('lifetime')
            discount_rate = request.POST.get('discount_rate')
            emissions = request.POST.get('emissions')
            
            # Validation
            if not technology_name:
                messages.error(request, 'Technology name is required.')
                return render(request, 'storage/edit.html', {
                    'technology': technology,
                    'storage_attrs': storage_attrs,
                    'form_data': request.POST
                })
            
            if not technology_signature:
                messages.error(request, 'Technology signature is required.')
                return render(request, 'storage/edit.html', {
                    'technology': technology,
                    'storage_attrs': storage_attrs,
                    'form_data': request.POST
                })
            
            # Check for duplicate names (excluding current)
            if Technologies.objects.filter(technology_name=technology_name).exclude(pk=pk).exists():
                messages.error(request, 'A technology with this name already exists.')
                return render(request, 'storage/edit.html', {
                    'technology': technology,
                    'storage_attrs': storage_attrs,
                    'form_data': request.POST
                })
            
            # Check for duplicate signatures (excluding current)
            if Technologies.objects.filter(technology_signature=technology_signature).exclude(pk=pk).exists():
                messages.error(request, 'A technology with this signature already exists.')
                return render(request, 'storage/edit.html', {
                    'technology': technology,
                    'storage_attrs': storage_attrs,
                    'form_data': request.POST
                })
            
            # Update the technology (category remains 'Storage')
            technology.technology_name = technology_name
            technology.technology_signature = technology_signature
            technology.description = description if description else None
            technology.lifetime = float(lifetime) if lifetime else None
            technology.discount_rate = float(discount_rate) if discount_rate else None
            technology.emissions = float(emissions) if emissions else None
            technology.save()
            
            # Extract Storage Attributes form data (NO capacity fields - those are in FacilityStorage)
            round_trip_efficiency = request.POST.get('round_trip_efficiency')
            charge_efficiency = request.POST.get('charge_efficiency')
            discharge_efficiency = request.POST.get('discharge_efficiency')
            min_state_of_charge = request.POST.get('min_state_of_charge')
            max_state_of_charge = request.POST.get('max_state_of_charge')
            initial_state_of_charge = request.POST.get('initial_state_of_charge')
            cycle_life = request.POST.get('cycle_life')
            calendar_life = request.POST.get('calendar_life')
            degradation_rate = request.POST.get('degradation_rate')
            self_discharge_rate = request.POST.get('self_discharge_rate')
            auxiliary_load = request.POST.get('auxiliary_load')
            
            # Update or create storage attributes (technology characteristics only)
            if storage_attrs:
                storage_attrs.round_trip_efficiency = float(round_trip_efficiency) if round_trip_efficiency else None
                storage_attrs.charge_efficiency = float(charge_efficiency) if charge_efficiency else None
                storage_attrs.discharge_efficiency = float(discharge_efficiency) if discharge_efficiency else None
                storage_attrs.min_state_of_charge = float(min_state_of_charge) if min_state_of_charge else 0.0
                storage_attrs.max_state_of_charge = float(max_state_of_charge) if max_state_of_charge else 1.0
                storage_attrs.initial_state_of_charge = float(initial_state_of_charge) if initial_state_of_charge else 0.5
                storage_attrs.cycle_life = int(cycle_life) if cycle_life else None
                storage_attrs.calendar_life = float(calendar_life) if calendar_life else None
                storage_attrs.degradation_rate = float(degradation_rate) if degradation_rate else None
                storage_attrs.self_discharge_rate = float(self_discharge_rate) if self_discharge_rate else None
                storage_attrs.auxiliary_load = float(auxiliary_load) if auxiliary_load else None
                storage_attrs.save()
            else:
                Storageattributes.objects.create(
                    idtechnologies=technology,
                    round_trip_efficiency=float(round_trip_efficiency) if round_trip_efficiency else None,
                    charge_efficiency=float(charge_efficiency) if charge_efficiency else None,
                    discharge_efficiency=float(discharge_efficiency) if discharge_efficiency else None,
                    min_state_of_charge=float(min_state_of_charge) if min_state_of_charge else 0.0,
                    max_state_of_charge=float(max_state_of_charge) if max_state_of_charge else 1.0,
                    initial_state_of_charge=float(initial_state_of_charge) if initial_state_of_charge else 0.5,
                    cycle_life=int(cycle_life) if cycle_life else None,
                    calendar_life=float(calendar_life) if calendar_life else None,
                    degradation_rate=float(degradation_rate) if degradation_rate else None,
                    self_discharge_rate=float(self_discharge_rate) if self_discharge_rate else None,
                    auxiliary_load=float(auxiliary_load) if auxiliary_load else None,
                )
            
            messages.success(request, f'Storage technology "{technology_name}" updated successfully.')
            return redirect('powermapui:storage_detail', pk=technology.pk)
            
        except ValueError as e:
            messages.error(request, f'Invalid numeric value provided: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error updating storage technology: {str(e)}')
    
    context = {
        'technology': technology,
        'storage_attrs': storage_attrs,
    }
    return render(request, 'storage/edit.html', context)

def get_storage_json(request):
    """Return storage technologies data as JSON for frontend consumption"""
    storage_techs = Technologies.objects.filter(
        category='Storage'
    ).prefetch_related('storageattributes_set')
    
    results = []
    for tech in storage_techs:
        storage_attrs = tech.storageattributes_set.first()
        results.append({
            'id': tech.idtechnologies,
            'name': tech.technology_name,
            'signature': tech.technology_signature,
            'power_capacity': storage_attrs.power_capacity if storage_attrs else None,
            'energy_capacity': storage_attrs.energy_capacity if storage_attrs else None,
            'duration': storage_attrs.duration if storage_attrs else None,
            'round_trip_efficiency': storage_attrs.round_trip_efficiency if storage_attrs else None,
        })
    
    return JsonResponse({
        'storage_technologies': results,
        'count': len(results)
    })