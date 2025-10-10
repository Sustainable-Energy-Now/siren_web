# powerplot/views.py (updated)
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from siren_web.models import LoadAnalysisSummary
from powerplotui.services.chart_generator import ChartGenerator
from powerplotui.services.load_analyzer import LoadAnalyzer
from datetime import datetime, date
import calendar

def scada_analysis_report(request, year=None, month=None):
    """Display monthly load analysis report"""
    if year is None or month is None:
        # Default to latest available
        latest = LoadAnalysisSummary.objects.filter(
            period_type='MONTHLY'
        ).first()
        if latest:
            year = latest.period_date.year
            month = latest.period_date.month
        else:
            return render(request, 'scada/no_data.html', {
                'month_name': 'Unknown',
                'year': datetime.now().year,
                'latest_available': None
            })
    
    summary = LoadAnalysisSummary.objects.filter(
        period_date=date(year, month, 1),
        period_type='MONTHLY'
    ).first()
    
    if not summary:
        latest_available = LoadAnalysisSummary.objects.filter(
            period_type='MONTHLY'
        ).first()
        return render(request, 'scada/no_data.html', {
            'month_name': calendar.month_name[month],
            'year': year,
            'latest_available': latest_available
        })
    
    # Get previous year same month for comparison
    prev_summary = LoadAnalysisSummary.objects.filter(
        period_date=date(year-1, month, 1),
        period_type='MONTHLY'
    ).first()
    
    # Get YTD summaries
    ytd_summaries = LoadAnalysisSummary.objects.filter(
        period_date__year=year,
        period_date__month__lte=month,
        period_type='MONTHLY'
    )
    
    ytd_prev_summaries = LoadAnalysisSummary.objects.filter(
        period_date__year=year-1,
        period_date__month__lte=month,
        period_type='MONTHLY'
    )
    
    # Aggregate YTD data
    ytd_summary = aggregate_summaries(ytd_summaries)
    ytd_prev_summary = aggregate_summaries(ytd_prev_summaries)
    
    # Calculate changes
    changes = {}
    if prev_summary:
        changes['operational_demand'] = (
            (summary.operational_demand / prev_summary.operational_demand - 1) * 100
        )
    
    ytd_changes = {}
    if ytd_prev_summary['operational_demand'] > 0:
        ytd_changes['operational_demand'] = (
            (ytd_summary['operational_demand'] / ytd_prev_summary['operational_demand'] - 1) * 100
        )
    
    # Calculate BESS percentages
    bess_percentage = (
        (summary.battery_discharge / summary.operational_demand) * 100 
        if summary.operational_demand > 0 else 0
    )
    ytd_bess_percentage = (
        (ytd_summary['battery_discharge'] / ytd_summary['operational_demand']) * 100
        if ytd_summary['operational_demand'] > 0 else 0
    )
    
    # Generate charts
    chart_gen = ChartGenerator()
    pie_chart_html = chart_gen.create_demand_breakdown_pie(summary, ytd_summary)
    
    analyzer = LoadAnalyzer()
    diurnal_data_month = analyzer.get_diurnal_profile(year, month)
    diurnal_data_ytd = analyzer.get_diurnal_profile_ytd(year, month)
    
    diurnal_chart_month = chart_gen.create_diurnal_profile(diurnal_data_month)
    diurnal_chart_ytd = chart_gen.create_diurnal_profile(diurnal_data_ytd)
    
    # Get available periods for selector
    available_months = [
        {'value': i, 'label': calendar.month_name[i]} 
        for i in range(1, 13)
    ]
    available_years = list(range(2023, datetime.now().year + 1))
    
    context = {
        'summary': summary,
        'prev_summary': prev_summary,
        'ytd_summary': ytd_summary,
        'ytd_prev_summary': ytd_prev_summary,
        'changes': changes,
        'ytd_changes': ytd_changes,
        'bess_percentage': bess_percentage,
        'ytd_bess_percentage': ytd_bess_percentage,
        'pie_chart': pie_chart_html,
        'diurnal_chart_month': diurnal_chart_month,
        'diurnal_chart_ytd': diurnal_chart_ytd,
        'year': year,
        'month': month,
        'month_name': calendar.month_name[month],
        'available_months': available_months,
        'available_years': available_years,
    }
    
    return render(request, 'scada/analysis.html', context)

def aggregate_summaries(summaries):
    """Aggregate multiple monthly summaries into totals"""
    if not summaries:
        return {
            'operational_demand': 0,
            'underlying_demand': 0,
            'battery_discharge': 0,
            're_percentage_operational': 0,
            're_percentage_underlying': 0,
        }
    
    total = {
        'operational_demand': sum(s.operational_demand for s in summaries),
        'underlying_demand': sum(s.underlying_demand for s in summaries),
        'battery_discharge': sum(s.battery_discharge for s in summaries),
        'dpv_generation': sum(s.dpv_generation for s in summaries),
        'wind_generation': sum(s.wind_generation for s in summaries),
        'solar_generation': sum(s.solar_generation for s in summaries),
    }
    
    # Recalculate percentages
    total_re = total['wind_generation'] + total['solar_generation']
    total['re_percentage_operational'] = (
        (total_re / total['operational_demand']) * 100 
        if total['operational_demand'] > 0 else 0
    )
    total['re_percentage_underlying'] = (
        (total_re / total['underlying_demand']) * 100
        if total['underlying_demand'] > 0 else 0
    )
    
    return total