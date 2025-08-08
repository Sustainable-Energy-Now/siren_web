# Enhanced powermapui_home_views.py with grid line support

from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db.models import Max, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from powermatchui.forms import DemandScenarioSettings
from siren_web.database_operations import fetch_module_settings_data, fetch_scenario_settings_data
from siren_web.models import facilities, Technologies, Scenarios, GridLines, FacilityGridConnections
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

def find_nearest_grid_line(facility_lat, facility_lon, max_distance_km=50):
    """Find the nearest grid line to a facility location"""
    nearest_line = None
    min_distance = float('inf')
    connection_point = None
    
    for grid_line in GridLines.objects.filter(active=True):
        # Calculate distance to both endpoints
        dist_from = calculate_distance_km(facility_lat, facility_lon, 
                                         grid_line.from_latitude, grid_line.from_longitude)
        dist_to = calculate_distance_km(facility_lat, facility_lon, 
                                       grid_line.to_latitude, grid_line.to_longitude)
        
        # Find the closest point (simplified - using endpoints only)
        if dist_from < dist_to:
            closest_distance = dist_from
            closest_point = (grid_line.from_latitude, grid_line.from_longitude)
        else:
            closest_distance = dist_to
            closest_point = (grid_line.to_latitude, grid_line.to_longitude)
        
        if closest_distance < min_distance and closest_distance <= max_distance_km:
            min_distance = closest_distance
            nearest_line = grid_line
            connection_point = closest_point
    
    return nearest_line, min_distance, connection_point

@login_required
def home(request):
    # Get demand_year and scenario from session or default to empty string
    demand_year = request.session.get('demand_year', '')
    scenario = request.session.get('scenario', '')
    config_file = request.session.get('config_file')
    # Get success message from session and clear it
    success_message = request.session.pop('success_message', '')
    
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
    if not demand_year:
        success_message = "Set a demand year, scenario and config first."
    else:
        scenario_settings = fetch_module_settings_data('Power')
        if not scenario_settings:
            scenario_settings = fetch_scenario_settings_data(scenario)
    
    # Query facilities for the selected scenario with latitude and longitude available
    if scenario:
        # Filter facilities that belong to the selected scenario and have coordinates
        scenario_obj = Scenarios.objects.get(title=scenario)
        facilities_data = facilities.objects.filter(
            scenarios=scenario_obj,
            latitude__isnull=False, 
            longitude__isnull=False
        ).values('facility_name', 'idtechnologies', 'latitude', 'longitude', 'idfacilities')
    else:
        # If no scenario is selected, return an empty queryset
        facilities_data = facilities.objects.none().values('facility_name', 'idtechnologies', 'latitude', 'longitude', 'idfacilities')
    
    # Convert the queryset to JSON
    facilities_json = json.dumps(list(facilities_data))
    
    # Get grid lines data for the map with detailed coordinates
    grid_lines_data = []
    for grid_line in GridLines.objects.filter(active=True):
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
            'coordinates': grid_line.get_line_coordinates(),  # Full coordinate path
            'style': grid_line.get_line_style(),  # Styling info
            'popup_content': grid_line.get_popup_content(),  # Popup HTML
            # Simple from/to for backward compatibility
            'from_latitude': grid_line.from_latitude,
            'from_longitude': grid_line.from_longitude,
            'to_latitude': grid_line.to_latitude,
            'to_longitude': grid_line.to_longitude
        }
        grid_lines_data.append(grid_line_data)
        
    grid_lines_json = json.dumps(grid_lines_data)
    
    context = {
        'demand_weather_scenario': demand_weather_scenario,
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
        'success_message': success_message, 
        'facilities_json': facilities_json,
        'grid_lines_json': grid_lines_json,
    }
    return render(request, 'powermapui_home.html', context)

@login_required
@csrf_exempt
def add_facility(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Extract data from the request
            facility_name = data.get('facility_name')
            technology_id = data.get('technology_id')
            latitude = data.get('latitude')
            longitude = data.get('longitude')
            capacity = data.get('capacity')
            
            # Grid connection data
            grid_line_id = data.get('grid_line_id')
            create_new_grid_line = data.get('create_new_grid_line', False)
            new_grid_line_data = data.get('new_grid_line_data', {})
            
            # Wind turbine specific fields
            turbine = data.get('turbine')
            hub_height = data.get('hub_height')
            no_turbines = data.get('no_turbines')
            tilt = data.get('tilt')
            
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
            
            # Check if scenario is 'Current' - facilities cannot be added to this scenario
            if scenario_title == 'Current':
                return JsonResponse({'status': 'error', 'message': 'Cannot add facilities to the "Current" scenario. Please select a different scenario.'}, status=400)
            
            try:
                scenario_obj = Scenarios.objects.get(title=scenario_title)
            except Scenarios.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Selected scenario not found'}, status=400)
            
            # Create a basic facility code based on name and technology
            tech_prefix = technology.technology_name[:3].upper() if technology.technology_name else "FAC"
            facility_code = f"{tech_prefix}_{facility_name.replace(' ', '_').lower()}"[:30]
            
            # Validate wind turbine specific fields if applicable
            wind_tech_ids = [15, 16, 17]  # Onshore, Offshore, Floating wind IDs
            if technology_id in wind_tech_ids:
                if not turbine:
                    return JsonResponse({'status': 'error', 'message': 'Turbine model is required for wind facilities'}, status=400)
                if not hub_height:
                    return JsonResponse({'status': 'error', 'message': 'Hub height is required for wind facilities'}, status=400)
                if not no_turbines or int(no_turbines) < 1:
                    return JsonResponse({'status': 'error', 'message': 'Number of turbines must be at least 1'}, status=400)
            
            # Handle grid line connection
            grid_line = None
            connection_distance = 0
            
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
                except Exception as e:
                    return JsonResponse({'status': 'error', 'message': f'Error creating grid line: {str(e)}'}, status=400)
            
            elif grid_line_id:
                # Use existing grid line
                try:
                    grid_line = GridLines.objects.get(pk=grid_line_id)
                    # Calculate connection distance
                    _, connection_distance, _ = find_nearest_grid_line(latitude, longitude)
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
                capacity=capacity or 0.0,
                latitude=latitude,
                longitude=longitude,
                existing=False,
                primary_grid_line=grid_line
            )
            
            # Add wind turbine specific fields if applicable
            if technology_id in wind_tech_ids:
                new_facility.turbine = turbine
                new_facility.hub_height = hub_height
                new_facility.no_turbines = no_turbines
                new_facility.tilt = tilt
            
            new_facility.save()
            
            # Add the facility to the current scenario
            new_facility.scenarios.add(scenario_obj)
            
            # Create grid connection
            if grid_line:
                connection_voltage = 132  # Default connection voltage
                if grid_line.voltage_level >= 220:
                    connection_voltage = grid_line.voltage_level
                elif grid_line.voltage_level < 66:
                    connection_voltage = grid_line.voltage_level
                
                FacilityGridConnections.objects.create(
                    idfacilities=new_facility,
                    idgridlines=grid_line,
                    connection_type='direct',
                    connection_point_latitude=latitude,  # Simplified - using facility location
                    connection_point_longitude=longitude,
                    connection_voltage_kv=connection_voltage,
                    connection_capacity_mw=capacity or 0.0,
                    connection_distance_km=connection_distance,
                    is_primary=True,
                    active=True
                )
            
            # Get the technology name for the response
            tech_name = technology.technology_name
            
            response_data = {
                'status': 'success',
                'message': f'{tech_name} facility added successfully to scenario "{scenario_title}"',
                'facility_id': new_facility.idfacilities,
                'facility_name': new_facility.facility_name,
                'technology': tech_name,
                'scenario': scenario_title
            }
            
            if grid_line:
                response_data['grid_connection'] = {
                    'grid_line_name': grid_line.line_name,
                    'connection_distance_km': round(connection_distance, 2),
                    'voltage_level': grid_line.voltage_level
                }
            
            return JsonResponse(response_data)
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    # If not POST, return error
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

@login_required
def get_technologies(request):
    techs = Technologies.objects.all().values('idtechnologies', 'technology_name')
    return JsonResponse(list(techs), safe=False)

@login_required
def get_grid_lines(request):
    """Return available grid lines for facility connection"""
    grid_lines = GridLines.objects.filter(active=True).values(
        'idgridlines', 'line_name', 'line_code', 'line_type', 'voltage_level', 
        'thermal_capacity_mw', 'from_latitude', 'from_longitude', 'to_latitude', 'to_longitude'
    )
    return JsonResponse(list(grid_lines), safe=False)

@login_required
def find_nearest_grid_lines(request):
    """Find nearest grid lines to a given location"""
    lat = float(request.GET.get('lat', 0))
    lon = float(request.GET.get('lon', 0))
    max_distance = float(request.GET.get('max_distance', 50))
    
    if not lat or not lon:
        return JsonResponse({'error': 'Latitude and longitude required'}, status=400)
    
    nearby_lines = []
    
    for grid_line in GridLines.objects.filter(active=True):
        # Calculate distance to line endpoints
        dist_from = calculate_distance_km(lat, lon, grid_line.from_latitude, grid_line.from_longitude)
        dist_to = calculate_distance_km(lat, lon, grid_line.to_latitude, grid_line.to_longitude)
        
        min_distance = min(dist_from, dist_to)
        
        if min_distance <= max_distance:
            nearby_lines.append({
                'idgridlines': grid_line.idgridlines,
                'line_name': grid_line.line_name,
                'line_code': grid_line.line_code,
                'line_type': grid_line.line_type,
                'voltage_level': grid_line.voltage_level,
                'thermal_capacity_mw': grid_line.thermal_capacity_mw,
                'distance_km': round(min_distance, 2),
                'from_lat': grid_line.from_latitude,
                'from_lon': grid_line.from_longitude,
                'to_lat': grid_line.to_latitude,
                'to_lon': grid_line.to_longitude
            })
    
    # Sort by distance
    nearby_lines.sort(key=lambda x: x['distance_km'])
    
    return JsonResponse(nearby_lines, safe=False)

@login_required
@csrf_exempt
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
# Refresh facilities when the scenario is changed
def get_facilities_for_scenario(request):
    """Return facilities data for the selected scenario"""
    scenario_title = request.GET.get('scenario')
    
    if not scenario_title:
        return JsonResponse([], safe=False)
    
    try:
        scenario_obj = Scenarios.objects.get(title=scenario_title)
        facilities_data = facilities.objects.filter(
            scenarios=scenario_obj,
            latitude__isnull=False, 
            longitude__isnull=False
        ).values('facility_name', 'idtechnologies', 'latitude', 'longitude', 'idfacilities')
        
        return JsonResponse(list(facilities_data), safe=False)
    except Scenarios.DoesNotExist:
        return JsonResponse({'error': 'Scenario not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def sync_kml_gridlines(request):
    """API endpoint to sync KML data with GridLines database"""
    if request.method == 'POST':
        try:
            from django.core.management import call_command
            from io import StringIO
            
            # Capture command output
            out = StringIO()
            call_command('import_kml_gridlines', 
                        kml_file='kml/SWIS_Grid.kml',
                        update_existing=True,
                        stdout=out)
            
            output = out.getvalue()
            
            return JsonResponse({
                'status': 'success',
                'message': 'KML sync completed successfully',
                'output': output
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'KML sync failed: {str(e)}'
            }, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

@login_required
def export_gridlines_kml(request):
    """Export current GridLines to KML format"""
    try:
        from django.http import HttpResponse
        import tempfile
        import os
        
        # Create temporary KML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.kml', delete=False) as tmp_file:
            filename = GridLines.export_all_to_kml(tmp_file.name)
        
        # Read the file and return as response
        with open(filename, 'r', encoding='utf-8') as f:
            kml_content = f.read()
        
        # Clean up temp file
        os.unlink(filename)
        
        response = HttpResponse(kml_content, content_type='application/vnd.google-earth.kml+xml')
        response['Content-Disposition'] = 'attachment; filename="gridlines.kml"'
        
        return response
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'KML export failed: {str(e)}'
        }, status=500)

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
        
        # Add wind turbine specific details if applicable
        wind_tech_ids = [15, 16, 147]  # Onshore, Offshore, Floating wind
        if technology_info['technology_id'] in wind_tech_ids:
            turbine_details = {
                'turbine': getattr(facility, 'turbine', None),
                'hub_height': float(facility.hub_height) if getattr(facility, 'hub_height', None) else None,
                'no_turbines': int(facility.no_turbines) if getattr(facility, 'no_turbines', None) else None,
                'tilt': float(facility.tilt) if getattr(facility, 'tilt', None) else None,
            }
            
            # Calculate additional turbine metrics if we have the data
            if turbine_details['turbine'] and facility.capacity and turbine_details['no_turbines']:
                turbine_details['capacity_per_turbine'] = float(facility.capacity) / int(turbine_details['no_turbines'])
            
            # Add rotor diameter if available (you might need to add this field to your model)
            if hasattr(facility, 'rotor_diameter') and facility.rotor_diameter:
                turbine_details['rotor_diameter'] = float(facility.rotor_diameter)
            
            facility_data['turbine_details'] = turbine_details
        
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
                    if hasattr(conn, 'calculate_connection_losses_mw'):
                        connection_losses = conn.calculate_connection_losses_mw(float(facility.capacity))
                    if hasattr(grid_line, 'calculate_line_losses_mw'):
                        grid_line_losses = grid_line.calculate_line_losses_mw(float(facility.capacity))
                    total_losses = connection_losses + grid_line_losses
                except (AttributeError, TypeError):
                    pass
            
            connection_info = {
                'connection_id': conn.idfacilitygridconnections,
                'facility_name': facility.facility_name,
                'grid_line_id': grid_line.idgridlines,
                'grid_line_name': grid_line.line_name,
                'grid_line_code': grid_line.line_code,
                'grid_line_type': grid_line.line_type,
                'voltage_level': conn.connection_voltage_kv,
                'grid_line_voltage': grid_line.voltage_level,
                'connection_type': conn.connection_type,
                'capacity_mw': float(conn.connection_capacity_mw),
                'distance_km': float(conn.connection_distance_km),
                'is_primary': conn.is_primary,
                'active': conn.active,
                'connection_point_lat': float(conn.connection_point_latitude) if conn.connection_point_latitude else None,
                'connection_point_lng': float(conn.connection_point_longitude) if conn.connection_point_longitude else None,
                'connection_losses_mw': round(connection_losses, 3),
                'grid_line_losses_mw': round(grid_line_losses, 3),
                'total_losses_mw': round(total_losses, 3),
                'loss_percentage': round((total_losses / float(facility.capacity)) * 100, 2) if facility.capacity and facility.capacity > 0 else 0
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
        weather_year = request.GET.get('weather_year', '2019')
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
    