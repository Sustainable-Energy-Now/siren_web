from django.shortcuts import render
from django.http import JsonResponse
from siren_web.models import facilities, FacilityScada, Technologies
from django.db.models import Min, Max
from datetime import datetime, timedelta
import math


def get_hour_of_year(dt):
    """Calculate hour of year from datetime (1-based)"""
    start_of_year = datetime(dt.year, 1, 1, tzinfo=dt.tzinfo)
    delta = dt - start_of_year
    # Convert to hours and add 1 for 1-based indexing
    return int(delta.total_seconds() / 3600) + 1


def get_hour_range_from_months(start_month, end_month):
    """Convert month numbers to hour ranges (1-based months and hours)"""
    days_per_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    start_hour = sum(days_per_month[:start_month-1]) * 24 + 1
    end_hour = sum(days_per_month[:end_month]) * 24
    return start_hour, end_hour


def scada_plot_view(request):
    """Main view to render the SCADA plot page"""
    # Get all facilities (SCADA data can be for any facility)
    all_facilities = facilities.objects.select_related('idtechnologies').order_by('facility_name')
    
    # Get all technologies
    all_technologies = Technologies.objects.all().order_by('technology_name')
    
    # Get available years from FacilityScada dispatch_interval
    years_queryset = FacilityScada.objects.dates('dispatch_interval', 'year', order='ASC')
    years = [dt.year for dt in years_queryset]
    
    context = {
        'facilities': all_facilities,
        'technologies': all_technologies,
        'years': years,
    }
    return render(request, 'facility_scada.html', context)


def get_scada_data(request):
    """API endpoint to get SCADA data for multiple facilities"""
    facility_ids = request.GET.getlist('facility_id[]')  # Changed to support multiple
    year = request.GET.get('year')
    aggregation = request.GET.get('aggregation', 'hour')
    start_hour = request.GET.get('start_hour')
    end_hour = request.GET.get('end_hour')
    
    if not facility_ids or len(facility_ids) == 0:
        return JsonResponse({'error': 'At least one facility must be selected'}, status=400)
    
    if not year:
        return JsonResponse({'error': 'Year is required'}, status=400)
    
    try:
        selected_facilities = facilities.objects.filter(
            idfacilities__in=facility_ids
        ).select_related('idtechnologies')
        
        if not selected_facilities.exists():
            return JsonResponse({'error': 'No valid facilities found'}, status=404)
        
        year = int(year)
    except ValueError:
        return JsonResponse({'error': 'Invalid year format'}, status=400)
    
    # Parse hour range
    if start_hour and end_hour:
        try:
            start_hour = int(start_hour)
            end_hour = int(end_hour)
        except ValueError:
            return JsonResponse({'error': 'Invalid hour range'}, status=400)
    else:
        start_hour = None
        end_hour = None
    
    # Get data for each facility
    facility_data = []
    for facility in selected_facilities:
        scada_queryset = FacilityScada.objects.filter(
            facility=facility,
            dispatch_interval__year=year
        ).order_by('dispatch_interval')
        
        if not scada_queryset.exists():
            continue
        
        # Convert to hour-based data
        hour_data = []
        for record in scada_queryset:
            hour = get_hour_of_year(record.dispatch_interval)
            if start_hour and end_hour:
                if hour < start_hour or hour > end_hour:
                    continue
            hour_data.append({
                'hour': hour,
                'quantity': float(record.quantity) if record.quantity else 0
            })
        
        if not hour_data:
            continue
        
        # Aggregate data based on selected time period
        if aggregation == 'hour':
            data = aggregate_scada_by_hour(hour_data)
            x_label = 'Hour of Year'
        elif aggregation == 'week':
            data = aggregate_scada_by_week(hour_data)
            x_label = 'Week of Year'
        elif aggregation == 'month':
            data = aggregate_scada_by_month(hour_data)
            x_label = 'Month of Year'
        else:
            return JsonResponse({'error': 'Invalid aggregation type'}, status=400)
        
        facility_data.append({
            'facility_name': facility.facility_name,
            'facility_code': facility.facility_code,
            'technology': facility.idtechnologies.technology_name,
            'periods': data['periods'],
            'quantity': data['quantity']
        })
    
    if not facility_data:
        return JsonResponse({
            'error': f'No SCADA data found for selected facilities in {year}'
        }, status=404)
    
    return JsonResponse({
        'facilities': facility_data,
        'year': year,
        'aggregation': aggregation,
        'x_label': x_label,
        'total_periods': len(facility_data[0]['periods']) if facility_data else 0,
        'start_hour': start_hour if start_hour else 1,
        'end_hour': end_hour if end_hour else 8760,
        'facility_count': len(facility_data)
    })


def get_scada_comparison_data(request):
    """API endpoint to compare SCADA data between two groups of facilities"""
    facility1_ids = request.GET.getlist('facility1_id[]')  # Changed to support multiple
    facility2_ids = request.GET.getlist('facility2_id[]')  # Changed to support multiple
    year = request.GET.get('year')
    aggregation = request.GET.get('aggregation', 'hour')
    start_hour = request.GET.get('start_hour')
    end_hour = request.GET.get('end_hour')
    
    if not facility1_ids or len(facility1_ids) == 0:
        return JsonResponse({'error': 'At least one facility must be selected for Group 1'}, status=400)
    
    if not facility2_ids or len(facility2_ids) == 0:
        return JsonResponse({'error': 'At least one facility must be selected for Group 2'}, status=400)
    
    if not year:
        return JsonResponse({'error': 'Year is required'}, status=400)
    
    try:
        facilities1 = facilities.objects.filter(
            idfacilities__in=facility1_ids
        ).select_related('idtechnologies')
        
        facilities2 = facilities.objects.filter(
            idfacilities__in=facility2_ids
        ).select_related('idtechnologies')
        
        if not facilities1.exists():
            return JsonResponse({'error': 'No valid facilities found for Group 1'}, status=404)
        
        if not facilities2.exists():
            return JsonResponse({'error': 'No valid facilities found for Group 2'}, status=404)
        
        year = int(year)
    except ValueError:
        return JsonResponse({'error': 'Invalid year format'}, status=400)
    
    # Parse hour range
    if start_hour and end_hour:
        try:
            start_hour_int = int(start_hour)
            end_hour_int = int(end_hour)
        except ValueError:
            return JsonResponse({'error': 'Invalid hour range'}, status=400)
    else:
        start_hour_int = None
        end_hour_int = None
    
    # Get aggregated data for both facility groups
    def get_facility_group_scada_data(facility_list, year, start_hour, end_hour):
        scada_queryset = FacilityScada.objects.filter(
            facility__in=facility_list,
            dispatch_interval__year=year
        ).order_by('dispatch_interval')
        
        if not scada_queryset.exists():
            return None
        
        # Aggregate by hour first
        hour_aggregated = {}
        for record in scada_queryset:
            hour = get_hour_of_year(record.dispatch_interval)
            if start_hour and end_hour:
                if hour < start_hour or hour > end_hour:
                    continue
            if hour not in hour_aggregated:
                hour_aggregated[hour] = 0
            hour_aggregated[hour] += float(record.quantity) if record.quantity else 0
        
        if not hour_aggregated:
            return None
        
        hours = sorted(hour_aggregated.keys())
        quantity_by_hour = [hour_aggregated[h] for h in hours]
        
        return {
            'hours': hours,
            'quantity_by_hour': quantity_by_hour,
            'facility_count': facility_list.count(),
            'facilities': facility_list
        }
    
    result1 = get_facility_group_scada_data(facilities1, year, start_hour_int, end_hour_int)
    result2 = get_facility_group_scada_data(facilities2, year, start_hour_int, end_hour_int)
    
    if result1 is None:
        facility1_names = ', '.join(facilities1.values_list('facility_name', flat=True))
        return JsonResponse({
            'error': f'No SCADA data found for {facility1_names} in {year}'
        }, status=404)
    
    if result2 is None:
        facility2_names = ', '.join(facilities2.values_list('facility_name', flat=True))
        return JsonResponse({
            'error': f'No SCADA data found for {facility2_names} in {year}'
        }, status=404)
    
    # Create hour data structures for aggregation
    hour_data1 = [{'hour': h, 'quantity': q} 
                  for h, q in zip(result1['hours'], result1['quantity_by_hour'])]
    hour_data2 = [{'hour': h, 'quantity': q} 
                  for h, q in zip(result2['hours'], result2['quantity_by_hour'])]
    
    # Aggregate based on time period
    if aggregation == 'hour':
        data1 = {'periods': result1['hours'], 'quantity': result1['quantity_by_hour']}
        data2 = {'periods': result2['hours'], 'quantity': result2['quantity_by_hour']}
        x_label = 'Hour of Year'
    elif aggregation == 'week':
        data1 = aggregate_scada_by_week(hour_data1)
        data2 = aggregate_scada_by_week(hour_data2)
        x_label = 'Week of Year'
    elif aggregation == 'month':
        data1 = aggregate_scada_by_month(hour_data1)
        data2 = aggregate_scada_by_month(hour_data2)
        x_label = 'Month of Year'
    else:
        return JsonResponse({'error': 'Invalid aggregation type'}, status=400)
    
    # Calculate correlation metrics
    correlation_metrics = calculate_correlation_metrics(data1['quantity'], data2['quantity'])
    
    facility1_names = list(facilities1.values_list('facility_name', flat=True))
    facility2_names = list(facilities2.values_list('facility_name', flat=True))
    
    # Get technology breakdown for each group
    tech1_breakdown = []
    technologies1 = facilities1.values_list('idtechnologies__technology_name', flat=True).distinct()
    for tech_name in technologies1:
        count = facilities1.filter(idtechnologies__technology_name=tech_name).count()
        tech1_breakdown.append({
            'name': tech_name,
            'facility_count': count
        })
    
    tech2_breakdown = []
    technologies2 = facilities2.values_list('idtechnologies__technology_name', flat=True).distinct()
    for tech_name in technologies2:
        count = facilities2.filter(idtechnologies__technology_name=tech_name).count()
        tech2_breakdown.append({
            'name': tech_name,
            'facility_count': count
        })
    
    return JsonResponse({
        'facility_group1': {
            'names': facility1_names,
            'facility_count': result1['facility_count'],
            'breakdown': tech1_breakdown,
        },
        'facility_group2': {
            'names': facility2_names,
            'facility_count': result2['facility_count'],
            'breakdown': tech2_breakdown,
        },
        'year': year,
        'aggregation': aggregation,
        'x_label': x_label,
        'periods': data1['periods'],
        'group1_quantity': data1['quantity'],
        'group2_quantity': data2['quantity'],
        'correlation_metrics': correlation_metrics,
        'total_periods': len(data1['periods']),
    })


def get_scada_technology_data(request):
    """API endpoint to get aggregated SCADA data for all facilities of selected technologies"""
    technology_ids = request.GET.getlist('technology_id[]')
    year = request.GET.get('year')
    aggregation = request.GET.get('aggregation', 'hour')
    start_hour = request.GET.get('start_hour')
    end_hour = request.GET.get('end_hour')
    
    if not technology_ids or len(technology_ids) == 0:
        return JsonResponse({'error': 'At least one technology must be selected'}, status=400)
    
    if not year:
        return JsonResponse({'error': 'Year is required'}, status=400)
    
    try:
        technologies = Technologies.objects.filter(idtechnologies__in=technology_ids)
        if not technologies.exists():
            return JsonResponse({'error': 'No valid technologies found'}, status=404)
        
        year = int(year)
    except ValueError:
        return JsonResponse({'error': 'Invalid year format'}, status=400)
    
    # Parse hour range
    if start_hour and end_hour:
        try:
            start_hour = int(start_hour)
            end_hour = int(end_hour)
        except ValueError:
            return JsonResponse({'error': 'Invalid hour range'}, status=400)
    else:
        start_hour = None
        end_hour = None
    
    # Get facilities with these technologies
    tech_facilities = facilities.objects.filter(idtechnologies__in=technologies)
    facility_count = tech_facilities.count()
    
    if facility_count == 0:
        return JsonResponse({'error': 'No facilities found for selected technologies'}, status=404)
    
    # Get SCADA data for all these facilities
    scada_queryset = FacilityScada.objects.filter(
        facility__in=tech_facilities,
        dispatch_interval__year=year
    ).order_by('dispatch_interval')
    
    if not scada_queryset.exists():
        tech_names = ', '.join(technologies.values_list('technology_name', flat=True))
        return JsonResponse({
            'error': f'No SCADA data found for {tech_names} in {year}'
        }, status=404)
    
    # Convert to hour-based data and aggregate across facilities
    hour_aggregated = {}
    for record in scada_queryset:
        hour = get_hour_of_year(record.dispatch_interval)
        if start_hour and end_hour:
            if hour < start_hour or hour > end_hour:
                continue
        if hour not in hour_aggregated:
            hour_aggregated[hour] = 0
        hour_aggregated[hour] += float(record.quantity) if record.quantity else 0
    
    if not hour_aggregated:
        return JsonResponse({
            'error': 'No SCADA data found in specified hour range'
        }, status=404)
    
    hours = sorted(hour_aggregated.keys())
    quantity_by_hour = [hour_aggregated[h] for h in hours]
    
    hour_data = [{'hour': h, 'quantity': q} for h, q in zip(hours, quantity_by_hour)]
    
    # Aggregate based on time period
    if aggregation == 'hour':
        data = {'periods': hours, 'quantity': quantity_by_hour}
        x_label = 'Hour of Year'
    elif aggregation == 'week':
        data = aggregate_scada_by_week(hour_data)
        x_label = 'Week of Year'
    elif aggregation == 'month':
        data = aggregate_scada_by_month(hour_data)
        x_label = 'Month of Year'
    else:
        return JsonResponse({'error': 'Invalid aggregation type'}, status=400)
    
    technology_names = list(technologies.values_list('technology_name', flat=True))
    facility_names = list(tech_facilities.values_list('facility_name', flat=True))
    
    # Get facility count per technology
    tech_breakdown = []
    for tech in technologies:
        count = tech_facilities.filter(idtechnologies=tech).count()
        tech_breakdown.append({
            'name': tech.technology_name,
            'facility_count': count
        })
    
    return JsonResponse({
        'technology_names': technology_names,
        'technology_breakdown': tech_breakdown,
        'year': year,
        'aggregation': aggregation,
        'x_label': x_label,
        'periods': data['periods'],
        'quantity': data['quantity'],
        'total_periods': len(data['periods']),
        'facility_count': facility_count,
        'facilities': facility_names[:10],
        'total_facilities': facility_count
    })


def get_scada_technology_comparison_data(request):
    """API endpoint to compare SCADA data between two groups of technology types"""
    technology1_ids = request.GET.getlist('technology1_id[]')
    technology2_ids = request.GET.getlist('technology2_id[]')
    year = request.GET.get('year')
    aggregation = request.GET.get('aggregation', 'hour')
    start_hour = request.GET.get('start_hour')
    end_hour = request.GET.get('end_hour')
    
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
    except ValueError:
        return JsonResponse({'error': 'Invalid year format'}, status=400)
    
    # Parse hour range
    if start_hour and end_hour:
        try:
            start_hour_int = int(start_hour)
            end_hour_int = int(end_hour)
        except ValueError:
            return JsonResponse({'error': 'Invalid hour range'}, status=400)
    else:
        start_hour_int = None
        end_hour_int = None
    
    # Get aggregated data for both technology groups
    def get_tech_group_scada_data(technologies, year, start_hour, end_hour):
        tech_facilities = facilities.objects.filter(idtechnologies__in=technologies)
        
        if not tech_facilities.exists():
            return None
        
        scada_queryset = FacilityScada.objects.filter(
            facility__in=tech_facilities,
            dispatch_interval__year=year
        ).order_by('dispatch_interval')
        
        if not scada_queryset.exists():
            return None
        
        # Aggregate by hour first
        hour_aggregated = {}
        for record in scada_queryset:
            hour = get_hour_of_year(record.dispatch_interval)
            if start_hour and end_hour:
                if hour < start_hour or hour > end_hour:
                    continue
            if hour not in hour_aggregated:
                hour_aggregated[hour] = 0
            hour_aggregated[hour] += float(record.quantity) if record.quantity else 0
        
        if not hour_aggregated:
            return None
        
        hours = sorted(hour_aggregated.keys())
        quantity_by_hour = [hour_aggregated[h] for h in hours]
        
        return {
            'hours': hours,
            'quantity_by_hour': quantity_by_hour,
            'facility_count': tech_facilities.count(),
            'facilities': tech_facilities
        }
    
    result1 = get_tech_group_scada_data(technologies1, year, start_hour_int, end_hour_int)
    result2 = get_tech_group_scada_data(technologies2, year, start_hour_int, end_hour_int)
    
    if result1 is None:
        tech1_names = ', '.join(technologies1.values_list('technology_name', flat=True))
        return JsonResponse({
            'error': f'No SCADA data found for {tech1_names} in {year}'
        }, status=404)
    
    if result2 is None:
        tech2_names = ', '.join(technologies2.values_list('technology_name', flat=True))
        return JsonResponse({
            'error': f'No SCADA data found for {tech2_names} in {year}'
        }, status=404)
    
    # Create hour data structures for aggregation
    hour_data1 = [{'hour': h, 'quantity': q} 
                  for h, q in zip(result1['hours'], result1['quantity_by_hour'])]
    hour_data2 = [{'hour': h, 'quantity': q} 
                  for h, q in zip(result2['hours'], result2['quantity_by_hour'])]
    
    # Aggregate based on time period
    if aggregation == 'hour':
        data1 = {'periods': result1['hours'], 'quantity': result1['quantity_by_hour']}
        data2 = {'periods': result2['hours'], 'quantity': result2['quantity_by_hour']}
        x_label = 'Hour of Year'
    elif aggregation == 'week':
        data1 = aggregate_scada_by_week(hour_data1)
        data2 = aggregate_scada_by_week(hour_data2)
        x_label = 'Week of Year'
    elif aggregation == 'month':
        data1 = aggregate_scada_by_month(hour_data1)
        data2 = aggregate_scada_by_month(hour_data2)
        x_label = 'Month of Year'
    else:
        return JsonResponse({'error': 'Invalid aggregation type'}, status=400)
    
    # Calculate correlation metrics
    correlation_metrics = calculate_correlation_metrics(data1['quantity'], data2['quantity'])
    
    technology1_names = list(technologies1.values_list('technology_name', flat=True))
    technology2_names = list(technologies2.values_list('technology_name', flat=True))
    
    # Get facility count per technology for both groups
    tech1_breakdown = []
    for tech in technologies1:
        count = result1['facilities'].filter(idtechnologies=tech).count()
        tech1_breakdown.append({
            'name': tech.technology_name,
            'facility_count': count
        })
    
    tech2_breakdown = []
    for tech in technologies2:
        count = result2['facilities'].filter(idtechnologies=tech).count()
        tech2_breakdown.append({
            'name': tech.technology_name,
            'facility_count': count
        })
    
    return JsonResponse({
        'technology1': {
            'names': technology1_names,
            'facility_count': result1['facility_count'],
            'breakdown': tech1_breakdown,
        },
        'technology2': {
            'names': technology2_names,
            'facility_count': result2['facility_count'],
            'breakdown': tech2_breakdown,
        },
        'year': year,
        'aggregation': aggregation,
        'x_label': x_label,
        'periods': data1['periods'],
        'technology1_quantity': data1['quantity'],
        'technology2_quantity': data2['quantity'],
        'correlation_metrics': correlation_metrics,
        'total_periods': len(data1['periods']),
    })


# Aggregation helper functions
def aggregate_scada_by_hour(hour_data):
    """Aggregate SCADA data by hour (no aggregation needed, just format)"""
    # Group by hour in case there are duplicates
    hour_dict = {}
    for entry in hour_data:
        hour = entry['hour']
        if hour not in hour_dict:
            hour_dict[hour] = []
        hour_dict[hour].append(entry['quantity'])
    
    # Average if multiple entries per hour
    hours = sorted(hour_dict.keys())
    quantities = [sum(hour_dict[h]) / len(hour_dict[h]) for h in hours]
    
    return {
        'periods': hours,
        'quantity': quantities
    }


def aggregate_scada_by_week(hour_data):
    """Aggregate SCADA data by week"""
    week_dict = {}
    
    for entry in hour_data:
        hour = entry['hour']
        week = ((hour - 1) // 168) + 1  # 168 hours per week
        
        if week not in week_dict:
            week_dict[week] = []
        week_dict[week].append(entry['quantity'])
    
    weeks = sorted(week_dict.keys())
    quantities = [sum(week_dict[w]) / len(week_dict[w]) for w in weeks]
    
    return {
        'periods': weeks,
        'quantity': quantities
    }


def aggregate_scada_by_month(hour_data):
    """Aggregate SCADA data by month"""
    month_dict = {}
    days_per_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    
    # Calculate cumulative hours for month boundaries
    cumulative_hours = [0]
    for days in days_per_month:
        cumulative_hours.append(cumulative_hours[-1] + days * 24)
    
    for entry in hour_data:
        hour = entry['hour']
        
        # Find which month this hour belongs to
        month = 1
        for i in range(12):
            if hour <= cumulative_hours[i + 1]:
                month = i + 1
                break
        
        if month not in month_dict:
            month_dict[month] = []
        month_dict[month].append(entry['quantity'])
    
    months = sorted(month_dict.keys())
    quantities = [sum(month_dict[m]) / len(month_dict[m]) for m in months]
    
    return {
        'periods': months,
        'quantity': quantities
    }


def calculate_correlation_metrics(data1, data2):
    """Calculate correlation and complementarity metrics between two datasets"""
    if len(data1) != len(data2):
        # Pad shorter array with zeros
        max_len = max(len(data1), len(data2))
        data1 = list(data1) + [0] * (max_len - len(data1))
        data2 = list(data2) + [0] * (max_len - len(data2))
    
    n = len(data1)
    
    # Calculate means
    mean1 = sum(data1) / n
    mean2 = sum(data2) / n
    
    # Calculate correlation coefficient
    numerator = sum((data1[i] - mean1) * (data2[i] - mean2) for i in range(n))
    denom1 = math.sqrt(sum((data1[i] - mean1) ** 2 for i in range(n)))
    denom2 = math.sqrt(sum((data2[i] - mean2) ** 2 for i in range(n)))
    
    if denom1 == 0 or denom2 == 0:
        correlation = 0
    else:
        correlation = numerator / (denom1 * denom2)
    
    # Calculate complementarity score (inverse of correlation for generation)
    complementarity_score = 1 - abs(correlation)
    
    # Calculate percentage of complementary periods (one high when other is low)
    complementary_periods = 0
    for i in range(n):
        if (data1[i] > mean1 and data2[i] < mean2) or (data1[i] < mean1 and data2[i] > mean2):
            complementary_periods += 1
    
    complementary_pct = (complementary_periods / n) * 100
    
    # Calculate combined variability reduction
    combined = [(data1[i] + data2[i]) / 2 for i in range(n)]
    combined_mean = sum(combined) / n
    
    var1 = sum((data1[i] - mean1) ** 2 for i in range(n)) / n
    var2 = sum((data2[i] - mean2) ** 2 for i in range(n)) / n
    var_combined = sum((combined[i] - combined_mean) ** 2 for i in range(n)) / n
    
    avg_var = (var1 + var2) / 2
    if avg_var > 0:
        variability_reduction = ((avg_var - var_combined) / avg_var) * 100
    else:
        variability_reduction = 0
    
    # Interpretation
    if abs(correlation) < 0.3:
        interpretation = "Low correlation - sources are relatively independent"
    elif abs(correlation) < 0.7:
        interpretation = "Moderate correlation - sources show some relationship"
    else:
        interpretation = "High correlation - sources are highly related"
    
    return {
        'correlation': round(correlation, 3),
        'complementarity_score': round(complementarity_score, 3),
        'complementary_periods_pct': round(complementary_pct, 1),
        'variability_reduction': round(variability_reduction, 1),
        'interpretation': interpretation
    }