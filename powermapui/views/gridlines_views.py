"""
GridLines CRUD views
Similar to terminals_views.py but for grid lines
"""
from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from django.views.decorators.http import require_POST
from siren_web.models import GridLines, Terminals, FacilityGridConnections


def gridlines_list(request):
    """List all grid lines with search and pagination"""
    search_query = request.GET.get('search', '')
    line_type_filter = request.GET.get('line_type', '')
    voltage_min = request.GET.get('voltage_min', '')
    voltage_max = request.GET.get('voltage_max', '')
    active_filter = request.GET.get('active', '')
    connected_filter = request.GET.get('connected', '')
    
    gridlines = GridLines.objects.select_related(
        'from_terminal', 'to_terminal'
    ).all().order_by('line_name')
    
    # Apply search filter
    if search_query:
        gridlines = gridlines.filter(
            Q(line_name__icontains=search_query) |
            Q(line_code__icontains=search_query) |
            Q(owner__icontains=search_query)
        )
    
    # Apply line type filter
    if line_type_filter:
        gridlines = gridlines.filter(line_type=line_type_filter)
    
    # Apply voltage filters
    if voltage_min:
        try:
            gridlines = gridlines.filter(voltage_level__gte=float(voltage_min))
        except ValueError:
            pass
    
    if voltage_max:
        try:
            gridlines = gridlines.filter(voltage_level__lte=float(voltage_max))
        except ValueError:
            pass
    
    # Apply active filter
    if active_filter:
        gridlines = gridlines.filter(active=(active_filter == 'true'))
    
    # Apply connected filter
    if connected_filter == 'true':
        gridlines = gridlines.filter(
            Q(from_terminal__isnull=False) | Q(to_terminal__isnull=False)
        )
    elif connected_filter == 'false':
        gridlines = gridlines.filter(from_terminal__isnull=True, to_terminal__isnull=True)
    
    # Get filter options
    line_types = GridLines._meta.get_field('line_type').choices
    
    # Pagination
    paginator = Paginator(gridlines, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calculate statistics for current page
    connected_count = sum(1 for line in page_obj.object_list if line.from_terminal or line.to_terminal)
    total_length = sum(line.length_km for line in page_obj.object_list if line.length_km)
    total_capacity = sum(line.thermal_capacity_mw for line in page_obj.object_list if line.thermal_capacity_mw)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'line_type_filter': line_type_filter,
        'voltage_min': voltage_min,
        'voltage_max': voltage_max,
        'active_filter': active_filter,
        'connected_filter': connected_filter,
        'line_types': line_types,
        'total_count': gridlines.count(),
        'connected_count': connected_count,
        'total_length': total_length,
        'total_capacity': total_capacity,
    }
    
    return render(request, 'gridlines/list.html', context)

def gridline_detail(request, pk):
    """Detail view for a specific grid line"""
    gridline = get_object_or_404(GridLines, pk=pk)
    
    # Get connected facilities
    facility_connections = FacilityGridConnections.objects.filter(
        idgridlines=gridline,
        active=True
    ).select_related('idfacilities', 'idfacilities__idtechnologies')
    
    # Calculate statistics
    total_connected_capacity = sum(
        conn.idfacilities.capacity for conn in facility_connections 
        if conn.idfacilities.capacity
    )
    
    utilization = gridline.get_utilization_percent(total_connected_capacity)
    
    # Calculate impedance
    impedance = gridline.calculate_impedance()
    resistance = gridline.calculate_resistance()
    reactance = gridline.calculate_reactance()
    
    # Calculate losses at current capacity
    losses = gridline.calculate_line_losses_mw(total_connected_capacity) if total_connected_capacity else 0
    
    context = {
        'gridline': gridline,
        'facility_connections': facility_connections,
        'total_connected_capacity': total_connected_capacity,
        'utilization': utilization,
        'impedance': impedance,
        'resistance': resistance,
        'reactance': reactance,
        'losses': losses,
    }
    
    return render(request, 'gridlines/detail.html', context)

def gridline_create(request):
    """Create a new grid line"""
    if request.method == 'POST':
        try:
            # Extract form data
            line_name = request.POST.get('line_name', '').strip()
            line_code = request.POST.get('line_code', '').strip()
            line_type = request.POST.get('line_type')
            voltage_level = request.POST.get('voltage_level')
            length_km = request.POST.get('length_km')
            resistance_per_km = request.POST.get('resistance_per_km')
            reactance_per_km = request.POST.get('reactance_per_km')
            conductance_per_km = request.POST.get('conductance_per_km', '0')
            susceptance_per_km = request.POST.get('susceptance_per_km', '0')
            thermal_capacity_mw = request.POST.get('thermal_capacity_mw')
            emergency_capacity_mw = request.POST.get('emergency_capacity_mw')
            from_terminal_id = request.POST.get('from_terminal')
            to_terminal_id = request.POST.get('to_terminal')
            from_latitude = request.POST.get('from_latitude')
            from_longitude = request.POST.get('from_longitude')
            to_latitude = request.POST.get('to_latitude')
            to_longitude = request.POST.get('to_longitude')
            owner = request.POST.get('owner', '').strip()
            active = request.POST.get('active') == 'on'
            
            # Validation
            if not line_name:
                messages.error(request, 'Line name is required.')
                return render(request, 'gridlines/create.html', get_create_context(request.POST))
            
            if not line_code:
                messages.error(request, 'Line code is required.')
                return render(request, 'gridlines/create.html', get_create_context(request.POST))
            
            if not voltage_level:
                messages.error(request, 'Voltage level is required.')
                return render(request, 'gridlines/create.html', get_create_context(request.POST))
            
            # Check for duplicates
            if GridLines.objects.filter(line_name=line_name).exists():
                messages.error(request, 'A grid line with this name already exists.')
                return render(request, 'gridlines/create.html', get_create_context(request.POST))
            
            if GridLines.objects.filter(line_code=line_code).exists():
                messages.error(request, 'A grid line with this code already exists.')
                return render(request, 'gridlines/create.html', get_create_context(request.POST))
            
            # Get terminals
            from_terminal = None
            to_terminal = None
            
            if from_terminal_id:
                from_terminal = get_object_or_404(Terminals, pk=from_terminal_id)
            
            if to_terminal_id:
                to_terminal = get_object_or_404(Terminals, pk=to_terminal_id)
            
            # Create the grid line
            gridline = GridLines.objects.create(
                line_name=line_name,
                line_code=line_code,
                line_type=line_type,
                voltage_level=float(voltage_level),
                length_km=float(length_km) if length_km else 0,
                resistance_per_km=float(resistance_per_km) if resistance_per_km else 0,
                reactance_per_km=float(reactance_per_km) if reactance_per_km else 0,
                conductance_per_km=float(conductance_per_km) if conductance_per_km else 0,
                susceptance_per_km=float(susceptance_per_km) if susceptance_per_km else 0,
                thermal_capacity_mw=float(thermal_capacity_mw) if thermal_capacity_mw else None,
                emergency_capacity_mw=float(emergency_capacity_mw) if emergency_capacity_mw else None,
                from_terminal=from_terminal,
                to_terminal=to_terminal,
                from_latitude=float(from_latitude) if from_latitude else None,
                from_longitude=float(from_longitude) if from_longitude else None,
                to_latitude=float(to_latitude) if to_latitude else None,
                to_longitude=float(to_longitude) if to_longitude else None,
                owner=owner if owner else None,
                active=active,
            )
            
            messages.success(request, f'Grid line "{line_name}" created successfully.')
            return redirect('powermapui:gridline_detail', pk=gridline.pk)
            
        except ValueError as e:
            messages.error(request, f'Invalid numeric value provided: {str(e)}')
            return render(request, 'gridlines/create.html', get_create_context(request.POST))
        except Exception as e:
            messages.error(request, f'Error creating grid line: {str(e)}')
            return render(request, 'gridlines/create.html', get_create_context(request.POST))
    
    return render(request, 'gridlines/create.html', get_create_context())


def gridline_edit(request, pk):
    """Edit an existing grid line"""
    gridline = get_object_or_404(GridLines, pk=pk)
    
    if request.method == 'POST':
        try:
            # Extract form data
            line_name = request.POST.get('line_name', '').strip()
            line_code = request.POST.get('line_code', '').strip()
            line_type = request.POST.get('line_type')
            voltage_level = request.POST.get('voltage_level')
            length_km = request.POST.get('length_km')
            resistance_per_km = request.POST.get('resistance_per_km')
            reactance_per_km = request.POST.get('reactance_per_km')
            conductance_per_km = request.POST.get('conductance_per_km', '0')
            susceptance_per_km = request.POST.get('susceptance_per_km', '0')
            thermal_capacity_mw = request.POST.get('thermal_capacity_mw')
            emergency_capacity_mw = request.POST.get('emergency_capacity_mw')
            from_terminal_id = request.POST.get('from_terminal')
            to_terminal_id = request.POST.get('to_terminal')
            from_latitude = request.POST.get('from_latitude')
            from_longitude = request.POST.get('from_longitude')
            to_latitude = request.POST.get('to_latitude')
            to_longitude = request.POST.get('to_longitude')
            owner = request.POST.get('owner', '').strip()
            active = request.POST.get('active') == 'on'
            
            # Validation
            if not line_name:
                messages.error(request, 'Line name is required.')
                return render(request, 'gridlines/edit.html', get_edit_context(gridline))
            
            if not line_code:
                messages.error(request, 'Line code is required.')
                return render(request, 'gridlines/edit.html', get_edit_context(gridline))
            
            # Check for duplicates (excluding current)
            if GridLines.objects.filter(line_name=line_name).exclude(pk=pk).exists():
                messages.error(request, 'A grid line with this name already exists.')
                return render(request, 'gridlines/edit.html', get_edit_context(gridline))
            
            if GridLines.objects.filter(line_code=line_code).exclude(pk=pk).exists():
                messages.error(request, 'A grid line with this code already exists.')
                return render(request, 'gridlines/edit.html', get_edit_context(gridline))
            
            # Get terminals
            from_terminal = None
            to_terminal = None
            
            if from_terminal_id:
                from_terminal = get_object_or_404(Terminals, pk=from_terminal_id)
            
            if to_terminal_id:
                to_terminal = get_object_or_404(Terminals, pk=to_terminal_id)
            
            # Update the grid line
            gridline.line_name = line_name
            gridline.line_code = line_code
            gridline.line_type = line_type
            gridline.voltage_level = float(voltage_level)
            gridline.length_km = float(length_km) if length_km else 0
            gridline.resistance_per_km = float(resistance_per_km) if resistance_per_km else 0
            gridline.reactance_per_km = float(reactance_per_km) if reactance_per_km else 0
            gridline.conductance_per_km = float(conductance_per_km) if conductance_per_km else 0
            gridline.susceptance_per_km = float(susceptance_per_km) if susceptance_per_km else 0
            gridline.thermal_capacity_mw = float(thermal_capacity_mw) if thermal_capacity_mw else None
            gridline.emergency_capacity_mw = float(emergency_capacity_mw) if emergency_capacity_mw else None
            gridline.from_terminal = from_terminal
            gridline.to_terminal = to_terminal
            gridline.from_latitude = float(from_latitude) if from_latitude else None
            gridline.from_longitude = float(from_longitude) if from_longitude else None
            gridline.to_latitude = float(to_latitude) if to_latitude else None
            gridline.to_longitude = float(to_longitude) if to_longitude else None
            gridline.owner = owner if owner else None
            gridline.active = active
            gridline.save()
            
            messages.success(request, f'Grid line "{line_name}" updated successfully.')
            return redirect('powermapui:gridline_detail', pk=gridline.pk)
            
        except ValueError as e:
            messages.error(request, f'Invalid numeric value provided: {str(e)}')
            return render(request, 'gridlines/edit.html', get_edit_context(gridline))
        except Exception as e:
            messages.error(request, f'Error updating grid line: {str(e)}')
            return render(request, 'gridlines/edit.html', get_edit_context(gridline))
    
    return render(request, 'gridlines/edit.html', get_edit_context(gridline))

@require_POST
def gridline_delete(request, pk):
    """Delete a grid line"""
    gridline = get_object_or_404(GridLines, pk=pk)
    
    line_name = gridline.line_name
    
    # Check if grid line has connected facilities
    connected_facilities = FacilityGridConnections.objects.filter(
        idgridlines=gridline,
        active=True
    ).count()
    
    if connected_facilities > 0:
        messages.error(request, f'Cannot delete grid line "{line_name}" because it has {connected_facilities} connected facilities. Remove these connections first.')
        return redirect('powermapui:gridline_detail', pk=pk)
    
    # Delete the grid line
    gridline.delete()
    
    messages.success(request, f'Grid line "{line_name}" deleted successfully.')
    return redirect('powermapui:gridlines_list')

# Helper functions

def get_create_context(form_data=None):
    """Get context for create form"""
    terminals = Terminals.objects.filter(active=True).order_by('terminal_name')
    line_types = GridLines._meta.get_field('line_type').choices
    
    context = {
        'terminals': terminals,
        'line_types': line_types,
    }
    
    if form_data:
        context['form_data'] = form_data
    
    return context

def get_edit_context(gridline):
    """Get context for edit form"""
    terminals = Terminals.objects.filter(active=True).order_by('terminal_name')
    line_types = GridLines._meta.get_field('line_type').choices
    
    return {
        'gridline': gridline,
        'terminals': terminals,
        'line_types': line_types,
    }