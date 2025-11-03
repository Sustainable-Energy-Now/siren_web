from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from siren_web.models import GridLines
import json
from siren_web.models import Terminals

@login_required
@csrf_exempt
def add_terminal(request):
    """Add a new terminal to the system"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Extract data from the request
            terminal_name = data.get('terminal_name')
            terminal_code = data.get('terminal_code')
            terminal_type = data.get('terminal_type', 'substation')
            latitude = data.get('latitude')
            longitude = data.get('longitude')
            primary_voltage_kv = data.get('primary_voltage_kv')
            secondary_voltage_kv = data.get('secondary_voltage_kv')
            transformer_capacity_mva = data.get('transformer_capacity_mva')
            bay_count = data.get('bay_count')
            owner = data.get('owner', '')
            description = data.get('description', '')
            
            # Validate required fields
            if not all([terminal_name, terminal_code, latitude, longitude, primary_voltage_kv]):
                return JsonResponse({'status': 'error', 'message': 'Missing required fields'}, status=400)
            
            # Check for duplicate names/codes
            if Terminals.objects.filter(terminal_name=terminal_name).exists():
                return JsonResponse({'status': 'error', 'message': 'Terminal name already exists'}, status=400)
            
            if Terminals.objects.filter(terminal_code=terminal_code).exists():
                return JsonResponse({'status': 'error', 'message': 'Terminal code already exists'}, status=400)
            
            # Determine voltage class
            voltage_class = 'low'
            voltage_kv = float(primary_voltage_kv)
            if voltage_kv >= 800:
                voltage_class = 'ultra_high'
            elif voltage_kv >= 138:
                voltage_class = 'extra_high'
            elif voltage_kv >= 35:
                voltage_class = 'high'
            elif voltage_kv >= 1:
                voltage_class = 'medium'
            
            # Create new terminal
            new_terminal = Terminals.objects.create(
                terminal_name=terminal_name,
                terminal_code=terminal_code,
                terminal_type=terminal_type,
                latitude=float(latitude),
                longitude=float(longitude),
                primary_voltage_kv=float(primary_voltage_kv),
                secondary_voltage_kv=float(secondary_voltage_kv) if secondary_voltage_kv else None,
                voltage_class=voltage_class,
                transformer_capacity_mva=float(transformer_capacity_mva) if transformer_capacity_mva else None,
                bay_count=int(bay_count) if bay_count else None,
                owner=owner,
                description=description,
                active=True
            )
            
            return JsonResponse({
                'status': 'success',
                'message': f'Terminal "{terminal_name}" added successfully',
                'terminal_id': new_terminal.idterminals,
                'terminal_name': new_terminal.terminal_name,
                'terminal_code': new_terminal.terminal_code,
                'terminal_type': new_terminal.terminal_type,
                'primary_voltage_kv': new_terminal.primary_voltage_kv
            })
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

@login_required
def get_terminal_details(request, terminal_id):
    """Get detailed information about a specific terminal"""
    try:
        terminal = Terminals.objects.get(pk=terminal_id)
        
        # Get connected grid lines
        connected_lines = []
        for line in terminal.get_connected_grid_lines():
            line_data = {
                'line_id': line.idgridlines,
                'line_name': line.line_name,
                'line_code': line.line_code,
                'voltage_level': line.voltage_level,
                'thermal_capacity_mw': line.thermal_capacity_mw,
                'length_km': line.length_km,
                'connection_type': 'from' if line.from_terminal == terminal else 'to',
                'other_terminal': line.to_terminal.terminal_name if line.from_terminal == terminal and line.to_terminal else 
                               line.from_terminal.terminal_name if line.to_terminal == terminal and line.from_terminal else 'None',
                'connected_facilities_count': line.connected_facilities.count()
            }
            connected_lines.append(line_data)
        
        # Get facilities indirectly connected through grid lines
        connected_facilities = []
        for line in terminal.get_connected_grid_lines():
            for connection in line.facilitygridconnections_set.filter(active=True):
                facility = connection.idfacilities
                facility_data = {
                    'facility_name': facility.facility_name,
                    'technology': facility.idtechnologies.technology_name,
                    'capacity': facility.capacity,
                    'via_line': line.line_name,
                    'connection_distance': connection.connection_distance_km
                }
                connected_facilities.append(facility_data)
        
        terminal_data = {
            'idterminals': terminal.idterminals,
            'terminal_name': terminal.terminal_name,
            'terminal_code': terminal.terminal_code,
            'terminal_type': terminal.terminal_type,
            'terminal_type_display': terminal.get_terminal_type_display(),
            'latitude': terminal.latitude,
            'longitude': terminal.longitude,
            'elevation': terminal.elevation,
            'primary_voltage_kv': terminal.primary_voltage_kv,
            'secondary_voltage_kv': terminal.secondary_voltage_kv,
            'voltage_class': terminal.voltage_class,
            'voltage_class_display': terminal.get_voltage_class_display(),
            'transformer_capacity_mva': terminal.transformer_capacity_mva,
            'short_circuit_capacity_mva': terminal.short_circuit_capacity_mva,
            'bay_count': terminal.bay_count,
            'commissioned_date': terminal.commissioned_date.isoformat() if terminal.commissioned_date else None,
            'active': terminal.active,
            'owner': terminal.owner,
            'operator': terminal.operator,
            'maintenance_zone': terminal.maintenance_zone,
            'control_center': terminal.control_center,
            'scada_id': terminal.scada_id,
            'description': terminal.description,
            'connected_lines': connected_lines,
            'connected_facilities': connected_facilities,
            'utilization_percent': terminal.get_utilization_percent(),
            'total_connected_capacity': terminal.calculate_total_connected_capacity()
        }
        
        return JsonResponse(terminal_data)
        
    except Terminals.DoesNotExist:
        return JsonResponse({'error': 'Terminal not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_terminals(request):
    """Return all active terminals for dropdown selection"""
    terminals = Terminals.objects.filter(active=True).values(
        'idterminals', 'terminal_name', 'terminal_code', 'terminal_type', 
        'primary_voltage_kv', 'latitude', 'longitude'
    ).order_by('terminal_name')
    
    # Add additional computed fields
    enhanced_terminals = []
    for terminal_data in terminals:
        terminal = Terminals.objects.get(idterminals=terminal_data['idterminals'])
        terminal_data.update({
            'connected_lines_count': terminal.get_connected_grid_lines().count(),
            'utilization_percent': round(terminal.get_utilization_percent(), 1)
        })
        enhanced_terminals.append(terminal_data)
    
    return JsonResponse(enhanced_terminals, safe=False)

@login_required  
def find_nearest_terminals(request):
    """Find nearest terminals to a given location"""
    lat = float(request.GET.get('lat', 0))
    lon = float(request.GET.get('lon', 0))
    max_distance = float(request.GET.get('max_distance', 100))
    
    if not lat or not lon:
        return JsonResponse({'error': 'Latitude and longitude required'}, status=400)
    
    nearby_terminals = []
    
    for terminal in Terminals.objects.filter(active=True):
        distance = calculate_distance_km(lat, lon, terminal.latitude, terminal.longitude)
        
        if distance <= max_distance:
            utilization = terminal.get_utilization_percent()
            connected_lines = terminal.get_connected_grid_lines().count()
            
            nearby_terminals.append({
                'idterminals': terminal.idterminals,
                'terminal_name': terminal.terminal_name,
                'terminal_code': terminal.terminal_code,
                'terminal_type': terminal.terminal_type,
                'primary_voltage_kv': terminal.primary_voltage_kv,
                'secondary_voltage_kv': terminal.secondary_voltage_kv,
                'transformer_capacity_mva': terminal.transformer_capacity_mva,
                'distance_km': round(distance, 2),
                'utilization_percent': round(utilization, 1),
                'connected_lines_count': connected_lines,
                'latitude': terminal.latitude,
                'longitude': terminal.longitude,
                'suitability_score': max(0, 100 - (distance * 1.5) - (utilization * 0.5))
            })
    
    # Sort by suitability score (combination of distance and utilization)
    nearby_terminals.sort(key=lambda x: x['suitability_score'], reverse=True)
    
    return JsonResponse(nearby_terminals, safe=False)

# Enhanced create_grid_line function to handle terminal connections
@login_required
@csrf_exempt
def create_grid_line_with_terminals(request):
    """Create a new grid line with terminal connections"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['line_name', 'line_code', 'voltage_level', 'thermal_capacity_mw']
            
            for field in required_fields:
                if not data.get(field):
                    return JsonResponse({'status': 'error', 'message': f'Missing required field: {field}'}, status=400)
            
            # Get terminal connections if provided
            from_terminal_id = data.get('from_terminal_id')
            to_terminal_id = data.get('to_terminal_id')
            
            from_terminal = None
            to_terminal = None
            
            if from_terminal_id:
                try:
                    from_terminal = Terminals.objects.get(pk=from_terminal_id)
                except Terminals.DoesNotExist:
                    return JsonResponse({'status': 'error', 'message': 'From terminal not found'}, status=400)
            
            if to_terminal_id:
                try:
                    to_terminal = Terminals.objects.get(pk=to_terminal_id)
                except Terminals.DoesNotExist:
                    return JsonResponse({'status': 'error', 'message': 'To terminal not found'}, status=400)
            
            # Determine coordinates - use terminal locations if available, otherwise use provided coordinates
            if from_terminal:
                from_lat, from_lng = from_terminal.latitude, from_terminal.longitude
            else:
                from_lat = float(data.get('from_latitude', 0))
                from_lng = float(data.get('from_longitude', 0))
            
            if to_terminal:
                to_lat, to_lng = to_terminal.latitude, to_terminal.longitude
            else:
                to_lat = float(data.get('to_latitude', 0))
                to_lng = float(data.get('to_longitude', 0))
            
            # Calculate line length
            length_km = calculate_distance_km(from_lat, from_lng, to_lat, to_lng)
            
            # Create new grid line
            grid_line = GridLines.objects.create(
                line_name=data['line_name'],
                line_code=data['line_code'],
                line_type=data.get('line_type', 'transmission'),
                voltage_level=float(data['voltage_level']),
                length_km=length_km,
                resistance_per_km=float(data.get('resistance_per_km', 0.1)),
                reactance_per_km=float(data.get('reactance_per_km', 0.4)),
                thermal_capacity_mw=float(data['thermal_capacity_mw']),
                emergency_capacity_mw=data.get('emergency_capacity_mw'),
                from_latitude=from_lat,
                from_longitude=from_lng,
                to_latitude=to_lat,
                to_longitude=to_lng,
                from_terminal=from_terminal,
                to_terminal=to_terminal,
                owner=data.get('owner', ''),
                commissioned_date=data.get('commissioned_date')
            )
            
            response_data = {
                'status': 'success',
                'message': 'Grid line created successfully',
                'grid_line': {
                    'idgridlines': grid_line.idgridlines,
                    'line_name': grid_line.line_name,
                    'line_code': grid_line.line_code,
                    'voltage_level': grid_line.voltage_level,
                    'length_km': round(grid_line.length_km, 2),
                    'from_terminal': from_terminal.terminal_name if from_terminal else None,
                    'to_terminal': to_terminal.terminal_name if to_terminal else None
                }
            }
            
            return JsonResponse(response_data)
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)