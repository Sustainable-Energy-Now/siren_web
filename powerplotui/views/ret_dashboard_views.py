"""
SWIS Renewable Energy Target Dashboard Views

This module provides views for the renewable energy dashboard, including:
- Monthly dashboard
- Quarterly reports
- Annual reviews
- API endpoints for data updates

RE% Calculation Policy:
- Operational demand = grid connected load
- Underlying demand = operational demand + that proportion rooftop solar (DPV) consumed behind the meter.
- RE% (operational) = (wind + utility solar + biomass+ BESS) / operational demand
- RE% (underlying) = (wind + utility solar + biomass + DPV) / underlying demand
"""
from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.db.models import Sum
from django.utils import timezone
from datetime import datetime, timedelta
from calendar import month_name, monthrange
import json
from django.http import JsonResponse

from siren_web.models import (
    DPVGeneration, 
    MonthlyREPerformance, 
    ReportComment,
    NewCapacityCommissioned,
    TargetScenario
)
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Main Dashboard View
# =============================================================================

def ret_dashboard(request, year=None, month=None):
    """
    Main dashboard view for renewable energy tracking.
    Shows monthly performance vs targets.
    """
    # Default to last complete month if not specified
    now = timezone.now()
    if not year and not month:
        target_date = (now.replace(day=1) - timedelta(days=1))
        year = target_date.year
        month = target_date.month
    if not year:
        year = now.year
    if not month:
        month = now.month
    year = int(year)
    month = int(month)
    quarter = (month - 1) // 3 + 1

    # Calculate completed quarters for the report year
    completed_quarters = get_completed_quarters(year)
    
    # Get selected month's performance
    try:
        performance = MonthlyREPerformance.objects.get(year=year, month=month)
    except MonthlyREPerformance.DoesNotExist:
        return render(request, 'ret_dashboard/no_data.html', {
            'year': year,
            'month': month_name[month]
        })

    # Get target for this year
    target = performance.get_target_for_period()
    target_status = performance.get_status_vs_target()
    
    # Calculate YTD summary using the model's method
    ytd_summary = performance.calculate_ytd_summary()
    
    # Get previous year same month for comparison
    try:
        prev_year_performance = MonthlyREPerformance.objects.get(
            year=year-1, month=month
        )
        prev_ytd_summary = prev_year_performance.calculate_ytd_summary()
    except MonthlyREPerformance.DoesNotExist:
        prev_year_performance = None
        prev_ytd_summary = None
    
    # Get new capacity commissioned this month
    new_capacity = NewCapacityCommissioned.objects.filter(
        report_year=year,
        report_month=month,
        status='commissioned'
    ).select_related('facility')
    
    # Get upcoming capacity (next 3 months)
    upcoming_capacity = NewCapacityCommissioned.objects.filter(
        status='under_construction',
        expected_commissioning_date__gte=datetime(year, month, 1),
        expected_commissioning_date__lte=datetime(year, month, 1) + timedelta(days=90)
    ).select_related('facility').order_by('expected_commissioning_date')
    
    # Get 2040 scenario projections
    scenarios = TargetScenario.objects.filter(is_active=True)
    base_case = scenarios.filter(scenario_type='base_case').first()
    
    # Generate charts - TWO separate pie charts for operational and underlying
    generation_mix_operational_chart = generate_generation_mix_operational_chart(performance)
    generation_mix_underlying_chart = generate_generation_mix_underlying_chart(performance)
    pathway_chart = generate_pathway_chart(year, month)
    
    # Calculate emissions reduction
    emissions_change = None
    if prev_year_performance:
        emissions_change = ((performance.total_emissions_tonnes - 
                           prev_year_performance.total_emissions_tonnes) / 
                          prev_year_performance.total_emissions_tonnes * 100)
    
    ytd_emissions_change = None
    if prev_ytd_summary and ytd_summary:
        ytd_emissions_change = ((ytd_summary['total_emissions'] - 
                               prev_ytd_summary['total_emissions']) / 
                              prev_ytd_summary['total_emissions'] * 100)

    comments = ReportComment.get_comments_for_report('monthly', year, month=month)

    context = {
        'year': year,
        'month': month,
        'quarter': quarter,
        'month_name': month_name[month],
        'performance': performance,
        'target': target,
        'target_status': target_status,
        'ytd_summary': ytd_summary,
        'prev_year_performance': prev_year_performance,
        'prev_ytd_summary': prev_ytd_summary,
        'emissions_change': emissions_change,
        'ytd_emissions_change': ytd_emissions_change,
        'new_capacity': new_capacity,
        'upcoming_capacity': upcoming_capacity,
        'base_case_scenario': base_case,
        # Two separate charts
        'generation_mix_operational_chart': generation_mix_operational_chart,
        'generation_mix_underlying_chart': generation_mix_underlying_chart,
        'pathway_chart': pathway_chart,
        'available_months': get_available_months(),
        'available_years': get_available_years(),
        'completed_quarters': completed_quarters,
        'comments': comments,
        'report_type': 'monthly',
    }

    return render(request, 'ret_dashboard/dashboard.html', context)

def get_dpv_generation(year, month):
    """
    Get DPV (Distributed PV / Rooftop Solar) generation for a month.
    Returns generation in GWh.
    """
    _, last_day = monthrange(year, month)
    
    # Try to get from DPVGeneration model
    qs = DPVGeneration.objects.filter(
        trading_date__year=year,
        trading_date__month=month
    )

    total_mw = qs.aggregate(total=Sum('estimated_generation'))['total']

    if not total_mw:
        return 0.0

    # Convert: MW * 0.5h → MWh → /1000 to get GWh
    total_gwh = (total_mw * 0.5) / 1000

    return total_gwh

# =============================================================================
# Chart Generation Functions
# =============================================================================

def generate_generation_mix_operational_chart(performance):
    """
    Generate Plotly pie chart for OPERATIONAL generation mix.
    
    Shows grid-sent generation only (excludes rooftop solar/DPV).
    Storage (BESS + Hydro) is also excluded as it's not counted in RE%.
    """
    import plotly.graph_objects as go
    
    # Data for pie chart - EXCLUDES DPV (rooftop solar) and storage
    labels = ['Wind', 'Solar (Utility)', 'Biomass', 'Gas (CCGT)']
    
    values = [
        performance.wind_generation,
        performance.solar_generation,
        performance.biomass_generation,
        performance.gas_generation,
    ]
    
    # Add coal if present
    if performance.coal_generation and performance.coal_generation > 0:
        labels.append('Coal')
        values.append(performance.coal_generation)
    
    # Colors - green for renewables, gray for fossil
    colors = ['#27ae60', '#f39c12', '#16a085', '#95a5a6', '#7f8c8d']
    
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        marker=dict(colors=colors[:len(labels)]),
        textposition='inside',
        textinfo='label+percent',
        hovertemplate='<b>%{label}</b><br>%{value:.1f} GWh<br>%{percent}<extra></extra>',
        hole=0,
        domain=dict(x=[0.1, 0.9], y=[0.15, 0.85])
    )])
    
    fig.update_layout(
        title=dict(
            text=f"Operational Demand - RE: {performance.re_percentage_operational:.1f}%",
            x=0.5,
            xanchor='center',
            font=dict(size=14)
        ),
        height=400,
        showlegend=True,
        legend=dict(orientation='h', yanchor='top', y=0.02, xanchor='center', x=0.5),
        margin=dict(l=20, r=20, t=50, b=50),
    )
    
    # Wrap in a div with explicit width control
    chart_html = fig.to_html(include_plotlyjs='cdn', div_id='generation_mix_operational_chart', 
                             full_html=False)
    return f'<div style="width:100%;overflow:hidden;">{chart_html}</div>'

def generate_generation_mix_underlying_chart(performance):
    """
    Generate Plotly pie chart for UNDERLYING generation mix.
    
    Shows total generation including rooftop solar (DPV).
    Storage (BESS + Hydro) is excluded as it's not counted in RE%.
    """
    import plotly.graph_objects as go
    
    # Data for pie chart - INCLUDES DPV (rooftop solar), excludes storage
    labels = ['Wind', 'Solar (Utility)', 'Solar (Rooftop)', 'Biomass', 'Gas (CCGT)']
    
    values = [
        performance.wind_generation,
        performance.solar_generation,
        performance.dpv_generation,
        performance.biomass_generation,
        performance.gas_generation,
    ]
    
    # Add coal if present
    if performance.coal_generation and performance.coal_generation > 0:
        labels.append('Coal')
        values.append(performance.coal_generation)
    
    # Colors - green for renewables (including rooftop solar in yellow), gray for fossil
    colors = ['#27ae60', '#f39c12', '#f1c40f', '#16a085', '#95a5a6', '#7f8c8d']
    
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        marker=dict(colors=colors[:len(labels)]),
        textposition='inside',
        textinfo='label+percent',
        hovertemplate='<b>%{label}</b><br>%{value:.1f} GWh<br>%{percent}<extra></extra>',
        hole=0,
        domain=dict(x=[0.1, 0.9], y=[0.15, 0.85])
    )])
    
    fig.update_layout(
        title=dict(
            text=f"Underlying Demand - RE: {performance.re_percentage_underlying:.1f}%",
            x=0.5,
            xanchor='center',
            font=dict(size=14)
        ),
        height=400,
        showlegend=True,
        legend=dict(orientation='h', yanchor='top', y=0.02, xanchor='center', x=0.5),
        margin=dict(l=20, r=20, t=50, b=50),
    )
    
    # Wrap in a div with explicit width control
    chart_html = fig.to_html(include_plotlyjs=False, div_id='generation_mix_underlying_chart',
                             full_html=False)
    return f'<div style="width:100%;overflow:hidden;">{chart_html}</div>'

def generate_pathway_chart(current_year, current_month):
    """
    Generate chart showing pathway to 2040 target.
    
    Uses OPERATIONAL RE% (not underlying) as this is the primary policy metric.
    Includes a cumulative YTD RE% line that builds month by month.
    """
    import plotly.graph_objects as go
    
    # Get historical performance
    historical = MonthlyREPerformance.objects.filter(
        year__gte=2023
    ).order_by('year', 'month')
    
    # Get targets (major and interim only)
    targets = TargetScenario.objects.filter(
        target_type__in=['major', 'interim']
    ).order_by('year')
    
    # Prepare data for plotting - USE OPERATIONAL RE%
    hist_years = []
    hist_re_pct = []
    
    for record in historical:
        date_label = f"{record.year}-{record.month:02d}"
        hist_years.append(date_label)
        hist_re_pct.append(record.re_percentage_operational)
    
    # Calculate cumulative YTD RE% for current year (month by month)
    ytd_months = []
    ytd_re_pcts = []
    
    # Get all months for current year up to current_month
    current_year_data = MonthlyREPerformance.objects.filter(
        year=current_year,
        month__lte=current_month
    ).order_by('month')
    
    if current_year_data.exists():
        cumulative_renewable = 0
        cumulative_operational = 0
        
        for record in current_year_data:
            # Add this month's values to cumulative totals
            cumulative_renewable += (
                record.wind_generation + 
                record.solar_generation + 
                record.biomass_generation
            )
            cumulative_operational += record.operational_demand
            
            # Calculate YTD RE% up to this month
            if cumulative_operational > 0:
                ytd_pct = (cumulative_renewable / cumulative_operational) * 100
                ytd_months.append(f"{current_year}-{record.month:02d}")
                ytd_re_pcts.append(ytd_pct)
    
    # Target trajectory
    target_years = [t.year for t in targets]
    target_pcts = [t.target_re_percentage for t in targets]
    
    # Create figure
    fig = go.Figure()
    
    # Historical performance (monthly)
    fig.add_trace(go.Scatter(
        x=hist_years,
        y=hist_re_pct,
        mode='lines+markers',
        name='Monthly RE% (Operational)',
        line=dict(color='#27ae60', width=2),
        marker=dict(size=6)
    ))
    
    # YTD RE% cumulative line (only for current year)
    if ytd_months and ytd_re_pcts:
        fig.add_trace(go.Scatter(
            x=ytd_months,
            y=ytd_re_pcts,
            mode='lines+markers',
            name=f'YTD {current_year} RE%',
            line=dict(color='#2980b9', width=3),
            marker=dict(size=8, symbol='square')
        ))
    
    # Target line
    if target_years and target_pcts:
        fig.add_trace(go.Scatter(
            x=[str(y) for y in target_years],
            y=target_pcts,
            mode='lines+markers',
            name='Target',
            line=dict(color='#e74c3c', width=2, dash='dash'),
            marker=dict(size=8, symbol='diamond')
        ))
    
    fig.update_layout(
        title='Pathway to 2040 Target (Operational RE%)',
        xaxis_title='Year',
        yaxis_title='Renewable Energy %',
        height=400,
        hovermode='x unified',
        yaxis=dict(range=[0, 100])
    )
    
    chart_html = fig.to_html(include_plotlyjs=False, div_id='pathway_chart', full_html=False)
    return f'<div style="width:100%;overflow:hidden;">{chart_html}</div>'

def generate_annual_generation_chart(annual_data):
    """Generate chart showing monthly generation trends for the year"""
    import plotly.graph_objects as go
    
    months = [month_name[record.month] for record in annual_data]
    
    fig = go.Figure()
    
    # Add traces for each technology (excluding storage from stacked display)
    fig.add_trace(go.Bar(
        name='Wind',
        x=months,
        y=[record.wind_generation for record in annual_data],
        marker_color='#27ae60'
    ))
    
    fig.add_trace(go.Bar(
        name='Solar (Utility)',
        x=months,
        y=[record.solar_generation for record in annual_data],
        marker_color='#f39c12'
    ))
    
    fig.add_trace(go.Bar(
        name='Solar (Rooftop)',
        x=months,
        y=[record.dpv_generation for record in annual_data],
        marker_color='#f1c40f'
    ))
    
    fig.add_trace(go.Bar(
        name='Biomass',
        x=months,
        y=[record.biomass_generation for record in annual_data],
        marker_color='#16a085'
    ))
    
    fig.add_trace(go.Bar(
        name='Gas',
        x=months,
        y=[record.gas_generation for record in annual_data],
        marker_color='#95a5a6'
    ))
    
    fig.update_layout(
        title='Monthly Generation by Technology (Storage excluded)',
        xaxis_title='Month',
        yaxis_title='Generation (GWh)',
        barmode='stack',
        height=400,
        hovermode='x unified'
    )
    
    return fig.to_html(include_plotlyjs='cdn', div_id='annual_generation_chart')

def generate_annual_trends_chart(year):
    """Generate multi-year trends chart"""
    import plotly.graph_objects as go
    
    # Get data for past 3 years
    start_year = year - 2
    historical = MonthlyREPerformance.objects.filter(
        year__gte=start_year,
        year__lte=year
    ).order_by('year', 'month')
    
    if not historical.exists():
        return ""
    
    # Group by year
    years_data = {}
    for record in historical:
        if record.year not in years_data:
            years_data[record.year] = []
        years_data[record.year].append(record)
    
    fig = go.Figure()
    
    # Add line for each year - USE OPERATIONAL RE%
    for y in sorted(years_data.keys()):
        records = years_data[y]
        months = [record.month for record in records]
        re_pcts = [record.re_percentage_operational for record in records]  # CHANGED
        
        fig.add_trace(go.Scatter(
            name=str(y),
            x=months,
            y=re_pcts,
            mode='lines+markers',
            line=dict(width=2),
            marker=dict(size=6)
        ))
    
    # Add target line if available
    try:
        target = TargetScenario.objects.filter(
            year=year,
            target_type__in=['major', 'interim']
        ).first()
        if target:
            fig.add_trace(go.Scatter(
                name=f'{year} Target',
                x=list(range(1, 13)),
                y=[target.target_re_percentage] * 12,
                mode='lines',
                line=dict(color='red', width=2, dash='dash'),
                showlegend=True
            ))
    except Exception:
        pass
    
    fig.update_layout(
        title='Multi-Year RE% Trends (Operational)',
        xaxis_title='Month',
        yaxis_title='Renewable Energy %',
        height=400,
        hovermode='x unified',
        xaxis=dict(
            tickmode='array',
            tickvals=list(range(1, 13)),
            ticktext=[month_name[i][:3] for i in range(1, 13)]
        )
    )
    
    return fig.to_html(include_plotlyjs='cdn', div_id='annual_trends_chart')

def generate_scenario_comparison_chart(scenarios):
    """Generate chart comparing different 2040 scenarios"""
    import plotly.graph_objects as go

    if not scenarios:
        return ""

    scenario_names = [s.display_name for s in scenarios]
    re_percentages = [s.target_re_percentage for s in scenarios]
    
    # Color code based on meeting 75% target
    colors = ['#27ae60' if pct >= 75 else '#e74c3c' for pct in re_percentages]
    
    fig = go.Figure(data=[
        go.Bar(
            x=scenario_names,
            y=re_percentages,
            marker_color=colors,
            text=[f"{pct:.1f}%" for pct in re_percentages],
            textposition='auto',
        )
    ])
    
    # Add 75% target line
    fig.add_hline(y=75, line_dash="dash", line_color="red",
                  annotation_text="75% Target", annotation_position="right")
    
    fig.update_layout(
        title='2040 Scenario Comparison',
        xaxis_title='Scenario',
        yaxis_title='Projected RE%',
        height=400,
        yaxis=dict(range=[0, 100])
    )
    
    return fig.to_html(include_plotlyjs='cdn', div_id='scenario_comparison_chart')

# =============================================================================
# Helper Functions
# =============================================================================

def get_available_months():
    """Get list of months with available data for dropdown"""
    records = MonthlyREPerformance.objects.all().order_by('-year', '-month')
    
    months = []
    for record in records:
        months.append({
            'value': f"{record.year}-{record.month:02d}",
            'label': f"{month_name[record.month]} {record.year}"
        })
    
    return months

def get_available_years():
    """Get list of years with available data"""
    years = MonthlyREPerformance.objects.values_list(
        'year', flat=True
    ).distinct().order_by('-year')
    
    return list(years)

def aggregate_wholesale_price_stats(queryset):
    """
    Aggregate wholesale price statistics from a queryset of MonthlyREPerformance records.
    
    Returns a dictionary with aggregated wholesale price statistics.
    """
    if not queryset.exists():
        return None
    
    # Get records with wholesale price data
    records_with_prices = [r for r in queryset if r.wholesale_price_avg is not None]
    
    if not records_with_prices:
        return None
    
    # Find overall max and min
    max_record = max(
        [r for r in records_with_prices if r.wholesale_price_max is not None],
        key=lambda r: r.wholesale_price_max,
        default=None
    )
    min_record = min(
        [r for r in records_with_prices if r.wholesale_price_min is not None],
        key=lambda r: r.wholesale_price_min,
        default=None
    )
    
    # Calculate weighted average price (weighted by number of trading intervals in each month)
    # Approximation: weight by days in month
    total_weighted_avg = 0
    total_weight = 0
    total_negative_count = 0
    total_spike_count = 0
    
    for record in records_with_prices:
        if record.wholesale_price_avg is not None:
            _, days_in_month = monthrange(record.year, record.month)
            intervals_in_month = days_in_month * 48  # 48 half-hour intervals per day
            total_weighted_avg += record.wholesale_price_avg * intervals_in_month
            total_weight += intervals_in_month
        
        if record.wholesale_negative_count is not None:
            total_negative_count += record.wholesale_negative_count
        
        if record.wholesale_spike_count is not None:
            total_spike_count += record.wholesale_spike_count
    
    weighted_avg = total_weighted_avg / total_weight if total_weight > 0 else None
    
    return {
        'wholesale_price_max': max_record.wholesale_price_max if max_record else None,
        'wholesale_price_max_datetime': max_record.wholesale_price_max_datetime if max_record else None,
        'wholesale_price_max_month': month_name[max_record.month] if max_record else None,
        'wholesale_price_min': min_record.wholesale_price_min if min_record else None,
        'wholesale_price_min_datetime': min_record.wholesale_price_min_datetime if min_record else None,
        'wholesale_price_min_month': month_name[min_record.month] if min_record else None,
        'wholesale_price_avg': weighted_avg,
        'wholesale_negative_count': total_negative_count,
        'wholesale_spike_count': total_spike_count,
    }

# =============================================================================
# Quarterly Report View
# =============================================================================

def quarterly_report(request, year, quarter):
    """
    Generate quarterly report view.
    Uses MonthlyREPerformance.aggregate_summary() for consistent RE% calculations.
    """
    year = int(year)
    quarter = int(quarter)
    
    start_month = (quarter - 1) * 3 + 1
    end_month = quarter * 3
    
    # Get quarterly data
    quarterly_data = MonthlyREPerformance.objects.filter(
        year=year,
        month__gte=start_month,
        month__lte=end_month
    ).order_by('month')
    
    if not quarterly_data.exists():
        return render(request, 'ret_dashboard/no_data.html', {
            'year': year,
            'quarter': quarter
        })
    if quarter == 3:
        next_report = f"{year} Annual Report"
    else:
        next_report = f"Q{quarter + 1} {year} Quarterly Report"
    
    # Use model's aggregate_summary for quarterly totals (single source of truth)
    quarterly_summary = MonthlyREPerformance.aggregate_summary(quarterly_data)
    
    # Aggregate wholesale price statistics for the quarter
    quarterly_wholesale_stats = aggregate_wholesale_price_stats(quarterly_data)
    if quarterly_wholesale_stats and quarterly_summary:
        quarterly_summary.update(quarterly_wholesale_stats)
    
    # Previous quarter (same quarter, previous year) for comparison
    prev_quarter_data = MonthlyREPerformance.objects.filter(
        year=year-1,
        month__gte=start_month,
        month__lte=end_month
    )
    prev_quarter_summary = MonthlyREPerformance.aggregate_summary(prev_quarter_data)
    
    # Add wholesale stats for previous quarter comparison
    prev_quarterly_wholesale_stats = aggregate_wholesale_price_stats(prev_quarter_data)
    if prev_quarterly_wholesale_stats and prev_quarter_summary:
        prev_quarter_summary.update(prev_quarterly_wholesale_stats)
    
    # YTD summary - get last month of quarter and use calculate_ytd_summary()
    try:
        end_month_record = MonthlyREPerformance.objects.get(year=year, month=end_month)
        ytd_summary = end_month_record.calculate_ytd_summary()
    except MonthlyREPerformance.DoesNotExist:
        # Fall back to aggregate_summary if exact end month missing
        ytd_data = MonthlyREPerformance.objects.filter(year=year, month__lte=end_month)
        ytd_summary = MonthlyREPerformance.aggregate_summary(ytd_data)
    
    # Add YTD wholesale stats
    ytd_data = MonthlyREPerformance.objects.filter(year=year, month__lte=end_month)
    ytd_wholesale_stats = aggregate_wholesale_price_stats(ytd_data)
    if ytd_wholesale_stats and ytd_summary:
        ytd_summary.update(ytd_wholesale_stats)
    
    # Previous year YTD comparison
    try:
        prev_end_month_record = MonthlyREPerformance.objects.get(year=year-1, month=end_month)
        prev_ytd_summary = prev_end_month_record.calculate_ytd_summary()
    except MonthlyREPerformance.DoesNotExist:
        prev_ytd_data = MonthlyREPerformance.objects.filter(year=year-1, month__lte=end_month)
        prev_ytd_summary = MonthlyREPerformance.aggregate_summary(prev_ytd_data)
    
    # Get target - include ordinary years if no major/interim target exists
    try:
        target = TargetScenario.objects.filter(
            year=year,
            target_type__in=['major', 'interim']
        ).first()
        if not target:
            target = TargetScenario.objects.filter(year=year).first()
    except Exception:
        target = None

    comments = ReportComment.get_comments_for_report('quarterly', year, quarter=quarter)

    # Get Executive Summary from comments
    executive_summary = comments.filter(category='executive_summary').first()
    # Calculate completed quarters for the report year
    completed_quarters = get_completed_quarters(year)
    
    context = {
        'year': year,
        'quarter': quarter,
        'quarter_start_month': month_name[start_month],
        'quarter_end_month': month_name[end_month],
        'quarterly_data': quarterly_data,
        'quarterly_summary': quarterly_summary,
        'prev_quarter_summary': prev_quarter_summary,
        'next_report': next_report,
        'ytd_summary': ytd_summary,
        'prev_ytd_summary': prev_ytd_summary,
        'target': target,
        'completed_quarters': completed_quarters,
        'comments': comments,
        'executive_summary': executive_summary,
        'report_type': 'quarterly',
    }
    
    return render(request, 'ret_dashboard/quarterly_report.html', context)

# =============================================================================
# Annual Review View
# =============================================================================

def annual_review(request, year):
    """
    Generate annual review view.
    """
    year = int(year)
    
    # Calculate completed quarters for the report year
    completed_quarters = get_completed_quarters(year)
    next_report = f"Q1 {year + 1} Quarterly Report"
    # Get all monthly data for this year
    annual_data = MonthlyREPerformance.objects.filter(
        year=year
    ).order_by('month')
    
    if not annual_data.exists():
        return render(request, 'ret_dashboard/no_data.html', {
            'year': year
        })
    
    # Calculate annual totals
    total_generation = sum(r.total_generation for r in annual_data)
    total_renewable_operational = sum(r.renewable_gen_operational for r in annual_data)
    total_renewable = sum(r.total_renewable_generation for r in annual_data)
    total_emissions = sum(r.total_emissions_tonnes for r in annual_data)
    total_operational_demand = sum(r.operational_demand for r in annual_data)
    total_underlying_demand = sum(r.underlying_demand for r in annual_data)
    total_dpv = sum(r.dpv_generation for r in annual_data)
    total_wind = sum(r.wind_generation for r in annual_data)
    total_solar = sum(r.solar_generation for r in annual_data)
    total_biomass = sum(r.biomass_generation for r in annual_data)
    total_gas = sum(r.gas_generation for r in annual_data)
    total_coal = sum(r.coal_generation or 0 for r in annual_data)
    
    # Calculate annual RE percentages
    re_pct_operational = (total_renewable_operational / total_operational_demand * 100) if total_operational_demand > 0 else 0
    re_pct_underlying = (total_renewable / total_underlying_demand * 100) if total_underlying_demand > 0 else 0
    
    # Build annual_summary dictionary for template
    annual_summary = {
        'total_generation': total_generation,
        'renewable_generation': total_renewable,
        'total_emissions': total_emissions,
        'operational_demand': total_operational_demand,
        'underlying_demand': total_underlying_demand,
        're_percentage_operational': re_pct_operational,
        're_percentage_underlying': re_pct_underlying,
        'wind_generation': total_wind,
        'solar_generation': total_solar,
        'dpv_generation': total_dpv,
        'biomass_generation': total_biomass,
        'gas_generation': total_gas,
        'coal_generation': total_coal,
    }
    
    # Aggregate wholesale price statistics for the year
    annual_wholesale_stats = aggregate_wholesale_price_stats(annual_data)
    if annual_wholesale_stats:
        annual_summary.update(annual_wholesale_stats)
    
    # Get target
    try:
        target = TargetScenario.objects.filter(
            year=year,
            target_type__in=['major', 'interim']
        ).first()
    except Exception:
        target = None
    
    # Calculate target status
    target_status = None
    if target:
        diff = re_pct_underlying - target.target_re_percentage
        if diff >= 0:
            target_status = {
                'status': 'ahead',
                'message': f'✓ {diff:.1f} pp above target'
            }
        else:
            target_status = {
                'status': 'behind',
                'message': f'⚠ {abs(diff):.1f} pp below target'
            }
    
    # Get previous year data for comparison
    prev_annual_data = MonthlyREPerformance.objects.filter(
        year=year-1
    ).order_by('month')
    
    prev_annual_summary = None
    yoy_changes = {}
    
    if prev_annual_data.exists():
        prev_total_renewable_operational = sum(r.renewable_gen_operational for r in prev_annual_data)
        prev_total_generation = sum(r.total_generation for r in prev_annual_data)
        prev_total_renewable = sum(r.total_renewable_generation for r in prev_annual_data)
        prev_total_emissions = sum(r.total_emissions_tonnes for r in prev_annual_data)
        prev_operational_demand = sum(r.operational_demand for r in prev_annual_data)
        prev_underlying_demand = sum(r.underlying_demand for r in prev_annual_data)
        prev_total_dpv = sum(r.dpv_generation for r in prev_annual_data)
        prev_total_wind = sum(r.wind_generation for r in prev_annual_data)
        prev_total_solar = sum(r.solar_generation for r in prev_annual_data)
        prev_total_biomass = sum(r.biomass_generation for r in prev_annual_data)
        prev_total_gas = sum(r.gas_generation for r in prev_annual_data)
        prev_total_coal = sum(r.coal_generation or 0 for r in prev_annual_data)
        
        prev_re_pct_operational = (prev_total_renewable_operational / prev_operational_demand * 100) if prev_operational_demand > 0 else 0
        prev_re_with_dpv = prev_total_renewable + prev_total_dpv
        prev_re_pct_underlying = (prev_re_with_dpv / prev_underlying_demand * 100) if prev_underlying_demand > 0 else 0
        
        prev_annual_summary = {
            'total_generation': prev_total_generation,
            'renewable_generation': prev_total_renewable,
            'total_emissions': prev_total_emissions,
            'operational_demand': prev_operational_demand,
            'underlying_demand': prev_underlying_demand,
            're_percentage_operational': prev_re_pct_operational,
            're_percentage_underlying': prev_re_pct_underlying,
            'wind_generation': prev_total_wind,
            'solar_generation': prev_total_solar,
            'dpv_generation': prev_total_dpv,
            'biomass_generation': prev_total_biomass,
            'gas_generation': prev_total_gas,
            'coal_generation': prev_total_coal,
        }
        
        # Add wholesale stats for previous year
        prev_annual_wholesale_stats = aggregate_wholesale_price_stats(prev_annual_data)
        if prev_annual_wholesale_stats:
            prev_annual_summary.update(prev_annual_wholesale_stats)
        
        # Calculate year-over-year changes
        yoy_changes = {
            'emissions': ((total_emissions - prev_total_emissions) / prev_total_emissions * 100) if prev_total_emissions > 0 else None,
            'underlying_demand': ((total_underlying_demand - prev_underlying_demand) / prev_underlying_demand * 100) if prev_underlying_demand > 0 else None,
            're_percentage': re_pct_underlying - prev_re_pct_underlying,
            'renewable_generation': ((total_renewable - prev_total_renewable) / prev_total_renewable * 100) if prev_total_renewable > 0 else None,
        }
        
        # Add wholesale price change
        if annual_wholesale_stats and prev_annual_wholesale_stats:
            if annual_wholesale_stats.get('wholesale_price_avg') and prev_annual_wholesale_stats.get('wholesale_price_avg'):
                yoy_changes['wholesale_price_avg'] = (
                    (annual_wholesale_stats['wholesale_price_avg'] - prev_annual_wholesale_stats['wholesale_price_avg']) /
                    prev_annual_wholesale_stats['wholesale_price_avg'] * 100
                )
    
    # Generate annual charts
    annual_generation_chart = generate_annual_generation_chart(annual_data)
    annual_trends_chart = generate_annual_trends_chart(year)
    
    # Get scenarios for projection - only show base case scenario
    scenarios = TargetScenario.objects.filter(is_active=True, scenario_type='base_case')
    scenario_chart = generate_scenario_comparison_chart(scenarios)
    
    # New capacity this year
    new_capacity = NewCapacityCommissioned.objects.filter(
        report_year=year,
        status='commissioned'
    ).select_related('facility').order_by('commissioned_date')
    
    total_new_capacity = sum(nc.capacity_mw for nc in new_capacity) if new_capacity else 0
    comments = ReportComment.get_comments_for_report('annual', year)
    
    # Get Executive Summary from comments
    executive_summary = comments.filter(category='executive_summary').first()

    context = {
        'year': year,
        'annual_data': annual_data,
        'annual_summary': annual_summary,
        'prev_annual_summary': prev_annual_summary,
        'yoy_changes': yoy_changes,
        'target': target,
        'target_status': target_status,
        'new_capacity': new_capacity,
        'total_new_capacity': total_new_capacity,
        'annual_generation_chart': annual_generation_chart,
        'annual_trends_chart': annual_trends_chart,
        'scenario_chart': scenario_chart,
        'scenarios': scenarios,
        'available_years': get_available_years(),
        'completed_quarters': completed_quarters,
        'comments': comments,
        'executive_summary': executive_summary,
        'report_type': 'annual',
        'next_report': next_report,
    }
    
    return render(request, 'ret_dashboard/annual_review.html', context)

def get_monthly_summary_json(performance):
    """Helper to convert MonthlyREPerformance to JSON-serializable dict"""
    if not performance:
        return None
    
    result = {
        'year': performance.year,
        'month': performance.month,
        'month_name': performance.get_month_name(),
        're_percentage_operational': round(performance.re_percentage_operational, 2),
        're_percentage_underlying': round(performance.re_percentage_underlying, 2),
        'total_generation': round(performance.total_generation, 2),
        'underlying_demand': round(performance.underlying_demand, 2),
        'operational_demand': round(performance.operational_demand, 2),
        'renewable_generation': round(performance.total_renewable_generation, 2),
        'total_emissions': round(performance.total_emissions_tonnes, 2),
        'emissions_intensity': round(performance.emissions_intensity_kg_mwh, 2),
        'data_complete': performance.data_complete,
        'updated_at': performance.updated_at.isoformat() if performance.updated_at else None,
    }
    
    # Add wholesale price statistics if available
    if performance.wholesale_price_avg is not None:
        result['wholesale_price_avg'] = round(performance.wholesale_price_avg, 2)
    if performance.wholesale_price_max is not None:
        result['wholesale_price_max'] = round(performance.wholesale_price_max, 2)
    if performance.wholesale_price_max_datetime:
        result['wholesale_price_max_datetime'] = performance.wholesale_price_max_datetime.isoformat()
    if performance.wholesale_price_min is not None:
        result['wholesale_price_min'] = round(performance.wholesale_price_min, 2)
    if performance.wholesale_price_min_datetime:
        result['wholesale_price_min_datetime'] = performance.wholesale_price_min_datetime.isoformat()
    if performance.wholesale_price_std_dev is not None:
        result['wholesale_price_std_dev'] = round(performance.wholesale_price_std_dev, 2)
    if performance.wholesale_negative_count is not None:
        result['wholesale_negative_count'] = performance.wholesale_negative_count
    if performance.wholesale_spike_count is not None:
        result['wholesale_spike_count'] = performance.wholesale_spike_count
    
    return result

@require_POST
def update_executive_summary(request):
    """
    Update or create executive summary via AJAX.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Authentication required'}, status=403)
        
    try:
        data = json.loads(request.body)
        report_type = data.get('report_type')
        year = int(data.get('year'))
        content = data.get('content')
        
        month = data.get('month')
        if month:
            month = int(month)
            
        quarter = data.get('quarter')
        if quarter:
            quarter = int(quarter)
            
        if not report_type or not year or not content:
            return JsonResponse({'success': False, 'error': 'Missing required fields'})
            
        # Create or update
        summary, created = ReportComment.objects.update_or_create(
            report_type=report_type,
            year=year,
            month=month,
            quarter=quarter,
            author=request.user,
            author_name=request.user.get_full_name() or request.user.username,
            category='executive_summary',
            defaults={
                'content': content,
            }
        )
        
        return JsonResponse({
            'success': True,
            'updated_at': summary.updated_at.strftime('%d %b %Y, %I:%M %p'),
            'author': summary.author_name or summary.author
        })
        
    except Exception as e:
        logger.error(f"Error updating executive summary: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

def get_completed_quarters(year):
    """Get list of completed quarters for a given year"""
    from datetime import date
    
    today = date.today()
    current_year = today.year
    current_quarter = (today.month - 1) // 3 + 1
    
    if year < current_year:
        return [1, 2, 3, 4]
    elif year == current_year:
        return list(range(1, current_quarter))
    else:
        return []