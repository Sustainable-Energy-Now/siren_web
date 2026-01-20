from django.shortcuts import render
from django.http import JsonResponse
from siren_web.models import facilities, supplyfactors, Technologies
import math

from ..services.generation_utils import (
    get_week_from_hour,
    get_month_from_hour,
    interpret_correlation
)

def supply_plot_view(request):
    """Main view to render the supply plot page"""
    # Get only non dispatchable facilities with renewable technology (renewable = 1)
    renewable_facilities = facilities.objects.filter(
        idtechnologies__renewable=1,
        idtechnologies__dispatchable=0
    ).select_related('idtechnologies').order_by('facility_name')
    
    # Get renewable and non dispatchable technologies
    renewable_technologies = Technologies.objects.filter(
        renewable=1,
        dispatchable=0
    ).order_by('technology_name')
    
    # Get available years from supplyfactors
    years = supplyfactors.objects.values_list('year', flat=True).distinct().order_by('year')
    
    context = {
        'facilities': renewable_facilities,
        'technologies': renewable_technologies,
        'years': list(years),
    }
    return render(request, 'facility_supply.html', context)

def get_supply_data(request):
    """API endpoint to get supply data for a facility and year"""
    facility_id = request.GET.get('facility_id')
    year = request.GET.get('year')
    aggregation = request.GET.get('aggregation', 'hour')  # hour, week, or month
    start_hour = request.GET.get('start_hour')  # Optional hour range
    end_hour = request.GET.get('end_hour')
    
    if not facility_id or not year:
        return JsonResponse({'error': 'facility_id and year are required'}, status=400)
    
    try:
        facility = facilities.objects.select_related('idtechnologies').get(idfacilities=facility_id)
        year = int(year)
        
        # Verify facility has renewable technology
        if not facility.idtechnologies.renewable:
            return JsonResponse({
                'error': f'{facility.facility_name} does not have renewable technology'
            }, status=400)
            
    except facilities.DoesNotExist:
        return JsonResponse({'error': 'Facility not found'}, status=404)
    except ValueError:
        return JsonResponse({'error': 'Invalid year format'}, status=400)
    
    # Get supply data for the facility and year
    supply_queryset = supplyfactors.objects.filter(
        idfacilities=facility,
        year=year
    )
    
    # Apply hour range filter if provided
    if start_hour and end_hour:
        try:
            start_hour = int(start_hour)
            end_hour = int(end_hour)
            supply_queryset = supply_queryset.filter(hour__gte=start_hour, hour__lte=end_hour)
        except ValueError:
            return JsonResponse({'error': 'Invalid hour range'}, status=400)
    
    supply_queryset = supply_queryset.order_by('hour')
    
    if not supply_queryset.exists():
        return JsonResponse({
            'error': f'No supply data found for {facility.facility_name} in {year}'
        }, status=404)
    
    # Aggregate data based on selected time period
    if aggregation == 'hour':
        data = aggregate_by_hour(supply_queryset)
        x_label = 'Hour of Year'
    elif aggregation == 'week':
        data = aggregate_by_week(supply_queryset)
        x_label = 'Week of Year'
    elif aggregation == 'month':
        data = aggregate_by_month(supply_queryset)
        x_label = 'Month of Year'
    else:
        return JsonResponse({'error': 'Invalid aggregation type'}, status=400)
    
    return JsonResponse({
        'facility_name': facility.facility_name,
        'facility_code': facility.facility_code,
        'technology': facility.idtechnologies.technology_name,
        'year': year,
        'aggregation': aggregation,
        'x_label': x_label,
        'periods': data['periods'],
        'quantum': data['quantum'],
        'supply': data['supply'],
        'total_periods': len(data['periods']),
        'start_hour': start_hour if start_hour else 1,
        'end_hour': end_hour if end_hour else max(data['periods']) if data['periods'] else 8760,
    })

def get_comparison_data(request):
    """API endpoint to compare supply data between two facilities"""
    facility1_id = request.GET.get('facility1_id')
    facility2_id = request.GET.get('facility2_id')
    year = request.GET.get('year')
    aggregation = request.GET.get('aggregation', 'hour')
    start_hour = request.GET.get('start_hour')
    end_hour = request.GET.get('end_hour')
    
    if not facility1_id or not facility2_id or not year:
        return JsonResponse({'error': 'Both facility IDs and year are required'}, status=400)
    
    try:
        facility1 = facilities.objects.select_related('idtechnologies').get(idfacilities=facility1_id)
        facility2 = facilities.objects.select_related('idtechnologies').get(idfacilities=facility2_id)
        year = int(year)
        
        # Verify both facilities have renewable technology
        if not facility1.idtechnologies.renewable or not facility2.idtechnologies.renewable:
            return JsonResponse({'error': 'Both facilities must have renewable technology'}, status=400)
            
    except facilities.DoesNotExist:
        return JsonResponse({'error': 'One or both facilities not found'}, status=404)
    except ValueError:
        return JsonResponse({'error': 'Invalid year format'}, status=400)
    
    # Get supply data for both facilities
    supply1_queryset = supplyfactors.objects.filter(
        idfacilities=facility1,
        year=year
    )
    
    supply2_queryset = supplyfactors.objects.filter(
        idfacilities=facility2,
        year=year
    )
    
    # Apply hour range filter if provided
    if start_hour and end_hour:
        try:
            start_hour = int(start_hour)
            end_hour = int(end_hour)
            supply1_queryset = supply1_queryset.filter(hour__gte=start_hour, hour__lte=end_hour)
            supply2_queryset = supply2_queryset.filter(hour__gte=start_hour, hour__lte=end_hour)
        except ValueError:
            return JsonResponse({'error': 'Invalid hour range'}, status=400)
    
    supply1_queryset = supply1_queryset.order_by('hour')
    supply2_queryset = supply2_queryset.order_by('hour')
    
    if not supply1_queryset.exists():
        return JsonResponse({
            'error': f'No supply data found for {facility1.facility_name} in {year}'
        }, status=404)
    
    if not supply2_queryset.exists():
        return JsonResponse({
            'error': f'No supply data found for {facility2.facility_name} in {year}'
        }, status=404)
    
    # Aggregate data based on selected time period
    if aggregation == 'hour':
        data1 = aggregate_by_hour(supply1_queryset)
        data2 = aggregate_by_hour(supply2_queryset)
        x_label = 'Hour of Year'
    elif aggregation == 'week':
        data1 = aggregate_by_week(supply1_queryset)
        data2 = aggregate_by_week(supply2_queryset)
        x_label = 'Week of Year'
    elif aggregation == 'month':
        data1 = aggregate_by_month(supply1_queryset)
        data2 = aggregate_by_month(supply2_queryset)
        x_label = 'Month of Year'
    else:
        return JsonResponse({'error': 'Invalid aggregation type'}, status=400)
    
    # Calculate correlation and complementarity metrics
    correlation_metrics = calculate_correlation_metrics(data1['quantum'], data2['quantum'])
    
    return JsonResponse({
        'facility1': {
            'name': facility1.facility_name,
            'code': facility1.facility_code,
            'technology': facility1.idtechnologies.technology_name,
        },
        'facility2': {
            'name': facility2.facility_name,
            'code': facility2.facility_code,
            'technology': facility2.idtechnologies.technology_name,
        },
        'year': year,
        'aggregation': aggregation,
        'x_label': x_label,
        'periods': data1['periods'],
        'facility1_quantum': data1['quantum'],
        'facility2_quantum': data2['quantum'],
        'correlation_metrics': correlation_metrics,
        'total_periods': len(data1['periods']),
    })

def calculate_correlation_metrics(data1, data2):
    """Calculate correlation and complementarity metrics between two datasets"""
    n = len(data1)
    
    if n != len(data2) or n == 0:
        return None
    
    # Calculate means
    mean1 = sum(data1) / n
    mean2 = sum(data2) / n
    
    # Calculate standard deviations
    variance1 = sum((x - mean1) ** 2 for x in data1) / n
    variance2 = sum((x - mean2) ** 2 for x in data2) / n
    std1 = math.sqrt(variance1)
    std2 = math.sqrt(variance2)
    
    # Calculate Pearson correlation coefficient
    if std1 == 0 or std2 == 0:
        correlation = 0
    else:
        covariance = sum((data1[i] - mean1) * (data2[i] - mean2) for i in range(n)) / n
        correlation = covariance / (std1 * std2)
    
    # Calculate complementarity score (inverse of absolute correlation)
    # Range: 0 (perfectly correlated) to 1 (perfectly anti-correlated or uncorrelated)
    complementarity = 1 - abs(correlation)
    
    # Calculate combined output variability
    combined = [(data1[i] + data2[i]) / 2 for i in range(n)]
    combined_mean = sum(combined) / n
    combined_variance = sum((x - combined_mean) ** 2 for x in combined) / n
    combined_std = math.sqrt(combined_variance)
    
    # Calculate coefficient of variation for each dataset and combined
    cv1 = (std1 / mean1 * 100) if mean1 > 0 else 0
    cv2 = (std2 / mean2 * 100) if mean2 > 0 else 0
    cv_combined = (combined_std / combined_mean * 100) if combined_mean > 0 else 0
    
    # Variability reduction (positive means combining reduces variability)
    variability_reduction = ((cv1 + cv2) / 2 - cv_combined)
    
    # Calculate times when outputs are complementary (one high, other low)
    threshold = 0.3  # 30% of max
    max1 = max(data1) if data1 else 1
    max2 = max(data2) if data2 else 1
    
    complementary_periods = 0
    for i in range(n):
        norm1 = data1[i] / max1 if max1 > 0 else 0
        norm2 = data2[i] / max2 if max2 > 0 else 0
        
        # One is high while other is low
        if (norm1 > threshold and norm2 < threshold) or (norm2 > threshold and norm1 < threshold):
            complementary_periods += 1
    
    complementary_percentage = (complementary_periods / n * 100) if n > 0 else 0
    
    return {
        'correlation': round(correlation, 4),
        'complementarity_score': round(complementarity, 4),
        'variability_reduction': round(variability_reduction, 2),
        'cv_facility1': round(cv1, 2),
        'cv_facility2': round(cv2, 2),
        'cv_combined': round(cv_combined, 2),
        'complementary_periods_pct': round(complementary_percentage, 2),
        'interpretation': interpret_correlation(correlation, complementarity, variability_reduction)
    }

# Note: interpret_correlation is now imported from generation_utils

def aggregate_by_hour(queryset):
    """Return hourly data (no aggregation)"""
    data = queryset.values('hour', 'quantum', 'supply')
    
    periods = []
    quantum_values = []
    supply_values = []
    
    for entry in data:
        periods.append(entry['hour'])
        quantum_values.append(entry['quantum'] if entry['quantum'] is not None else 0)
        supply_values.append(entry['supply'] if entry['supply'] is not None else 0)
    
    return {
        'periods': periods,
        'quantum': quantum_values,
        'supply': supply_values
    }

def aggregate_by_week(queryset):
    """Aggregate data by week using shared utilities"""
    periods = []
    quantum_values = []
    supply_values = []

    week_data = {}

    for entry in queryset.values('hour', 'quantum', 'supply'):
        week = get_week_from_hour(entry['hour'])

        if week not in week_data:
            week_data[week] = {
                'quantum_sum': 0,
                'supply_sum': 0,
                'count': 0
            }

        week_data[week]['quantum_sum'] += entry['quantum'] if entry['quantum'] is not None else 0
        week_data[week]['supply_sum'] += entry['supply'] if entry['supply'] is not None else 0
        week_data[week]['count'] += 1

    for week in sorted(week_data.keys()):
        periods.append(week)
        quantum_values.append(week_data[week]['quantum_sum'] / week_data[week]['count'])
        supply_values.append(week_data[week]['supply_sum'] / week_data[week]['count'])

    return {
        'periods': periods,
        'quantum': quantum_values,
        'supply': supply_values
    }

def aggregate_by_month(queryset):
    """Aggregate data by month using shared utilities"""
    periods = []
    quantum_values = []
    supply_values = []

    month_data = {}

    for entry in queryset.values('hour', 'quantum', 'supply'):
        month = get_month_from_hour(entry['hour'])

        if month not in month_data:
            month_data[month] = {
                'quantum_sum': 0,
                'supply_sum': 0,
                'count': 0
            }

        month_data[month]['quantum_sum'] += entry['quantum'] if entry['quantum'] is not None else 0
        month_data[month]['supply_sum'] += entry['supply'] if entry['supply'] is not None else 0
        month_data[month]['count'] += 1

    for month in sorted(month_data.keys()):
        periods.append(month)
        quantum_values.append(month_data[month]['quantum_sum'] / month_data[month]['count'])
        supply_values.append(month_data[month]['supply_sum'] / month_data[month]['count'])

    return {
        'periods': periods,
        'quantum': quantum_values,
        'supply': supply_values
    }

def get_facility_years(request):
    """API endpoint to get available years for a specific facility"""
    facility_id = request.GET.get('facility_id')
    
    if not facility_id:
        return JsonResponse({'error': 'facility_id is required'}, status=400)
    
    try:
        facility = facilities.objects.get(idfacilities=facility_id)
    except facilities.DoesNotExist:
        return JsonResponse({'error': 'Facility not found'}, status=404)
    
    # Get years with data for this facility
    years = supplyfactors.objects.filter(
        idfacilities=facility
    ).values_list('year', flat=True).distinct().order_by('year')
    
    return JsonResponse({
        'facility_name': facility.facility_name,
        'years': list(years),
    })

def get_technology_data(request):
    """API endpoint to get aggregated supply data for one or more technology types"""
    technology_ids = request.GET.getlist('technology_id[]')  # Get list of technology IDs
    year = request.GET.get('year')
    aggregation = request.GET.get('aggregation', 'hour')
    start_hour = request.GET.get('start_hour')
    end_hour = request.GET.get('end_hour')
    
    # Validate inputs
    if not technology_ids or len(technology_ids) == 0:
        return JsonResponse({'error': 'At least one technology must be selected'}, status=400)
    
    if not year:
        return JsonResponse({'error': 'Year is required'}, status=400)
    
    try:
        # Get all selected technologies
        technologies = Technologies.objects.filter(idtechnologies__in=technology_ids)
        
        if not technologies.exists():
            return JsonResponse({'error': 'No valid technologies found'}, status=404)
        
        # Verify all technologies are renewable
        non_renewable = technologies.filter(renewable=0)
        if non_renewable.exists():
            non_renewable_names = ', '.join(non_renewable.values_list('technology_name', flat=True))
            return JsonResponse({
                'error': f'The following technologies are not renewable: {non_renewable_names}'
            }, status=400)
        
        year = int(year)
            
    except ValueError:
        return JsonResponse({'error': 'Invalid year format'}, status=400)
    
    # Get all facilities with any of the selected technologies
    tech_facilities = facilities.objects.filter(
        idtechnologies__in=technologies
    )
    
    if not tech_facilities.exists():
        return JsonResponse({
            'error': f'No facilities found with the selected technologies'
        }, status=404)
    
    # Get supply data for all facilities with the selected technologies
    supply_queryset = supplyfactors.objects.filter(
        idfacilities__idtechnologies__in=technologies,
        year=year
    )
    
    # Apply hour range filter if provided
    if start_hour and end_hour:
        try:
            start_hour = int(start_hour)
            end_hour = int(end_hour)
            supply_queryset = supply_queryset.filter(hour__gte=start_hour, hour__lte=end_hour)
        except ValueError:
            return JsonResponse({'error': 'Invalid hour range'}, status=400)
    
    supply_queryset = supply_queryset.order_by('hour')
    
    if not supply_queryset.exists():
        return JsonResponse({
            'error': f'No supply data found for the selected technologies in {year}'
        }, status=404)
    
    # Aggregate by hour first, summing across all facilities
    hour_aggregated = {}
    for entry in supply_queryset.values('hour', 'quantum', 'supply'):
        hour = entry['hour']
        if hour not in hour_aggregated:
            hour_aggregated[hour] = {'quantum': 0, 'supply': 0}
        hour_aggregated[hour]['quantum'] += entry['quantum'] if entry['quantum'] is not None else 0
        hour_aggregated[hour]['supply'] += entry['supply'] if entry['supply'] is not None else 0
    
    # Convert to sorted lists
    hours = sorted(hour_aggregated.keys())
    quantum_by_hour = [hour_aggregated[h]['quantum'] for h in hours]
    supply_by_hour = [hour_aggregated[h]['supply'] for h in hours]
    
    # Create a mock queryset-like structure for time aggregation
    class HourData:
        def __init__(self, hours, quantum, supply):
            self.data = [{'hour': h, 'quantum': q, 'supply': s} 
                        for h, q, s in zip(hours, quantum, supply)]
        
        def values(self, *fields):
            return self.data
    
    hour_data = HourData(hours, quantum_by_hour, supply_by_hour)
    
    # Now aggregate by selected time period
    if aggregation == 'hour':
        data = {
            'periods': hours,
            'quantum': quantum_by_hour,
            'supply': supply_by_hour
        }
        x_label = 'Hour of Year'
    elif aggregation == 'week':
        data = aggregate_by_week(hour_data)
        x_label = 'Week of Year'
    elif aggregation == 'month':
        data = aggregate_by_month(hour_data)
        x_label = 'Month of Year'
    else:
        return JsonResponse({'error': 'Invalid aggregation type'}, status=400)
    
    # Count facilities and get technology names
    facility_count = tech_facilities.count()
    facility_names = list(tech_facilities.values_list('facility_name', flat=True))
    technology_names = list(technologies.values_list('technology_name', flat=True))
    
    # Get facility count per technology
    tech_breakdown = []
    for tech in technologies:
        count = tech_facilities.filter(idtechnologies=tech).count()
        tech_breakdown.append({
            'name': tech.technology_name,
            'facility_count': count
        })
    
    return JsonResponse({
        'technology_names': technology_names,  # List of technology names
        'technology_breakdown': tech_breakdown,  # Breakdown by technology
        'year': year,
        'aggregation': aggregation,
        'x_label': x_label,
        'periods': data['periods'],
        'quantum': data['quantum'],
        'supply': data['supply'],
        'total_periods': len(data['periods']),
        'facility_count': facility_count,
        'facilities': facility_names[:10],  # Return first 10 facility names
        'total_facilities': facility_count
    })
    
def get_technology_comparison_data(request):
    """API endpoint to compare supply data between two groups of technology types"""
    technology1_ids = request.GET.getlist('technology1_id[]')
    technology2_ids = request.GET.getlist('technology2_id[]')
    year = request.GET.get('year')
    aggregation = request.GET.get('aggregation', 'hour')
    start_hour = request.GET.get('start_hour')
    end_hour = request.GET.get('end_hour')
    
    # Validate inputs
    if not technology1_ids or len(technology1_ids) == 0:
        return JsonResponse({'error': 'At least one technology must be selected for Group 1'}, status=400)
    
    if not technology2_ids or len(technology2_ids) == 0:
        return JsonResponse({'error': 'At least one technology must be selected for Group 2'}, status=400)
    
    if not year:
        return JsonResponse({'error': 'Year is required'}, status=400)
    
    try:
        technologies1 = Technologies.objects.filter(idtechnologies__in=technology1_ids)
        technologies2 = Technologies.objects.filter(idtechnologies__in=technology2_ids)
        
        if not technologies1.exists():
            return JsonResponse({'error': 'No valid technologies found for Group 1'}, status=404)
        
        if not technologies2.exists():
            return JsonResponse({'error': 'No valid technologies found for Group 2'}, status=404)
        
        year = int(year)
        
        # Verify all technologies are renewable
        non_renewable1 = technologies1.filter(renewable=0)
        non_renewable2 = technologies2.filter(renewable=0)
        
        if non_renewable1.exists() or non_renewable2.exists():
            non_renewable_names = []
            if non_renewable1.exists():
                non_renewable_names.extend(non_renewable1.values_list('technology_name', flat=True))
            if non_renewable2.exists():
                non_renewable_names.extend(non_renewable2.values_list('technology_name', flat=True))
            return JsonResponse({
                'error': f'The following technologies are not renewable: {", ".join(non_renewable_names)}'
            }, status=400)
            
    except ValueError:
        return JsonResponse({'error': 'Invalid year format'}, status=400)
    
    # Get aggregated data for both technology groups
    def get_tech_group_aggregated_data(technologies, year, aggregation, start_hour, end_hour):
        supply_queryset = supplyfactors.objects.filter(
            idfacilities__idtechnologies__in=technologies,
            year=year
        )
        
        # Apply hour range filter if provided
        if start_hour and end_hour:
            try:
                start_hour_int = int(start_hour)
                end_hour_int = int(end_hour)
                supply_queryset = supply_queryset.filter(hour__gte=start_hour_int, hour__lte=end_hour_int)
            except ValueError:
                pass
        
        supply_queryset = supply_queryset.order_by('hour')
        
        if not supply_queryset.exists():
            return None
        
        # Aggregate by hour first
        hour_aggregated = {}
        for entry in supply_queryset.values('hour', 'quantum', 'supply'):
            hour = entry['hour']
            if hour not in hour_aggregated:
                hour_aggregated[hour] = {'quantum': 0, 'supply': 0}
            hour_aggregated[hour]['quantum'] += entry['quantum'] if entry['quantum'] is not None else 0
            hour_aggregated[hour]['supply'] += entry['supply'] if entry['supply'] is not None else 0
        
        hours = sorted(hour_aggregated.keys())
        quantum_by_hour = [hour_aggregated[h]['quantum'] for h in hours]
        supply_by_hour = [hour_aggregated[h]['supply'] for h in hours]
        
        class HourData:
            def __init__(self, hours, quantum, supply):
                self.data = [{'hour': h, 'quantum': q, 'supply': s} 
                            for h, q, s in zip(hours, quantum, supply)]
            
            def values(self, *fields):
                return self.data
        
        hour_data = HourData(hours, quantum_by_hour, supply_by_hour)
        
        if aggregation == 'hour':
            return {'periods': hours, 'quantum': quantum_by_hour, 'supply': supply_by_hour}
        elif aggregation == 'week':
            return aggregate_by_week(hour_data)
        elif aggregation == 'month':
            return aggregate_by_month(hour_data)
        
        return None
    
    data1 = get_tech_group_aggregated_data(technologies1, year, aggregation, start_hour, end_hour)
    data2 = get_tech_group_aggregated_data(technologies2, year, aggregation, start_hour, end_hour)
    
    if data1 is None:
        tech1_names = ', '.join(technologies1.values_list('technology_name', flat=True))
        return JsonResponse({
            'error': f'No supply data found for {tech1_names} in {year}'
        }, status=404)
    
    if data2 is None:
        tech2_names = ', '.join(technologies2.values_list('technology_name', flat=True))
        return JsonResponse({
            'error': f'No supply data found for {tech2_names} in {year}'
        }, status=404)
    
    # Calculate correlation metrics
    correlation_metrics = calculate_correlation_metrics(data1['quantum'], data2['quantum'])
    
    # Get facility counts and names for each group
    facilities1 = facilities.objects.filter(idtechnologies__in=technologies1)
    facilities2 = facilities.objects.filter(idtechnologies__in=technologies2)
    
    facility1_count = facilities1.count()
    facility2_count = facilities2.count()
    
    technology1_names = list(technologies1.values_list('technology_name', flat=True))
    technology2_names = list(technologies2.values_list('technology_name', flat=True))
    
    # Get facility count per technology for both groups
    tech1_breakdown = []
    for tech in technologies1:
        count = facilities1.filter(idtechnologies=tech).count()
        tech1_breakdown.append({
            'name': tech.technology_name,
            'facility_count': count
        })
    
    tech2_breakdown = []
    for tech in technologies2:
        count = facilities2.filter(idtechnologies=tech).count()
        tech2_breakdown.append({
            'name': tech.technology_name,
            'facility_count': count
        })
    
    # Determine x_label
    if aggregation == 'hour':
        x_label = 'Hour of Year'
    elif aggregation == 'week':
        x_label = 'Week of Year'
    else:
        x_label = 'Month of Year'
    
    return JsonResponse({
        'technology1': {
            'names': technology1_names,
            'facility_count': facility1_count,
            'breakdown': tech1_breakdown,
        },
        'technology2': {
            'names': technology2_names,
            'facility_count': facility2_count,
            'breakdown': tech2_breakdown,
        },
        'year': year,
        'aggregation': aggregation,
        'x_label': x_label,
        'periods': data1['periods'],
        'technology1_quantum': data1['quantum'],
        'technology2_quantum': data2['quantum'],
        'correlation_metrics': correlation_metrics,
        'total_periods': len(data1['periods']),
    })