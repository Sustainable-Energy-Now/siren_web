from django.contrib.auth.decorators import login_required
from common.decorators import settings_required
from django.db.models import Max, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from siren_web.forms import DemandScenarioSettings
from siren_web.database_operations import fetch_module_settings_data, fetch_scenario_settings_data
from siren_web.models import facilities, Technologies, Terminals, Scenarios, GridLines, FacilityGridConnections
import json
import math

def calculate_distance_km(lat1, lon1, lat2, lon2):
    """Calculate distance between two points using Haversine formula"""
    R = 6371  # Earth's radius in kilometers
    
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c

def find_nearest_grid_line_point(facility_lat, facility_lon, grid_line):
    """Find the nearest point on a grid line to a facility location"""
    line_coords = grid_line.get_line_coordinates()
    
    if len(line_coords) < 2:
        # Fallback to endpoints
        coords = [[grid_line.from_latitude, grid_line.from_longitude],
                 [grid_line.to_latitude, grid_line.to_longitude]]
    else:
        coords = line_coords
    
    min_distance = float('inf')
    closest_point = None
    
    # Check distance to each point on the line
    for coord in coords:
        distance = calculate_distance_km(facility_lat, facility_lon, coord[0], coord[1])
        if distance < min_distance:
            min_distance = distance
            closest_point = coord
    
    # Also check distances to line segments (simplified)
    for i in range(len(coords) - 1):
        # Calculate distance to line segment (simplified to midpoint)
        mid_lat = (coords[i][0] + coords[i+1][0]) / 2
        mid_lon = (coords[i][1] + coords[i+1][1]) / 2
        distance = calculate_distance_km(facility_lat, facility_lon, mid_lat, mid_lon)
        if distance < min_distance:
            min_distance = distance
            closest_point = [mid_lat, mid_lon]
    
    return min_distance, closest_point

def find_nearest_grid_line(facility_lat, facility_lon, max_distance_km=50):
    """Find the nearest grid line to a facility location"""
    nearest_line = None
    min_distance = float('inf')
    connection_point = None
    
    for grid_line in GridLines.objects.filter(active=True):
        distance, point = find_nearest_grid_line_point(facility_lat, facility_lon, grid_line)
        
        if distance < min_distance and distance <= max_distance_km:
            min_distance = distance
            nearest_line = grid_line
            connection_point = point
    
    return nearest_line, min_distance, connection_point

@login_required
@settings_required(redirect_view='powermapui:powermapui_home')
def home(request):
    # Get weather_year and scenario from session or default to empty string
    weather_year = request.session.get('weather_year', '')
    demand_year = request.session.get('demand_year', '')
    scenario = request.session.get('scenario', '')
    config_file = request.session.get('config_file')
    success_message = ''
    if request.method == 'POST':
        # Handle form submission
        demand_weather_scenario = DemandScenarioSettings(request.POST)
        if demand_weather_scenario.is_valid():
            demand_year = demand_weather_scenario.cleaned_data['demand_year']
            request.session['demand_year'] = demand_year
            
            scenario = demand_weather_scenario.cleaned_data['scenario']
            request.session['scenario'] = scenario
            
            success_message = "Settings updated."
    
    # Create form instance with current session values
    demand_weather_scenario = DemandScenarioSettings(initial={
        'demand_year': demand_year,
        'scenario': scenario
    })
    
    scenario_settings = {}
    scenario_settings = fetch_module_settings_data('Power')
    if not scenario_settings:
        scenario_settings = fetch_scenario_settings_data(scenario)
    
    # Query facilities for the selected scenario with latitude and longitude available
    if scenario:
        # Filter facilities that belong to the selected scenario and have coordinates
        scenario_obj = Scenarios.objects.get(title=scenario)
        facilities_queryset = facilities.objects.filter(
            scenarios=scenario_obj,
            latitude__isnull=False, 
            longitude__isnull=False
        ).select_related('idtechnologies', 'primary_grid_line').prefetch_related('grid_connections')
        
        facilities_data = []
        for facility in facilities_queryset:
            retirement_year = None
            if facility.commissioning_date and facility.idtechnologies and facility.idtechnologies.lifetime:
                retirement_year = facility.commissioning_date.year + int(facility.idtechnologies.lifetime)
            facility_dict = {
                'facility_name': facility.facility_name,
                'idtechnologies': facility.idtechnologies.idtechnologies,
                'latitude': facility.latitude,
                'longitude': facility.longitude,
                'idfacilities': facility.idfacilities,
                'capacity': float(facility.capacity) if facility.capacity else 0,
                'technology_name': facility.idtechnologies.technology_name,
                'has_grid_connection': facility.grid_connections.exists(),
                'primary_grid_line_id': facility.primary_grid_line.idgridlines if facility.primary_grid_line else None,
                'primary_grid_line_name': facility.primary_grid_line.line_name if facility.primary_grid_line else None,
                'connection_count': facility.grid_connections.count(),
                'status': facility.status if facility.status else 'commissioned',
                'commissioning_probability': float(facility.commissioning_probability) if facility.commissioning_probability is not None else 1.0,
                'commissioning_date': facility.commissioning_date.isoformat() if facility.commissioning_date else None,
                'decommissioning_date': facility.decommissioning_date.isoformat() if facility.decommissioning_date else None,
                'technology_category': facility.idtechnologies.category if facility.idtechnologies and facility.idtechnologies.category else 'Unknown',
                'retirement_year': retirement_year,
            }
            facilities_data.append(facility_dict)
    else:
        facilities_data = []

    # Compute year range and categories for filter controls
    categories = set()
    year_min = None
    year_max = None
    for fd in facilities_data:
        categories.add(fd['technology_category'])
        if fd['commissioning_date']:
            cy = int(fd['commissioning_date'][:4])
            if year_min is None or cy < year_min:
                year_min = cy
            if year_max is None or cy > year_max:
                year_max = cy
        if fd['retirement_year']:
            ry = fd['retirement_year']
            if year_max is None or ry > year_max:
                year_max = ry
    from datetime import date
    last_year = date.today().year - 1
    year_min = last_year
    if year_max is None or year_max < last_year:
        year_max = 2040
    else:
        year_max = min(year_max, 2040)
    
    # Convert to JSON
    facilities_json = json.dumps(facilities_data)
    
    # Get grid lines data with enhanced information
    grid_lines_data = []
    for grid_line in GridLines.objects.filter(active=True).prefetch_related('connected_facilities'):
        grid_line_data = {
            'idgridlines': grid_line.idgridlines,
            'line_name': grid_line.line_name,
            'line_code': grid_line.line_code,
            'line_type': grid_line.line_type,
            'voltage_level': grid_line.voltage_level,
            'thermal_capacity_mw': grid_line.thermal_capacity_mw,
            'length_km': grid_line.length_km,
            'owner': grid_line.owner,
            'active': grid_line.active,
            'coordinates': grid_line.get_line_coordinates(),
            'style': grid_line.get_line_style(),
            'popup_content': grid_line.get_popup_content(),
            'from_latitude': grid_line.from_latitude,
            'from_longitude': grid_line.from_longitude,
            'to_latitude': grid_line.to_latitude,
            'to_longitude': grid_line.to_longitude,
            'connected_facilities_count': grid_line.connected_facilities.count(),
            'total_connected_capacity': sum(f.capacity or 0 for f in grid_line.connected_facilities.all())
        }
        grid_lines_data.append(grid_line_data)
        
    grid_lines_json = json.dumps(grid_lines_data)
    # Get terminals data
    terminals_data = []
    for terminal in Terminals.objects.filter(active=True).prefetch_related('outgoing_lines', 'incoming_lines'):
        connected_lines = terminal.get_connected_grid_lines()
        terminal_data = {
            'idterminals': terminal.idterminals,
            'terminal_name': terminal.terminal_name,
            'terminal_code': terminal.terminal_code,
            'terminal_type': terminal.terminal_type,
            'primary_voltage_kv': terminal.primary_voltage_kv,
            'secondary_voltage_kv': terminal.secondary_voltage_kv,
            'transformer_capacity_mva': terminal.transformer_capacity_mva,
            'latitude': terminal.latitude,
            'longitude': terminal.longitude,
            'active': terminal.active,
            'owner': terminal.owner,
            'connected_lines_count': connected_lines.count(),
            'connected_facilities_count': terminal.get_connected_facilities_count(),
            'total_connected_capacity': terminal.calculate_total_connected_capacity(),
            'utilization_percent': terminal.get_utilization_percent(),
            'popup_content': terminal.get_popup_content(),
            'icon_type': terminal.get_terminal_icon_type()
        }
        terminals_data.append(terminal_data)
    
    terminals_json = json.dumps(terminals_data)
    context = {
        'demand_weather_scenario': demand_weather_scenario,
        'weather_year': weather_year,
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
        'success_message': success_message,
        'facilities_json': facilities_json,
        'grid_lines_json': grid_lines_json,
        'terminals_json': terminals_json,
        'categories_json': json.dumps(sorted(categories)),
        'year_min': year_min,
        'year_max': year_max,
    }
    return render(request, 'map_home.html', context)

@login_required
@settings_required(redirect_view='powermapui:powermapui_home') 
def add_facility(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Extract data from the request
            facility_name = data.get('facility_name')
            technology_id = data.get('technology_id')
            latitude = data.get('latitude')
            longitude = data.get('longitude')
            capacity = data.get('capacity', 0)
            
            # Grid connection data
            grid_line_id = data.get('grid_line_id')
            create_new_grid_line = data.get('create_new_grid_line', False)
            new_grid_line_data = data.get('new_grid_line_data', {})
            
            # Validate required fields
            if not all([facility_name, technology_id, latitude, longitude]):
                return JsonResponse({'status': 'error', 'message': 'Missing required fields'}, status=400)
            
            # Get the technology object
            try:
                technology = Technologies.objects.get(pk=technology_id)
            except Technologies.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Invalid technology ID'}, status=400)
            
            # Get the current scenario from session
            scenario_title = request.session.get('scenario')
            if not scenario_title:
                return JsonResponse({'status': 'error', 'message': 'No scenario selected. Please select a scenario first.'}, status=400)
            
            try:
                scenario_obj = Scenarios.objects.get(title=scenario_title)
            except Scenarios.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Selected scenario not found'}, status=400)
            
            # Create facility code
            tech_prefix = technology.technology_name[:3].upper() if technology.technology_name else "FAC"
            facility_code = f"{tech_prefix}_{facility_name.replace(' ', '_').lower()}"[:30]
                        
            # Handle grid line connection
            grid_line = None
            connection_distance = 0
            connection_point = None
            
            if create_new_grid_line and new_grid_line_data:
                # Create new grid line
                try:
                    grid_line = GridLines.objects.create(
                        line_name=new_grid_line_data.get('line_name'),
                        line_code=new_grid_line_data.get('line_code'),
                        line_type=new_grid_line_data.get('line_type', 'transmission'),
                        voltage_level=float(new_grid_line_data.get('voltage_level', 132)),
                        length_km=float(new_grid_line_data.get('length_km', 10)),
                        resistance_per_km=float(new_grid_line_data.get('resistance_per_km', 0.1)),
                        reactance_per_km=float(new_grid_line_data.get('reactance_per_km', 0.4)),
                        thermal_capacity_mw=float(new_grid_line_data.get('thermal_capacity_mw', 100)),
                        from_latitude=float(new_grid_line_data.get('from_latitude', latitude)),
                        from_longitude=float(new_grid_line_data.get('from_longitude', longitude)),
                        to_latitude=float(new_grid_line_data.get('to_latitude', latitude)),
                        to_longitude=float(new_grid_line_data.get('to_longitude', longitude)),
                    )
                    connection_distance = 0  # Direct connection to new line
                    connection_point = [latitude, longitude]
                except Exception as e:
                    return JsonResponse({'status': 'error', 'message': f'Error creating grid line: {str(e)}'}, status=400)
            
            elif grid_line_id:
                # Use existing grid line
                try:
                    # Calculate connection distance
                    grid_line = GridLines.objects.get(pk=grid_line_id)
                    connection_distance, connection_point = find_nearest_grid_line_point(latitude, longitude, grid_line)
                except GridLines.DoesNotExist:
                    return JsonResponse({'status': 'error', 'message': 'Selected grid line not found'}, status=400)
            
            else:
                # Auto-find nearest grid line
                grid_line, connection_distance, connection_point = find_nearest_grid_line(latitude, longitude)
                if not grid_line:
                    return JsonResponse({'status': 'error', 'message': 'No suitable grid line found within 50km. Please create a new grid line or select an existing one.'}, status=400)
            
            # Create new facility
            new_facility = facilities(
                facility_name=facility_name,
                facility_code=facility_code,
                active=True,
                idtechnologies=technology,
                capacity=float(capacity) if capacity else 0.0,
                latitude=latitude,
                longitude=longitude,
                existing=False,
                primary_grid_line=grid_line
            )
            
            new_facility.save()
            
            # Add facility to scenario
            new_facility.scenarios.add(scenario_obj)
            
            # Create grid connection
            if grid_line and connection_point:
                # Determine appropriate connection voltage
                connection_voltage = min(grid_line.voltage_level, 132)  # Cap at 132kV for facility connections
                if grid_line.voltage_level < 66:
                    connection_voltage = grid_line.voltage_level
                
                FacilityGridConnections.objects.create(
                    idfacilities=new_facility,
                    idgridlines=grid_line,
                    connection_type='direct',
                    connection_point_latitude=connection_point[0],
                    connection_point_longitude=connection_point[1],
                    connection_voltage_kv=connection_voltage,
                    connection_capacity_mw=float(capacity) if capacity else 0.0,
                    connection_distance_km=connection_distance,
                    is_primary=True,
                    active=True
                )
            
            response_data = {
                'status': 'success',
                'message': f'{technology.technology_name} facility added successfully to scenario "{scenario_title}"',
                'facility_id': new_facility.idfacilities,
                'facility_name': new_facility.facility_name,
                'technology': technology.technology_name,
                'scenario': scenario_title
            }
            
            if grid_line:
                response_data['grid_connection'] = {
                    'grid_line_name': grid_line.line_name,
                    'grid_line_id': grid_line.idgridlines,
                    'connection_distance_km': round(connection_distance, 2),
                    'voltage_level': grid_line.voltage_level,
                    'connection_voltage_kv': connection_voltage if 'connection_voltage' in locals() else grid_line.voltage_level
                }
            
            return JsonResponse(response_data)
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

@login_required
@settings_required(redirect_view='powermapui:powermapui_home')
def create_grid_line(request):
    """Create a new grid line"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['line_name', 'line_code', 'voltage_level', 'thermal_capacity_mw',
                             'from_latitude', 'from_longitude', 'to_latitude', 'to_longitude']
            
            for field in required_fields:
                if not data.get(field):
                    return JsonResponse({'status': 'error', 'message': f'Missing required field: {field}'}, status=400)
            
            # Calculate line length
            length_km = calculate_distance_km(
                float(data['from_latitude']), float(data['from_longitude']),
                float(data['to_latitude']), float(data['to_longitude'])
            )
            
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
                from_latitude=float(data['from_latitude']),
                from_longitude=float(data['from_longitude']),
                to_latitude=float(data['to_latitude']),
                to_longitude=float(data['to_longitude']),
                owner=data.get('owner', ''),
                commissioned_date=data.get('commissioned_date')
            )
            
            return JsonResponse({
                'status': 'success',
                'message': 'Grid line created successfully',
                'grid_line': {
                    'idgridlines': grid_line.idgridlines,
                    'line_name': grid_line.line_name,
                    'line_code': grid_line.line_code,
                    'voltage_level': grid_line.voltage_level,
                    'length_km': round(grid_line.length_km, 2)
                }
            })
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

@login_required
def manage_facility_grid_connections(request, facility_id):
    """Add, update, or remove grid connections for a facility"""
    if request.method == 'POST':
        try:
            facility = facilities.objects.get(pk=facility_id)
            data = json.loads(request.body)
            action = data.get('action')  # 'add', 'remove', 'update', 'set_primary'
            
            if action == 'add':
                grid_line_id = data.get('grid_line_id')
                connection_type = data.get('connection_type', 'direct')
                is_primary = data.get('is_primary', False)
                
                if not grid_line_id:
                    return JsonResponse({'status': 'error', 'message': 'Grid line ID required'}, status=400)
                
                try:
                    grid_line = GridLines.objects.get(pk=grid_line_id)
                except GridLines.DoesNotExist:
                    return JsonResponse({'status': 'error', 'message': 'Grid line not found'}, status=400)
                
                # Calculate connection details
                connection_distance, connection_point = find_nearest_grid_line_point(
                    facility.latitude, facility.longitude, grid_line
                )
                
                # If setting as primary, unset other primary connections
                if is_primary:
                    FacilityGridConnections.objects.filter(
                        idfacilities=facility, is_primary=True
                    ).update(is_primary=False)
                    facility.primary_grid_line = grid_line
                    facility.save()
                
                # Create connection
                connection = FacilityGridConnections.objects.create(
                    idfacilities=facility,
                    idgridlines=grid_line,
                    connection_type=connection_type,
                    connection_point_latitude=connection_point[0],
                    connection_point_longitude=connection_point[1],
                    connection_voltage_kv=min(grid_line.voltage_level, 132),
                    connection_capacity_mw=facility.capacity or 0,
                    connection_distance_km=connection_distance,
                    is_primary=is_primary,
                    active=True
                )
                
                return JsonResponse({
                    'status': 'success',
                    'message': f'Connection to {grid_line.line_name} added successfully',
                    'connection_id': connection.idfacilitygridconnections
                })
            
            elif action == 'remove':
                connection_id = data.get('connection_id')
                try:
                    connection = FacilityGridConnections.objects.get(
                        pk=connection_id, idfacilities=facility
                    )
                    grid_line_name = connection.idgridlines.line_name
                    
                    # If removing primary connection, update facility
                    if connection.is_primary:
                        facility.primary_grid_line = None
                        facility.save()
                    
                    connection.delete()
                    
                    return JsonResponse({
                        'status': 'success',
                        'message': f'Connection to {grid_line_name} removed successfully'
                    })
                except FacilityGridConnections.DoesNotExist:
                    return JsonResponse({'status': 'error', 'message': 'Connection not found'}, status=404)
            
            elif action == 'set_primary':
                connection_id = data.get('connection_id')
                try:
                    # Unset all primary connections for this facility
                    FacilityGridConnections.objects.filter(
                        idfacilities=facility, is_primary=True
                    ).update(is_primary=False)
                    
                    # Set new primary connection
                    connection = FacilityGridConnections.objects.get(
                        pk=connection_id, idfacilities=facility
                    )
                    connection.is_primary = True
                    connection.save()
                    
                    # Update facility primary grid line
                    facility.primary_grid_line = connection.idgridlines
                    facility.save()
                    
                    return JsonResponse({
                        'status': 'success',
                        'message': f'Primary connection set to {connection.idgridlines.line_name}'
                    })
                except FacilityGridConnections.DoesNotExist:
                    return JsonResponse({'status': 'error', 'message': 'Connection not found'}, status=404)
            
            else:
                return JsonResponse({'status': 'error', 'message': 'Invalid action'}, status=400)
                
        except facilities.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Facility not found'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

@login_required
def calculate_grid_losses(request):
    """Calculate grid losses for a facility at given power output"""
    facility_id = request.GET.get('facility_id')
    power_output = float(request.GET.get('power_output', 0))
    
    if not facility_id:
        return JsonResponse({'error': 'Facility ID required'}, status=400)
    
    try:
        facility = facilities.objects.get(pk=facility_id)
        total_losses = facility.calculate_total_grid_losses_mw(power_output)
        
        # Get detailed breakdown
        connections = facility.get_all_grid_connections()
        loss_breakdown = []
        
        if connections:
            power_per_connection = power_output / len(connections)
            
            for conn in connections:
                connection_losses = conn.calculate_connection_losses_mw(power_per_connection)
                grid_line_losses = conn.idgridlines.calculate_line_losses_mw(power_per_connection)
                
                loss_breakdown.append({
                    'grid_line': conn.idgridlines.line_name,
                    'power_flow_mw': power_per_connection,
                    'connection_losses_mw': round(connection_losses, 3),
                    'grid_line_losses_mw': round(grid_line_losses, 3),
                    'total_losses_mw': round(connection_losses + grid_line_losses, 3),
                    'loss_percentage': round(((connection_losses + grid_line_losses) / power_per_connection) * 100, 2) if power_per_connection > 0 else 0
                })
        
        return JsonResponse({
            'facility_name': facility.facility_name,
            'total_power_output_mw': power_output,
            'total_losses_mw': round(total_losses, 3),
            'total_loss_percentage': round((total_losses / power_output) * 100, 2) if power_output > 0 else 0,
            'loss_breakdown': loss_breakdown
        })
        
    except facilities.DoesNotExist:
        return JsonResponse({'error': 'Facility not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_facility_grid_connections(request, facility_id):
    """Get all grid connections for a facility"""
    try:
        facility = facilities.objects.get(pk=facility_id)
        connections = FacilityGridConnections.objects.filter(
            idfacilities=facility
        ).select_related('idgridlines').order_by('-is_primary', 'connection_distance_km')
        
        connection_data = []
        for conn in connections:
            grid_line = conn.idgridlines
            
            # Calculate losses if possible
            connection_losses = 0
            grid_line_losses = 0
            if facility.capacity and facility.capacity > 0:
                try:
                    connection_losses = conn.calculate_connection_losses_mw(float(facility.capacity))
                    grid_line_losses = grid_line.calculate_line_losses_mw(float(facility.capacity))
                except (AttributeError, TypeError):
                    pass
            
            connection_info = {
                'connection_id': conn.idfacilitygridconnections,
                'grid_line_id': grid_line.idgridlines,
                'grid_line_name': grid_line.line_name,
                'grid_line_code': grid_line.line_code,
                'voltage_level': conn.connection_voltage_kv,
                'grid_line_voltage': grid_line.voltage_level,
                'connection_type': conn.connection_type,
                'capacity_mw': float(conn.connection_capacity_mw),
                'distance_km': float(conn.connection_distance_km),
                'is_primary': conn.is_primary,
                'active': conn.active,
                'connection_losses_mw': round(connection_losses, 3),
                'grid_line_losses_mw': round(grid_line_losses, 3),
                'total_losses_mw': round(connection_losses + grid_line_losses, 3),
                'loss_percentage': round(((connection_losses + grid_line_losses) / float(facility.capacity)) * 100, 2) if facility.capacity and facility.capacity > 0 else 0
            }
            connection_data.append(connection_info)
        
        return JsonResponse({
            'facility_id': facility.idfacilities,
            'facility_name': facility.facility_name,
            'total_connections': len(connection_data),
            'connections': connection_data
        })
        
    except facilities.DoesNotExist:
        return JsonResponse({'error': 'Facility not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
# Refresh facilities when the scenario is changed
def get_facilities_for_scenario(request):
    """Return facilities data for the selected scenario"""
    scenario_title = request.GET.get('scenario')

    if not scenario_title:
        return JsonResponse([], safe=False)

    try:
        scenario_obj = Scenarios.objects.get(title=scenario_title)
        facilities_queryset = facilities.objects.filter(
            scenarios=scenario_obj,
            latitude__isnull=False,
            longitude__isnull=False
        ).select_related('idtechnologies', 'primary_grid_line').prefetch_related('grid_connections')

        facilities_data = []
        for facility in facilities_queryset:
            retirement_year = None
            if facility.commissioning_date and facility.idtechnologies and facility.idtechnologies.lifetime:
                retirement_year = facility.commissioning_date.year + int(facility.idtechnologies.lifetime)
            facility_dict = {
                'facility_name': facility.facility_name,
                'idtechnologies': facility.idtechnologies.idtechnologies,
                'latitude': facility.latitude,
                'longitude': facility.longitude,
                'idfacilities': facility.idfacilities,
                'capacity': float(facility.capacity) if facility.capacity else 0,
                'technology_name': facility.idtechnologies.technology_name,
                'has_grid_connection': facility.grid_connections.exists(),
                'primary_grid_line_id': facility.primary_grid_line.idgridlines if facility.primary_grid_line else None,
                'primary_grid_line_name': facility.primary_grid_line.line_name if facility.primary_grid_line else None,
                'connection_count': facility.grid_connections.count(),
                'status': facility.status if facility.status else 'commissioned',
                'commissioning_probability': float(facility.commissioning_probability) if facility.commissioning_probability is not None else 1.0,
                'commissioning_date': facility.commissioning_date.isoformat() if facility.commissioning_date else None,
                'decommissioning_date': facility.decommissioning_date.isoformat() if facility.decommissioning_date else None,
                'technology_category': facility.idtechnologies.category if facility.idtechnologies and facility.idtechnologies.category else 'Unknown',
                'retirement_year': retirement_year,
            }
            facilities_data.append(facility_dict)

        return JsonResponse(facilities_data, safe=False)
    except Scenarios.DoesNotExist:
        return JsonResponse({'error': 'Scenario not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_grid_line_details(request, grid_line_id):
    """Get detailed information about a specific grid line"""
    try:
        grid_line = GridLines.objects.get(pk=grid_line_id)
        
        # Get connected facilities
        connected_facilities = []
        for connection in grid_line.facilitygridconnections_set.filter(active=True):
            connected_facilities.append({
                'facility_name': connection.idfacilities.facility_name,
                'technology': connection.idfacilities.idtechnologies.technology_name,
                'capacity': connection.idfacilities.capacity,
                'connection_distance': connection.connection_distance_km,
                'is_primary': connection.is_primary
            })
        
        # Calculate current utilization if we have power flow data
        # This would need to be connected to your power flow analysis
        current_utilization = 0  # Placeholder
        
        grid_line_data = {
            'idgridlines': grid_line.idgridlines,
            'line_name': grid_line.line_name,
            'line_code': grid_line.line_code,
            'line_type': grid_line.line_type,
            'voltage_level': grid_line.voltage_level,
            'length_km': grid_line.length_km,
            'thermal_capacity_mw': grid_line.thermal_capacity_mw,
            'emergency_capacity_mw': grid_line.emergency_capacity_mw,
            'resistance_total': grid_line.calculate_resistance(),
            'reactance_total': grid_line.calculate_reactance(),
            'impedance_total': grid_line.calculate_impedance(),
            'owner': grid_line.owner,
            'commissioned_date': grid_line.commissioned_date.isoformat() if grid_line.commissioned_date else None,
            'coordinates': grid_line.get_line_coordinates(),
            'connected_facilities': connected_facilities,
            'current_utilization_percent': current_utilization,
            'losses_at_full_capacity': grid_line.calculate_line_losses_mw(grid_line.thermal_capacity_mw)
        }
        
        return JsonResponse(grid_line_data)
        
    except GridLines.DoesNotExist:
        return JsonResponse({'error': 'Grid line not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_facility_details(request, facility_id):
    """Get detailed information about a specific facility"""
    try:
        facility = facilities.objects.get(pk=facility_id)
        
        # Get technology information
        technology_info = {
            'technology_id': facility.idtechnologies.idtechnologies,
            'technology_name': facility.idtechnologies.technology_name
        }
        
        # Get basic facility data
        facility_data = {
            'facility_id': facility.idfacilities,
            'facility_name': facility.facility_name,
            'facility_code': facility.facility_code,
            'technology_name': technology_info['technology_name'],
            'technology_id': technology_info['technology_id'],
            'capacity': float(facility.capacity) if facility.capacity else None,
            'latitude': float(facility.latitude) if facility.latitude else None,
            'longitude': float(facility.longitude) if facility.longitude else None,
            'active': facility.active,
            'existing': facility.existing,
            # 'registered_from': facility.registered_from.isoformat()
        }
        
        # Get economic data if available
        economic_data = {}
        if hasattr(facility, 'capex') and facility.capex:
            economic_data['capex'] = float(facility.capex)
        if hasattr(facility, 'opex') and facility.opex:
            economic_data['opex'] = float(facility.opex)
        if hasattr(facility, 'discount_rate') and facility.discount_rate:
            economic_data['discount_rate'] = float(facility.discount_rate)
        if hasattr(facility, 'lifetime') and facility.lifetime:
            economic_data['lifetime'] = int(facility.lifetime)
        
        if economic_data:
            facility_data['economic_data'] = economic_data
        
        # Get grid connections
        grid_connections = []
        facility_connections = FacilityGridConnections.objects.filter(
            idfacilities=facility, 
            active=True
        ).select_related('idgridlines')
        
        for connection in facility_connections:
            connection_data = {
                'connection_id': connection.idfacilitygridconnections,
                'grid_line_name': connection.idgridlines.line_name,
                'grid_line_id': connection.idgridlines.idgridlines,
                'voltage_level': connection.connection_voltage_kv,
                'capacity_mw': float(connection.connection_capacity_mw),
                'distance_km': float(connection.connection_distance_km),
                'connection_type': connection.connection_type,
                'is_primary': connection.is_primary,
                'active': connection.active
            }
            
            # Calculate losses for this connection if capacity is available
            if facility.capacity and facility.capacity > 0:
                try:
                    connection_losses = connection.calculate_connection_losses_mw(float(facility.capacity))
                    grid_line_losses = connection.idgridlines.calculate_line_losses_mw(float(facility.capacity))
                    total_losses = connection_losses + grid_line_losses
                    
                    connection_data['losses_at_full_output'] = total_losses
                    connection_data['loss_percentage'] = (total_losses / float(facility.capacity)) * 100
                except (AttributeError, ZeroDivisionError):
                    # If loss calculation methods don't exist or there's a division by zero
                    pass
            
            grid_connections.append(connection_data)
        
        facility_data['grid_connections'] = grid_connections
        
        # Get associated scenarios
        scenarios = []
        for scenario in facility.scenarios.all():
            scenarios.append(scenario.title)
        facility_data['scenarios'] = scenarios
        
        # Get performance metrics if available
        performance_metrics = {}
        if hasattr(facility, 'capacity_factor') and facility.capacity_factor:
            performance_metrics['capacity_factor'] = float(facility.capacity_factor)
        
        if hasattr(facility, 'annual_output') and facility.annual_output:
            performance_metrics['annual_output'] = float(facility.annual_output)
        elif facility.capacity and 'capacity_factor' in performance_metrics:
            # Calculate annual output if we have capacity and capacity factor
            hours_per_year = 8760
            performance_metrics['annual_output'] = float(facility.capacity) * performance_metrics['capacity_factor'] * hours_per_year
        
        if hasattr(facility, 'availability') and facility.availability:
            performance_metrics['availability'] = float(facility.availability)
        
        if performance_metrics:
            facility_data['performance_metrics'] = performance_metrics
        
        # Add additional technical specifications based on technology type
        technical_specs = {}
        
        # Solar PV specifications
        if technology_info['technology_id'] in [11, 13, 14]:  # Solar PV types
            if hasattr(facility, 'tilt') and facility.tilt is not None:
                technical_specs['panel_tilt'] = float(facility.tilt)
            if hasattr(facility, 'azimuth') and facility.azimuth is not None:
                technical_specs['azimuth'] = float(facility.azimuth)
            if hasattr(facility, 'tracking') and facility.tracking is not None:
                technical_specs['tracking_system'] = facility.tracking
            if hasattr(facility, 'inverter_efficiency') and facility.inverter_efficiency:
                technical_specs['inverter_efficiency'] = float(facility.inverter_efficiency)
        
        # Battery storage specifications
        elif technology_info['technology_id'] in [2, 3, 4, 5, 143, 144]:  # Battery types
            if hasattr(facility, 'storage_capacity_mwh') and facility.storage_capacity_mwh:
                technical_specs['storage_capacity_mwh'] = float(facility.storage_capacity_mwh)
            if hasattr(facility, 'round_trip_efficiency') and facility.round_trip_efficiency:
                technical_specs['round_trip_efficiency'] = float(facility.round_trip_efficiency)
            if hasattr(facility, 'max_charge_rate') and facility.max_charge_rate:
                technical_specs['max_charge_rate'] = float(facility.max_charge_rate)
            if hasattr(facility, 'max_discharge_rate') and facility.max_discharge_rate:
                technical_specs['max_discharge_rate'] = float(facility.max_discharge_rate)
            if hasattr(facility, 'min_soc') and facility.min_soc is not None:
                technical_specs['min_state_of_charge'] = float(facility.min_soc)
        
        # Gas/thermal specifications
        elif technology_info['technology_id'] in [1, 7, 19, 20]:  # Coal, CCGT, Gas peaking, Reciprocating
            if hasattr(facility, 'heat_rate') and facility.heat_rate:
                technical_specs['heat_rate'] = float(facility.heat_rate)
            if hasattr(facility, 'fuel_type') and facility.fuel_type:
                technical_specs['fuel_type'] = facility.fuel_type
            if hasattr(facility, 'emission_factor') and facility.emission_factor:
                technical_specs['emission_factor'] = float(facility.emission_factor)
            if hasattr(facility, 'min_load_factor') and facility.min_load_factor:
                technical_specs['min_load_factor'] = float(facility.min_load_factor)
        
        # Pumped hydro specifications
        elif technology_info['technology_id'] in [8, 9]:  # PHES
            if hasattr(facility, 'upper_reservoir_capacity') and facility.upper_reservoir_capacity:
                technical_specs['upper_reservoir_capacity'] = float(facility.upper_reservoir_capacity)
            if hasattr(facility, 'lower_reservoir_capacity') and facility.lower_reservoir_capacity:
                technical_specs['lower_reservoir_capacity'] = float(facility.lower_reservoir_capacity)
            if hasattr(facility, 'head_height') and facility.head_height:
                technical_specs['head_height'] = float(facility.head_height)
            if hasattr(facility, 'pump_efficiency') and facility.pump_efficiency:
                technical_specs['pump_efficiency'] = float(facility.pump_efficiency)
            if hasattr(facility, 'turbine_efficiency') and facility.turbine_efficiency:
                technical_specs['turbine_efficiency'] = float(facility.turbine_efficiency)
        
        if technical_specs:
            facility_data['technical_specifications'] = technical_specs
        
        # Add environmental data if available
        environmental_data = {}
        if hasattr(facility, 'water_usage') and facility.water_usage:
            environmental_data['water_usage'] = float(facility.water_usage)
        if hasattr(facility, 'noise_level') and facility.noise_level:
            environmental_data['noise_level'] = float(facility.noise_level)
        if hasattr(facility, 'visual_impact_score') and facility.visual_impact_score:
            environmental_data['visual_impact_score'] = float(facility.visual_impact_score)
        if hasattr(facility, 'carbon_intensity') and facility.carbon_intensity:
            environmental_data['carbon_intensity'] = float(facility.carbon_intensity)
        
        if environmental_data:
            facility_data['environmental_data'] = environmental_data
        
        # Add maintenance and operational data
        operational_data = {}
        if hasattr(facility, 'maintenance_factor') and facility.maintenance_factor:
            operational_data['maintenance_factor'] = float(facility.maintenance_factor)
        if hasattr(facility, 'forced_outage_rate') and facility.forced_outage_rate:
            operational_data['forced_outage_rate'] = float(facility.forced_outage_rate)
        if hasattr(facility, 'planned_outage_rate') and facility.planned_outage_rate:
            operational_data['planned_outage_rate'] = float(facility.planned_outage_rate)
        if hasattr(facility, 'ramp_up_rate') and facility.ramp_up_rate:
            operational_data['ramp_up_rate'] = float(facility.ramp_up_rate)
        if hasattr(facility, 'ramp_down_rate') and facility.ramp_down_rate:
            operational_data['ramp_down_rate'] = float(facility.ramp_down_rate)
        
        if operational_data:
            facility_data['operational_data'] = operational_data
        
        return JsonResponse(facility_data)
        
    except facilities.DoesNotExist:
        return JsonResponse({'error': 'Facility not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_facility_connections(request, facility_id):
    """Get all grid connections for a specific facility with detailed information"""
    try:
        facility = facilities.objects.get(pk=facility_id)
        
        connections = FacilityGridConnections.objects.filter(
            idfacilities=facility
        ).select_related('idgridlines').order_by('-is_primary', 'connection_distance_km')
        
        connection_data = []
        for conn in connections:
            grid_line = conn.idgridlines
            
            # Calculate connection losses if possible
            connection_losses = 0
            grid_line_losses = 0
            total_losses = 0
            
            if facility.capacity and facility.capacity > 0:
                try:
                    connection_losses = conn.calculate_connection_losses_mw(float(facility.capacity))
                    grid_line_losses = grid_line.calculate_line_losses_mw(float(facility.capacity))
                except (AttributeError, TypeError):
                    pass
            
            connection_info = {
                'connection_id': conn.idfacilitygridconnections,
                'grid_line_id': grid_line.idgridlines,
                'grid_line_name': grid_line.line_name,
                'grid_line_code': grid_line.line_code,
                'voltage_level': conn.connection_voltage_kv,
                'grid_line_voltage': grid_line.voltage_level,
                'connection_type': conn.connection_type,
                'capacity_mw': float(conn.connection_capacity_mw),
                'distance_km': float(conn.connection_distance_km),
                'is_primary': conn.is_primary,
                'active': conn.active,
                'connection_losses_mw': round(connection_losses, 3),
                'grid_line_losses_mw': round(grid_line_losses, 3),
                'total_losses_mw': round(connection_losses + grid_line_losses, 3),
                'loss_percentage': round(((connection_losses + grid_line_losses) / float(facility.capacity)) * 100, 2) if facility.capacity and facility.capacity > 0 else 0
            }
            
            connection_data.append(connection_info)
        
        return JsonResponse({
            'facility_id': facility.idfacilities,
            'facility_name': facility.facility_name,
            'total_connections': len(connection_data),
            'connections': connection_data
        })
        
    except facilities.DoesNotExist:
        return JsonResponse({'error': 'Facility not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def calculate_facility_performance(request, facility_id):
    """Calculate detailed performance metrics for a facility"""
    try:
        facility = facilities.objects.get(pk=facility_id)
        
        # Get parameters from request
        weather_year = request.GET.get('weather_year', '2024')
        scenario = request.GET.get('scenario', request.session.get('scenario', ''))
        
        performance_data = {
            'facility_id': facility.idfacilities,
            'facility_name': facility.facility_name,
            'technology': facility.idtechnologies.technology_name,
            'capacity_mw': float(facility.capacity) if facility.capacity else 0,
            'weather_year': weather_year,
            'scenario': scenario
        }
        
        # Calculate basic performance metrics
        if facility.capacity and facility.capacity > 0:
            # These calculations would typically use SAM or other modeling tools
            # For now, we'll use simplified calculations or stored values
            
            capacity_factor = 0.35  # Default capacity factor
            if hasattr(facility, 'capacity_factor') and facility.capacity_factor:
                capacity_factor = float(facility.capacity_factor)
            elif facility.idtechnologies.idtechnologies == 11:  # Solar PV
                capacity_factor = 0.25
            elif facility.idtechnologies.idtechnologies in [15, 16]:  # Wind
                capacity_factor = 0.35
            elif facility.idtechnologies.idtechnologies == 1:  # Coal
                capacity_factor = 0.75
            
            hours_per_year = 8760
            annual_output = float(facility.capacity) * capacity_factor * hours_per_year
            
            # Calculate grid losses
            total_grid_losses = 0
            if hasattr(facility, 'calculate_total_grid_losses_mw'):
                total_grid_losses = facility.calculate_total_grid_losses_mw(float(facility.capacity))
            
            net_annual_output = annual_output - (total_grid_losses * hours_per_year)
            
            performance_data.update({
                'capacity_factor': round(capacity_factor, 3),
                'annual_output_mwh': round(annual_output, 0),
                'total_grid_losses_mw': round(total_grid_losses, 3),
                'net_annual_output_mwh': round(net_annual_output, 0),
                'availability_factor': 0.95,  # Default availability
                'performance_ratio': 0.85     # Default performance ratio
            })
            
            # Add technology-specific metrics
            if facility.idtechnologies.idtechnologies in [11, 13, 14]:  # Solar
                performance_data.update({
                    'specific_yield_kwh_kw': round(annual_output / float(facility.capacity), 0),
                    'degradation_rate_per_year': 0.005,
                    'temperature_coefficient': -0.004
                })
            
            elif facility.idtechnologies.idtechnologies in [15, 16, 147]:  # Wind
                performance_data.update({
                    'wind_speed_average': 7.5,  # m/s
                    'turbulence_intensity': 0.15,
                    'air_density': 1.225  # kg/m³
                })
        
        return JsonResponse(performance_data)
        
    except facilities.DoesNotExist:
        return JsonResponse({'error': 'Facility not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
@login_required
def get_technologies(request):
    techs = Technologies.objects.all().values('idtechnologies', 'technology_name')
    return JsonResponse(list(techs), safe=False)

@login_required
def get_grid_lines(request):
    """Return available grid lines for facility connection with enhanced data"""
    grid_lines = GridLines.objects.filter(active=True).prefetch_related('connected_facilities').values(
        'idgridlines', 'line_name', 'line_code', 'line_type', 'voltage_level', 
        'thermal_capacity_mw', 'from_latitude', 'from_longitude', 'to_latitude', 'to_longitude'
    )
    
    # Add connection counts and utilization
    enhanced_lines = []
    for line_data in grid_lines:
        line = GridLines.objects.get(idgridlines=line_data['idgridlines'])
        connected_capacity = sum(f.capacity or 0 for f in line.connected_facilities.all())
        utilization = (connected_capacity / line_data['thermal_capacity_mw']) * 100 if line_data['thermal_capacity_mw'] > 0 else 0
        
        line_data.update({
            'connected_facilities_count': line.connected_facilities.count(),
            'connected_capacity_mw': connected_capacity,
            'utilization_percent': round(utilization, 1)
        })
        enhanced_lines.append(line_data)
    
    return JsonResponse(enhanced_lines, safe=False)

@login_required
def find_nearest_grid_lines(request):
    """Find nearest grid lines to a given location with enhanced data"""
    lat = float(request.GET.get('lat', 0))
    lon = float(request.GET.get('lon', 0))
    max_distance = float(request.GET.get('max_distance', 50))
    
    if not lat or not lon:
        return JsonResponse({'error': 'Latitude and longitude required'}, status=400)
    
    nearby_lines = []
    
    for grid_line in GridLines.objects.filter(active=True).prefetch_related('connected_facilities'):
        distance, connection_point = find_nearest_grid_line_point(lat, lon, grid_line)
        
        if distance <= max_distance:
            connected_capacity = sum(f.capacity or 0 for f in grid_line.connected_facilities.all())
            available_capacity = grid_line.thermal_capacity_mw - connected_capacity
            
            nearby_lines.append({
                'idgridlines': grid_line.idgridlines,
                'line_name': grid_line.line_name,
                'line_code': grid_line.line_code,
                'line_type': grid_line.line_type,
                'voltage_level': grid_line.voltage_level,
                'thermal_capacity_mw': grid_line.thermal_capacity_mw,
                'connected_capacity_mw': connected_capacity,
                'available_capacity_mw': available_capacity,
                'utilization_percent': round((connected_capacity / grid_line.thermal_capacity_mw) * 100, 1),
                'distance_km': round(distance, 2),
                'connection_point_lat': connection_point[0] if connection_point else grid_line.from_latitude,
                'connection_point_lon': connection_point[1] if connection_point else grid_line.from_longitude,
                'suitability_score': max(0, 100 - (distance * 2) - (connected_capacity / grid_line.thermal_capacity_mw * 50))
            })
    
    # Sort by suitability score (combination of distance and available capacity)
    nearby_lines.sort(key=lambda x: x['suitability_score'], reverse=True)
    
    return JsonResponse(nearby_lines, safe=False)
