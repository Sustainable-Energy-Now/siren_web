from django.shortcuts import render
from django.http import JsonResponse
from siren_web.models import facilities, supplyfactors, Technologies
import math

def get_hour_range_from_months(start_month, end_month):
    """Convert month numbers to hour ranges (1-based months and hours)"""
    # Days in each month for a non-leap year
    days_per_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    
    # Calculate start hour (beginning of start_month)
    start_hour = sum(days_per_month[:start_month-1]) * 24 + 1
    
    # Calculate end hour (end of end_month)
    end_hour = sum(days_per_month[:end_month]) * 24
    
    return start_hour, end_hour

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

def interpret_correlation(correlation, complementarity, variability_reduction):
    """Provide human-readable interpretation of correlation metrics"""
    interpretation = []
    
    # Correlation interpretation
    if abs(correlation) < 0.3:
        interpretation.append("Weak correlation - outputs are largely independent")
    elif abs(correlation) < 0.7:
        interpretation.append("Moderate correlation")
    else:
        interpretation.append("Strong correlation")
    
    if correlation < 0:
        interpretation.append("negative (anti-correlated - when one is high, other tends to be low)")
    elif correlation > 0:
        interpretation.append("positive (when one is high, other tends to be high)")
    
    # Complementarity interpretation
    if complementarity > 0.7:
        interpretation.append("High complementarity - excellent for portfolio diversification")
    elif complementarity > 0.4:
        interpretation.append("Moderate complementarity - good for portfolio balance")
    else:
        interpretation.append("Low complementarity - outputs follow similar patterns")
    
    # Variability reduction interpretation
    if variability_reduction > 10:
        interpretation.append(f"Combining these sources significantly reduces output variability ({variability_reduction:.1f}% reduction)")
    elif variability_reduction > 0:
        interpretation.append(f"Combining these sources moderately reduces variability ({variability_reduction:.1f}% reduction)")
    else:
        interpretation.append("Combining these sources does not reduce variability")
    
    return " | ".join(interpretation)

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
    """Aggregate data by week (assuming 8760 hours in year)"""
    periods = []
    quantum_values = []
    supply_values = []
    
    # Group by week (168 hours per week)
    hours_per_week = 168
    week_data = {}
    
    for entry in queryset.values('hour', 'quantum', 'supply'):
        week = (entry['hour'] - 1) // hours_per_week + 1  # Week 1-52
        
        if week not in week_data:
            week_data[week] = {
                'quantum_sum': 0,
                'supply_sum': 0,
                'count': 0
            }
        
        week_data[week]['quantum_sum'] += entry['quantum'] if entry['quantum'] is not None else 0
        week_data[week]['supply_sum'] += entry['supply'] if entry['supply'] is not None else 0
        week_data[week]['count'] += 1
    
    # Calculate averages for each week
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
    """Aggregate data by month (assuming 8760 hours in year)"""
    periods = []
    quantum_values = []
    supply_values = []
    
    # Approximate hours per month (730 hours average)
    hours_per_month = [744, 672, 744, 720, 744, 720, 744, 744, 720, 744, 720, 744]  # Days * 24
    cumulative_hours = [0]
    for hours in hours_per_month:
        cumulative_hours.append(cumulative_hours[-1] + hours)
    
    month_data = {}
    
    for entry in queryset.values('hour', 'quantum', 'supply'):
        hour = entry['hour']
        
        # Determine which month this hour belongs to
        month = 12  # Default to December
        for i in range(12):
            if cumulative_hours[i] < hour <= cumulative_hours[i + 1]:
                month = i + 1
                break
        
        if month not in month_data:
            month_data[month] = {
                'quantum_sum': 0,
                'supply_sum': 0,
                'count': 0
            }
        
        month_data[month]['quantum_sum'] += entry['quantum'] if entry['quantum'] is not None else 0
        month_data[month]['supply_sum'] += entry['supply'] if entry['supply'] is not None else 0
        month_data[month]['count'] += 1
    
    # Calculate averages for each month
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
    """API endpoint to get aggregated supply data for all facilities of a technology type"""
    technology_id = request.GET.get('technology_id')
    year = request.GET.get('year')
    aggregation = request.GET.get('aggregation', 'hour')
    start_hour = request.GET.get('start_hour')
    end_hour = request.GET.get('end_hour')
    
    if not technology_id or not year:
        return JsonResponse({'error': 'technology_id and year are required'}, status=400)
    
    try:
        technology = Technologies.objects.get(idtechnologies=technology_id)
        year = int(year)
        
        # Verify technology is renewable
        if not technology.renewable:
            return JsonResponse({
                'error': f'{technology.technology_name} is not a renewable technology'
            }, status=400)
            
    except Technologies.DoesNotExist:
        return JsonResponse({'error': 'Technology not found'}, status=404)
    except ValueError:
        return JsonResponse({'error': 'Invalid year format'}, status=400)
    
    # Get all facilities with this technology
    tech_facilities = facilities.objects.filter(
        idtechnologies=technology
    )
    
    if not tech_facilities.exists():
        return JsonResponse({
            'error': f'No facilities found with {technology.technology_name} technology'
        }, status=404)
    
    # Get supply data for all facilities with this technology
    supply_queryset = supplyfactors.objects.filter(
        idfacilities__idtechnologies=technology,
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
            'error': f'No supply data found for {technology.technology_name} facilities in {year}'
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
    
    # Count facilities
    facility_count = tech_facilities.count()
    facility_names = list(tech_facilities.values_list('facility_name', flat=True))
    
    return JsonResponse({
        'technology_name': technology.technology_name,
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
    """API endpoint to compare supply data between two technology types"""
    technology1_id = request.GET.get('technology1_id')
    technology2_id = request.GET.get('technology2_id')
    year = request.GET.get('year')
    aggregation = request.GET.get('aggregation', 'hour')
    start_hour = request.GET.get('start_hour')
    end_hour = request.GET.get('end_hour')
    
    if not technology1_id or not technology2_id or not year:
        return JsonResponse({'error': 'Both technology IDs and year are required'}, status=400)
    
    try:
        technology1 = Technologies.objects.get(idtechnologies=technology1_id)
        technology2 = Technologies.objects.get(idtechnologies=technology2_id)
        year = int(year)
        
        # Verify both technologies are renewable
        if not technology1.renewable or not technology2.renewable:
            return JsonResponse({'error': 'Both technologies must be renewable'}, status=400)
            
    except Technologies.DoesNotExist:
        return JsonResponse({'error': 'One or both technologies not found'}, status=404)
    except ValueError:
        return JsonResponse({'error': 'Invalid year format'}, status=400)
    
    # Get aggregated data for both technologies
    def get_tech_aggregated_data(technology, year, aggregation, start_hour, end_hour):
        supply_queryset = supplyfactors.objects.filter(
            idfacilities__idtechnologies=technology,
            year=year
        )
        
        # Apply hour range filter if provided
        if start_hour and end_hour:
            try:
                start_hour = int(start_hour)
                end_hour = int(end_hour)
                supply_queryset = supply_queryset.filter(hour__gte=start_hour, hour__lte=end_hour)
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
    
    data1 = get_tech_aggregated_data(technology1, year, aggregation, start_hour, end_hour)
    data2 = get_tech_aggregated_data(technology2, year, aggregation, start_hour, end_hour)
    
    if data1 is None:
        return JsonResponse({
            'error': f'No supply data found for {technology1.technology_name} in {year}'
        }, status=404)
    
    if data2 is None:
        return JsonResponse({
            'error': f'No supply data found for {technology2.technology_name} in {year}'
        }, status=404)
    
    # Calculate correlation metrics
    correlation_metrics = calculate_correlation_metrics(data1['quantum'], data2['quantum'])
    
    # Get facility counts
    facility1_count = facilities.objects.filter(idtechnologies=technology1).count()
    facility2_count = facilities.objects.filter(idtechnologies=technology2).count()
    
    # Determine x_label
    if aggregation == 'hour':
        x_label = 'Hour of Year'
    elif aggregation == 'week':
        x_label = 'Week of Year'
    else:
        x_label = 'Month of Year'
    
    return JsonResponse({
        'technology1': {
            'name': technology1.technology_name,
            'facility_count': facility1_count,
        },
        'technology2': {
            'name': technology2.technology_name,
            'facility_count': facility2_count,
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
