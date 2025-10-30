from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q, Count
from django.views.decorators.http import require_POST
from siren_web.models import Terminals, GridLines, facilities, FacilityGridConnections

def terminal_connections(request, pk):
    """Manage all connections for a terminal with AI-powered suggestions"""
    from .terminal_utilities import suggest_terminal_connections
    
    terminal = get_object_or_404(Terminals, pk=pk)
    
    # Get max distance for suggestions from query params
    max_distance = request.GET.get('max_distance', 50)
    try:
        max_distance = float(max_distance)
    except ValueError:
        max_distance = 50
    
    # Get all grid lines (for adding new connections)
    available_gridlines = GridLines.objects.filter(active=True).exclude(
        Q(from_terminal=terminal) | Q(to_terminal=terminal)
    ).order_by('line_name')
    
    # Get connected grid lines
    outgoing_lines = terminal.get_outgoing_lines()
    incoming_lines = terminal.get_incoming_lines()
    
    # Get facilities connected through grid lines
    connected_facilities = []
    all_connected_lines = terminal.get_connected_grid_lines()
    
    for line in all_connected_lines:
        facility_connections = FacilityGridConnections.objects.filter(
            idgridlines=line,
            active=True
        ).select_related('idfacilities', 'idfacilities__idtechnologies')
        
        for conn in facility_connections:
            connected_facilities.append({
                'facility': conn.idfacilities,
                'grid_line': line,
                'connection': conn,
                'is_primary': conn.is_primary,
            })
    
    # Get all available facilities (not yet connected to this terminal)
    connected_facility_ids = [item['facility'].pk for item in connected_facilities]
    available_facilities = facilities.objects.filter(
        active=True
    ).exclude(
        pk__in=connected_facility_ids
    ).select_related('idtechnologies', 'idzones').order_by('facility_name')
    
    # NEW: Get intelligent connection suggestions
    suggestions = suggest_terminal_connections(terminal, max_distance_km=max_distance)
    
    # Calculate suggestion statistics
    excellent_matches = sum(1 for s in suggestions if s.get('overall_score', 0) >= 70)
    good_matches = sum(1 for s in suggestions if s.get('overall_score', 0) >= 50)
    closest_distance = suggestions[0]['distance_km'] if suggestions else 0
    best_score = suggestions[0]['overall_score'] if suggestions else 0
    
    context = {
        'terminal': terminal,
        'outgoing_lines': outgoing_lines,
        'incoming_lines': incoming_lines,
        'available_gridlines': available_gridlines,
        'connected_facilities': connected_facilities,
        'available_facilities': available_facilities,
        # Suggestion data
        'suggestions': suggestions,
        'max_distance': max_distance,
        'excellent_matches': excellent_matches,
        'good_matches': good_matches,
        'closest_distance': closest_distance,
        'best_score': best_score,
    }
    
    return render(request, 'terminals/connections.html', context)

@require_POST
def terminal_add_gridline(request, pk):
    """Add a grid line connection to a terminal"""
    from django.urls import reverse
    
    terminal = get_object_or_404(Terminals, pk=pk)
    
    gridline_id = request.POST.get('gridline_id')
    connection_type = request.POST.get('connection_type')  # 'from' or 'to'
    return_tab = request.POST.get('return_tab', '')  # Track which tab to return to
    
    # Build redirect URL with tab hash if specified
    redirect_url = reverse('powermapui:terminal_connections', kwargs={'pk': pk})
    if return_tab:
        redirect_url += f'#{return_tab}'
    
    if not gridline_id or not connection_type:
        messages.error(request, 'Grid line and connection type are required.')
        return redirect(redirect_url)
    
    try:
        gridline = get_object_or_404(GridLines, pk=gridline_id)
        
        if connection_type == 'from':
            # Check if already has a from_terminal
            if gridline.from_terminal:
                messages.error(request, f'Grid line "{gridline.line_name}" already has a from-terminal ({gridline.from_terminal.terminal_name}). Remove that connection first.')
                return redirect(redirect_url)
            
            gridline.from_terminal = terminal
            gridline.save()
            messages.success(request, f'Added "{gridline.line_name}" as outgoing line from {terminal.terminal_name}.')
            
        elif connection_type == 'to':
            # Check if already has a to_terminal
            if gridline.to_terminal:
                messages.error(request, f'Grid line "{gridline.line_name}" already has a to-terminal ({gridline.to_terminal.terminal_name}). Remove that connection first.')
                return redirect(redirect_url)
            
            gridline.to_terminal = terminal
            gridline.save()
            messages.success(request, f'Added "{gridline.line_name}" as incoming line to {terminal.terminal_name}.')
            
        else:
            messages.error(request, 'Invalid connection type.')
            
    except Exception as e:
        messages.error(request, f'Error adding grid line connection: {str(e)}')
    
    return redirect(redirect_url)
@require_POST
def terminal_remove_gridline(request, pk, gridline_id):
    """Remove a grid line connection from a terminal"""
    terminal = get_object_or_404(Terminals, pk=pk)
    gridline = get_object_or_404(GridLines, pk=gridline_id)
    
    try:
        removed = False
        
        if gridline.from_terminal == terminal:
            gridline.from_terminal = None
            removed = True
            connection_type = "outgoing"
        
        if gridline.to_terminal == terminal:
            gridline.to_terminal = None
            removed = True
            connection_type = "incoming"
        
        if removed:
            gridline.save()
            messages.success(request, f'Removed {connection_type} connection for "{gridline.line_name}".')
        else:
            messages.warning(request, f'Grid line "{gridline.line_name}" is not connected to this terminal.')
            
    except Exception as e:
        messages.error(request, f'Error removing grid line connection: {str(e)}')
    
    return redirect('powermapui:terminal_connections', pk=pk)

def terminal_facilities_view(request, pk):
    """View all facilities connected through this terminal's grid lines"""
    terminal = get_object_or_404(Terminals, pk=pk)
    
    # Get all grid lines connected to this terminal
    connected_lines = terminal.get_connected_grid_lines()
    
    # Get all facilities connected through these grid lines
    facility_data = []
    total_capacity = 0
    
    for line in connected_lines:
        facility_connections = FacilityGridConnections.objects.filter(
            idgridlines=line,
            active=True
        ).select_related('idfacilities', 'idfacilities__idtechnologies', 'idfacilities__idzones')
        
        for conn in facility_connections:
            facility = conn.idfacilities
            capacity = facility.capacity or 0
            total_capacity += capacity
            
            # Determine direction relative to terminal
            if line.from_terminal == terminal:
                direction = "Outgoing"
            elif line.to_terminal == terminal:
                direction = "Incoming"
            else:
                direction = "Unknown"
            
            facility_data.append({
                'facility': facility,
                'grid_line': line,
                'connection': conn,
                'capacity': capacity,
                'direction': direction,
                'is_primary': conn.is_primary,
                'connection_capacity': conn.connection_capacity_mw,
                'distance': conn.connection_distance_km,
            })
    
    # Sort by capacity (descending)
    facility_data.sort(key=lambda x: x['capacity'], reverse=True)
    
    # Pagination
    paginator = Paginator(facility_data, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'terminal': terminal,
        'page_obj': page_obj,
        'total_capacity': total_capacity,
        'total_facilities': len(facility_data),
        'connected_lines_count': connected_lines.count(),
    }
    
    return render(request, 'terminals/facilities.html', context)

def terminal_gridlines_view(request, pk):
    """View all grid lines connected to this terminal with details"""
    terminal = get_object_or_404(Terminals, pk=pk)
    
    # Get detailed grid line information
    outgoing_lines = []
    for line in terminal.get_outgoing_lines():
        facilities_count = line.connected_facilities.count()
        total_capacity = sum(
            f.capacity for f in line.connected_facilities.all() 
            if f.capacity
        )
        
        outgoing_lines.append({
            'line': line,
            'facilities_count': facilities_count,
            'total_capacity': total_capacity,
            'utilization': line.get_utilization_percent(total_capacity) if total_capacity else 0,
        })
    
    incoming_lines = []
    for line in terminal.get_incoming_lines():
        facilities_count = line.connected_facilities.count()
        total_capacity = sum(
            f.capacity for f in line.connected_facilities.all() 
            if f.capacity
        )
        
        incoming_lines.append({
            'line': line,
            'facilities_count': facilities_count,
            'total_capacity': total_capacity,
            'utilization': line.get_utilization_percent(total_capacity) if total_capacity else 0,
        })
    
    context = {
        'terminal': terminal,
        'outgoing_lines': outgoing_lines,
        'incoming_lines': incoming_lines,
        'total_lines': len(outgoing_lines) + len(incoming_lines),
    }
    
    return render(request, 'terminals/gridlines.html', context)

@require_POST
def terminal_set_primary_gridline(request, pk):
    """Set a grid line as the primary connection for the terminal"""
    terminal = get_object_or_404(Terminals, pk=pk)
    gridline_id = request.POST.get('gridline_id')
    
    if not gridline_id:
        messages.error(request, 'Grid line ID is required.')
        return redirect('powermapui:terminal_gridlines', pk=pk)
    
    try:
        gridline = get_object_or_404(GridLines, pk=gridline_id)
        
        # Verify the grid line is connected to this terminal
        if gridline.from_terminal != terminal and gridline.to_terminal != terminal:
            messages.error(request, 'This grid line is not connected to the terminal.')
            return redirect('powermapui:terminal_gridlines', pk=pk)
        
        # Could implement a primary_gridline field on Terminal if needed
        messages.info(request, 'Primary grid line designation noted. (Implementation can be extended based on requirements)')
        
    except Exception as e:
        messages.error(request, f'Error setting primary grid line: {str(e)}')
    
    return redirect('powermapui:terminal_gridlines', pk=pk)

# RENAMED from bulk_connect_facility_to_terminal
def connect_facility_to_terminal(request, terminal_pk, facility_pk):
    """Connect a facility to a terminal via grid line selection"""
    terminal = get_object_or_404(Terminals, pk=terminal_pk)
    facility = get_object_or_404(facilities, pk=facility_pk)
    
    # Get available grid lines connected to this terminal
    available_gridlines = terminal.get_connected_grid_lines()
    
    # Check if terminal has any connected grid lines
    if not available_gridlines.exists():
        messages.error(request, 'This terminal has no connected grid lines. Please connect grid lines first.')
        return redirect('powermapui:terminal_connections', pk=terminal_pk)
    
    if request.method == 'POST':
        gridline_id = request.POST.get('gridline_id')
        connection_type = request.POST.get('connection_type', 'direct')
        is_primary = request.POST.get('is_primary') == 'on'
        connection_capacity = request.POST.get('connection_capacity')
        connection_distance = request.POST.get('connection_distance')
        connection_voltage = request.POST.get('connection_voltage')
        
        if not gridline_id:
            messages.error(request, 'Please select a grid line.')
            context = {
                'terminal': terminal,
                'facility': facility,
                'available_gridlines': available_gridlines,
            }
            return render(request, 'terminals/connect_facility.html', context)
        
        try:
            gridline = get_object_or_404(GridLines, pk=gridline_id)
            
            # Verify the gridline is connected to this terminal
            if gridline not in available_gridlines:
                messages.error(request, 'Selected grid line is not connected to this terminal.')
                context = {
                    'terminal': terminal,
                    'facility': facility,
                    'available_gridlines': available_gridlines,
                }
                return render(request, 'terminals/connect_facility.html', context)
            
            # Check if connection already exists
            existing = FacilityGridConnections.objects.filter(
                idfacilities=facility,
                idgridlines=gridline,
                active=True
            ).first()
            
            if existing:
                messages.warning(request, f'Facility "{facility.facility_name}" is already connected to grid line "{gridline.line_name}".')
                return redirect('powermapui:terminal_connections', pk=terminal_pk)
            
            # Create the connection
            connection = FacilityGridConnections.objects.create(
                idfacilities=facility,
                idgridlines=gridline,
                connection_type=connection_type,
                connection_point_latitude=facility.latitude or 0,
                connection_point_longitude=facility.longitude or 0,
                connection_voltage_kv=float(connection_voltage) if connection_voltage else gridline.voltage_level,
                connection_capacity_mw=float(connection_capacity) if connection_capacity else (facility.capacity or 0),
                connection_distance_km=float(connection_distance) if connection_distance else 0,
                is_primary=is_primary,
                active=True,
            )
            
            messages.success(request, f'Successfully connected facility "{facility.facility_name}" to terminal "{terminal.terminal_name}" via grid line "{gridline.line_name}".')
            return redirect('powermapui:terminal_connections', pk=terminal_pk)
            
        except Exception as e:
            messages.error(request, f'Error connecting facility: {str(e)}')
            context = {
                'terminal': terminal,
                'facility': facility,
                'available_gridlines': available_gridlines,
            }
            return render(request, 'terminals/connect_facility.html', context)
    
    # GET request - show form
    context = {
        'terminal': terminal,
        'facility': facility,
        'available_gridlines': available_gridlines,
    }
    
    return render(request, 'terminals/connect_facility.html', context)

@require_POST
def terminal_remove_facility(request, pk, connection_id):
    """Remove a facility connection from a terminal's grid lines"""
    terminal = get_object_or_404(Terminals, pk=pk)
    
    try:
        connection = get_object_or_404(FacilityGridConnections, pk=connection_id)
        
        # Verify the connection is through one of this terminal's grid lines
        if connection.idgridlines not in terminal.get_connected_grid_lines():
            messages.error(request, 'This facility connection is not associated with this terminal.')
            return redirect('powermapui:terminal_connections', pk=pk)
        
        facility_name = connection.idfacilities.facility_name
        gridline_name = connection.idgridlines.line_name
        
        # Deactivate the connection instead of deleting
        connection.active = False
        connection.save()
        
        messages.success(request, f'Removed facility "{facility_name}" from grid line "{gridline_name}".')
        
    except Exception as e:
        messages.error(request, f'Error removing facility connection: {str(e)}')
    
    return redirect('powermapui:terminal_connections', pk=pk)

def terminal_node_diagram(request, pk):
    """Generate data for a network diagram showing terminal connections"""
    import json
    
    terminal = get_object_or_404(Terminals, pk=pk)
    
    # Prepare data for visualization
    nodes = []
    links = []
    added_terminals = set()
    added_facilities = set()
    
    # Add main terminal node
    terminal_id = f'terminal_{terminal.pk}'
    nodes.append({
        'id': terminal_id,
        'label': terminal.terminal_name,
        'type': 'terminal',
        'voltage': float(terminal.primary_voltage_kv) if terminal.primary_voltage_kv else 0,
        'is_main': True,
    })
    added_terminals.add(terminal.pk)
    
    # Process each grid line connected to this terminal
    for line in terminal.get_connected_grid_lines():
        # Determine the other terminal (if exists)
        other_terminal = None
        direction = 'unknown'
        
        if line.from_terminal == terminal and line.to_terminal:
            other_terminal = line.to_terminal
            direction = 'outgoing'
        elif line.to_terminal == terminal and line.from_terminal:
            other_terminal = line.from_terminal
            direction = 'incoming'
        elif line.from_terminal == terminal:
            direction = 'outgoing'
        elif line.to_terminal == terminal:
            direction = 'incoming'
        
        # If there's no other terminal, create a virtual endpoint node
        other_terminal_id = None
        if other_terminal and other_terminal.pk not in added_terminals:
            other_terminal_id = f'terminal_{other_terminal.pk}'
            nodes.append({
                'id': other_terminal_id,
                'label': other_terminal.terminal_name,
                'type': 'terminal',
                'voltage': float(other_terminal.primary_voltage_kv) if other_terminal.primary_voltage_kv else 0,
                'is_main': False,
            })
            added_terminals.add(other_terminal.pk)
        elif other_terminal:
            other_terminal_id = f'terminal_{other_terminal.pk}'
        else:
            # Create a virtual endpoint for incomplete grid line
            endpoint_id = f'endpoint_{line.pk}'
            endpoint_label = line.line_name.replace('to Mungarra Terminal', '').replace('from Mungarra Terminal', '').replace('Mungarra Terminal to', '').replace('Mungarra Power Station to', '').strip()
            if not endpoint_label:
                endpoint_label = f"Endpoint ({line.line_name})"
            
            nodes.append({
                'id': endpoint_id,
                'label': endpoint_label,
                'type': 'endpoint',
                'voltage': float(line.voltage_level) if line.voltage_level else 0,
                'is_main': False,
            })
            other_terminal_id = endpoint_id
        
        # Get facilities connected to this grid line
        facility_connections = FacilityGridConnections.objects.filter(
            idgridlines=line, 
            active=True
        ).select_related('idfacilities', 'idfacilities__idtechnologies')
        
        # Process each facility connection
        for conn in facility_connections:
            facility = conn.idfacilities
            facility_id = f'facility_{facility.pk}'
            
            # Add facility node if not already added
            if facility.pk not in added_facilities:
                nodes.append({
                    'id': facility_id,
                    'label': facility.facility_name,
                    'type': 'facility',
                    'capacity': float(facility.capacity) if facility.capacity else 0,
                    'technology': facility.idtechnologies.technology_name if facility.idtechnologies else 'Unknown',
                })
                added_facilities.add(facility.pk)
            
            # Determine which terminal the facility should connect to
            # Facilities connect to the terminal on their "side" of the grid line
            if direction == 'outgoing':
                # Line goes from main terminal outward
                # If there's another terminal, facility connects to it
                # Otherwise, connects to main terminal
                source_id = other_terminal_id if other_terminal_id else terminal_id
            elif direction == 'incoming':
                # Line comes into main terminal
                # Facility connects from the other terminal to main
                source_id = other_terminal_id if other_terminal_id else terminal_id
            else:
                source_id = terminal_id
            
            # Add link from appropriate terminal to facility
            link_data = {
                'source': source_id,
                'target': facility_id,
                'type': 'facility_connection',
                'is_primary': bool(conn.is_primary),
                'capacity': float(conn.connection_capacity_mw) if conn.connection_capacity_mw else 0,
                'voltage': float(conn.connection_voltage_kv) if conn.connection_voltage_kv else float(line.voltage_level) if line.voltage_level else 0,
                'gridline_name': line.line_name,
            }
            links.append(link_data)
        
        # Add link between terminals/endpoints - ALWAYS create this link
        if other_terminal_id:
            # Determine source and target based on direction
            if direction == 'outgoing':
                source_id = terminal_id
                target_id = other_terminal_id
            else:  # incoming
                source_id = other_terminal_id
                target_id = terminal_id
            
            link_data = {
                'source': source_id,
                'target': target_id,
                'type': 'gridline',
                'direction': direction,
                'voltage': float(line.voltage_level) if line.voltage_level else 0,
                'capacity': float(line.thermal_capacity_mw) if line.thermal_capacity_mw else 0,
                'gridline_name': line.line_name,
                'gridline_id': line.pk,
            }
            links.append(link_data)
    
    # Calculate node type counts for the legend
    terminal_count = sum(1 for node in nodes if node.get('type') == 'terminal')
    facility_count = sum(1 for node in nodes if node.get('type') == 'facility')
    endpoint_count = sum(1 for node in nodes if node.get('type') == 'endpoint')
    gridline_count = len([link for link in links if link.get('type') == 'gridline'])
    
    # Create the complete network data structure
    network_data = {
        'nodes': nodes,
        'links': links
    }
    
    # Convert to JSON string for embedding in template
    network_data_json = json.dumps(network_data)
    
    context = {
        'terminal': terminal,
        'network_data_json': network_data_json,
        'nodes': nodes,
        'links': links,
        'terminal_count': terminal_count,
        'gridline_count': gridline_count,
        'facility_count': facility_count,
    }
    
    return render(request, 'terminals/node_diagram.html', context)