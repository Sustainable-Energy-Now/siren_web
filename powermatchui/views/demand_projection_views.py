"""
Django views for demand projection visualization
Add to your views.py file
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Sum
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from common.decorators import settings_required
from configparser import ConfigParser
import os
import numpy as np
import json
from typing import Dict
from datetime import datetime
from siren_web.models import supplyfactors, DPVGeneration
from powermatchui.utils.demand_projector import DemandProjector, ScenarioComparator

from siren_web.models import supplyfactors, Scenarios, DemandFactor
from powermatchui.utils.factor_based_projector import FactorBasedProjector

def load_demand_config(config_file='siren.ini'):
    """Load demand projection configuration from INI file."""
    config_dir = './siren_web/siren_files/preferences/'
    config_path = os.path.join(config_dir, config_file)
    
    config = ConfigParser()
    config.read(config_path)
    
    # Get main demand projection settings
    if 'Demand Projection' in config.sections():
        demand_config = dict(config.items('Demand Projection'))
    else:
        # Default configuration if section doesn't exist
        demand_config = {
            'base_year': '2024',
            'operational_growth_rate': '0.025',
            'underlying_growth_rate': '0.04',
            'operational_growth_type': 'exponential',
            'underlying_growth_type': 's_curve',
            'operational_saturation': '2.0',
            'underlying_saturation': '3.5',
            'operational_midpoint_year': '2035',
            'underlying_midpoint_year': '2040',
            'projection_start_year': '2024',
            'projection_end_year': '2050'
        }
    
    # Get scenario configurations
    scenarios = {}
    for section in config.sections():
        if section.startswith('Scenario:'):
            scenario_name = section.replace('Scenario:', '').strip()
            scenarios[scenario_name] = dict(config.items(section))
    
    return demand_config, scenarios

def get_base_year_demand(year: int, config_section: Dict = None) -> Dict[str, np.ndarray]:
    """
    Retrieve hourly demand data for base year from supplyfactors (operational)
    and DPVGeneration (underlying) tables.
    
    Args:
        year: Base year to retrieve
        config_section: Config dict (can specify facility_id, default is 144)
        
    Returns:
        Dictionary with 'operational' and 'underlying' numpy arrays (8760 hours)
    """
    
    # Get operational facility ID from config, default to 144
    if config_section:
        operational_facility_id = int(config_section.get('operational_facility_id', 144))
    else:
        operational_facility_id = 144
    
    # ===================================================================
    # 1. Get Operational Demand from supplyfactors (facility 144)
    # ===================================================================
    
    operational_data = supplyfactors.objects.filter(
        idfacilities=operational_facility_id,
        year=year
    ).order_by('hour').values_list('hour', 'quantum')
    
    operational_array = np.zeros(8760)
    for hour, quantum in operational_data:
        if hour is not None and 0 <= hour < 8760:
            operational_array[hour] = quantum or 0.0
    
    if operational_array.sum() == 0:
        raise ValueError(
            f"No operational demand data found for facility {operational_facility_id}, year {year}"
        )
    
    # ===================================================================
    # 2. Get Underlying Demand from DPVGeneration table
    # ===================================================================
    
    # AEMO data has 48 intervals per day (30-minute intervals)
    # We need to convert to hourly by averaging pairs of intervals
    
    start_date = datetime(year, 1, 1)
    end_date = datetime(year, 12, 31, 23, 59, 59)
    
    dpv_data = DPVGeneration.objects.filter(
        trading_date__year=year
    ).order_by('trading_date', 'interval_number').values(
        'trading_date', 'interval_number', 'estimated_generation'
    )
    
    # Create a temporary dict to hold interval data
    # Key: (day_of_year, hour), Value: list of interval values
    hourly_intervals = {}
    
    for item in dpv_data:
        trading_date = item['trading_date']
        interval_num = item['interval_number']
        generation = float(item['estimated_generation'])
        
        # Calculate day of year (0-364 or 0-365 for leap year)
        day_of_year = (trading_date - start_date.date()).days
        
        # AEMO intervals are 30 minutes, numbered 1-48
        # Intervals 1-2 = hour 0, 3-4 = hour 1, etc.
        hour_of_day = (interval_num - 1) // 2
        
        # Calculate hour of year
        hour_of_year = day_of_year * 24 + hour_of_day
        
        if 0 <= hour_of_year < 8760:
            if hour_of_year not in hourly_intervals:
                hourly_intervals[hour_of_year] = []
            hourly_intervals[hour_of_year].append(generation)
    
    # Average the intervals to get hourly values
    underlying_array = np.zeros(8760)
    for hour, values in hourly_intervals.items():
        underlying_array[hour] = np.mean(values)
    
    # Note: DPV generation is already a demand (consumption offset)
    # If sum is 0, it's okay - means no DPV data for this year
    
    return {
        'operational': operational_array,
        'underlying': underlying_array
    }

def get_base_year_demand_with_total(year: int, config_section: Dict = None) -> Dict[str, np.ndarray]:
    """
    Alternative version that calculates total demand as operational + underlying.
    
    Returns:
        Dictionary with 'operational', 'underlying', and 'total' arrays
    """
    demand = get_base_year_demand(year, config_section)
    
    demand['total'] = demand['operational'] + demand['underlying']
    
    return demand

def validate_data_availability(year: int) -> Dict[str, bool]:
    """
    Check what data is available for a given year.
    Useful for debugging and configuration.
    
    Returns:
        Dictionary with availability flags and counts
    """
    result = {
        'year': year,
        'operational_available': False,
        'underlying_available': False,
        'operational_hours': 0,
        'underlying_intervals': 0,
        'operational_total_mwh': 0,
        'underlying_total_mwh': 0
    }
    
    # Check operational data (facility 144)
    operational_count = supplyfactors.objects.filter(
        idfacilities=144,
        year=year
    ).count()
    
    if operational_count > 0:
        result['operational_available'] = True
        result['operational_hours'] = operational_count
        
        operational_total = supplyfactors.objects.filter(
            idfacilities=144,
            year=year
        ).aggregate(total=Sum('quantum'))['total']
        result['operational_total_mwh'] = float(operational_total or 0)
    
    # Check DPV data
    dpv_count = DPVGeneration.objects.filter(
        trading_date__year=year
    ).count()
    
    if dpv_count > 0:
        result['underlying_available'] = True
        result['underlying_intervals'] = dpv_count
        
        dpv_total = DPVGeneration.objects.filter(
            trading_date__year=year
        ).aggregate(total=Sum('estimated_generation'))['total']
        # Convert from interval sum to hourly equivalent
        # 48 intervals per day, so divide by 2 to get hourly average * hours
        result['underlying_total_mwh'] = float(dpv_total or 0) / 2
    
    return result

def get_available_years() -> Dict[str, list]:
    """
    Get list of years with data available.
    
    Returns:
        Dictionary with 'operational', 'underlying', and 'both' year lists
    """
    # Get years with operational data
    operational_years = list(
        supplyfactors.objects.filter(
            idfacilities=144
        ).values_list('year', flat=True).distinct().order_by('year')
    )
    
    # Get years with DPV data
    underlying_years = list(
        DPVGeneration.objects.dates('trading_date', 'year').values_list('year', flat=True)
    )
    underlying_years = [d.year for d in DPVGeneration.objects.dates('trading_date', 'year')]
    
    # Years with both
    both_years = list(set(operational_years) & set(underlying_years))
    both_years.sort()
    
    return {
        'operational': operational_years,
        'underlying': underlying_years,
        'both': both_years,
        'all': sorted(list(set(operational_years + underlying_years)))
    }

def test_data_retrieval(year: int = None):
    """
    Test function to verify data retrieval works.
    Can be run from Django shell.
    
    Usage:
        python manage.py shell
        >>> from your_app.views import test_data_retrieval
        >>> test_data_retrieval(2024)
    """
    if year is None:
        # Get most recent year with data
        years = get_available_years()
        if years['both']:
            year = years['both'][-1]
        elif years['operational']:
            year = years['operational'][-1]
        else:
            print("No data available")
            return
    
    print(f"\nTesting data retrieval for year {year}")
    print("=" * 60)
    
    # Check availability
    availability = validate_data_availability(year)
    print(f"\nData Availability:")
    print(f"  Operational: {availability['operational_available']} "
          f"({availability['operational_hours']} hours, "
          f"{availability['operational_total_mwh']/1000:.1f} GWh)")
    print(f"  Underlying:  {availability['underlying_available']} "
          f"({availability['underlying_intervals']} intervals, "
          f"{availability['underlying_total_mwh']/1000:.1f} GWh)")
    
    # Try to retrieve data
    try:
        config = {'operational_facility_id': 144}
        demand = get_base_year_demand(year, config)
        
        print(f"\nRetrieved Data:")
        print(f"  Operational array shape: {demand['operational'].shape}")
        print(f"  Operational sum: {demand['operational'].sum()/1000:.1f} GWh")
        print(f"  Operational peak: {demand['operational'].max():.1f} MW")
        print(f"  Operational average: {demand['operational'].mean():.1f} MW")
        
        print(f"\n  Underlying array shape: {demand['underlying'].shape}")
        print(f"  Underlying sum: {demand['underlying'].sum()/1000:.1f} GWh")
        print(f"  Underlying peak: {demand['underlying'].max():.1f} MW")
        print(f"  Underlying average: {demand['underlying'].mean():.1f} MW")
        
        print(f"\n  Total demand: {(demand['operational'].sum() + demand['underlying'].sum())/1000:.1f} GWh")
        
        print("\n✓ Data retrieval successful!")
        
    except Exception as e:
        print(f"\n✗ Error retrieving data: {str(e)}")
        import traceback
        traceback.print_exc()

@login_required
def demand_projection_view(request):
    """Main view for demand projection visualization."""

    # Load configuration
    config_file = request.session.get('config_file', 'siren.ini')
    demand_config, scenarios = load_demand_config(config_file)

    # Get available years for base year selection
    # TODO: Replace with actual years available in your database
    available_years = list(range(2024, 2025))

    # Get database scenarios with factor configurations
    db_scenarios = Scenarios.objects.all().order_by('title')
    scenarios_with_factors = []
    for scenario in db_scenarios:
        factor_count = DemandFactor.objects.filter(
            scenario=scenario,
            is_active=True
        ).count()
        scenarios_with_factors.append({
            'id': scenario.idscenarios,
            'title': scenario.title,
            'has_factors': factor_count > 0,
            'factor_count': factor_count
        })

    context = {
        'demand_config': demand_config,
        'scenarios': scenarios,  # Legacy config-based scenarios
        'db_scenarios': scenarios_with_factors,  # New factor-based scenarios
        'available_years': available_years,
        'current_file': config_file
    }

    return render(request, 'demand_projection.html', context)

@require_http_methods(["POST"])
@login_required
def calculate_demand_projection(request):
    """
    API endpoint to calculate demand projections.
    Returns JSON data for plotting.
    Supports both legacy (simple rates) and factor-based projections.
    """
    try:
        data = json.loads(request.body)

        # Get parameters from request
        base_year = int(data.get('base_year', 2024))
        end_year = int(data.get('end_year', 2050))
        scenario_id = data.get('scenario_id')  # New: DB scenario ID
        scenario_name = data.get('scenario', 'Current Config')  # Legacy: config name
        use_factors = data.get('use_factors', False)  # New: explicit factor mode

        # Get base year demand data
        base_demand = get_base_year_demand(base_year)
        year_range = list(range(base_year, end_year + 1))

        # CHECK 1: Try factor-based projection if scenario_id provided
        if scenario_id:
            try:
                scenario = Scenarios.objects.get(idscenarios=scenario_id)
                factors = DemandFactor.objects.filter(
                    scenario=scenario,
                    is_active=True
                )

                if factors.exists():
                    # Use factor-based projector
                    projector = FactorBasedProjector(factors, base_year)
                    projections = projector.project_multiple_years(
                        base_demand['operational'],
                        base_demand['underlying'],
                        year_range
                    )

                    # Prepare factor breakdown data
                    factor_breakdown = {}
                    for year in year_range:
                        factor_breakdown[year] = {
                            'operational': projections[year]['factor_breakdown_operational_gwh'],
                            'underlying': projections[year]['factor_breakdown_underlying_gwh']
                        }

                    response_data = {
                        'years': year_range,
                        'operational_total_gwh': [projections[y]['operational_total_mwh'] / 1000
                                                  for y in year_range],
                        'underlying_total_gwh': [projections[y]['underlying_total_mwh'] / 1000
                                                 for y in year_range],
                        'total_gwh': [projections[y]['total_mwh'] / 1000
                                     for y in year_range],
                        'operational_peak_mw': [projections[y]['operational_peak_mw']
                                               for y in year_range],
                        'underlying_peak_mw': [projections[y]['underlying_peak_mw']
                                              for y in year_range],
                        'total_peak_mw': [projections[y]['total_peak_mw']
                                         for y in year_range],
                        'projection_type': 'factor_based',
                        'scenario_id': scenario_id,
                        'scenario_title': scenario.title,
                        'factor_count': factors.count(),
                        'factor_breakdown': factor_breakdown,
                        'metadata': projections[base_year]['metadata']
                    }

                    return JsonResponse(response_data)
            except Scenarios.DoesNotExist:
                pass  # Fall through to legacy projection

        # CHECK 2: Legacy projection using config file
        # Optional: custom growth rates from sliders
        custom_operational_rate = data.get('operational_growth_rate')
        custom_underlying_rate = data.get('underlying_growth_rate')

        # Load configuration
        config_file = request.session.get('config_file', 'siren.ini')
        demand_config, scenarios = load_demand_config(config_file)

        # Use scenario config or custom values
        if scenario_name in scenarios:
            projection_config = scenarios[scenario_name]
            projection_config['base_year'] = str(base_year)
        else:
            projection_config = demand_config.copy()
            projection_config['base_year'] = str(base_year)

        # Override with custom slider values if provided
        if custom_operational_rate is not None:
            projection_config['operational_growth_rate'] = str(custom_operational_rate)
        if custom_underlying_rate is not None:
            projection_config['underlying_growth_rate'] = str(custom_underlying_rate)

        # Use legacy projector
        projector = DemandProjector(projection_config)
        projections = projector.project_multiple_years(
            base_demand['operational'],
            base_demand['underlying'],
            year_range
        )

        # Prepare response data (legacy format)
        response_data = {
            'years': year_range,
            'operational_total_gwh': [projections[y]['operational_total_mwh'] / 1000
                                      for y in year_range],
            'underlying_total_gwh': [projections[y]['underlying_total_mwh'] / 1000
                                     for y in year_range],
            'total_gwh': [projections[y]['total_mwh'] / 1000
                         for y in year_range],
            'operational_peak_mw': [projections[y]['operational_peak_mw']
                                   for y in year_range],
            'underlying_peak_mw': [projections[y]['underlying_peak_mw']
                                  for y in year_range],
            'total_peak_mw': [projections[y]['total_peak_mw']
                             for y in year_range],
            'projection_type': 'legacy',
            'config': {
                'operational_growth_rate': float(projection_config['operational_growth_rate']),
                'underlying_growth_rate': float(projection_config['underlying_growth_rate']),
                'operational_growth_type': projection_config['operational_growth_type'],
                'underlying_growth_type': projection_config['underlying_growth_type']
            }
        }

        return JsonResponse(response_data)

    except Exception as e:
        import traceback
        return JsonResponse({
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=400)

@require_http_methods(["POST"])
@login_required
def compare_scenarios(request):
    """
    API endpoint to compare multiple scenarios.
    Returns data for multiple scenarios on same plot.
    """
    try:
        data = json.loads(request.body)
        
        base_year = int(data.get('base_year', 2024))
        end_year = int(data.get('end_year', 2050))
        scenario_names = data.get('scenarios', [])
        
        if not scenario_names:
            return JsonResponse({'error': 'No scenarios selected'}, status=400)
        
        # Load configuration
        config_file = request.session.get('config_file', 'siren.ini')
        demand_config, scenarios = load_demand_config(config_file)
        
        # Get base year demand
        base_demand = get_base_year_demand(base_year)
        
        # Import scenario comparator
        comparator = ScenarioComparator(
            base_demand['operational'],
            base_demand['underlying'],
            base_year
        )
        
        # Prepare scenarios for comparison
        scenario_configs = {}
        for name in scenario_names:
            if name in scenarios:
                scenario_configs[name] = scenarios[name]
        
        year_range = list(range(base_year, end_year + 1))
        results = comparator.compare_scenarios(scenario_configs, year_range)
        
        # Format response
        response_data = {
            'years': year_range,
            'scenarios': {}
        }
        
        for scenario_name, projections in results.items():
            response_data['scenarios'][scenario_name] = {
                'total_gwh': [projections[y]['total_mwh'] / 1000 for y in year_range],
                'operational_gwh': [projections[y]['operational_total_mwh'] / 1000 
                                   for y in year_range],
                'underlying_gwh': [projections[y]['underlying_total_mwh'] / 1000 
                                  for y in year_range],
                'total_peak_mw': [projections[y]['total_peak_mw'] for y in year_range]
            }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@require_http_methods(["GET"])
@login_required
def get_hourly_projection(request):
    """
    Get hourly demand profile for a specific projected year.
    Useful for detailed analysis.
    """
    try:
        year = int(request.GET.get('year', 2030))
        base_year = int(request.GET.get('base_year', 2024))
        scenario = request.GET.get('scenario', 'Current Config')
        
        # Load config and get base demand
        config_file = request.session.get('config_file', 'siren.ini')
        demand_config, scenarios = load_demand_config(config_file)
        
        projection_config = scenarios.get(scenario, demand_config)
        projection_config['base_year'] = str(base_year)
        
        base_demand = get_base_year_demand(base_year)
        
        # Project to target year
        projector = DemandProjector(projection_config)
        
        proj_op, proj_und = projector.project_demand(
            base_demand['operational'],
            base_demand['underlying'],
            year
        )
        
        # Return hourly data (can sample or return all 8760 hours)
        # For efficiency, might want to aggregate or sample
        response_data = {
            'year': year,
            'hours': list(range(len(proj_op))),
            'operational': proj_op.tolist(),
            'underlying': proj_und.tolist(),
            'total': (proj_op + proj_und).tolist()
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)