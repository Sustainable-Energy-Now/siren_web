from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q, Sum, Count
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from siren_web.models import HybridSolarStorage, FacilitySolar, FacilityStorage, facilities

def hybrid_list(request):
    """List all hybrid solar+storage configurations"""
    demand_year = request.session.get('demand_year', '')
    scenario = request.session.get('scenario', '')
    config_file = request.session.get('config_file')
    
    search_query = request.GET.get('search', '')
    facility_filter = request.GET.get('facility', '')
    coupling_filter = request.GET.get('coupling', '')
    active_only = request.GET.get('active_only', '') == 'on'
    
    # Get all hybrid configurations
    hybrids = HybridSolarStorage.objects.select_related(
        'solar_installation__idfacilities',
        'solar_installation__idtechnologies',
        'storage_installation__idtechnologies'
    ).order_by('-is_active', 'solar_installation__idfacilities__facility_name')
    
    # Apply filters
    if search_query:
        hybrids = hybrids.filter(
            Q(solar_installation__idfacilities__facility_name__icontains=search_query) |
            Q(configuration_name__icontains=search_query)
        )
    
    if facility_filter:
        hybrids = hybrids.filter(
            solar_installation__idfacilities__facility_name__icontains=facility_filter
        )
    
    if coupling_filter:
        hybrids = hybrids.filter(coupling_type=coupling_filter)
    
    if active_only:
        hybrids = hybrids.filter(is_active=True)
    
    # Get filter options
    facilities_list = facilities.objects.values_list('facility_name', flat=True).distinct().order_by('facility_name')
    
    # Calculate statistics
    active_hybrids = hybrids.filter(is_active=True)
    total_solar_dc = sum(h.total_solar_capacity_dc or 0 for h in active_hybrids)
    total_storage_power = sum(h.total_storage_power or 0 for h in active_hybrids)
    total_storage_energy = sum(h.total_storage_energy or 0 for h in active_hybrids)
    
    # Pagination
    paginator = Paginator(hybrids, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
        'page_obj': page_obj,
        'search_query': search_query,
        'facility_filter': facility_filter,
        'coupling_filter': coupling_filter,
        'active_only': active_only,
        'facilities_list': facilities_list,
        'total_count': hybrids.count(),
        'total_solar_dc': total_solar_dc,
        'total_storage_power': total_storage_power,
        'total_storage_energy': total_storage_energy,
        'dc_coupled_count': active_hybrids.filter(coupling_type='dc_coupled').count(),
        'ac_coupled_count': active_hybrids.filter(coupling_type='ac_coupled').count(),
    }
    
    return render(request, 'hybrid_solar_storage/list.html', context)

def hybrid_detail(request, pk):
    """Detail view for a hybrid configuration"""
    demand_year = request.session.get('demand_year', '')
    scenario = request.session.get('scenario', '')
    config_file = request.session.get('config_file')
    
    hybrid = get_object_or_404(
        HybridSolarStorage.objects.select_related(
            'solar_installation__idfacilities',
            'solar_installation__idtechnologies',
            'storage_installation__idtechnologies'
        ),
        pk=pk
    )
    
    # Calculate derived metrics
    derived_values = {
        'effective_ac_capacity': hybrid.get_effective_ac_capacity(),
        'solar_to_storage_ratio': hybrid.get_solar_to_storage_ratio(),
        'storage_to_solar_duration': hybrid.get_storage_to_solar_duration(),
        'configuration_summary': hybrid.get_configuration_summary(),
    }
    
    # Calculate capacity factors and utilization
    if hybrid.grid_connection_capacity:
        solar_ac = hybrid.total_solar_capacity_ac or 0
        storage_power = hybrid.total_storage_power or 0
        derived_values['poi_utilization_solar'] = (solar_ac / hybrid.grid_connection_capacity * 100) if hybrid.grid_connection_capacity > 0 else 0
        derived_values['poi_utilization_combined'] = ((solar_ac + storage_power) / hybrid.grid_connection_capacity * 100) if hybrid.grid_connection_capacity > 0 else 0
    
    context = {
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
        'hybrid': hybrid,
        'derived_values': derived_values,
    }
    
    return render(request, 'hybrid_solar_storage/detail.html', context)

def hybrid_create(request):
    """Create a new hybrid configuration"""
    if request.method == 'POST':
        try:
            # Extract form data
            solar_installation_id = request.POST.get('solar_installation')
            storage_installation_id = request.POST.get('storage_installation')
            configuration_name = request.POST.get('configuration_name', '').strip()
            coupling_type = request.POST.get('coupling_type')
            shared_grid_connection = request.POST.get('shared_grid_connection') == 'on'
            shared_inverter_capacity = request.POST.get('shared_inverter_capacity')
            grid_connection_capacity = request.POST.get('grid_connection_capacity')
            charge_from_solar_only = request.POST.get('charge_from_solar_only') == 'on'
            priority_dispatch = request.POST.get('priority_dispatch')
            commissioning_date = request.POST.get('commissioning_date')
            energy_clipping_losses = request.POST.get('energy_clipping_losses')
            notes = request.POST.get('notes', '').strip()
            
            # Validation
            if not solar_installation_id or not storage_installation_id:
                messages.error(request, 'Both solar and storage installations are required.')
                return render(request, 'hybrid_solar_storage/create.html', {
                    'solar_installations': FacilitySolar.objects.filter(is_active=True).select_related('idfacilities', 'idtechnologies'),
                    'storage_installations': FacilityStorage.objects.filter(is_active=True).select_related('idfacilities', 'idtechnologies'),
                    'form_data': request.POST
                })
            
            solar = get_object_or_404(FacilitySolar, pk=solar_installation_id)
            storage = get_object_or_404(FacilityStorage, pk=storage_installation_id)
            
            # Check they're at the same facility
            if solar.facility != storage.facility:
                messages.error(request, 'Solar and storage installations must be at the same facility.')
                return render(request, 'hybrid_solar_storage/create.html', {
                    'solar_installations': FacilitySolar.objects.filter(is_active=True).select_related('idfacilities', 'idtechnologies'),
                    'storage_installations': FacilityStorage.objects.filter(is_active=True).select_related('idfacilities', 'idtechnologies'),
                    'form_data': request.POST
                })
            
            # Check for existing hybrid configuration
            if HybridSolarStorage.objects.filter(
                solar_installation=solar,
                storage_installation=storage
            ).exists():
                messages.error(request, 'This solar and storage combination is already configured as hybrid.')
                return render(request, 'hybrid_solar_storage/create.html', {
                    'solar_installations': FacilitySolar.objects.filter(is_active=True).select_related('idfacilities', 'idtechnologies'),
                    'storage_installations': FacilityStorage.objects.filter(is_active=True).select_related('idfacilities', 'idtechnologies'),
                    'form_data': request.POST
                })
            
            # Create the hybrid configuration
            hybrid = HybridSolarStorage.objects.create(
                solar_installation=solar,
                storage_installation=storage,
                configuration_name=configuration_name if configuration_name else None,
                coupling_type=coupling_type,
                shared_grid_connection=shared_grid_connection,
                shared_inverter_capacity=float(shared_inverter_capacity) if shared_inverter_capacity else None,
                grid_connection_capacity=float(grid_connection_capacity) if grid_connection_capacity else None,
                charge_from_solar_only=charge_from_solar_only,
                priority_dispatch=priority_dispatch,
                commissioning_date=commissioning_date if commissioning_date else None,
                energy_clipping_losses=float(energy_clipping_losses) if energy_clipping_losses else None,
                notes=notes if notes else None,
                is_active=True
            )
            
            messages.success(request, f'Hybrid configuration created successfully at {solar.facility.facility_name}.')
            return redirect('powermapui:hybrid_detail', pk=hybrid.pk)
            
        except ValueError as e:
            messages.error(request, f'Invalid numeric value provided: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error creating hybrid configuration: {str(e)}')
    
    # Get available installations grouped by facility
    solar_installations = FacilitySolar.objects.filter(is_active=True).select_related('idfacilities', 'idtechnologies').order_by('idfacilities__facility_name')
    storage_installations = FacilityStorage.objects.filter(is_active=True).select_related('idfacilities', 'idtechnologies').order_by('idfacilities__facility_name')
    
    context = {
        'solar_installations': solar_installations,
        'storage_installations': storage_installations,
    }
    
    if request.method == 'POST':
        context['form_data'] = request.POST
    
    return render(request, 'hybrid_solar_storage/create.html', context)

def hybrid_edit(request, pk):
    """Edit an existing hybrid configuration"""
    hybrid = get_object_or_404(HybridSolarStorage, pk=pk)
    
    if request.method == 'POST':
        try:
            # Extract form data
            configuration_name = request.POST.get('configuration_name', '').strip()
            coupling_type = request.POST.get('coupling_type')
            shared_grid_connection = request.POST.get('shared_grid_connection') == 'on'
            shared_inverter_capacity = request.POST.get('shared_inverter_capacity')
            grid_connection_capacity = request.POST.get('grid_connection_capacity')
            charge_from_solar_only = request.POST.get('charge_from_solar_only') == 'on'
            priority_dispatch = request.POST.get('priority_dispatch')
            commissioning_date = request.POST.get('commissioning_date')
            energy_clipping_losses = request.POST.get('energy_clipping_losses')
            notes = request.POST.get('notes', '').strip()
            is_active = request.POST.get('is_active') == 'on'
            
            # Update the hybrid configuration
            hybrid.configuration_name = configuration_name if configuration_name else None
            hybrid.coupling_type = coupling_type
            hybrid.shared_grid_connection = shared_grid_connection
            hybrid.shared_inverter_capacity = float(shared_inverter_capacity) if shared_inverter_capacity else None
            hybrid.grid_connection_capacity = float(grid_connection_capacity) if grid_connection_capacity else None
            hybrid.charge_from_solar_only = charge_from_solar_only
            hybrid.priority_dispatch = priority_dispatch
            hybrid.commissioning_date = commissioning_date if commissioning_date else None
            hybrid.energy_clipping_losses = float(energy_clipping_losses) if energy_clipping_losses else None
            hybrid.notes = notes if notes else None
            hybrid.is_active = is_active
            hybrid.save()
            
            messages.success(request, 'Hybrid configuration updated successfully.')
            return redirect('powermapui:hybrid_detail', pk=hybrid.pk)
            
        except ValueError as e:
            messages.error(request, f'Invalid numeric value provided: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error updating hybrid configuration: {str(e)}')
    
    context = {
        'hybrid': hybrid,
    }
    return render(request, 'hybrid_solar_storage/edit.html', context)

@require_POST
def hybrid_delete(request, pk):
    """Delete a hybrid configuration"""
    hybrid = get_object_or_404(HybridSolarStorage, pk=pk)
    
    facility_name = hybrid.facility.facility_name
    config_name = hybrid.configuration_name or "Hybrid System"
    
    hybrid.delete()
    messages.success(request, f'Removed hybrid configuration "{config_name}" from {facility_name}.')
    return redirect('powermapui:hybrid_list')

def get_hybrid_json(request):
    """Return hybrid configurations as JSON"""
    hybrids = HybridSolarStorage.objects.select_related(
        'solar_installation__idfacilities',
        'storage_installation'
    ).filter(is_active=True)
    
    data = []
    for hybrid in hybrids:
        data.append({
            'id': hybrid.idhybridsolarstorstorage,
            'facility_id': hybrid.facility.idfacilities,
            'facility_name': hybrid.facility.facility_name,
            'configuration_name': hybrid.configuration_name,
            'coupling_type': hybrid.coupling_type,
            'solar_dc_capacity': hybrid.total_solar_capacity_dc,
            'solar_ac_capacity': hybrid.total_solar_capacity_ac,
            'storage_power': hybrid.total_storage_power,
            'storage_energy': hybrid.total_storage_energy,
            'storage_duration': hybrid.storage_duration,
            'effective_ac_capacity': hybrid.get_effective_ac_capacity(),
            'grid_connection_capacity': hybrid.grid_connection_capacity,
            'is_dc_coupled': hybrid.is_dc_coupled,
            'charges_from_solar_only': hybrid.charge_from_solar_only,
            'is_active': hybrid.is_active,
        })
    
    return JsonResponse({
        'hybrids': data,
        'count': len(data),
        'total_solar_dc_mw': sum(d['solar_dc_capacity'] or 0 for d in data),
        'total_storage_power_mw': sum(d['storage_power'] or 0 for d in data),
        'total_storage_energy_mwh': sum(d['storage_energy'] or 0 for d in data),
    })

def get_available_storage_for_solar(request, solar_pk):
    """AJAX endpoint to get available storage at same facility as solar"""
    try:
        solar = FacilitySolar.objects.get(pk=solar_pk)
        # Get storage at same facility that isn't already in a hybrid config
        available_storage = FacilityStorage.objects.filter(
            idfacilities=solar.facility,
            is_active=True
        ).exclude(
            hybrid_configurations__is_active=True
        )
        
        data = [{
            'id': s.idfacilitystorage,
            'name': f"{s.technology.technology_name} - {s.installation_name or 'Unnamed'}",
            'power': s.power_capacity,
            'energy': s.energy_capacity,
        } for s in available_storage]
        
        return JsonResponse({'storage_installations': data})
    except FacilitySolar.DoesNotExist:
        return JsonResponse({'error': 'Solar installation not found'}, status=404)
