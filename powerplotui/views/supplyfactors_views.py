from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from siren_web.models import facilities, Technologies, SupplyFactorMatrix
from siren_web.services.supply_matrix import facility_trace, load_year_matrix, facility_row_index
import math
import numpy as np
import openpyxl
from openpyxl.utils import get_column_letter

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
    
    # Get available years from the supply factor matrix
    years = SupplyFactorMatrix.objects.values_list('year', flat=True).order_by('year')
    
    context = {
        'facilities': renewable_facilities,
        'technologies': renewable_technologies,
        'years': list(years),
    }
    return render(request, 'facility_supply.html', context)

def _aggregate_trace(hours, quantum, aggregation):
    """Aggregate a numpy (hours, quantum) pair into hour/week/month buckets."""
    if aggregation == 'hour':
        return {'periods': hours.tolist(), 'quantum': quantum.tolist()}

    bucket_key = get_week_from_hour if aggregation == 'week' else get_month_from_hour
    buckets = {}
    for h, q in zip(hours.tolist(), quantum.tolist()):
        buckets.setdefault(bucket_key(h), []).append(q)

    periods = sorted(buckets)
    return {
        'periods': periods,
        'quantum': [float(np.mean(buckets[p])) for p in periods],
    }


def _x_label(aggregation):
    return {'hour': 'Hour of Year', 'week': 'Week of Year', 'month': 'Month of Year'}[aggregation]


def _slice_trace(trace, start_hour, end_hour):
    """
    Slice a raw (possibly NaN-containing) hourly trace to an optional
    [start_hour, end_hour] range. Returns (hours, quantum, error_response);
    error_response is None on success and should be returned as-is otherwise.
    """
    hours = np.arange(trace.shape[0])
    quantum = np.nan_to_num(trace, nan=0.0)

    if start_hour and end_hour:
        try:
            start_hour = int(start_hour)
            end_hour = int(end_hour)
        except ValueError:
            return None, None, JsonResponse({'error': 'Invalid hour range'}, status=400)
        mask = (hours >= start_hour) & (hours <= end_hour)
        hours = hours[mask]
        quantum = quantum[mask]

    return hours, quantum, None


def _slice_trace_lenient(trace, start_hour, end_hour):
    """
    As _slice_trace, but silently falls back to the full trace on an invalid
    hour range instead of erroring — matches the historical (pass-on-error)
    behaviour of the Excel export endpoint.
    """
    hours, quantum, err = _slice_trace(trace, start_hour, end_hour)
    if err:
        hours = np.arange(trace.shape[0])
        quantum = np.nan_to_num(trace, nan=0.0)
    return hours, quantum


def get_supply_data(request):
    """API endpoint to get supply data for a facility and year (matrix-backed)"""
    facility_id = request.GET.get('facility_id')
    year = request.GET.get('year')
    aggregation = request.GET.get('aggregation', 'hour')  # hour, week, or month
    start_hour = request.GET.get('start_hour')  # Optional hour range
    end_hour = request.GET.get('end_hour')

    if not facility_id or not year:
        return JsonResponse({'error': 'facility_id and year are required'}, status=400)

    try:
        facility = facilities.objects.select_related('idtechnologies').get(idfacilities=facility_id)
        facility_id = int(facility_id)
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

    # Get the facility's full-year trace from the packed per-year matrix
    # (one query + one reshape) instead of filtering 8760 supplyfactors rows.
    try:
        trace = facility_trace(year, facility_id)
    except SupplyFactorMatrix.DoesNotExist:
        trace = None

    if trace is None:
        return JsonResponse({
            'error': f'No supply data found for {facility.facility_name} in {year}'
        }, status=404)

    hours, quantum, err = _slice_trace(trace, start_hour, end_hour)
    if err:
        return err

    if hours.size == 0:
        return JsonResponse({
            'error': f'No supply data found for {facility.facility_name} in {year}'
        }, status=404)

    if aggregation not in ('hour', 'week', 'month'):
        return JsonResponse({'error': 'Invalid aggregation type'}, status=400)

    data = _aggregate_trace(hours, quantum, aggregation)
    x_label = _x_label(aggregation)

    return JsonResponse({
        'facility_name': facility.facility_name,
        'facility_code': facility.facility_code,
        'technology': facility.idtechnologies.technology_name,
        'year': year,
        'aggregation': aggregation,
        'x_label': x_label,
        'periods': data['periods'],
        'quantum': data['quantum'],
        # `supply` was never populated as real per-hour data by any writer
        # (always a constant 0 or 1) and isn't carried by the matrix; kept
        # as zeros only for response-shape compatibility with the frontend.
        'supply': [0.0] * len(data['periods']),
        'total_periods': len(data['periods']),
        'start_hour': int(start_hour) if start_hour else 1,
        'end_hour': int(end_hour) if end_hour else (int(hours[-1]) if hours.size else 8760),
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
        facility1_id = int(facility1_id)
        facility2_id = int(facility2_id)
        year = int(year)

        # Verify both facilities have renewable technology
        if not facility1.idtechnologies.renewable or not facility2.idtechnologies.renewable:
            return JsonResponse({'error': 'Both facilities must have renewable technology'}, status=400)

    except facilities.DoesNotExist:
        return JsonResponse({'error': 'One or both facilities not found'}, status=404)
    except ValueError:
        return JsonResponse({'error': 'Invalid year format'}, status=400)

    # Get each facility's full-year trace from the packed per-year matrix
    try:
        trace1 = facility_trace(year, facility1_id)
        trace2 = facility_trace(year, facility2_id)
    except SupplyFactorMatrix.DoesNotExist:
        trace1 = trace2 = None

    if trace1 is None:
        return JsonResponse({
            'error': f'No supply data found for {facility1.facility_name} in {year}'
        }, status=404)

    if trace2 is None:
        return JsonResponse({
            'error': f'No supply data found for {facility2.facility_name} in {year}'
        }, status=404)

    hours1, quantum1, err = _slice_trace(trace1, start_hour, end_hour)
    if err:
        return err
    hours2, quantum2, err = _slice_trace(trace2, start_hour, end_hour)
    if err:
        return err

    if hours1.size == 0 or hours2.size == 0:
        return JsonResponse({
            'error': f'No supply data found for the given hour range in {year}'
        }, status=404)

    if aggregation not in ('hour', 'week', 'month'):
        return JsonResponse({'error': 'Invalid aggregation type'}, status=400)

    data1 = _aggregate_trace(hours1, quantum1, aggregation)
    data2 = _aggregate_trace(hours2, quantum2, aggregation)
    x_label = _x_label(aggregation)

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

def get_facility_years(request):
    """API endpoint to get available years for a specific facility"""
    facility_id = request.GET.get('facility_id')
    
    if not facility_id:
        return JsonResponse({'error': 'facility_id is required'}, status=400)
    
    try:
        facility = facilities.objects.get(idfacilities=facility_id)
        facility_id = int(facility_id)
    except facilities.DoesNotExist:
        return JsonResponse({'error': 'Facility not found'}, status=404)

    # A facility's years are whichever years' matrices list it in facility_ids
    years = sorted(
        row.year
        for row in SupplyFactorMatrix.objects.only('year', 'facility_ids')
        if facility_id in row.facility_ids
    )

    return JsonResponse({
        'facility_name': facility.facility_name,
        'years': years,
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

    wanted_facility_ids = list(tech_facilities.values_list('idfacilities', flat=True))

    # Sum the wanted facilities straight out of the year's matrix — one query
    # + one vectorised sum instead of a per-row Python accumulation.
    try:
        matrix_facility_ids, matrix = load_year_matrix(year)
    except SupplyFactorMatrix.DoesNotExist:
        return JsonResponse({
            'error': f'No supply data found for the selected technologies in {year}'
        }, status=404)

    idx = facility_row_index(matrix_facility_ids)
    matched_rows = [idx[fid] for fid in wanted_facility_ids if fid in idx]

    if not matched_rows:
        return JsonResponse({
            'error': f'No supply data found for the selected technologies in {year}'
        }, status=404)

    trace_sum = np.nansum(matrix[matched_rows, :], axis=0)

    hours, quantum, err = _slice_trace(trace_sum, start_hour, end_hour)
    if err:
        return err

    if hours.size == 0:
        return JsonResponse({
            'error': f'No supply data found for the selected technologies in {year}'
        }, status=404)

    if aggregation not in ('hour', 'week', 'month'):
        return JsonResponse({'error': 'Invalid aggregation type'}, status=400)

    data = _aggregate_trace(hours, quantum, aggregation)
    x_label = _x_label(aggregation)

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
        # Kept only for response-shape compatibility with the frontend
        # (see get_supply_data) — no longer real per-hour data.
        'supply': [0.0] * len(data['periods']),
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
    
    # Get aggregated data for both technology groups, summed straight out of
    # the year's matrix (one query + one vectorised sum per group).
    def get_tech_group_aggregated_data(technologies, year, aggregation, start_hour, end_hour):
        wanted_facility_ids = list(
            facilities.objects.filter(idtechnologies__in=technologies).values_list('idfacilities', flat=True)
        )

        try:
            matrix_facility_ids, matrix = load_year_matrix(year)
        except SupplyFactorMatrix.DoesNotExist:
            return None

        idx = facility_row_index(matrix_facility_ids)
        matched_rows = [idx[fid] for fid in wanted_facility_ids if fid in idx]
        if not matched_rows:
            return None

        trace_sum = np.nansum(matrix[matched_rows, :], axis=0)

        hours = np.arange(trace_sum.shape[0])
        quantum = np.nan_to_num(trace_sum, nan=0.0)
        if start_hour and end_hour:
            try:
                start_hour_int = int(start_hour)
                end_hour_int = int(end_hour)
                mask = (hours >= start_hour_int) & (hours <= end_hour_int)
                hours, quantum = hours[mask], quantum[mask]
            except ValueError:
                pass

        if hours.size == 0:
            return None

        return _aggregate_trace(hours, quantum, aggregation)

    if aggregation not in ('hour', 'week', 'month'):
        return JsonResponse({'error': 'Invalid aggregation type'}, status=400)

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
    
    x_label = _x_label(aggregation)

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


def export_supply_to_excel(request):
    """Export supply factors data to Excel based on current view mode."""
    export_type = request.GET.get('type', 'single')  # single, compare, technology, techcompare
    year = request.GET.get('year')
    aggregation = request.GET.get('aggregation', 'hour')
    start_hour = request.GET.get('start_hour')
    end_hour = request.GET.get('end_hour')

    if not year:
        return JsonResponse({'error': 'Year is required'}, status=400)

    try:
        year = int(year)
    except ValueError:
        return JsonResponse({'error': 'Invalid year format'}, status=400)

    workbook = openpyxl.Workbook()
    worksheet = workbook.active

    agg = aggregation if aggregation in ('hour', 'week', 'month') else 'hour'

    def _group_trace_sum(technologies_qs):
        """Sum a technology group's facility traces straight out of the year's matrix."""
        wanted_facility_ids = list(
            facilities.objects.filter(idtechnologies__in=technologies_qs).values_list('idfacilities', flat=True)
        )
        try:
            matrix_facility_ids, matrix = load_year_matrix(year)
        except SupplyFactorMatrix.DoesNotExist:
            return np.zeros(0, dtype='float32')
        idx = facility_row_index(matrix_facility_ids)
        matched_rows = [idx[fid] for fid in wanted_facility_ids if fid in idx]
        if not matched_rows:
            return np.zeros(matrix.shape[1], dtype=matrix.dtype)
        return np.nansum(matrix[matched_rows, :], axis=0)

    if export_type == 'single':
        facility_id = request.GET.get('facility_id')
        if not facility_id:
            return JsonResponse({'error': 'Facility ID is required'}, status=400)

        try:
            facility = facilities.objects.select_related('idtechnologies').get(idfacilities=facility_id)
            facility_id = int(facility_id)
        except facilities.DoesNotExist:
            return JsonResponse({'error': 'Facility not found'}, status=404)

        try:
            trace = facility_trace(year, facility_id)
        except SupplyFactorMatrix.DoesNotExist:
            trace = None

        if trace is None:
            return JsonResponse({'error': 'No data found'}, status=404)

        hours, quantum = _slice_trace_lenient(trace, start_hour, end_hour)
        data = _aggregate_trace(hours, quantum, agg)

        worksheet.title = 'Supply Data'
        x_label = _x_label(agg)
        headers = [x_label, 'Generation (MW)', 'Supply (MW)']
        worksheet.append(headers)

        for i, period in enumerate(data['periods']):
            worksheet.append([period, data['quantum'][i], 0])

        filename = f"supply_{facility.facility_code or facility.facility_name}_{year}_{aggregation}"

    elif export_type == 'compare':
        facility1_id = request.GET.get('facility1_id')
        facility2_id = request.GET.get('facility2_id')

        if not facility1_id or not facility2_id:
            return JsonResponse({'error': 'Both facility IDs are required'}, status=400)

        try:
            facility1 = facilities.objects.select_related('idtechnologies').get(idfacilities=facility1_id)
            facility2 = facilities.objects.select_related('idtechnologies').get(idfacilities=facility2_id)
            facility1_id = int(facility1_id)
            facility2_id = int(facility2_id)
        except facilities.DoesNotExist:
            return JsonResponse({'error': 'Facility not found'}, status=404)

        def get_facility_data(fid):
            try:
                trace = facility_trace(year, fid)
            except SupplyFactorMatrix.DoesNotExist:
                trace = None
            if trace is None:
                return {'periods': [], 'quantum': []}
            hours, quantum = _slice_trace_lenient(trace, start_hour, end_hour)
            return _aggregate_trace(hours, quantum, agg)

        data1 = get_facility_data(facility1_id)
        data2 = get_facility_data(facility2_id)

        worksheet.title = 'Facility Comparison'
        x_label = _x_label(agg)
        headers = [x_label, f'{facility1.facility_name} (MW)', f'{facility2.facility_name} (MW)']
        worksheet.append(headers)

        for i, period in enumerate(data1['periods']):
            row = [period]
            row.append(data1['quantum'][i] if i < len(data1['quantum']) else '')
            row.append(data2['quantum'][i] if i < len(data2['quantum']) else '')
            worksheet.append(row)

        filename = f"supply_comparison_{year}_{aggregation}"

    elif export_type == 'technology':
        technology_ids = request.GET.getlist('technology_id[]')
        if not technology_ids:
            return JsonResponse({'error': 'At least one technology must be selected'}, status=400)

        technologies_qs = Technologies.objects.filter(idtechnologies__in=technology_ids)
        trace_sum = _group_trace_sum(technologies_qs)
        hours, quantum = _slice_trace_lenient(trace_sum, start_hour, end_hour)
        data = _aggregate_trace(hours, quantum, agg)

        worksheet.title = 'Technology Supply'
        tech_names = ', '.join(list(technologies_qs.values_list('technology_name', flat=True)))
        x_label = _x_label(agg)
        headers = [x_label, f'{tech_names} Generation (MW)', f'{tech_names} Supply (MW)']
        worksheet.append(headers)

        for i, period in enumerate(data['periods']):
            worksheet.append([period, data['quantum'][i], 0])

        filename = f"supply_technology_{year}_{aggregation}"

    elif export_type == 'techcompare':
        technology1_ids = request.GET.getlist('technology1_id[]')
        technology2_ids = request.GET.getlist('technology2_id[]')

        if not technology1_ids or not technology2_ids:
            return JsonResponse({'error': 'Both technology groups are required'}, status=400)

        technologies1_qs = Technologies.objects.filter(idtechnologies__in=technology1_ids)
        technologies2_qs = Technologies.objects.filter(idtechnologies__in=technology2_ids)

        def get_tech_data(technologies_list):
            hours, quantum = _slice_trace_lenient(_group_trace_sum(technologies_list), start_hour, end_hour)
            return _aggregate_trace(hours, quantum, agg)

        data1 = get_tech_data(technologies1_qs)
        data2 = get_tech_data(technologies2_qs)

        worksheet.title = 'Technology Comparison'
        tech1_names = ', '.join(list(technologies1_qs.values_list('technology_name', flat=True)))
        tech2_names = ', '.join(list(technologies2_qs.values_list('technology_name', flat=True)))
        x_label = _x_label(agg)
        headers = [x_label, f'Group 1: {tech1_names} (MW)', f'Group 2: {tech2_names} (MW)']
        worksheet.append(headers)

        for i, period in enumerate(data1['periods']):
            row = [period]
            row.append(data1['quantum'][i] if i < len(data1['quantum']) else '')
            row.append(data2['quantum'][i] if i < len(data2['quantum']) else '')
            worksheet.append(row)

        filename = f"supply_tech_comparison_{year}_{aggregation}"

    else:
        return JsonResponse({'error': 'Invalid export type'}, status=400)

    # Auto-size columns
    for column_cells in worksheet.columns:
        max_length = 0
        column = column_cells[0].column_letter
        for cell in column_cells:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        worksheet.column_dimensions[column].width = adjusted_width

    # Create response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
    workbook.save(response)

    return response