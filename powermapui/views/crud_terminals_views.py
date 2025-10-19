from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from django.views.decorators.http import require_POST
from siren_web.models import Terminals

def terminals_list(request):
    """List all terminals with search and pagination"""
    search_query = request.GET.get('search', '')
    terminal_type_filter = request.GET.get('terminal_type', '')
    voltage_class_filter = request.GET.get('voltage_class', '')
    active_filter = request.GET.get('active', '')
    
    terminals = Terminals.objects.all().order_by('terminal_name')
    
    # Apply search filter
    if search_query:
        terminals = terminals.filter(
            Q(terminal_name__icontains=search_query) |
            Q(terminal_code__icontains=search_query) |
            Q(owner__icontains=search_query) |
            Q(operator__icontains=search_query)
        )
    
    # Apply terminal type filter
    if terminal_type_filter:
        terminals = terminals.filter(terminal_type=terminal_type_filter)
    
    # Apply voltage class filter
    if voltage_class_filter:
        terminals = terminals.filter(voltage_class=voltage_class_filter)
    
    # Apply active filter
    if active_filter:
        terminals = terminals.filter(active=(active_filter == 'true'))
    
    # Get filter options
    terminal_types = Terminals.TERMINAL_TYPES
    voltage_classes = Terminals.VOLTAGE_CLASSES
    
    # Pagination
    paginator = Paginator(terminals, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'terminal_type_filter': terminal_type_filter,
        'voltage_class_filter': voltage_class_filter,
        'active_filter': active_filter,
        'terminal_types': terminal_types,
        'voltage_classes': voltage_classes,
        'total_count': terminals.count(),
    }
    
    return render(request, 'terminals/list.html', context)

def terminal_detail(request, pk):
    """Detail view for a specific terminal"""
    terminal = get_object_or_404(Terminals, pk=pk)
    
    # Get connected grid lines
    connected_lines = terminal.get_connected_grid_lines()
    outgoing_lines = terminal.get_outgoing_lines()
    incoming_lines = terminal.get_incoming_lines()
    
    # Get connected facilities count
    connected_facilities_count = terminal.get_connected_facilities_count()
    
    # Get total connected capacity
    total_capacity = terminal.calculate_total_connected_capacity()
    
    # Get utilization
    utilization = terminal.get_utilization_percent()
    
    context = {
        'terminal': terminal,
        'connected_lines': connected_lines,
        'outgoing_lines': outgoing_lines,
        'incoming_lines': incoming_lines,
        'connected_facilities_count': connected_facilities_count,
        'total_capacity': total_capacity,
        'utilization': utilization,
    }
    
    return render(request, 'terminals/detail.html', context)

def terminal_create(request):
    """Create a new terminal"""
    if request.method == 'POST':
        try:
            # Extract form data
            terminal_name = request.POST.get('terminal_name', '').strip()
            terminal_code = request.POST.get('terminal_code', '').strip()
            terminal_type = request.POST.get('terminal_type')
            latitude = request.POST.get('latitude')
            longitude = request.POST.get('longitude')
            elevation = request.POST.get('elevation')
            primary_voltage_kv = request.POST.get('primary_voltage_kv')
            secondary_voltage_kv = request.POST.get('secondary_voltage_kv')
            voltage_class = request.POST.get('voltage_class')
            transformer_capacity_mva = request.POST.get('transformer_capacity_mva')
            short_circuit_capacity_mva = request.POST.get('short_circuit_capacity_mva')
            bay_count = request.POST.get('bay_count')
            owner = request.POST.get('owner', '').strip()
            operator = request.POST.get('operator', '').strip()
            maintenance_zone = request.POST.get('maintenance_zone', '').strip()
            control_center = request.POST.get('control_center', '').strip()
            scada_id = request.POST.get('scada_id', '').strip()
            description = request.POST.get('description', '').strip()
            active = request.POST.get('active') == 'on'
            
            # Validation
            if not terminal_name:
                messages.error(request, 'Terminal name is required.')
                return render(request, 'terminals/create.html', {
                    'form_data': request.POST,
                    'terminal_types': Terminals.TERMINAL_TYPES,
                    'voltage_classes': Terminals.VOLTAGE_CLASSES,
                })
            
            if not terminal_code:
                messages.error(request, 'Terminal code is required.')
                return render(request, 'terminals/create.html', {
                    'form_data': request.POST,
                    'terminal_types': Terminals.TERMINAL_TYPES,
                    'voltage_classes': Terminals.VOLTAGE_CLASSES,
                })
            
            if not primary_voltage_kv:
                messages.error(request, 'Primary voltage is required.')
                return render(request, 'terminals/create.html', {
                    'form_data': request.POST,
                    'terminal_types': Terminals.TERMINAL_TYPES,
                    'voltage_classes': Terminals.VOLTAGE_CLASSES,
                })
            
            # Check for duplicate terminal name
            if Terminals.objects.filter(terminal_name=terminal_name).exists():
                messages.error(request, 'A terminal with this name already exists.')
                return render(request, 'terminals/create.html', {
                    'form_data': request.POST,
                    'terminal_types': Terminals.TERMINAL_TYPES,
                    'voltage_classes': Terminals.VOLTAGE_CLASSES,
                })
            
            # Check for duplicate terminal code
            if Terminals.objects.filter(terminal_code=terminal_code).exists():
                messages.error(request, 'A terminal with this code already exists.')
                return render(request, 'terminals/create.html', {
                    'form_data': request.POST,
                    'terminal_types': Terminals.TERMINAL_TYPES,
                    'voltage_classes': Terminals.VOLTAGE_CLASSES,
                })
            
            # Create the terminal
            terminal = Terminals.objects.create(
                terminal_name=terminal_name,
                terminal_code=terminal_code,
                terminal_type=terminal_type,
                latitude=float(latitude) if latitude else None,
                longitude=float(longitude) if longitude else None,
                elevation=float(elevation) if elevation else None,
                primary_voltage_kv=float(primary_voltage_kv),
                secondary_voltage_kv=float(secondary_voltage_kv) if secondary_voltage_kv else None,
                voltage_class=voltage_class,
                transformer_capacity_mva=float(transformer_capacity_mva) if transformer_capacity_mva else None,
                short_circuit_capacity_mva=float(short_circuit_capacity_mva) if short_circuit_capacity_mva else None,
                bay_count=int(bay_count) if bay_count else None,
                owner=owner if owner else None,
                operator=operator if operator else None,
                maintenance_zone=maintenance_zone if maintenance_zone else None,
                control_center=control_center if control_center else None,
                scada_id=scada_id if scada_id else None,
                description=description if description else None,
                active=active,
            )
            
            messages.success(request, f'Terminal "{terminal_name}" created successfully.')
            return redirect('powermapui:terminal_detail', pk=terminal.pk)
            
        except ValueError as e:
            messages.error(request, f'Invalid numeric value provided: {str(e)}')
            return render(request, 'terminals/create.html', {
                'form_data': request.POST,
                'terminal_types': Terminals.TERMINAL_TYPES,
                'voltage_classes': Terminals.VOLTAGE_CLASSES,
            })
        except Exception as e:
            messages.error(request, f'Error creating terminal: {str(e)}')
            return render(request, 'terminals/create.html', {
                'form_data': request.POST,
                'terminal_types': Terminals.TERMINAL_TYPES,
                'voltage_classes': Terminals.VOLTAGE_CLASSES,
            })
    
    context = {
        'terminal_types': Terminals.TERMINAL_TYPES,
        'voltage_classes': Terminals.VOLTAGE_CLASSES,
    }
    return render(request, 'terminals/create.html', context)

def terminal_edit(request, pk):
    """Edit an existing terminal"""
    terminal = get_object_or_404(Terminals, pk=pk)
    
    if request.method == 'POST':
        try:
            # Extract form data
            terminal_name = request.POST.get('terminal_name', '').strip()
            terminal_code = request.POST.get('terminal_code', '').strip()
            terminal_type = request.POST.get('terminal_type')
            latitude = request.POST.get('latitude')
            longitude = request.POST.get('longitude')
            elevation = request.POST.get('elevation')
            primary_voltage_kv = request.POST.get('primary_voltage_kv')
            secondary_voltage_kv = request.POST.get('secondary_voltage_kv')
            voltage_class = request.POST.get('voltage_class')
            transformer_capacity_mva = request.POST.get('transformer_capacity_mva')
            short_circuit_capacity_mva = request.POST.get('short_circuit_capacity_mva')
            bay_count = request.POST.get('bay_count')
            owner = request.POST.get('owner', '').strip()
            operator = request.POST.get('operator', '').strip()
            maintenance_zone = request.POST.get('maintenance_zone', '').strip()
            control_center = request.POST.get('control_center', '').strip()
            scada_id = request.POST.get('scada_id', '').strip()
            description = request.POST.get('description', '').strip()
            active = request.POST.get('active') == 'on'
            
            # Validation
            if not terminal_name:
                messages.error(request, 'Terminal name is required.')
                return render(request, 'terminals/edit.html', {
                    'terminal': terminal,
                    'terminal_types': Terminals.TERMINAL_TYPES,
                    'voltage_classes': Terminals.VOLTAGE_CLASSES,
                })
            
            if not terminal_code:
                messages.error(request, 'Terminal code is required.')
                return render(request, 'terminals/edit.html', {
                    'terminal': terminal,
                    'terminal_types': Terminals.TERMINAL_TYPES,
                    'voltage_classes': Terminals.VOLTAGE_CLASSES,
                })
            
            if not primary_voltage_kv:
                messages.error(request, 'Primary voltage is required.')
                return render(request, 'terminals/edit.html', {
                    'terminal': terminal,
                    'terminal_types': Terminals.TERMINAL_TYPES,
                    'voltage_classes': Terminals.VOLTAGE_CLASSES,
                })
            
            # Check for duplicate terminal name (excluding current terminal)
            if Terminals.objects.filter(terminal_name=terminal_name).exclude(pk=pk).exists():
                messages.error(request, 'A terminal with this name already exists.')
                return render(request, 'terminals/edit.html', {
                    'terminal': terminal,
                    'form_data': request.POST,
                    'terminal_types': Terminals.TERMINAL_TYPES,
                    'voltage_classes': Terminals.VOLTAGE_CLASSES,
                })
            
            # Check for duplicate terminal code (excluding current terminal)
            if Terminals.objects.filter(terminal_code=terminal_code).exclude(pk=pk).exists():
                messages.error(request, 'A terminal with this code already exists.')
                return render(request, 'terminals/edit.html', {
                    'terminal': terminal,
                    'form_data': request.POST,
                    'terminal_types': Terminals.TERMINAL_TYPES,
                    'voltage_classes': Terminals.VOLTAGE_CLASSES,
                })
            
            # Update the terminal
            terminal.terminal_name = terminal_name
            terminal.terminal_code = terminal_code
            terminal.terminal_type = terminal_type
            terminal.latitude = float(latitude) if latitude else None
            terminal.longitude = float(longitude) if longitude else None
            terminal.elevation = float(elevation) if elevation else None
            terminal.primary_voltage_kv = float(primary_voltage_kv)
            terminal.secondary_voltage_kv = float(secondary_voltage_kv) if secondary_voltage_kv else None
            terminal.voltage_class = voltage_class
            terminal.transformer_capacity_mva = float(transformer_capacity_mva) if transformer_capacity_mva else None
            terminal.short_circuit_capacity_mva = float(short_circuit_capacity_mva) if short_circuit_capacity_mva else None
            terminal.bay_count = int(bay_count) if bay_count else None
            terminal.owner = owner if owner else None
            terminal.operator = operator if operator else None
            terminal.maintenance_zone = maintenance_zone if maintenance_zone else None
            terminal.control_center = control_center if control_center else None
            terminal.scada_id = scada_id if scada_id else None
            terminal.description = description if description else None
            terminal.active = active
            terminal.save()
            
            messages.success(request, f'Terminal "{terminal_name}" updated successfully.')
            return redirect('powermapui:terminal_detail', pk=terminal.pk)
            
        except ValueError as e:
            messages.error(request, f'Invalid numeric value provided: {str(e)}')
            return render(request, 'terminals/edit.html', {
                'terminal': terminal,
                'terminal_types': Terminals.TERMINAL_TYPES,
                'voltage_classes': Terminals.VOLTAGE_CLASSES,
            })
        except Exception as e:
            messages.error(request, f'Error updating terminal: {str(e)}')
            return render(request, 'terminals/edit.html', {
                'terminal': terminal,
                'terminal_types': Terminals.TERMINAL_TYPES,
                'voltage_classes': Terminals.VOLTAGE_CLASSES,
            })
    
    context = {
        'terminal': terminal,
        'terminal_types': Terminals.TERMINAL_TYPES,
        'voltage_classes': Terminals.VOLTAGE_CLASSES,
    }
    
    return render(request, 'terminals/edit.html', context)

@require_POST
def terminal_delete(request, pk):
    """Delete a terminal"""
    terminal = get_object_or_404(Terminals, pk=pk)
    
    terminal_name = terminal.terminal_name
    
    # Check if terminal has connected grid lines
    connected_lines = terminal.get_connected_grid_lines()
    if connected_lines.exists():
        messages.error(request, f'Cannot delete terminal "{terminal_name}" because it has {connected_lines.count()} connected grid line(s). Remove these connections first.')
        return redirect('powermapui:terminal_detail', pk=pk)
    
    # Delete the terminal
    terminal.delete()
    
    messages.success(request, f'Terminal "{terminal_name}" deleted successfully.')
    return redirect('powermapui:terminals_list')