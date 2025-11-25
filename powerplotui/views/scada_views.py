# powerplot/views.py
from django.db.models import Case, Count, FloatField, Sum, Q, When
from django.db.models.functions import Coalesce
from django.shortcuts import render
from django.http import HttpResponse
from siren_web.models import LoadAnalysisSummary, facilities, Technologies
from powerplotui.services.load_analyzer import LoadAnalyzer
from datetime import datetime, date
import calendar
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import logging
import csv

logger = logging.getLogger(__name__)

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
    
    # Calculate BESS percentages and efficiency
    bess_percentage = (
        (summary.storage_discharge / summary.operational_demand) * 100 
        if summary.operational_demand > 0 else 0
    )
    ytd_bess_percentage = (
        (ytd_summary['storage_discharge'] / ytd_summary['operational_demand']) * 100
        if ytd_summary['operational_demand'] > 0 else 0
    )
    ytd_prev_bess_percentage = (
        (ytd_prev_summary['storage_discharge'] / ytd_prev_summary['operational_demand']) * 100
        if ytd_prev_summary['operational_demand'] > 0 else 0
    )
    
    bess_efficiency = (
        (summary.storage_discharge / abs(summary.storage_charge)) * 100
        if summary.storage_charge != 0 else 0
    )
    ytd_bess_efficiency = (
        (ytd_summary['storage_discharge'] / abs(ytd_summary['storage_charge'])) * 100
        if ytd_summary['storage_charge'] != 0 else 0
    )
    
    # Generate improved charts
    chart_gen = ChartGenerator()
    pie_chart_html = chart_gen.create_technology_breakdown_pies(summary, ytd_summary)
    
    # Load diurnal data from LoadAnalyzer
    analyzer = LoadAnalyzer()
    diurnal_data_month = analyzer.get_diurnal_profile(year, month)
    diurnal_data_ytd = analyzer.get_diurnal_profile_ytd(year, month)
    
    # Create stacked area charts
    diurnal_chart_month = chart_gen.create_diurnal_area_chart(
        diurnal_data_month, 
        f"{calendar.month_name[month]} {year}"
    )
    diurnal_chart_ytd = chart_gen.create_diurnal_area_chart(
        diurnal_data_ytd, 
        f"YTD {year}"
    )
    
    # Get facility data for Facility Overview tab
    facility_manager = FacilityManager()
    facilities_data = facility_manager.get_all_facilities_with_performance(year, month)
    facility_stats = facility_manager.get_facility_statistics()
    capacity_chart = chart_gen.create_capacity_by_fuel_chart(facilities_data)
    top_performers = facility_manager.get_top_performers(year, month, limit=10)
    
    # Get historical data for Historical Data tab
    historical_data = get_historical_data(year, month)
    historical_stats = calculate_historical_stats(historical_data)
    yearly_comparison = get_yearly_comparison()
    
    # Generate historical charts
    historical_demand_chart = chart_gen.create_historical_demand_chart(historical_data)
    historical_re_chart = chart_gen.create_historical_re_chart(historical_data)
    historical_mix_chart = chart_gen.create_historical_mix_chart(historical_data)
    
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
        'ytd_prev_bess_percentage': ytd_prev_bess_percentage,
        'bess_efficiency': bess_efficiency,
        'ytd_bess_efficiency': ytd_bess_efficiency,
        'pie_chart': pie_chart_html,
        'diurnal_chart_month': diurnal_chart_month,
        'diurnal_chart_ytd': diurnal_chart_ytd,
        'year': year,
        'month': month,
        'month_name': calendar.month_name[month],
        'available_months': available_months,
        'available_years': available_years,
        # Facility Overview data
        'facilities': facilities_data,
        'facility_stats': facility_stats,
        'capacity_chart': capacity_chart,
        'top_performers': top_performers,
        # Historical Data tab
        'historical_data': historical_data,
        'historical_stats': historical_stats,
        'yearly_comparison': yearly_comparison,
        'historical_demand_chart': historical_demand_chart,
        'historical_re_chart': historical_re_chart,
        'historical_mix_chart': historical_mix_chart,
    }
    
    return render(request, 'scada/analysis.html', context)


def get_historical_data(current_year, current_month, years_back=3):
    """
    Retrieve historical monthly data for the past N years
    Returns a list of dictionaries with monthly summaries
    """
    start_year = current_year - years_back
    
    summaries = LoadAnalysisSummary.objects.filter(
        period_type='MONTHLY',
        period_date__gte=date(start_year, 1, 1),
        period_date__lte=date(current_year, current_month, 1)
    ).order_by('period_date')
    
    historical_records = []
    for summary in summaries:
        historical_records.append({
            'period_date': summary.period_date,
            'period_label': f"{calendar.month_name[summary.period_date.month]} {summary.period_date.year}",
            'operational_demand': float(summary.operational_demand),
            'underlying_demand': float(summary.underlying_demand),
            'wind_generation': float(summary.wind_generation),
            'solar_generation': float(summary.solar_generation),
            'dpv_generation': float(summary.dpv_generation),
            'fossil_generation': float(summary.fossil_generation),
            'storage_discharge': float(summary.storage_discharge),
            'storage_charge': float(summary.storage_charge),
            're_percentage_operational': float(summary.re_percentage_operational),
            're_percentage_underlying': float(summary.re_percentage_underlying),
            'dpv_percentage_underlying': float(summary.dpv_percentage_underlying),
        })
    
    return historical_records


def calculate_historical_stats(historical_data):
    """Calculate summary statistics from historical data"""
    if not historical_data:
        return {
            'avg_operational_demand': 0,
            'min_operational_demand': 0,
            'max_operational_demand': 0,
            're_growth': 0,
            'first_re_percent': 0,
            'last_re_percent': 0,
            'total_re_generation': 0,
            'peak_re_month': 'N/A',
            'peak_re_value': 0,
        }
    
    operational_demands = [record['operational_demand'] for record in historical_data]
    re_percentages = [record['re_percentage_operational'] for record in historical_data]
    
    # Find peak RE month
    peak_record = max(historical_data, key=lambda x: x['re_percentage_operational'])
    
    # Calculate total RE generation
    total_re = sum(
        record['wind_generation'] + record['solar_generation'] 
        for record in historical_data
    )
    
    return {
        'avg_operational_demand': sum(operational_demands) / len(operational_demands),
        'min_operational_demand': min(operational_demands),
        'max_operational_demand': max(operational_demands),
        're_growth': re_percentages[-1] - re_percentages[0] if len(re_percentages) > 1 else 0,
        'first_re_percent': re_percentages[0] if re_percentages else 0,
        'last_re_percent': re_percentages[-1] if re_percentages else 0,
        'total_re_generation': total_re,
        'peak_re_month': peak_record['period_label'],
        'peak_re_value': peak_record['re_percentage_operational'],
    }


def get_yearly_comparison():
    """
    Get year-over-year comparison of annual totals
    """
    # Get all available years
    years = LoadAnalysisSummary.objects.filter(
        period_type='MONTHLY'
    ).values_list('period_date__year', flat=True).distinct().order_by('period_date__year')
    
    yearly_data = []
    prev_year_data = None
    
    for year in years:
        year_summaries = LoadAnalysisSummary.objects.filter(
            period_type='MONTHLY',
            period_date__year=year
        )
        
        if not year_summaries:
            continue
        
        # Aggregate annual data
        year_total = {
            'year': year,
            'total_operational_demand': sum(s.operational_demand for s in year_summaries),
            'total_underlying_demand': sum(s.underlying_demand for s in year_summaries),
            'total_wind': sum(s.wind_generation for s in year_summaries),
            'total_solar': sum(s.solar_generation for s in year_summaries),
            'total_dpv': sum(s.dpv_generation for s in year_summaries),
            'total_fossil': sum(s.fossil_generation for s in year_summaries),
        }
        
        # Calculate average RE percentage for the year
        re_percentages = [s.re_percentage_operational for s in year_summaries]
        year_total['avg_re_percentage'] = sum(re_percentages) / len(re_percentages) if re_percentages else 0
        
        # Calculate YoY changes
        if prev_year_data:
            year_total['yoy_demand_change'] = (
                (year_total['total_operational_demand'] / prev_year_data['total_operational_demand'] - 1) * 100
                if prev_year_data['total_operational_demand'] > 0 else None
            )
            year_total['yoy_re_change'] = (
                year_total['avg_re_percentage'] - prev_year_data['avg_re_percentage']
            )
        else:
            year_total['yoy_demand_change'] = None
            year_total['yoy_re_change'] = None
        
        yearly_data.append(year_total)
        prev_year_data = year_total
    
    return yearly_data


def export_historical_data(request):
    """Export historical data as CSV"""
    start_year = int(request.GET.get('start', 2023))
    end_year = int(request.GET.get('end', datetime.now().year))
    
    summaries = LoadAnalysisSummary.objects.filter(
        period_type='MONTHLY',
        period_date__year__gte=start_year,
        period_date__year__lte=end_year
    ).order_by('period_date')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="swis_historical_data_{start_year}_{end_year}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Period', 'Operational Demand (GWh)', 'Underlying Demand (GWh)',
        'Wind Generation (GWh)', 'Solar Generation (GWh)', 'DPV Generation (GWh)',
        'Battery Discharge (GWh)', 'Battery Charge (GWh)', 'Fossil Generation (GWh)',
        'RE % Operational', 'RE % Underlying', 'DPV % Underlying'
    ])
    
    for summary in summaries:
        writer.writerow([
            f"{calendar.month_name[summary.period_date.month]} {summary.period_date.year}",
            float(summary.operational_demand),
            float(summary.underlying_demand),
            float(summary.wind_generation),
            float(summary.solar_generation),
            float(summary.dpv_generation),
            float(summary.storage_discharge),
            float(summary.storage_charge),
            float(summary.fossil_generation),
            float(summary.re_percentage_operational),
            float(summary.re_percentage_underlying),
            float(summary.dpv_percentage_underlying),
        ])
    
    return response


def aggregate_summaries(summaries):
    """Aggregate multiple monthly summaries into totals"""
    if not summaries:
        return {
            'operational_demand': 0,
            'underlying_demand': 0,
            'storage_discharge': 0,
            'storage_charge': 0,
            'fossil_generation': 0,
            're_percentage_operational': 0,
            're_percentage_underlying': 0,
            'dpv_generation': 0,
            'dpv_percentage_underlying': 0,
            'wind_generation': 0,
            'solar_generation': 0,
        }
    
    total = {
        'operational_demand': sum(s.operational_demand for s in summaries),
        'underlying_demand': sum(s.underlying_demand for s in summaries),
        'storage_discharge': sum(s.storage_discharge for s in summaries),
        'storage_charge': sum(s.storage_charge for s in summaries),
        'fossil_generation': sum(s.fossil_generation for s in summaries),
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
        ((total_re + total['dpv_generation']) / total['underlying_demand']) * 100
        if total['underlying_demand'] > 0 else 0
    )
    
    total['dpv_percentage_underlying'] = (
        (total['dpv_generation'] / total['underlying_demand']) * 100
        if total['underlying_demand'] > 0 else 0
    )
    
    return total


class ChartGenerator:
    """Generate Plotly charts for the analysis report"""
    
    COLORS = {
        'wind': '#3498db',      # Blue
        'solar': '#f39c12',     # Orange
        'dpv': '#f1c40f',       # Yellow
        'battery': '#9b59b6',   # Purple
        'fossil': '#95a5a6',    # Gray
        'hydro': '#1abc9c',     # Teal
        're': '#27ae60',        # Green
    }
    
    def create_technology_breakdown_pies(self, monthly_summary, ytd_summary):
        """Create 4 pie charts showing operational and underlying demand breakdown"""
        
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                'Monthly Operational Demand',
                'Monthly Underlying Demand',
                'YTD Operational Demand',
                'YTD Underlying Demand'
            ),
            specs=[[{'type': 'pie'}, {'type': 'pie'}],
                   [{'type': 'pie'}, {'type': 'pie'}]]
        )
        
        # Monthly Operational
        fig.add_trace(go.Pie(
            labels=['Wind', 'Solar', 'Battery', 'Fossil'],
            values=[
                float(monthly_summary.wind_generation),
                float(monthly_summary.solar_generation),
                float(monthly_summary.storage_discharge),
                float(monthly_summary.fossil_generation)
            ],
            marker_colors=[self.COLORS['wind'], self.COLORS['solar'], 
                          self.COLORS['battery'], self.COLORS['fossil']],
            textinfo='label+percent',
            hovertemplate='%{label}<br>%{value:.1f} GWh<br>%{percent}<extra></extra>'
        ), row=1, col=1)
        
        # Monthly Underlying
        fig.add_trace(go.Pie(
            labels=['Wind', 'Solar', 'DPV', 'Battery', 'Fossil'],
            values=[
                float(monthly_summary.wind_generation),
                float(monthly_summary.solar_generation),
                float(monthly_summary.dpv_generation),
                float(monthly_summary.storage_discharge),
                float(monthly_summary.fossil_generation)
            ],
            marker_colors=[self.COLORS['wind'], self.COLORS['solar'], 
                          self.COLORS['dpv'], self.COLORS['battery'], 
                          self.COLORS['fossil']],
            textinfo='label+percent',
            hovertemplate='%{label}<br>%{value:.1f} GWh<br>%{percent}<extra></extra>'
        ), row=1, col=2)
        
        # YTD Operational
        fig.add_trace(go.Pie(
            labels=['Wind', 'Solar', 'Battery', 'Fossil'],
            values=[
                ytd_summary['wind_generation'],
                ytd_summary['solar_generation'],
                ytd_summary['storage_discharge'],
                ytd_summary['fossil_generation']
            ],
            marker_colors=[self.COLORS['wind'], self.COLORS['solar'], 
                          self.COLORS['battery'], self.COLORS['fossil']],
            textinfo='label+percent',
            hovertemplate='%{label}<br>%{value:.1f} GWh<br>%{percent}<extra></extra>'
        ), row=2, col=1)
        
        # YTD Underlying
        fig.add_trace(go.Pie(
            labels=['Wind', 'Solar', 'DPV', 'Battery', 'Fossil'],
            values=[
                ytd_summary['wind_generation'],
                ytd_summary['solar_generation'],
                ytd_summary['dpv_generation'],
                ytd_summary['storage_discharge'],
                ytd_summary['fossil_generation']
            ],
            marker_colors=[self.COLORS['wind'], self.COLORS['solar'], 
                          self.COLORS['dpv'], self.COLORS['battery'], 
                          self.COLORS['fossil']],
            textinfo='label+percent',
            hovertemplate='%{label}<br>%{value:.1f} GWh<br>%{percent}<extra></extra>'
        ), row=2, col=2)
        
        fig.update_layout(
            height=700,
            showlegend=True,
            template='plotly_white'
        )
        
        return fig.to_html(full_html=False, include_plotlyjs='cdn')
    
    def create_diurnal_area_chart(self, diurnal_data, title):
        """Create stacked area chart for diurnal profiles"""
        if not diurnal_data:
            return "<p>No diurnal data available</p>"
        
        fig = go.Figure()
        
        # diurnal_data is a list of dicts with 'time_of_day', 'operational_demand', 'underlying_demand', 'dpv_generation'
        # Extract time values (convert fractional hours to integers for display)
        times = [int(d['time_of_day']) for d in diurnal_data]
        
        # Extract operational demand data
        operational_demands = [d['operational_demand'] for d in diurnal_data]
        
        # Extract DPV generation data
        dpv_values = [d.get('dpv_generation', 0) for d in diurnal_data]
        
        # Calculate underlying demand
        underlying_demands = [d.get('underlying_demand', d['operational_demand']) for d in diurnal_data]
        
        # Create the area chart for operational demand
        fig.add_trace(go.Scatter(
            x=times,
            y=operational_demands,
            name='Operational Demand',
            mode='lines',
            line=dict(color=self.COLORS['wind'], width=2),
            fill='tozeroy',
            fillcolor='rgba(52, 152, 219, 0.3)'
        ))
        
        # Add underlying demand as a line (not filled)
        fig.add_trace(go.Scatter(
            x=times,
            y=underlying_demands,
            name='Underlying Demand',
            mode='lines',
            line=dict(color=self.COLORS['re'], width=2, dash='dash')
        ))
        
        # Add DPV generation if present
        if any(dpv_values):
            fig.add_trace(go.Scatter(
                x=times,
                y=dpv_values,
                name='DPV Generation',
                mode='lines',
                line=dict(color=self.COLORS['dpv'], width=1.5),
                fill='tozeroy',
                fillcolor='rgba(241, 196, 15, 0.2)'
            ))
        
        fig.update_layout(
            title=title,
            xaxis_title='Hour of Day',
            yaxis_title='Average Demand (GW)',
            hovermode='x unified',
            height=400,
            template='plotly_white',
            xaxis=dict(
                tickmode='linear',
                tick0=0,
                dtick=2,
                range=[0, 23]
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        return fig.to_html(full_html=False, include_plotlyjs='cdn')
    
    def create_historical_demand_chart(self, historical_data):
        """Create line chart showing operational and underlying demand trends"""
        if not historical_data:
            return "<p>No historical data available</p>"
        
        fig = go.Figure()
        
        dates = [record['period_label'] for record in historical_data]
        
        fig.add_trace(go.Scatter(
            x=dates,
            y=[record['operational_demand'] for record in historical_data],
            name='Operational Demand',
            mode='lines+markers',
            line=dict(color='#3498db', width=2),
            marker=dict(size=6)
        ))
        
        fig.add_trace(go.Scatter(
            x=dates,
            y=[record['underlying_demand'] for record in historical_data],
            name='Underlying Demand',
            mode='lines+markers',
            line=dict(color='#e74c3c', width=2, dash='dash'),
            marker=dict(size=6)
        ))
        
        fig.update_layout(
            xaxis_title='Period',
            yaxis_title='Demand (GWh)',
            hovermode='x unified',
            height=450,
            template='plotly_white',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        return fig.to_html(full_html=False, include_plotlyjs='cdn')
    
    def create_historical_re_chart(self, historical_data):
        """Create line chart showing RE percentage trends"""
        if not historical_data:
            return "<p>No historical data available</p>"
        
        fig = go.Figure()
        
        dates = [record['period_label'] for record in historical_data]
        
        fig.add_trace(go.Scatter(
            x=dates,
            y=[record['re_percentage_operational'] for record in historical_data],
            name='RE % of Operational',
            mode='lines+markers',
            line=dict(color='#27ae60', width=3),
            marker=dict(size=6),
            fill='tozeroy',
            fillcolor='rgba(39, 174, 96, 0.1)'
        ))
        
        fig.add_trace(go.Scatter(
            x=dates,
            y=[record['re_percentage_underlying'] for record in historical_data],
            name='RE % of Underlying',
            mode='lines+markers',
            line=dict(color='#16a085', width=2, dash='dash'),
            marker=dict(size=6)
        ))
        
        fig.update_layout(
            xaxis_title='Period',
            yaxis_title='Renewable Energy Percentage (%)',
            hovermode='x unified',
            height=450,
            template='plotly_white',
            yaxis=dict(range=[0, 100]),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        return fig.to_html(full_html=False, include_plotlyjs='cdn')
    
    def create_historical_mix_chart(self, historical_data):
        """Create stacked area chart showing generation mix evolution"""
        if not historical_data:
            return "<p>No historical data available</p>"
        
        fig = go.Figure()
        
        dates = [record['period_label'] for record in historical_data]
        
        # Add traces for each generation type (stacked)
        fig.add_trace(go.Scatter(
            x=dates,
            y=[record['fossil_generation'] for record in historical_data],
            name='Fossil',
            stackgroup='one',
            fillcolor=self.COLORS['fossil'],
            line=dict(width=0.5, color=self.COLORS['fossil'])
        ))
        
        fig.add_trace(go.Scatter(
            x=dates,
            y=[record['storage_discharge'] for record in historical_data],
            name='Battery',
            stackgroup='one',
            fillcolor=self.COLORS['battery'],
            line=dict(width=0.5, color=self.COLORS['battery'])
        ))
        
        fig.add_trace(go.Scatter(
            x=dates,
            y=[record['solar_generation'] for record in historical_data],
            name='Solar',
            stackgroup='one',
            fillcolor=self.COLORS['solar'],
            line=dict(width=0.5, color=self.COLORS['solar'])
        ))
        
        fig.add_trace(go.Scatter(
            x=dates,
            y=[record['wind_generation'] for record in historical_data],
            name='Wind',
            stackgroup='one',
            fillcolor=self.COLORS['wind'],
            line=dict(width=0.5, color=self.COLORS['wind'])
        ))
        
        fig.update_layout(
            xaxis_title='Period',
            yaxis_title='Generation (GWh)',
            hovermode='x unified',
            height=450,
            template='plotly_white',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        return fig.to_html(full_html=False, include_plotlyjs='cdn')
    
    def create_capacity_by_fuel_chart(self, facilities):
        """Create bar chart showing installed capacity by fuel type"""
        if not facilities:
            return "<p>No facility data available</p>"
        
        # Aggregate capacity by fuel type
        fuel_capacity = {}
        for facility in facilities:
            fuel_type = facility['fuel_type']
            capacity = facility['capacity']
            fuel_capacity[fuel_type] = fuel_capacity.get(fuel_type, 0) + capacity
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=list(fuel_capacity.keys()),
            y=list(fuel_capacity.values()),
            marker_color=[self.COLORS.get(ft, '#95a5a6') for ft in fuel_capacity.keys()],
            text=[f"{v:.0f} MW" for v in fuel_capacity.values()],
            textposition='outside'
        ))
        
        fig.update_layout(
            title='Installed Capacity by Fuel Type',
            xaxis_title='Fuel Type',
            yaxis_title='Capacity (MW)',
            height=400,
            template='plotly_white',
            showlegend=False
        )
        
        return fig.to_html(full_html=False, include_plotlyjs='cdn')


class FacilityManager:
    """Manage facility data and queries"""
    
    FUEL_COLORS = {
        'wind': '#3498db',
        'solar': '#f39c12',
        'battery': '#9b59b6',
        'gas': '#95a5a6',
        'coal': '#34495e',
        'diesel': '#7f8c8d',
        'biomass': '#16a085',
        'hydro': '#1abc9c',
        'unknown': '#bdc3c7',
    }
    
    def get_all_facilities_with_performance(self, year, month):
        """
        Get all facilities with their monthly performance metrics
        Optimized to use ONE query with aggregation
        """
        
        # Calculate hours in the month for capacity factor
        days_in_month = calendar.monthrange(year, month)[1]
        hours_in_month = days_in_month * 24
        
        # Get all facilities with their monthly generation in ONE query
        facilities_qs = facilities.objects.filter(
            active=True
        ).select_related(
            'idtechnologies', 'idzones'
        ).annotate(
            # Aggregate SCADA data directly in the query
            total_quantity=Coalesce(
                Sum(
                    'scada_records__quantity',
                    filter=Q(
                        scada_records__dispatch_interval__year=year,
                        scada_records__dispatch_interval__month=month
                    )
                ),
                0.0,
                output_field=FloatField()
            ),
            record_count=Count(
                'scada_records',
                filter=Q(
                    scada_records__dispatch_interval__year=year,
                    scada_records__dispatch_interval__month=month
                )
            )
        )
        
        # Build a mapping of technology IDs to fuel types from Technologies model
        tech_fuel_map = {
            tech.idtechnologies: tech.fuel_type.lower() if tech.fuel_type else 'unknown'
            for tech in Technologies.objects.all()
        }
        
        result = []
        
        for facility in facilities_qs:
            # Convert to MWh (5-minute intervals = 5/60 hours)
            total_mwh = facility.total_quantity * (5/60) if facility.total_quantity else 0
            
            # Convert MWh to GWh
            monthly_generation_gwh = total_mwh / 1000
            
            # Calculate capacity factor
            capacity_factor = 0
            if facility.capacity and facility.capacity > 0:
                max_possible_mwh = facility.capacity * hours_in_month
                capacity_factor = (total_mwh / max_possible_mwh * 100) if max_possible_mwh > 0 else 0
            
            # Get fuel type from Technologies model via facility's foreign key
            fuel_type = 'unknown'
            if facility.idtechnologies:
                fuel_type = tech_fuel_map.get(
                    facility.idtechnologies.idtechnologies,
                    'unknown'
                )
            
            # Determine status
            status = 'operational' if facility.active and facility.existing else 'inactive'
            
            # Get color based on fuel type
            color = self.FUEL_COLORS.get(fuel_type, '#808080')
            
            facility_data = {
                'name': facility.facility_name or 'Unknown',
                'facility_code': facility.facility_code or '',
                'capacity': float(facility.capacity) if facility.capacity else 0.0,
                'fuel_type': fuel_type,
                'status': status,
                'owner': facility.participant_code or 'Unknown',
                'location': facility.idzones.name if facility.idzones and hasattr(facility.idzones, 'name') else 'Unknown',
                'commissioned_date': facility.registered_from.isoformat() if facility.registered_from else None,
                'monthly_generation': round(monthly_generation_gwh, 1),
                'capacity_factor': round(capacity_factor, 1),
                'color': color
            }
            
            result.append(facility_data)
        
        # Sort by monthly generation (descending)
        result.sort(key=lambda x: x['monthly_generation'], reverse=True)
        
        return result
    
    def get_facility_statistics(self):
        """Calculate aggregate statistics across all facilities"""
        
        # Get all active facilities
        facilities_qs = facilities.objects.filter(active=True)
        
        # Get technology IDs for renewable sources from Technologies model
        renewable_tech_ids = set(
            Technologies.objects.filter(
                Q(renewable=1) | 
                Q(fuel_type__in=['WIND', 'SOLAR', 'HYDRO', 'BIOMASS'])
            ).values_list('idtechnologies', flat=True)
        )
        
        # Calculate totals with conditional aggregation
        stats = facilities_qs.aggregate(
            total_capacity=Sum('capacity'),
            total_facilities=Count('idfacilities'),
            renewable_capacity=Sum(
                Case(
                    When(idtechnologies__in=renewable_tech_ids, then='capacity'),
                    default=0,
                    output_field=FloatField()
                )
            )
        )
        
        total_capacity = float(stats['total_capacity'] or 0)
        total_facilities = stats['total_facilities'] or 0
        renewable_capacity = float(stats['renewable_capacity'] or 0)
        
        # Calculate renewable percentage
        renewable_percentage = (renewable_capacity / total_capacity * 100) if total_capacity > 0 else 0
        
        return {
            'total_capacity': round(total_capacity, 1),  # MW
            'total_facilities': total_facilities,
            'renewable_capacity': round(renewable_capacity, 1),  # MW
            'renewable_percentage': round(renewable_percentage, 1),
        }

    def get_top_performers(self, year, month, limit=10):
        """Get top performing renewable facilities by monthly generation"""
        
        # Calculate hours in the month for capacity factor calculation
        days_in_month = calendar.monthrange(year, month)[1]
        hours_in_month = days_in_month * 24
        
        # Get renewable facilities with their monthly generation in ONE query
        facilities_qs = facilities.objects.filter(
            active=True,
            idtechnologies__renewable=1
        ).select_related(
            'idtechnologies', 'idzones'
        ).annotate(
            total_quantity=Coalesce(
                Sum(
                    'scada_records__quantity',
                    filter=Q(
                        scada_records__dispatch_interval__year=year,
                        scada_records__dispatch_interval__month=month
                    )
                ),
                0.0,
                output_field=FloatField()
            ),
            record_count=Count(
                'scada_records',
                filter=Q(
                    scada_records__dispatch_interval__year=year,
                    scada_records__dispatch_interval__month=month
                )
            )
        )
        
        # Build a mapping of technology IDs to fuel types
        tech_fuel_map = {
            tech.idtechnologies: tech.fuel_type.lower() if tech.fuel_type else 'unknown'
            for tech in Technologies.objects.all()
        }
        
        result = []
        
        for facility in facilities_qs:
            # Convert to MWh (5-minute intervals = 5/60 hours)
            total_mwh = facility.total_quantity if facility.total_quantity else 0
            
            # Convert MWh to GWh
            monthly_generation_gwh = total_mwh / 1000
            
            # Calculate capacity factor
            capacity_factor = 0
            if facility.capacity and facility.capacity > 0:
                max_possible_mwh = facility.capacity * hours_in_month
                capacity_factor = (total_mwh / max_possible_mwh * 100) if max_possible_mwh > 0 else 0
            
            # Get fuel type from Technologies model
            fuel_type = 'unknown'
            if facility.idtechnologies:
                fuel_type = tech_fuel_map.get(
                    facility.idtechnologies.idtechnologies,
                    'unknown'
                )
            
            # Get color based on fuel type
            color = self.FUEL_COLORS.get(fuel_type, '#808080')
            
            facility_data = {
                'name': facility.facility_name or 'Unknown',
                'facility_code': facility.facility_code or '',
                'capacity': float(facility.capacity) if facility.capacity else 0.0,
                'fuel_type': fuel_type,
                'status': 'operational' if facility.active and facility.existing else 'inactive',
                'owner': facility.participant_code or 'Unknown',
                'location': facility.idzones.name if facility.idzones and hasattr(facility.idzones, 'name') else 'Unknown',
                'commissioned_date': facility.registered_from.isoformat() if facility.registered_from else None,
                'monthly_generation': round(monthly_generation_gwh, 1),
                'capacity_factor': round(capacity_factor, 1),
                'color': color
            }
            
            result.append(facility_data)
        
        # Sort by monthly generation (descending)
        result.sort(key=lambda x: x['monthly_generation'], reverse=True)
        
        return result[:limit]