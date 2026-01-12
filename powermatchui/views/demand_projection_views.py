"""
Django views for demand projection visualization
Add to your views.py file
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Sum
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
import numpy as np
import json
from typing import Dict
from datetime import datetime
from calendar import monthrange
from siren_web.models import MonthlyREPerformance, FacilityScada, facilities, DPVGeneration

from siren_web.models import Scenarios, DemandFactor, TargetScenario
from powermatchui.utils.factor_based_projector import FactorBasedProjector

def get_base_year_demand(year: int, config_section: Dict = None) -> Dict[str, np.ndarray]:
    """
    Retrieve hourly demand data for base year from MonthlyREPerformance model.
    Converts monthly GWh totals to hourly MW arrays using FacilityScada for hourly shape.

    Args:
        year: Base year to retrieve
        config_section: Config dict (currently unused, kept for compatibility)

    Returns:
        Dictionary with 'operational' and 'underlying' numpy arrays (8760 or 8784 hours in MW)
    """

    # ===================================================================
    # 1. Get monthly totals from MonthlyREPerformance
    # ===================================================================

    monthly_data = MonthlyREPerformance.objects.filter(
        year=year
    ).order_by('month').values('month', 'operational_demand', 'underlying_demand')

    if not monthly_data:
        raise ValueError(
            f"No MonthlyREPerformance data found for year {year}"
        )

    # Store monthly totals (in GWh)
    monthly_operational = {}
    monthly_underlying = {}

    for month_record in monthly_data:
        month = month_record['month']
        monthly_operational[month] = month_record['operational_demand']  # GWh
        monthly_underlying[month] = month_record['underlying_demand']     # GWh

    # Check if we have 12 months of data
    if len(monthly_operational) != 12:
        raise ValueError(
            f"Incomplete data for year {year}: only {len(monthly_operational)} months available"
        )

    # ===================================================================
    # 2. Determine array size (8760 for normal years, 8784 for leap years)
    # ===================================================================

    is_leap_year = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
    total_hours = 8784 if is_leap_year else 8760

    # Initialize hourly arrays
    operational_array = np.zeros(total_hours)
    underlying_array = np.zeros(total_hours)

    # ===================================================================
    # 3. Process each month - get shape from FacilityScada and scale
    # ===================================================================

    for month in range(1, 13):
        # Get date range for the month
        _, last_day = monthrange(year, month)
        start_datetime = timezone.make_aware(datetime(year, month, 1, 0, 0, 0))
        end_datetime = timezone.make_aware(datetime(year, month, last_day, 23, 59, 59))

        # Calculate hour range for this month
        if month == 1:
            start_hour = 0
        else:
            # Sum hours from previous months
            start_hour = sum(monthrange(year, m)[1] * 24 for m in range(1, month))

        hours_in_month = monthrange(year, month)[1] * 24
        end_hour = start_hour + hours_in_month

        # ---------------------------------------------------------------
        # OPERATIONAL DEMAND - Get hourly shape from FacilityScada
        # ---------------------------------------------------------------

        # Query FacilityScada for all generation facilities (grid-sent)
        # Sum all facilities - we'll use MonthlyREPerformance total to scale
        scada_operational = FacilityScada.objects.filter(
            dispatch_interval__gte=start_datetime,
            dispatch_interval__lte=end_datetime
        ).exclude(
            facility__idtechnologies__technology_signature='rooftop_pv'
        ).values('dispatch_interval').annotate(
            total_mw=Sum('quantity')
        ).order_by('dispatch_interval')

        # Build hourly shape array
        hourly_operational_shape = np.zeros(hours_in_month)
        for record in scada_operational:
            dt = record['dispatch_interval']
            # Calculate hour index within the month (0-indexed)
            hour_in_month = (dt.day - 1) * 24 + dt.hour
            if 0 <= hour_in_month < hours_in_month:
                hourly_operational_shape[hour_in_month] = float(record['total_mw'])

        # Normalize shape and scale to monthly total
        if hourly_operational_shape.sum() > 0:
            # Normalize to sum = 1
            hourly_operational_shape = hourly_operational_shape / hourly_operational_shape.sum()
            # Scale by monthly total (convert GWh to MW average)
            monthly_total_mwh = monthly_operational[month] * 1000  # GWh to MWh
            scaled_operational = monthly_total_mwh * hourly_operational_shape
        else:
            # Fallback: distribute evenly across hours
            monthly_total_mwh = monthly_operational[month] * 1000
            scaled_operational = np.ones(hours_in_month) * (monthly_total_mwh / hours_in_month)

        operational_array[start_hour:end_hour] = scaled_operational

        # ---------------------------------------------------------------
        # UNDERLYING DEMAND - Use DPV from DPVGeneration
        # ---------------------------------------------------------------

        # Query DPVGeneration for rooftop solar (30-minute intervals)
        dpv_data = DPVGeneration.objects.filter(
            trading_date__year=year,
            trading_date__month=month
        ).order_by('trading_date', 'interval_number').values(
            'trading_date', 'interval_number', 'estimated_generation'
        )

        # Build hourly DPV shape
        hourly_dpv_dict = {}
        for item in dpv_data:
            trading_date = item['trading_date']
            interval_num = item['interval_number']
            generation = float(item['estimated_generation'])

            # AEMO intervals are 30 minutes, numbered 1-48
            # Intervals 1-2 = hour 0, 3-4 = hour 1, etc.
            hour_of_day = (interval_num - 1) // 2
            hour_in_month = (trading_date.day - 1) * 24 + hour_of_day

            if 0 <= hour_in_month < hours_in_month:
                if hour_in_month not in hourly_dpv_dict:
                    hourly_dpv_dict[hour_in_month] = []
                hourly_dpv_dict[hour_in_month].append(generation)

        # Average intervals to hourly
        hourly_dpv_shape = np.zeros(hours_in_month)
        for hour_idx, values in hourly_dpv_dict.items():
            hourly_dpv_shape[hour_idx] = np.mean(values)

        # Calculate underlying demand for this month
        # Underlying = Operational + DPV
        # We need to scale DPV to match: monthly_underlying - monthly_operational
        dpv_monthly_total_gwh = monthly_underlying[month] - monthly_operational[month]

        if hourly_dpv_shape.sum() > 0 and dpv_monthly_total_gwh > 0:
            # Normalize and scale DPV shape
            hourly_dpv_shape = hourly_dpv_shape / hourly_dpv_shape.sum()
            dpv_total_mwh = dpv_monthly_total_gwh * 1000  # GWh to MWh
            scaled_dpv = dpv_total_mwh * hourly_dpv_shape
        else:
            # Fallback: distribute DPV evenly or use zero
            if dpv_monthly_total_gwh > 0:
                dpv_total_mwh = dpv_monthly_total_gwh * 1000
                scaled_dpv = np.ones(hours_in_month) * (dpv_total_mwh / hours_in_month)
            else:
                scaled_dpv = np.zeros(hours_in_month)

        # Underlying = Operational + DPV (for this month)
        underlying_array[start_hour:end_hour] = scaled_operational + scaled_dpv

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
        'months_available': 0,
        'operational_total_gwh': 0,
        'underlying_total_gwh': 0,
        'scada_records': 0,
        'dpv_records': 0
    }

    # Check MonthlyREPerformance data
    monthly_data = MonthlyREPerformance.objects.filter(year=year)
    months_count = monthly_data.count()

    if months_count > 0:
        result['months_available'] = months_count
        result['operational_available'] = True
        result['underlying_available'] = True

        # Sum up all months
        operational_total = monthly_data.aggregate(
            total=Sum('operational_demand')
        )['total']
        underlying_total = monthly_data.aggregate(
            total=Sum('underlying_demand')
        )['total']

        result['operational_total_gwh'] = float(operational_total or 0)
        result['underlying_total_gwh'] = float(underlying_total or 0)

    # Check FacilityScada data availability for hourly shape
    scada_count = FacilityScada.objects.filter(
        dispatch_interval__year=year
    ).count()
    result['scada_records'] = scada_count

    # Check DPV data availability
    dpv_count = DPVGeneration.objects.filter(
        trading_date__year=year
    ).count()
    result['dpv_records'] = dpv_count

    return result

def get_available_years() -> Dict[str, list]:
    """
    Get list of years with data available from MonthlyREPerformance.

    Returns:
        Dictionary with available years and completeness information
    """
    from django.db.models import Count

    # Get years with any MonthlyREPerformance data
    years_with_data = MonthlyREPerformance.objects.values('year').annotate(
        month_count=Count('month')
    ).order_by('year')

    all_years = []
    complete_years = []  # Years with all 12 months

    for item in years_with_data:
        year = item['year']
        month_count = item['month_count']

        all_years.append(year)
        if month_count == 12:
            complete_years.append(year)

    return {
        'all': all_years,
        'complete': complete_years,
        'operational': complete_years,  # For backward compatibility
        'underlying': complete_years,   # For backward compatibility
        'both': complete_years          # For backward compatibility
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
          f"({availability['months_available']} months, "
          f"{availability['operational_total_gwh']:.1f} GWh)")
    print(f"  Underlying:  {availability['underlying_available']} "
          f"({availability['months_available']} months, "
          f"{availability['underlying_total_gwh']:.1f} GWh)")
    print(f"  SCADA records: {availability['scada_records']:,}")
    print(f"  DPV records: {availability['dpv_records']:,}")

    # Try to retrieve data
    try:
        demand = get_base_year_demand(year)
        
        print(f"\nRetrieved Data:")
        print(f"  Operational array shape: {demand['operational'].shape}")
        print(f"  Operational sum: {demand['operational'].sum()/1000:.1f} GWh")
        print(f"  Operational peak: {demand['operational'].max():.1f} MW")
        print(f"  Operational average: {demand['operational'].mean():.1f} MW")
        
        print(f"\n  Underlying array shape: {demand['underlying'].shape}")
        print(f"  Underlying sum: {demand['underlying'].sum()/1000:.1f} GWh")
        print(f"  Underlying peak: {demand['underlying'].max():.1f} MW")
        print(f"  Underlying average: {demand['underlying'].mean():.1f} MW")

        # Verify totals match MonthlyREPerformance
        print(f"\nValidation:")
        print(f"  Expected operational total: {availability['operational_total_gwh']:.1f} GWh")
        print(f"  Actual operational total:   {demand['operational'].sum()/1000:.1f} GWh")
        print(f"  Expected underlying total:  {availability['underlying_total_gwh']:.1f} GWh")
        print(f"  Actual underlying total:    {demand['underlying'].sum()/1000:.1f} GWh")
        
        print("\n[SUCCESS] Data retrieval successful!")

    except Exception as e:
        print(f"\n[ERROR] Error retrieving data: {str(e)}")
        import traceback
        traceback.print_exc()

@login_required
def demand_projection_view(request):
    """Main view for demand projection visualization."""

    # Get available years for base year selection
    available_years_data = get_available_years()
    available_years = available_years_data.get('all', [2024])

    # Determine the minimum base year for projection range calculation
    min_base_year = min(available_years) if available_years else 2024

    # Projection years range: from (min_base_year + 1) to 2040
    projection_years = list(range(min_base_year + 1, 2041))

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
        'db_scenarios': scenarios_with_factors,
        'available_years': available_years,
        'projection_years': projection_years,
    }

    return render(request, 'demand_projection.html', context)

@require_http_methods(["POST"])
@login_required
def calculate_demand_projection(request):
    """
    API endpoint to calculate demand projections.
    Returns JSON data for plotting.
    Uses factor-based projections from database scenarios.
    """
    try:
        data = json.loads(request.body)

        # Get parameters from request
        base_year = int(data.get('base_year', 2024))
        end_year = int(data.get('end_year', 2050))
        scenario_id = data.get('scenario_id')

        if not scenario_id:
            return JsonResponse({
                'error': 'scenario_id is required'
            }, status=400)

        # Get base year demand data
        base_demand = get_base_year_demand(base_year)
        year_range = list(range(base_year, end_year + 1))

        # Get scenario and factors from database
        scenario = Scenarios.objects.get(idscenarios=scenario_id)
        factors = DemandFactor.objects.filter(
            scenario=scenario,
            is_active=True
        )

        if not factors.exists():
            return JsonResponse({
                'error': f'No active demand factors found for scenario "{scenario.title}"'
            }, status=400)

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
        return JsonResponse({
            'error': f'Scenario with ID {scenario_id} not found'
        }, status=404)
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
    Uses factor-based projections from database scenarios.
    """
    try:
        data = json.loads(request.body)

        base_year = int(data.get('base_year', 2024))
        end_year = int(data.get('end_year', 2050))
        scenario_ids = data.get('scenario_ids', [])

        if not scenario_ids:
            return JsonResponse({'error': 'No scenarios selected'}, status=400)

        # Get base year demand
        base_demand = get_base_year_demand(base_year)
        year_range = list(range(base_year, end_year + 1))

        # Format response
        response_data = {
            'years': year_range,
            'scenarios': {}
        }

        # Process each scenario
        for scenario_id in scenario_ids:
            try:
                scenario = Scenarios.objects.get(idscenarios=scenario_id)
                factors = DemandFactor.objects.filter(
                    scenario=scenario,
                    is_active=True
                )

                if not factors.exists():
                    continue

                # Use factor-based projector
                projector = FactorBasedProjector(factors, base_year)
                projections = projector.project_multiple_years(
                    base_demand['operational'],
                    base_demand['underlying'],
                    year_range
                )

                response_data['scenarios'][scenario.title] = {
                    'total_gwh': [projections[y]['total_mwh'] / 1000 for y in year_range],
                    'operational_gwh': [projections[y]['operational_total_mwh'] / 1000
                                       for y in year_range],
                    'underlying_gwh': [projections[y]['underlying_total_mwh'] / 1000
                                      for y in year_range],
                    'total_peak_mw': [projections[y]['total_peak_mw'] for y in year_range]
                }

            except Scenarios.DoesNotExist:
                continue

        return JsonResponse(response_data)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@require_http_methods(["GET"])
@login_required
def get_hourly_projection(request):
    """
    Get hourly demand profile for a specific projected year.
    Useful for detailed analysis.
    Uses factor-based projections from database scenarios.
    """
    try:
        year = int(request.GET.get('year', 2030))
        base_year = int(request.GET.get('base_year', 2024))
        scenario_id = request.GET.get('scenario_id')

        if not scenario_id:
            return JsonResponse({
                'error': 'scenario_id is required'
            }, status=400)

        # Get base demand
        base_demand = get_base_year_demand(base_year)

        # Get scenario and factors from database
        scenario = Scenarios.objects.get(idscenarios=scenario_id)
        factors = DemandFactor.objects.filter(
            scenario=scenario,
            is_active=True
        )

        if not factors.exists():
            return JsonResponse({
                'error': f'No active demand factors found for scenario "{scenario.title}"'
            }, status=400)

        # Use factor-based projector
        projector = FactorBasedProjector(factors, base_year)

        # Project to target year
        year_range = [base_year, year] if year != base_year else [base_year]
        projections = projector.project_multiple_years(
            base_demand['operational'],
            base_demand['underlying'],
            year_range
        )

        # Get the projected arrays for the target year
        proj_op = projections[year]['operational_hourly']
        proj_und = projections[year]['underlying_hourly']

        # Return hourly data
        response_data = {
            'year': year,
            'scenario_id': scenario_id,
            'scenario_title': scenario.title,
            'hours': list(range(len(proj_op))),
            'operational': proj_op.tolist(),
            'underlying': proj_und.tolist(),
            'total': (proj_op + proj_und).tolist()
        }

        return JsonResponse(response_data)

    except Scenarios.DoesNotExist:
        return JsonResponse({
            'error': f'Scenario with ID {scenario_id} not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@require_http_methods(["POST"])
@login_required
def update_target_scenario_with_projection(request):
    """
    Update TargetScenario records with demand values from projection.

    Rules:
    - scenario_name is derived from the Scenario FK (scenario.title)
    - Only operational_demand and underlying_demand are updated by this function
    - For 'base_case': Must exist first (created in Manage Targets)
    - For other scenario_types: Clone from base_case if doesn't exist
    """
    try:
        data = json.loads(request.body)

        base_year = int(data.get('base_year', 2024))
        end_year = int(data.get('end_year', 2050))
        scenario_id = data.get('scenario_id')
        scenario_type = data.get('scenario_type', 'base_case')

        if not scenario_id:
            return JsonResponse({
                'error': 'scenario_id is required'
            }, status=400)

        # Validate scenario_type
        valid_scenario_types = ['base_case', 'delayed_pipeline', 'accelerated_pipeline']
        if scenario_type not in valid_scenario_types:
            return JsonResponse({
                'error': f'Invalid scenario_type. Must be one of: {", ".join(valid_scenario_types)}'
            }, status=400)

        # Get scenario and use its title as the scenario_name
        scenario = Scenarios.objects.get(idscenarios=scenario_id)
        scenario_name = scenario.title

        # Get base year demand data
        base_demand = get_base_year_demand(base_year)
        year_range = list(range(base_year, end_year + 1))

        # Get scenario factors from database
        factors = DemandFactor.objects.filter(
            scenario=scenario,
            is_active=True
        )

        if not factors.exists():
            return JsonResponse({
                'error': f'No active demand factors found for scenario "{scenario.title}"'
            }, status=400)

        # Use factor-based projector
        projector = FactorBasedProjector(factors, base_year)
        projections = projector.project_multiple_years(
            base_demand['operational'],
            base_demand['underlying'],
            year_range
        )

        # Check if base_case exists (required for non-base_case scenarios)
        if scenario_type != 'base_case':
            base_case_count = TargetScenario.objects.filter(
                scenario_type='base_case',
                year__in=year_range
            ).count()

            if base_case_count == 0:
                return JsonResponse({
                    'error': 'base_case scenario must be created first in Manage Targets before creating other scenario types.'
                }, status=400)

        # Update or create TargetScenario records
        updated_years = []
        created_years = []
        cloned_years = []

        for year in year_range:
            # Convert from MWh to GWh
            operational_gwh = projections[year]['operational_total_mwh'] / 1000
            underlying_gwh = projections[year]['underlying_total_mwh'] / 1000

            # Check if TargetScenario exists
            existing = TargetScenario.objects.filter(
                scenario_type=scenario_type,
                year=year
            ).first()

            if existing:
                # Update existing record - ONLY update demand fields
                existing.operational_demand = operational_gwh
                existing.underlying_demand = underlying_gwh
                existing.scenario = scenario
                existing.scenario_name = scenario_name
                existing.save()
                updated_years.append(year)

            elif scenario_type == 'base_case':
                # base_case doesn't exist - return error
                return JsonResponse({
                    'error': f'base_case for year {year} does not exist. Please create it manually in Manage Targets first.'
                }, status=400)

            else:
                # Non-base_case doesn't exist - clone from base_case
                base_case = TargetScenario.objects.filter(
                    scenario_type='base_case',
                    year=year
                ).first()

                if not base_case:
                    return JsonResponse({
                        'error': f'Cannot clone: base_case for year {year} does not exist.'
                    }, status=400)

                # Clone from base_case
                cloned_scenario = TargetScenario.objects.create(
                    scenario_name=scenario_name,
                    scenario_type=scenario_type,
                    scenario=scenario,
                    description=base_case.description,
                    year=year,
                    target_type=base_case.target_type,
                    operational_demand=operational_gwh,  # Use projected demand
                    underlying_demand=underlying_gwh,    # Use projected demand
                    storage=base_case.storage,
                    target_re_percentage=base_case.target_re_percentage,
                    target_emissions_tonnes=base_case.target_emissions_tonnes,
                    wind_generation=base_case.wind_generation,
                    solar_generation=base_case.solar_generation,
                    dpv_generation=base_case.dpv_generation,
                    biomass_generation=base_case.biomass_generation,
                    gas_generation=base_case.gas_generation,
                    probability_percentage=base_case.probability_percentage,
                    is_active=base_case.is_active
                )
                cloned_years.append(year)

        return JsonResponse({
            'success': True,
            'message': f'Successfully updated TargetScenario records for {len(year_range)} years',
            'scenario_name': scenario_name,
            'scenario_type': scenario_type,
            'years_updated': updated_years,
            'years_created': created_years,
            'years_cloned': cloned_years,
            'total_years': len(year_range),
            'year_range': [year_range[0], year_range[-1]]
        })

    except Scenarios.DoesNotExist:
        return JsonResponse({
            'error': f'Scenario with ID {scenario_id} not found'
        }, status=404)
    except Exception as e:
        import traceback
        return JsonResponse({
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=400)