"""
SWIS Renewable Energy Target Dashboard Views

This module provides views for the renewable energy dashboard, including:
- Monthly dashboard
- Quarterly reports
- Annual reviews
- API endpoints for data updates

RE% Calculation Policy:
- Storage (BESS and Hydro pumped storage) is EXCLUDED from RE% calculations
- Operational demand = grid-sent generation minus storage charging
- Underlying demand = operational demand + rooftop solar (DPV)
- RE% (operational) = (wind + utility solar + biomass) / operational demand
- RE% (underlying) = (wind + utility solar + biomass + DPV) / underlying demand
"""

from decimal import Decimal
from collections import defaultdict
from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum
from django.utils import timezone
from datetime import datetime, timedelta
from calendar import month_name, monthrange

from siren_web.models import (
    DPVGeneration, 
    MonthlyREPerformance, 
    RenewableEnergyTarget, 
    NewCapacityCommissioned, 
    TargetScenario, 
    FacilityScada, 
    facilities
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
    
    # Get selected month's performance
    try:
        performance = MonthlyREPerformance.objects.get(year=year, month=month)
    except MonthlyREPerformance.DoesNotExist:
        # Calculate from SCADA data if monthly record doesn't exist
        performance = calculate_monthly_performance(year, month)
        if not performance:
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
    
    # Generate charts
    generation_mix_chart = generate_generation_mix_chart(performance)
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
        'generation_mix_chart': generation_mix_chart,
        'pathway_chart': pathway_chart,
        'available_months': get_available_months(),
        'available_years': get_available_years(),
    }
    
    return render(request, 'ret_dashboard/dashboard.html', context)

# =============================================================================
# Monthly Performance Calculation
# =============================================================================

def calculate_monthly_performance(year, month):
    """
    Calculate monthly performance from SCADA data.
    
    Uses:
    - dispatch_interval (instead of trading_date)
    - facility / facility_id (instead of facility_code)
    - quantity (for generation)
    
    Storage Policy:
    - BESS and Hydro (pumped storage) are excluded from RE% calculations
    - Storage discharge is excluded from demand calculations
    """
    # Get date range for the month
    _, last_day = monthrange(year, month)
    start_datetime = datetime(year, month, 1)
    end_datetime = datetime(year, month, last_day, 23, 59, 59)
    
    # Query SCADA data for this month using dispatch_interval
    scada_data = FacilityScada.objects.filter(
        dispatch_interval__gte=start_datetime,
        dispatch_interval__lte=end_datetime
    )
    
    if not scada_data.exists():
        return None
    
    print(f"Found {scada_data.count()} SCADA records for {month}/{year}")
    
    # Initialize generation totals
    generation = defaultdict(lambda: Decimal("0"))

    # Get unique facilities in this period
    facility_ids = scada_data.values_list('facility_id', flat=True).distinct()
    
    print(f"Found {len(list(facility_ids))} unique facilities")
    
    # Sum generation by facility, then categorize by technology
    for facility_id in facility_ids:
        try:
            facility = facilities.objects.select_related('idtechnologies').get(
                idfacilities=facility_id
            )
        except facilities.DoesNotExist:
            print(f"Warning: Facility ID {facility_id} not found in facilities table")
            continue
        
        # Sum this facility's generation for the period
        facility_gen = scada_data.filter(
            facility_id=facility_id
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        # Convert MWh to GWh
        facility_gen_gwh = facility_gen / 1000
        
        # Get technology type
        tech = facility.idtechnologies.fuel_type.lower()
        
        # Categorize by technology
        if tech == 'bess':
            if facility_gen_gwh >= 0:
                generation['bess_discharge'] += facility_gen_gwh
            else:
                generation['bess_charge'] += abs(facility_gen_gwh)
        elif tech == 'hydro_pumped_storage':
            if facility_gen_gwh >= 0:
                generation['hydro_discharge'] += facility_gen_gwh
            else:
                generation['hydro_charge'] += abs(facility_gen_gwh)
        else:
            generation[tech] += facility_gen_gwh

    # Calculate total operational demand
    # Operational demand = sum of all generation less storage charging
    # Storage discharge is NOT added to demand (it's already in the generation that serves load)
    generation['operational_demand'] = (
        sum(value for key, value in generation.items() 
            if key not in ['bess_charge', 'hydro_charge', 'bess_discharge', 'hydro_discharge', 'operational_demand'])
    )
    
    # Get rooftop solar generation estimate
    generation['dpv'] = estimate_rooftop_generation(year, month)
    
    # Calculate underlying demand (operational + rooftop)
    underlying_demand = generation['operational_demand'] + generation['dpv']
    
    # Calculate renewable generation totals
    # Note: Hydro (pumped storage) is EXCLUDED - it's storage like BESS
    renewable_gen_operational = (
        generation['wind'] +
        generation['solar'] +
        generation['biomass']
    )
    renewable_gen_underlying = renewable_gen_operational + generation['dpv']
    
    # Calculate RE percentages
    if generation['operational_demand'] > 0:
        re_percentage_operational = (renewable_gen_operational / generation['operational_demand']) * 100
    else:
        re_percentage_operational = 0
        
    if underlying_demand > 0:
        re_percentage_underlying = (renewable_gen_underlying / underlying_demand) * 100
    else:
        re_percentage_underlying = 0
    
    # Calculate emissions
    gas_emissions = generation['gas'] * 380  # tonnes CO2-e/GWh
    coal_emissions = generation['coal'] * 900  # tonnes CO2-e/GWh
    total_emissions = gas_emissions + coal_emissions
    
    # Calculate emissions intensity (kg CO2-e per MWh)
    if underlying_demand > 0:
        emissions_intensity = (total_emissions * 1000) / underlying_demand
    else:
        emissions_intensity = 0
    
    # Get peak/minimum demand
    peak_record = scada_data.order_by('-quantity').first()
    min_record = scada_data.order_by('quantity').first()
    
    # Calculate best RE hour (placeholder - would need interval-level calculation for accuracy)
    best_re_hour = None
    best_re_percentage = 0
    
    print(f"Creating MonthlyREPerformance record for {month}/{year}")
    print(f"  Operational demand: {generation['operational_demand']:.1f} GWh")
    print(f"  Underlying demand: {underlying_demand:.1f} GWh")
    print(f"  Wind: {generation['wind']:.1f} GWh")
    print(f"  Solar (Utility): {generation['solar']:.1f} GWh")
    print(f"  Solar (Rooftop): {generation['dpv']:.1f} GWh")
    print(f"  Biomass: {generation['biomass']:.1f} GWh")
    print(f"  Hydro (pumped storage): {generation.get('hydro_discharge', 0):.1f} GWh (excluded from RE%)")
    print(f"  Gas: {generation['gas']:.1f} GWh")
    print(f"  RE% (operational): {re_percentage_operational:.1f}%")
    print(f"  RE% (underlying): {re_percentage_underlying:.1f}%")
    print(f"  Total emissions: {total_emissions:.0f} tonnes")
    
    # Total storage discharge (BESS + Hydro)
    total_storage_discharge = generation['bess_discharge'] + generation.get('hydro_discharge', 0)
    total_storage_charge = generation['bess_charge'] + generation.get('hydro_charge', 0)
    
    # Create or update MonthlyREPerformance record
    performance, created = MonthlyREPerformance.objects.update_or_create(
        year=year,
        month=month,
        defaults={
            'total_generation': generation['operational_demand'],
            'operational_demand': generation['operational_demand'],
            'underlying_demand': underlying_demand,
            'wind_generation': generation['wind'],
            'solar_generation': generation['solar'],
            'dpv_generation': generation['dpv'],
            'biomass_generation': generation['biomass'],
            'hydro_generation': generation.get('hydro_discharge', 0),  # Store for reference, excluded from RE%
            'gas_generation': generation['gas'],
            'coal_generation': generation['coal'],
            'storage_discharge': total_storage_discharge,
            'storage_charge': total_storage_charge,
            'total_emissions_tonnes': total_emissions,
            'emissions_intensity_kg_mwh': emissions_intensity,
            'peak_demand_mw': peak_record.quantity if peak_record else None,
            'peak_demand_datetime': peak_record.dispatch_interval if peak_record else None,
            'minimum_demand_mw': min_record.quantity if min_record else None,
            'minimum_demand_datetime': min_record.dispatch_interval if min_record else None,
            'best_re_hour_percentage': best_re_percentage if best_re_percentage > 0 else None,
            'best_re_hour_datetime': best_re_hour,
            'data_complete': True,
            'data_source': 'SCADA',
        }
    )
    
    return performance

def estimate_rooftop_generation(year: int, month: int) -> float:
    """
    Returns total rooftop PV generation for the given year and month in GWh.
    DPVGeneration intervals are 30 minutes and estimated_generation is in MW.
    """

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

def generate_generation_mix_chart(performance):
    """
    Generate Plotly chart for generation mix.
    
    Note: Storage (BESS + Hydro) is excluded from the pie chart
    as it's not counted in RE% calculations.
    """
    import plotly.graph_objects as go
    
    # Data for pie chart - excludes storage
    labels = ['Wind', 'Solar (Utility)', 'Solar (Rooftop)', 'Biomass', 'Gas (CCGT)']
    
    values = [
        performance.wind_generation,
        performance.solar_generation,
        performance.dpv_generation,
        performance.biomass_generation,
        performance.gas_generation,
    ]
    
    # Colors - green for renewables, gray for fossil
    colors = ['#27ae60', '#f39c12', '#f1c40f', '#16a085', '#95a5a6']
    
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        marker=dict(colors=colors),
        textposition='auto',
        textinfo='label+percent',
        hovertemplate='<b>%{label}</b><br>%{value:.1f} GWh<br>%{percent}<extra></extra>'
    )])
    
    fig.update_layout(
        title=f"Generation Mix - {performance.get_month_name()} {performance.year}<br><sub>(Storage excluded from RE%)</sub>",
        height=400,
        showlegend=True,
        margin=dict(l=20, r=20, t=80, b=20)
    )
    
    return fig.to_html(include_plotlyjs='cdn', div_id='generation_mix_chart')

def generate_pathway_chart(current_year, current_month):
    """Generate chart showing pathway to 2040 target"""
    import plotly.graph_objects as go
    
    # Get historical performance
    historical = MonthlyREPerformance.objects.filter(
        year__gte=2023
    ).order_by('year', 'month')
    
    # Get targets
    targets = RenewableEnergyTarget.objects.all().order_by('target_year')
    
    # Prepare data for plotting
    hist_years = []
    hist_re_pct = []
    
    for record in historical:
        date_label = f"{record.year}-{record.month:02d}"
        hist_years.append(date_label)
        hist_re_pct.append(record.re_percentage_underlying)
    
    # Target trajectory
    target_years = [t.target_year for t in targets]
    target_pcts = [t.target_percentage for t in targets]
    
    # Create figure
    fig = go.Figure()
    
    # Historical performance
    fig.add_trace(go.Scatter(
        x=hist_years,
        y=hist_re_pct,
        mode='lines+markers',
        name='Actual RE%',
        line=dict(color='#27ae60', width=2),
        marker=dict(size=6)
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
        title='Pathway to 2040 Target',
        xaxis_title='Year',
        yaxis_title='Renewable Energy %',
        height=400,
        hovermode='x unified',
        yaxis=dict(range=[0, 100])
    )
    
    return fig.to_html(include_plotlyjs='cdn', div_id='pathway_chart')


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
    
    # Add line for each year
    for y in sorted(years_data.keys()):
        records = years_data[y]
        months = [record.month for record in records]
        re_pcts = [record.re_percentage_underlying for record in records]
        
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
        target = RenewableEnergyTarget.objects.get(target_year=year)
        fig.add_trace(go.Scatter(
            name=f'{year} Target',
            x=list(range(1, 13)),
            y=[target.target_percentage] * 12,
            mode='lines',
            line=dict(color='red', width=2, dash='dash'),
            showlegend=True
        ))
    except RenewableEnergyTarget.DoesNotExist:
        pass
    
    fig.update_layout(
        title='Multi-Year RE% Trends',
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
    
    scenario_names = [s.scenario_name for s in scenarios]
    re_percentages = [s.projected_re_percentage_2040 for s in scenarios]
    
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
    
    # Add target line
    fig.add_hline(
        y=75, 
        line_dash="dash", 
        line_color="red",
        annotation_text="2040 Target (75%)",
        annotation_position="right"
    )
    
    fig.update_layout(
        title='2040 Scenario Projections',
        xaxis_title='Scenario',
        yaxis_title='Projected RE% by 2040',
        height=400,
        showlegend=False
    )
    
    return fig.to_html(include_plotlyjs='cdn', div_id='scenario_comparison_chart')


# =============================================================================
# Helper Functions
# =============================================================================

def get_available_months():
    """Get list of available months with data"""
    records = MonthlyREPerformance.objects.values(
        'year', 'month'
    ).distinct().order_by('-year', '-month')
    
    months = []
    for record in records:
        months.append({
            'value': f"{record['year']}-{record['month']:02d}",
            'label': f"{month_name[record['month']]} {record['year']}"
        })
    
    return months

def get_available_years():
    """Get list of available years"""
    years = MonthlyREPerformance.objects.values_list(
        'year', flat=True
    ).distinct().order_by('-year')
    
    return list(years)

# =============================================================================
# Quarterly Report View
# =============================================================================

def quarterly_report(request, year, quarter):
    """
    Generate quarterly report (Q1, Q2, Q3, or Q4).
    Aggregates 3 months of data for the specified quarter.
    """
    year = int(year)
    quarter = int(quarter)
    
    # Validate quarter
    if quarter not in [1, 2, 3, 4]:
        return render(request, 'ret_dashboard/no_data.html', {
            'year': year,
            'message': f'Invalid quarter: {quarter}. Must be 1, 2, 3, or 4.'
        })
    
    # Map quarter to months
    quarter_months = {
        1: [1, 2, 3],    # Q1: Jan, Feb, Mar
        2: [4, 5, 6],    # Q2: Apr, May, Jun
        3: [7, 8, 9],    # Q3: Jul, Aug, Sep
        4: [10, 11, 12]  # Q4: Oct, Nov, Dec
    }
    
    months = quarter_months[quarter]
    quarter_start_month = month_name[months[0]]
    quarter_end_month = month_name[months[-1]]
    
    # Get monthly performance data for this quarter
    monthly_performances = MonthlyREPerformance.objects.filter(
        year=year,
        month__in=months
    ).order_by('month')
    
    if not monthly_performances.exists():
        return render(request, 'ret_dashboard/no_data.html', {
            'year': year,
            'quarter': quarter,
            'message': f'No data available for Q{quarter} {year}. Please process monthly data first.'
        })
    
    # Check if we have all 3 months
    if monthly_performances.count() < 3:
        missing_months = [m for m in months if not monthly_performances.filter(month=m).exists()]
        missing_names = [month_name[m] for m in missing_months]
        return render(request, 'ret_dashboard/no_data.html', {
            'year': year,
            'quarter': quarter,
            'message': f'Incomplete data for Q{quarter} {year}. Missing: {", ".join(missing_names)}'
        })
    
    # Calculate quarterly summary using model's classmethod
    quarterly_summary = MonthlyREPerformance.aggregate_summary(monthly_performances)
    
    # Add month names to monthly performances for template
    monthly_performances_with_names = []
    for perf in monthly_performances:
        perf.month_name = month_name[perf.month]
        monthly_performances_with_names.append(perf)
    
    # Get same quarter from previous year for comparison
    prev_year_monthly = MonthlyREPerformance.objects.filter(
        year=year-1,
        month__in=months
    )
    if prev_year_monthly.exists():
        prev_quarter_summary = MonthlyREPerformance.aggregate_summary(prev_year_monthly)
    else:
        prev_quarter_summary = {
            're_percentage_operational': 0,
            're_percentage_underlying': 0,
        }    
    # Get year-to-date summary (all months up to end of this quarter)
    ytd_months = list(range(1, months[-1] + 1))
    ytd_data = MonthlyREPerformance.objects.filter(
        year=year,
        month__in=ytd_months
    )
    ytd_summary = MonthlyREPerformance.aggregate_summary(ytd_data)
    
    # Get previous year YTD for comparison
    prev_ytd_data = MonthlyREPerformance.objects.filter(
        year=year-1,
        month__in=ytd_months
    )
    if prev_ytd_data.exists():
        prev_ytd_summary = MonthlyREPerformance.aggregate_summary(prev_ytd_data)
    else:
        # Provide default values to avoid template errors
        prev_ytd_summary = {
            're_percentage_operational': 0,
            're_percentage_underlying': 0,
            'total_emissions': 0,
            'emissions_intensity': 0,
        }
    
    # Get target for this year
    target = _get_target_for_year(year)
    
    # Get new capacity commissioned during this quarter
    new_capacity = NewCapacityCommissioned.objects.filter(
        report_year=year,
        report_month__in=months,
        status='commissioned'
    ).select_related('facility', 'facility__idtechnologies').order_by('commissioned_date')
    
    context = {
        'year': year,
        'quarter': quarter,
        'quarter_start_month': quarter_start_month,
        'quarter_end_month': quarter_end_month,
        'quarterly_summary': quarterly_summary,
        'monthly_performances': monthly_performances_with_names,
        'prev_quarter_summary': prev_quarter_summary,
        'ytd_summary': ytd_summary,
        'prev_ytd_summary': prev_ytd_summary,
        'target': target,
        'new_capacity': new_capacity,
    }
    
    return render(request, 'ret_dashboard/quarterly_report.html', context)


# =============================================================================
# Annual Review View
# =============================================================================

def annual_review(request, year):
    """Generate comprehensive annual review"""
    year = int(year)
    
    # Get all monthly data for the year
    annual_data = MonthlyREPerformance.objects.filter(
        year=year
    ).order_by('month')
    
    if not annual_data.exists():
        return render(request, 'ret_dashboard/no_data.html', {
            'year': year,
            'message': f'No data available for {year}'
        })
    
    # Calculate annual summary using model's classmethod
    annual_summary = MonthlyREPerformance.aggregate_summary(annual_data)
    
    # Get previous year for comparison
    prev_year_data = MonthlyREPerformance.objects.filter(year=year-1)
    prev_annual_summary = MonthlyREPerformance.aggregate_summary(prev_year_data) if prev_year_data.exists() else None
    
    # Get target for this year
    target = _get_target_for_year(year)
    
    # Calculate target status
    if target and annual_summary:
        gap = annual_summary['re_percentage_underlying'] - target.target_percentage
        target_status = {
            'status': 'ahead' if gap >= 0 else 'behind',
            'gap': gap,
            'message': f"{'✓' if gap >= 0 else '⚠'} {abs(gap):.1f} percentage points {'ahead' if gap >= 0 else 'behind'}"
        }
    else:
        target_status = None
    
    # Get all scenarios for 2040 projections
    scenarios = TargetScenario.objects.filter(is_active=True).order_by('scenario_type')
    
    # Get new capacity commissioned during the year
    new_capacity = NewCapacityCommissioned.objects.filter(
        report_year=year,
        status='commissioned'
    ).select_related('facility')
    
    total_new_capacity = new_capacity.aggregate(
        total=Sum('capacity_mw')
    )['total'] or 0
    
    # Calculate year-over-year changes
    yoy_changes = {}
    if prev_annual_summary and annual_summary:
        yoy_changes = {
            're_percentage': annual_summary['re_percentage_underlying'] - prev_annual_summary['re_percentage_underlying'],
            'total_generation': ((annual_summary['total_generation'] - prev_annual_summary['total_generation']) / 
                               prev_annual_summary['total_generation'] * 100) if prev_annual_summary['total_generation'] else 0,
            'emissions': ((annual_summary['total_emissions'] - prev_annual_summary['total_emissions']) / 
                         prev_annual_summary['total_emissions'] * 100) if prev_annual_summary['total_emissions'] else 0,
            'underlying_demand': ((annual_summary['underlying_demand'] - prev_annual_summary['underlying_demand']) / 
                                 prev_annual_summary['underlying_demand'] * 100) if prev_annual_summary['underlying_demand'] else 0,
        }
    
    # Generate annual charts
    annual_generation_chart = generate_annual_generation_chart(annual_data)
    annual_trends_chart = generate_annual_trends_chart(year)
    scenario_comparison_chart = generate_scenario_comparison_chart(scenarios)
    
    context = {
        'year': year,
        'annual_summary': annual_summary,
        'prev_annual_summary': prev_annual_summary,
        'target': target,
        'target_status': target_status,
        'yoy_changes': yoy_changes,
        'monthly_data': annual_data,
        'scenarios': scenarios,
        'new_capacity': new_capacity,
        'total_new_capacity': total_new_capacity,
        'annual_generation_chart': annual_generation_chart,
        'annual_trends_chart': annual_trends_chart,
        'scenario_comparison_chart': scenario_comparison_chart,
    }
    
    return render(request, 'ret_dashboard/annual_review.html', context)


def _get_target_for_year(year):
    """
    Get target for a given year, interpolating if necessary.
    
    Returns:
        Target object or namedtuple with target_year and target_percentage
    """
    try:
        return RenewableEnergyTarget.objects.get(target_year=year)
    except RenewableEnergyTarget.DoesNotExist:
        # Try to interpolate
        targets = RenewableEnergyTarget.objects.all().order_by('target_year')
        before = targets.filter(target_year__lt=year).last()
        after = targets.filter(target_year__gt=year).first()
        
        if before and after:
            # Linear interpolation
            year_diff = after.target_year - before.target_year
            year_progress = year - before.target_year
            target_diff = after.target_percentage - before.target_percentage
            interpolated_percentage = before.target_percentage + (target_diff * year_progress / year_diff)
            
            from collections import namedtuple
            Target = namedtuple('Target', ['target_year', 'target_percentage'])
            return Target(year, interpolated_percentage)
        
        return None


# =============================================================================
# API Endpoints
# =============================================================================

@csrf_exempt
@require_POST
def update_monthly_data(request):
    """
    API endpoint to trigger manual update of monthly data.
    POST to /api/ret_dashboard/update_monthly/
    
    Body (JSON):
    {
        "year": 2025,
        "month": 9,
        "force": true
    }
    """
    import json
    
    try:
        data = json.loads(request.body)
        year = data.get('year')
        month = data.get('month')
        force = data.get('force', False)
        
        if not year or not month:
            return JsonResponse({
                'success': False,
                'error': 'Year and month are required'
            }, status=400)
        
        # Check if data already exists
        existing = MonthlyREPerformance.objects.filter(
            year=year, month=month
        ).first()
        
        if existing and not force:
            return JsonResponse({
                'success': False,
                'error': f'Data for {month}/{year} already exists. Use force=true to overwrite.',
                'data': {
                    're_percentage_operational': existing.re_percentage_operational,
                    're_percentage_underlying': existing.re_percentage_underlying,
                    'total_emissions': existing.total_emissions_tonnes
                }
            }, status=409)
        
        # Calculate performance
        performance = calculate_monthly_performance(year, month)
        
        if not performance:
            return JsonResponse({
                'success': False,
                'error': f'No SCADA data found for {month}/{year}'
            }, status=404)
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully updated data for {month}/{year}',
            'data': {
                're_percentage_operational': performance.re_percentage_operational,
                're_percentage_underlying': performance.re_percentage_underlying,
                'total_generation': performance.total_generation,
                'operational_demand': performance.operational_demand,
                'underlying_demand': performance.underlying_demand,
                'total_emissions': performance.total_emissions_tonnes,
                'emissions_intensity': performance.emissions_intensity_kg_mwh
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON in request body'
        }, status=400)
    
    except Exception as e:
        logger.error(f"Error updating monthly data: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

def api_calculate_monthly(request, year, month):
    """
    API endpoint to calculate/recalculate monthly performance.
    GET /api/ret_dashboard/calculate/<year>/<month>/
    
    Query params:
    - force=1 : Force recalculation even if data exists
    - dry_run=1 : Calculate but don't save
    """
    year = int(year)
    month = int(month)
    force = request.GET.get('force', '0') == '1'
    dry_run = request.GET.get('dry_run', '0') == '1'
    
    try:
        # Check if data already exists
        existing = MonthlyREPerformance.objects.filter(
            year=year, month=month
        ).first()
        
        if existing and not force:
            return JsonResponse({
                'success': True,
                'message': f'Data for {month}/{year} already exists',
                'data': {
                    're_percentage_operational': existing.re_percentage_operational,
                    're_percentage_underlying': existing.re_percentage_underlying,
                    'total_generation': existing.total_generation,
                    'underlying_demand': existing.underlying_demand,
                    'operational_demand': existing.operational_demand,
                    'wind_generation': existing.wind_generation,
                    'solar_generation': existing.solar_generation,
                    'dpv_generation': existing.dpv_generation,
                    'total_emissions': existing.total_emissions_tonnes,
                    'emissions_intensity': existing.emissions_intensity_kg_mwh,
                    'data_complete': existing.data_complete,
                    'updated_at': existing.updated_at.isoformat() if existing.updated_at else None
                },
                'existing': True
            })
        
        if dry_run:
            # Calculate but don't save
            _, last_day = monthrange(year, month)
            start_date = datetime(year, month, 1).date()
            end_date = datetime(year, month, last_day).date()
            
            scada_data = FacilityScada.objects.filter(
                trading_date__gte=start_date,
                trading_date__lte=end_date
            )
            
            if not scada_data.exists():
                return JsonResponse({
                    'success': False,
                    'error': f'No SCADA data found for {month}/{year}'
                }, status=404)
            
            return JsonResponse({
                'success': True,
                'message': f'Dry run for {month}/{year}',
                'data': {
                    'scada_records': scada_data.count(),
                    'date_range': {
                        'start': start_date.isoformat(),
                        'end': end_date.isoformat()
                    }
                },
                'dry_run': True
            })
        
        # Calculate and save
        performance = calculate_monthly_performance(year, month)
        
        if not performance:
            return JsonResponse({
                'success': False,
                'error': f'No SCADA data found for {month}/{year}'
            }, status=404)
        
        # Get target status
        target_status = performance.get_status_vs_target()
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully calculated data for {month}/{year}',
            'data': {
                're_percentage_operational': performance.re_percentage_operational,
                're_percentage_underlying': performance.re_percentage_underlying,
                'total_generation': performance.total_generation,
                'underlying_demand': performance.underlying_demand,
                'operational_demand': performance.operational_demand,
                'renewable_generation': performance.total_renewable_generation,
                'wind_generation': performance.wind_generation,
                'solar_generation': performance.solar_generation,
                'dpv_generation': performance.dpv_generation,
                'biomass_generation': performance.biomass_generation,
                'hydro_generation': performance.hydro_generation,
                'gas_generation': performance.gas_generation,
                'total_emissions': performance.total_emissions_tonnes,
                'emissions_intensity': performance.emissions_intensity_kg_mwh,
                'peak_demand_mw': performance.peak_demand_mw,
                'minimum_demand_mw': performance.minimum_demand_mw,
                'target_status': target_status,
                'data_complete': performance.data_complete,
                'created_at': performance.created_at.isoformat() if performance.created_at else None,
                'updated_at': performance.updated_at.isoformat() if performance.updated_at else None
            },
            'calculated': True
        })
        
    except Exception as e:
        logger.error(f"Error calculating monthly data: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

def get_monthly_summary_json(performance):
    """Helper to convert MonthlyREPerformance to JSON-serializable dict"""
    if not performance:
        return None
    
    return {
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
        'updated_at': performance.updated_at.isoformat() if performance.updated_at else None
    }
