"""
Utility functions for Terminal connection management
"""
from django.db.models import Sum, Count, Q, Avg
from siren_web.models import Terminals, GridLines, facilities, FacilityGridConnections


def validate_terminal_gridline_connection(terminal, gridline, connection_type):
    """
    Validate if a grid line can be connected to a terminal
    
    Args:
        terminal: Terminal instance
        gridline: GridLine instance
        connection_type: 'from' or 'to'
    
    Returns:
        tuple: (is_valid, error_message)
    """
    # Check if grid line is already connected
    if connection_type == 'from' and gridline.from_terminal:
        return False, f"Grid line already has a from-terminal: {gridline.from_terminal.terminal_name}"
    
    if connection_type == 'to' and gridline.to_terminal:
        return False, f"Grid line already has a to-terminal: {gridline.to_terminal.terminal_name}"
    
    # Check voltage compatibility (within 20% tolerance)
    voltage_tolerance = 0.20
    voltage_diff = abs(terminal.primary_voltage_kv - gridline.voltage_level)
    voltage_ratio = voltage_diff / terminal.primary_voltage_kv
    
    if voltage_ratio > voltage_tolerance:
        return False, f"Voltage mismatch: Terminal {terminal.primary_voltage_kv}kV vs Grid Line {gridline.voltage_level}kV"
    
    # Check if connection would create a loop back to same terminal
    if connection_type == 'from':
        if gridline.to_terminal == terminal:
            return False, "Cannot connect: Would create a direct loop to the same terminal"
    elif connection_type == 'to':
        if gridline.from_terminal == terminal:
            return False, "Cannot connect: Would create a direct loop to the same terminal"
    
    return True, "Connection is valid"


def get_terminal_statistics(terminal):
    """
    Get comprehensive statistics for a terminal
    
    Returns:
        dict: Statistics including capacity, utilization, connections
    """
    # Grid line statistics
    outgoing_lines = terminal.get_outgoing_lines()
    incoming_lines = terminal.get_incoming_lines()
    
    total_line_capacity_out = sum(line.thermal_capacity_mw for line in outgoing_lines)
    total_line_capacity_in = sum(line.thermal_capacity_mw for line in incoming_lines)
    
    # Facility statistics
    connected_facilities = []
    for line in terminal.get_connected_grid_lines():
        connections = FacilityGridConnections.objects.filter(
            idgridlines=line,
            active=True
        ).select_related('idfacilities')
        connected_facilities.extend([conn.idfacilities for conn in connections])
    
    total_facility_capacity = sum(f.capacity for f in connected_facilities if f.capacity)
    
    # Calculate utilization
    utilization = 0
    if terminal.transformer_capacity_mva:
        # Convert MW to MVA (assuming 0.95 power factor)
        connected_mva = total_facility_capacity / 0.95
        utilization = (connected_mva / terminal.transformer_capacity_mva) * 100
    
    # Technology breakdown
    tech_breakdown = {}
    for facility in connected_facilities:
        if facility.idtechnologies:
            tech_name = facility.idtechnologies.technology_name
            if tech_name not in tech_breakdown:
                tech_breakdown[tech_name] = {'count': 0, 'capacity': 0}
            tech_breakdown[tech_name]['count'] += 1
            tech_breakdown[tech_name]['capacity'] += facility.capacity or 0
    
    return {
        'terminal_name': terminal.terminal_name,
        'terminal_voltage': terminal.primary_voltage_kv,
        'outgoing_lines_count': outgoing_lines.count(),
        'incoming_lines_count': incoming_lines.count(),
        'total_lines': outgoing_lines.count() + incoming_lines.count(),
        'total_line_capacity_out': total_line_capacity_out,
        'total_line_capacity_in': total_line_capacity_in,
        'connected_facilities_count': len(connected_facilities),
        'total_facility_capacity': total_facility_capacity,
        'utilization_percent': utilization,
        'transformer_capacity': terminal.transformer_capacity_mva,
        'technology_breakdown': tech_breakdown,
    }


def find_path_between_terminals(start_terminal, end_terminal, max_hops=5):
    """
    Find a path between two terminals through grid lines
    
    Args:
        start_terminal: Starting Terminal instance
        end_terminal: Target Terminal instance
        max_hops: Maximum number of grid lines to traverse
    
    Returns:
        list: Path of grid lines, or empty list if no path found
    """
    visited = set()
    queue = [(start_terminal, [])]
    
    while queue:
        current_terminal, path = queue.pop(0)
        
        if current_terminal == end_terminal:
            return path
        
        if len(path) >= max_hops:
            continue
        
        if current_terminal.pk in visited:
            continue
        
        visited.add(current_terminal.pk)
        
        # Check outgoing lines
        for line in current_terminal.get_outgoing_lines():
            if line.to_terminal and line.to_terminal.pk not in visited:
                queue.append((line.to_terminal, path + [line]))
        
        # Check incoming lines (reverse direction)
        for line in current_terminal.get_incoming_lines():
            if line.from_terminal and line.from_terminal.pk not in visited:
                queue.append((line.from_terminal, path + [line]))
    
    return []  # No path found


def calculate_terminal_losses(terminal):
    """
    Calculate total losses through a terminal's connections
    
    Returns:
        dict: Loss breakdown by grid line
    """
    losses = {
        'total_losses_mw': 0,
        'line_losses': [],
        'connection_losses': [],
    }
    
    for line in terminal.get_connected_grid_lines():
        # Get facilities on this line
        connections = FacilityGridConnections.objects.filter(
            idgridlines=line,
            active=True
        ).select_related('idfacilities')
        
        line_capacity = sum(
            conn.idfacilities.capacity for conn in connections 
            if conn.idfacilities.capacity
        )
        
        if line_capacity > 0:
            # Calculate line losses
            line_loss = line.calculate_line_losses_mw(line_capacity)
            losses['line_losses'].append({
                'line_name': line.line_name,
                'capacity_mw': line_capacity,
                'loss_mw': line_loss,
                'loss_percent': (line_loss / line_capacity * 100) if line_capacity else 0,
            })
            
            # Calculate connection losses for each facility
            for conn in connections:
                if conn.idfacilities.capacity:
                    conn_loss = conn.calculate_connection_losses_mw(conn.idfacilities.capacity)
                    losses['connection_losses'].append({
                        'facility_name': conn.idfacilities.facility_name,
                        'capacity_mw': conn.idfacilities.capacity,
                        'loss_mw': conn_loss,
                    })
            
            losses['total_losses_mw'] += line_loss
    
    return losses


def get_terminal_load_profile(terminal):
    """
    Get load profile for a terminal based on connected facilities
    
    Returns:
        dict: Load breakdown by direction and technology
    """
    load_profile = {
        'generation': {'total': 0, 'by_tech': {}},
        'consumption': {'total': 0, 'by_tech': {}},
        'net': 0,
    }
    
    # Iterate through connected facilities
    for line in terminal.get_connected_grid_lines():
        connections = FacilityGridConnections.objects.filter(
            idgridlines=line,
            active=True
        ).select_related('idfacilities', 'idfacilities__idtechnologies')
        
        for conn in connections:
            facility = conn.idfacilities
            if not facility.capacity:
                continue
            
            tech_name = facility.idtechnologies.technology_name if facility.idtechnologies else 'Unknown'
            
            # Determine if generation or consumption
            # This is simplified - adjust based on your business logic
            generation_techs = ['Wind', 'Solar', 'Hydro', 'Gas', 'Coal', 'Nuclear', 'Biomass']
            is_generation = any(gen_tech.lower() in tech_name.lower() for gen_tech in generation_techs)
            
            if is_generation:
                load_profile['generation']['total'] += facility.capacity
                if tech_name not in load_profile['generation']['by_tech']:
                    load_profile['generation']['by_tech'][tech_name] = 0
                load_profile['generation']['by_tech'][tech_name] += facility.capacity
            else:
                load_profile['consumption']['total'] += facility.capacity
                if tech_name not in load_profile['consumption']['by_tech']:
                    load_profile['consumption']['by_tech'][tech_name] = 0
                load_profile['consumption']['by_tech'][tech_name] += facility.capacity
    
    load_profile['net'] = load_profile['generation']['total'] - load_profile['consumption']['total']
    
    return load_profile


def get_system_wide_terminal_statistics():
    """
    Get statistics for all terminals in the system
    
    Returns:
        dict: System-wide statistics
    """
    terminals = Terminals.objects.filter(active=True)
    
    # Aggregate statistics
    stats = {
        'total_terminals': terminals.count(),
        'total_transformer_capacity_mva': terminals.aggregate(
            Sum('transformer_capacity_mva')
        )['transformer_capacity_mva__sum'] or 0,
        'average_voltage_kv': terminals.aggregate(
            Avg('primary_voltage_kv')
        )['primary_voltage_kv__avg'] or 0,
        'terminals_with_connections': 0,
        'terminals_without_connections': 0,
    }

def suggest_terminal_connections(terminal, max_distance_km=50):
    """
    Suggest potential grid line connections based on proximity and voltage
    
    Args:
        terminal: Terminal instance
        max_distance_km: Maximum distance to consider
    
    Returns:
        list: Suggested grid lines with scores
    """
    if not terminal.latitude or not terminal.longitude:
        return []
    
    from math import radians, sin, cos, sqrt, atan2
    
    def calculate_distance(lat1, lon1, lat2, lon2):
        """Calculate distance between two points using Haversine formula"""
        R = 6371  # Earth's radius in km
        
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c
    
    suggestions = []
    
    # Get all active grid lines not connected to this terminal
    available_lines = GridLines.objects.filter(active=True).exclude(
        Q(from_terminal=terminal) | Q(to_terminal=terminal)
    )
    
    for line in available_lines:
        # Calculate distance to line endpoints
        distances = []
        
        if line.from_latitude and line.from_longitude:
            dist_from = calculate_distance(
                terminal.latitude, terminal.longitude,
                line.from_latitude, line.from_longitude
            )
            distances.append(('from', dist_from))
        
        if line.to_latitude and line.to_longitude:
            dist_to = calculate_distance(
                terminal.latitude, terminal.longitude,
                line.to_latitude, line.to_longitude
            )
            distances.append(('to', dist_to))
        
        if not distances:
            continue
        
        # Get closest endpoint
        connection_type, distance = min(distances, key=lambda x: x[1])
        
        if distance > max_distance_km:
            continue
        
        # Calculate voltage compatibility score (0-100)
        voltage_diff = abs(terminal.primary_voltage_kv - line.voltage_level)
        voltage_ratio = voltage_diff / terminal.primary_voltage_kv
        voltage_score = max(0, 100 - (voltage_ratio * 200))  # Penalize >50% difference heavily
        
        # Calculate distance score (0-100)
        distance_score = max(0, 100 - (distance / max_distance_km * 100))
        
        # Calculate capacity score
        capacity_score = min(100, line.thermal_capacity_mw / 10)  # Scale to 100
        
        # Overall score (weighted average)
        overall_score = (voltage_score * 0.5 + distance_score * 0.3 + capacity_score * 0.2)
        
        suggestions.append({
            'grid_line': line,
            'connection_type': connection_type,
            'distance_km': round(distance, 2),
            'voltage_compatibility': round(voltage_score, 1),
            'distance_score': round(distance_score, 1),
            'capacity_score': round(capacity_score, 1),
            'overall_score': round(overall_score, 1),
        })
    
    # Sort by overall score
    suggestions.sort(key=lambda x: x['overall_score'], reverse=True)
    
    return suggestions[:10]  # Return top 10 suggestions


def bulk_disconnect_terminal(terminal):
    """
    Disconnect all grid lines from a terminal
    
    Returns:
        dict: Summary of disconnections
    """
    result = {
        'outgoing_disconnected': 0,
        'incoming_disconnected': 0,
        'total_disconnected': 0,
    }
    
    # Disconnect outgoing lines
    outgoing = GridLines.objects.filter(from_terminal=terminal)
    result['outgoing_disconnected'] = outgoing.count()
    outgoing.update(from_terminal=None)
    
    # Disconnect incoming lines
    incoming = GridLines.objects.filter(to_terminal=terminal)
    result['incoming_disconnected'] = incoming.count()
    incoming.update(to_terminal=None)
    
    result['total_disconnected'] = result['outgoing_disconnected'] + result['incoming_disconnected']
    
    return result


def export_terminal_topology_json(terminal):
    """
    Export terminal topology as JSON for network visualization
    
    Returns:
        dict: JSON-serializable topology data
    """
    import json
    
    topology = {
        'terminal': {
            'id': terminal.pk,
            'name': terminal.terminal_name,
            'voltage': terminal.primary_voltage_kv,
            'type': terminal.terminal_type,
            'latitude': terminal.latitude,
            'longitude': terminal.longitude,
        },
        'grid_lines': [],
        'facilities': [],
        'connections': [],
    }
    
    # Add grid lines
    for line in terminal.get_connected_grid_lines():
        direction = 'outgoing' if line.from_terminal == terminal else 'incoming'
        
        topology['grid_lines'].append({
            'id': line.pk,
            'name': line.line_name,
            'voltage': line.voltage_level,
            'capacity': line.thermal_capacity_mw,
            'length': line.length_km,
            'direction': direction,
        })
        
        # Add facilities on this line
        for conn in FacilityGridConnections.objects.filter(idgridlines=line, active=True):
            facility = conn.idfacilities
            
            facility_data = {
                'id': facility.pk,
                'name': facility.facility_name,
                'capacity': facility.capacity,
                'technology': facility.idtechnologies.technology_name if facility.idtechnologies else None,
                'latitude': facility.latitude,
                'longitude': facility.longitude,
            }
            
            if facility_data not in topology['facilities']:
                topology['facilities'].append(facility_data)
            
            topology['connections'].append({
                'from': f'gridline_{line.pk}',
                'to': f'facility_{facility.pk}',
                'is_primary': conn.is_primary,
            })
    
    return topology