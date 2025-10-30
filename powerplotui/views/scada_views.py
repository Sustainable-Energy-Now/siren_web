# powerplot/views.py
from django.db.models import Avg, Case, Count, FloatField,  Max, Min, Sum, Q, When
from django.db.models.functions import ExtractHour, TruncDate, TruncHour
from django.shortcuts import render, get_object_or_404
from siren_web.models import TradingPrice, DPVGeneration, LoadAnalysisSummary, facilities, FacilityScada, Technologies
from powerplotui.services.load_analyzer import LoadAnalyzer
from datetime import datetime, date, timedelta
import calendar
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import logging
from django.db.models.functions import ExtractHour
from django.http import JsonResponse
    
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
        (summary.battery_discharge / summary.operational_demand) * 100 
        if summary.operational_demand > 0 else 0
    )
    ytd_bess_percentage = (
        (ytd_summary['battery_discharge'] / ytd_summary['operational_demand']) * 100
        if ytd_summary['operational_demand'] > 0 else 0
    )
    ytd_prev_bess_percentage = (
        (ytd_prev_summary['battery_discharge'] / ytd_prev_summary['operational_demand']) * 100
        if ytd_prev_summary['operational_demand'] > 0 else 0
    )
    
    bess_efficiency = (
        (summary.battery_discharge / abs(summary.battery_charge)) * 100
        if summary.battery_charge != 0 else 0
    )
    ytd_bess_efficiency = (
        (ytd_summary['battery_discharge'] / abs(ytd_summary['battery_charge'])) * 100
        if ytd_summary['battery_charge'] != 0 else 0
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
    facilities = facility_manager.get_all_facilities_with_performance(year, month)
    facility_stats = facility_manager.get_facility_statistics()
    capacity_chart = chart_gen.create_capacity_by_fuel_chart(facilities)
    top_performers = facility_manager.get_top_performers(year, month, limit=10)
    
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
        'facilities': facilities,
        'facility_stats': facility_stats,
        'capacity_chart': capacity_chart,
        'top_performers': top_performers,
    }
    
    return render(request, 'scada/analysis.html', context)

def aggregate_summaries(summaries):
    """Aggregate multiple monthly summaries into totals"""
    if not summaries:
        return {
            'operational_demand': 0,
            'underlying_demand': 0,
            'battery_discharge': 0,
            'battery_charge': 0,
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
        'battery_discharge': sum(s.battery_discharge for s in summaries),
        'battery_charge': sum(s.battery_charge for s in summaries),
        'fossil_generation': sum(s.fossil_generation for s in summaries),
        'dpv_generation': sum(s.dpv_generation for s in summaries),
        'wind_generation': sum(s.wind_generation for s in summaries),
        'solar_generation': sum(s.solar_generation for s in summaries),
    }
    
    # Recalculate percentages
    total_re = total['wind_generation'] + total['solar_generation']
    total['re_percentage_operational'] = float(
        (total_re / total['operational_demand']) * 100 
        if total['operational_demand'] > 0 else 0.0
    )
    total['re_percentage_underlying'] = (
        (total_re / total['underlying_demand']) * 100
        if total['underlying_demand'] > 0 else 0.0
    )
    total['dpv_percentage_underlying'] = (
        (total['dpv_generation'] / total['underlying_demand']) * 100
        if total['underlying_demand'] > 0 else 0.0
    )
    
    return total

class ChartGenerator:
    """Generate Plotly charts for SCADA analysis"""
    # Technology color scheme
    COLORS = {
        'wind': '#2E86AB',
        'solar': '#F6AE2D',
        'dpv': '#F26419',
        'battery': '#33658A',
        'fossil': '#86BBD8',
        'gas': '#E63946',
        'coal': '#6C757D',
        'hydro': '#55DDE0',
        'biomass': '#88B04B',
        'other': '#95a5a6'
    }

    def create_facility_performance_chart(self, facility, start_date, end_date):
        """
        Create a time series chart of facility performance over a date range
        
        Shows daily generation with capacity reference line
        """
        
        try:
            # Get daily generation data
            daily_data = FacilityScada.objects.filter(
                facility=facility,
                timestamp__gte=start_date,
                timestamp__lte=end_date
            ).extra(
                select={'date': 'DATE(timestamp)'}
            ).values('date').annotate(
                daily_generation=Sum('generation_mwh')
            ).order_by('date')
            
            if not daily_data:
                return '<div style="padding: 20px; text-align: center; color: #999;">No performance data available for this period.</div>'
            
            dates = [d['date'] for d in daily_data]
            generation = [d['daily_generation'] for d in daily_data]
            
            # Calculate theoretical maximum daily generation
            max_daily = facility.capacity * 24 / 1000  # Convert to MWh
            
            fig = go.Figure()
            
            # Add generation line
            fig.add_trace(go.Scatter(
                x=dates,
                y=generation,
                mode='lines+markers',
                name='Daily Generation',
                line=dict(
                    color=self.COLORS.get(facility.fuel_type.lower() if facility.fuel_type else 'other', '#3498db'),
                    width=2
                ),
                marker=dict(size=4),
                fill='tozeroy',
                fillcolor='rgba(52, 152, 219, 0.1)',
                hovertemplate='<b>%{x}</b><br>Generation: %{y:.1f} MWh<extra></extra>'
            ))
            
            # Add maximum capacity reference line
            fig.add_trace(go.Scatter(
                x=dates,
                y=[max_daily] * len(dates),
                mode='lines',
                name='Max Capacity',
                line=dict(color='rgba(0,0,0,0.3)', width=1, dash='dash'),
                hovertemplate='Max Daily: %{y:.1f} MWh<extra></extra>'
            ))
            
            fig.update_layout(
                title=f'{facility.name} - Last 30 Days Performance',
                xaxis_title='Date',
                yaxis_title='Generation (MWh)',
                height=350,
                hovermode='x unified',
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
            
            return fig.to_html(full_html=False, include_plotlyjs='cdn')
            
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error creating facility performance chart: {e}")
            return f'<div style="padding: 20px; text-align: center; color: #e74c3c;">Error generating performance chart: {str(e)}</div>'
    
    def create_diurnal_area_chart(self, diurnal_data, title):
        """
        Create stacked area chart showing generation mix throughout the day
        
        Handles two data formats:
        1. Dictionary with keys: 'hours', 'wind', 'solar', etc.
        2. List of dicts with keys: 'time_of_day', technology fields
        """
        
        # Check if data is in list format (from existing LoadAnalyzer)
        if isinstance(diurnal_data, list):
            return self._create_diurnal_from_list(diurnal_data, title)
        
        # Original dictionary format
        fig = go.Figure()
        
        hours = diurnal_data.get('hours', list(range(24)))
        
        # Add stacked area traces for each technology
        # Order matters for stacking - add from bottom to top
        technologies = [
            ('fossil', 'Fossil', self.COLORS['fossil']),
            ('battery', 'BESS', self.COLORS['battery']),
            ('wind', 'Wind', self.COLORS['wind']),
            ('solar', 'Solar', self.COLORS['solar']),
            ('dpv', 'DPV', self.COLORS['dpv']),
        ]
        
        for tech_key, tech_label, color in technologies:
            if tech_key in diurnal_data:
                fig.add_trace(go.Scatter(
                    x=hours,
                    y=diurnal_data[tech_key],
                    name=tech_label,
                    mode='lines',
                    line=dict(width=0.5, color=color),
                    fillcolor=color,
                    fill='tonexty' if tech_key != 'fossil' else 'tozeroy',
                    stackgroup='one',
                    hovertemplate='<b>%{fullData.name}</b><br>Hour: %{x}<br>MW: %{y:.0f}<extra></extra>'
                ))
        
        # Add price line on secondary y-axis if available
        if 'price' in diurnal_data:
            fig.add_trace(go.Scatter(
                x=hours,
                y=diurnal_data['price'],
                name='Price',
                mode='lines',
                line=dict(width=2, color='#49C2A9', dash='dash'),
                yaxis='y2',
                hovertemplate='<b>Price</b><br>Hour: %{x}<br>$/MWh: %{y:.2f}<extra></extra>'
            ))
        
        fig.update_layout(
            title=title,
            xaxis=dict(
                title='Hour of Day',
                tickmode='linear',
                tick0=0,
                dtick=2,
                range=[0, 23]
            ),
            yaxis=dict(
                title='Generation (MW)',
                rangemode='tozero'
            ),
            yaxis2=dict(
                title='Price ($/MWh)',
                overlaying='y',
                side='right',
                rangemode='tozero'
            ),
            hovermode='x unified',
            height=500,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.25,
                xanchor="center",
                x=0.5
            )
        )
        
        return fig.to_html(full_html=False, include_plotlyjs='cdn')
    
    def _create_diurnal_from_list(self, diurnal_data_list, title):
        """
        Create diurnal chart from list format data (existing LoadAnalyzer format)
        
        Expected list format:
        [{'time_of_day': 0.0, 'operational_demand': 2.5, 'dpv_generation': 0.0, ...}, ...]
        """
        if not diurnal_data_list:
            return '<div style="padding: 20px; text-align: center;">No diurnal data available</div>'
        
        # Extract time and demand data
        times = [d.get('time_of_day', 0) for d in diurnal_data_list]
        operational_demand = [d.get('operational_demand', 0) for d in diurnal_data_list]
        underlying_demand = [d.get('underlying_demand', 0) for d in diurnal_data_list]
        dpv_generation = [d.get('dpv_generation', 0) for d in diurnal_data_list]
        
        # Convert fractional hours to integer hours for display
        hours = [int(t * 24) for t in times]
        
        fig = go.Figure()
        
        # Add operational demand area
        fig.add_trace(go.Scatter(
            x=hours,
            y=operational_demand,
            name='Operational Demand',
            mode='lines',
            line=dict(width=2, color=self.COLORS['fossil']),
            fill='tozeroy',
            fillcolor='rgba(134, 187, 216, 0.3)',
            hovertemplate='<b>Operational Demand</b><br>Hour: %{x}<br>GW: %{y:.2f}<extra></extra>'
        ))
        
        # Add DPV generation if present
        if any(dpv > 0 for dpv in dpv_generation):
            fig.add_trace(go.Scatter(
                x=hours,
                y=dpv_generation,
                name='DPV Generation',
                mode='lines',
                line=dict(width=2, color=self.COLORS['dpv']),
                fill='tozeroy',
                fillcolor='rgba(242, 100, 25, 0.3)',
                hovertemplate='<b>DPV</b><br>Hour: %{x}<br>GW: %{y:.2f}<extra></extra>'
            ))
        
        # Add underlying demand line
        fig.add_trace(go.Scatter(
            x=hours,
            y=underlying_demand,
            name='Underlying Demand',
            mode='lines',
            line=dict(width=2, color='#2c3e50', dash='dash'),
            hovertemplate='<b>Underlying Demand</b><br>Hour: %{x}<br>GW: %{y:.2f}<extra></extra>'
        ))
        
        fig.update_layout(
            title=title,
            xaxis=dict(
                title='Hour of Day',
                tickmode='linear',
                tick0=0,
                dtick=2,
                range=[0, 23]
            ),
            yaxis=dict(
                title='Demand (GW)',
                rangemode='tozero'
            ),
            hovermode='x unified',
            height=500,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.25,
                xanchor="center",
                x=0.5
            )
        )
        
        return fig.to_html(full_html=False, include_plotlyjs='cdn')
    
    def create_capacity_by_fuel_chart(self, facilities):
        """
        Create a bar chart showing total installed capacity by fuel type
        """
        if not facilities:
            return None
        
        # Aggregate capacity by fuel type
        fuel_totals = {}
        for facility in facilities:
            fuel_type = facility.get('fuel_type', 'other')
            capacity = facility.get('capacity', 0)
            fuel_totals[fuel_type] = fuel_totals.get(fuel_type, 0) + capacity
        
        # Sort by capacity
        sorted_fuels = sorted(fuel_totals.items(), key=lambda x: x[1], reverse=True)
        fuel_types = [f[0].title() for f in sorted_fuels]
        capacities = [f[1] for f in sorted_fuels]
        colors = [self.COLORS.get(f[0], self.COLORS['other']) for f in sorted_fuels]
        
        fig = go.Figure(data=[
            go.Bar(
                x=fuel_types,
                y=capacities,
                marker=dict(color=colors),
                text=[f'{c:.0f} MW' for c in capacities],
                textposition='outside',
                hovertemplate='<b>%{x}</b><br>Capacity: %{y:.1f} MW<extra></extra>'
            )
        ])
        
        fig.update_layout(
            title='Installed Capacity by Fuel Type',
            xaxis_title='Fuel Type',
            yaxis_title='Capacity (MW)',
            height=400,
            showlegend=False,
            yaxis=dict(rangemode='tozero')
        )
        
        return fig.to_html(full_html=False, include_plotlyjs='cdn')


    """Analyze load data and create diurnal profiles"""
    def get_diurnal_profile(self, year, month):
        """
        Get average hourly generation by technology for a specific month
        
        This method queries FacilityScada, DPVGeneration, and TradingPrice data 
        and aggregates by hour of day. Returns dict with hourly averages.
        """
        
        hours = list(range(24))
        
        # Get facility codes by fuel type using Technologies model
        # Build technology ID sets first for efficiency
        wind_tech_ids = set(Technologies.objects.filter(
            fuel_type__iexact='WIND'
        ).values_list('idtechnologies', flat=True))
        
        solar_tech_ids = set(Technologies.objects.filter(
            fuel_type__iexact='SOLAR'
        ).values_list('idtechnologies', flat=True))
        
        battery_tech_ids = set(Technologies.objects.filter(
            Q(fuel_type__icontains='battery') | Q(fuel_type__icontains='bess')
        ).values_list('idtechnologies', flat=True))
        
        fossil_tech_ids = set(Technologies.objects.filter(
            fuel_type__in=['GAS', 'COAL']
        ).values_list('idtechnologies', flat=True))
        
        # Map to facility codes
        fuel_type_codes = {
            'wind': set(facilities.objects.filter(
                idtechnologies__in=wind_tech_ids
            ).values_list('facility_code', flat=True)),
            'solar': set(facilities.objects.filter(
                idtechnologies__in=solar_tech_ids
            ).values_list('facility_code', flat=True)),
            'battery': set(facilities.objects.filter(
                idtechnologies__in=battery_tech_ids
            ).values_list('facility_code', flat=True)),
            'fossil': set(facilities.objects.filter(
                idtechnologies__in=fossil_tech_ids
            ).values_list('facility_code', flat=True)),
        }
        
        # Query and aggregate facility SCADA data by hour
        hourly_facility_data = FacilityScada.objects.filter(
            dispatch_interval__year=year,
            dispatch_interval__month=month
        ).annotate(
            hour=ExtractHour('dispatch_interval')
        ).values('hour').annotate(
            avg_wind=Avg(
                Case(
                    When(facility__facility_code__in=fuel_type_codes['wind'], then='quantity'),
                    default=0,
                    output_field=FloatField()
                )
            ),
            avg_solar=Avg(
                Case(
                    When(facility__facility_code__in=fuel_type_codes['solar'], then='quantity'),
                    default=0,
                    output_field=FloatField()
                )
            ),
            avg_battery=Avg(
                Case(
                    When(facility__facility_code__in=fuel_type_codes['battery'], then='quantity'),
                    default=0,
                    output_field=FloatField()
                )
            ),
            avg_fossil=Avg(
                Case(
                    When(facility__facility_code__in=fuel_type_codes['fossil'], then='quantity'),
                    default=0,
                    output_field=FloatField()
                )
            ),
        ).order_by('hour')
        
        # Initialize result arrays
        result = {
            'wind': [0] * 24,
            'solar': [0] * 24,
            'battery': [0] * 24,
            'fossil': [0] * 24,
            'dpv': [0] * 24,
            'price': [0] * 24,
        }
        
        # Populate facility data
        for agg in hourly_facility_data:
            h = agg['hour']
            result['wind'][h] = round(float(agg['avg_wind'] or 0), 2)
            result['solar'][h] = round(float(agg['avg_solar'] or 0), 2)
            result['battery'][h] = round(float(agg['avg_battery'] or 0), 2)
            result['fossil'][h] = round(float(agg['avg_fossil'] or 0), 2)
        
        # Query DPV generation data
        dpv_data = DPVGeneration.objects.filter(
            trading_date__year=year,
            trading_date__month=month
        ).annotate(
            hour=ExtractHour('trading_interval')
        ).values('hour').annotate(
            avg_dpv=Avg('estimated_generation')
        ).order_by('hour')
        
        for agg in dpv_data:
            h = agg['hour']
            result['dpv'][h] = round(float(agg['avg_dpv'] or 0), 2)
        
        # Query trading price data
        # Format: "YYYY-MM" for trading_month
        trading_month_str = f"{year}-{month:02d}"
        
        price_data = TradingPrice.objects.filter(
            trading_month=trading_month_str
        )
        
        # Group by hour (assuming trading_interval is interval number of the day)
        # AEMO typically uses 48 intervals (30-min) or 288 intervals (5-min)
        price_by_hour = [[] for _ in range(24)]
        
        for price_record in price_data:
            interval_num = price_record.trading_interval
            if interval_num:
                # Determine if 5-min (288 intervals) or 30-min (48 intervals)
                # Check the max interval to determine the type
                max_interval = TradingPrice.objects.filter(
                    trading_month=trading_month_str
                ).order_by('-trading_interval').first()
                
                if max_interval and max_interval.trading_interval:
                    if max_interval.trading_interval > 200:  # Likely 5-min intervals (288)
                        hour = (interval_num - 1) // 12  # 12 intervals per hour
                    else:  # Likely 30-min intervals (48)
                        hour = (interval_num - 1) // 2  # 2 intervals per hour
                    
                    if 0 <= hour < 24:
                        price_by_hour[hour].append(price_record.reference_price)
        
        # Calculate average price per hour
        for h in range(24):
            if price_by_hour[h]:
                result['price'][h] = round(sum(price_by_hour[h]) / len(price_by_hour[h]), 2)
        
        return {
            'hours': hours,
            'wind': result['wind'],
            'solar': result['solar'],
            'dpv': result['dpv'],
            'battery': result['battery'],
            'fossil': result['fossil'],
            'price': result['price']
        }

    def get_diurnal_profile_ytd(self, year, month):
        """
        Get average hourly generation by technology for year-to-date
        
        Aggregates data from January through the specified month.
        """
        
        hours = list(range(24))
        
        # Get facility codes by fuel type using Technologies model
        # Build technology ID sets first for efficiency
        wind_tech_ids = set(Technologies.objects.filter(
            fuel_type__iexact='WIND'
        ).values_list('idtechnologies', flat=True))
        
        solar_tech_ids = set(Technologies.objects.filter(
            fuel_type__iexact='SOLAR'
        ).values_list('idtechnologies', flat=True))
        
        battery_tech_ids = set(Technologies.objects.filter(
            Q(fuel_type__icontains='battery') | Q(fuel_type__icontains='bess')
        ).values_list('idtechnologies', flat=True))
        
        fossil_tech_ids = set(Technologies.objects.filter(
            fuel_type__in=['GAS', 'COAL']
        ).values_list('idtechnologies', flat=True))
        
        # Map to facility codes
        fuel_type_codes = {
            'wind': set(facilities.objects.filter(
                idtechnologies__in=wind_tech_ids
            ).values_list('facility_code', flat=True)),
            'solar': set(facilities.objects.filter(
                idtechnologies__in=solar_tech_ids
            ).values_list('facility_code', flat=True)),
            'battery': set(facilities.objects.filter(
                idtechnologies__in=battery_tech_ids
            ).values_list('facility_code', flat=True)),
            'fossil': set(facilities.objects.filter(
                idtechnologies__in=fossil_tech_ids
            ).values_list('facility_code', flat=True)),
        }
        
        # Query and aggregate facility SCADA data by hour (YTD)
        hourly_facility_data = FacilityScada.objects.filter(
            dispatch_interval__year=year,
            dispatch_interval__month__lte=month
        ).annotate(
            hour=ExtractHour('dispatch_interval')
        ).values('hour').annotate(
            avg_wind=Avg(
                Case(
                    When(facility__facility_code__in=fuel_type_codes['wind'], then='quantity'),
                    default=0,
                    output_field=FloatField()
                )
            ),
            avg_solar=Avg(
                Case(
                    When(facility__facility_code__in=fuel_type_codes['solar'], then='quantity'),
                    default=0,
                    output_field=FloatField()
                )
            ),
            avg_battery=Avg(
                Case(
                    When(facility__facility_code__in=fuel_type_codes['battery'], then='quantity'),
                    default=0,
                    output_field=FloatField()
                )
            ),
            avg_fossil=Avg(
                Case(
                    When(facility__facility_code__in=fuel_type_codes['fossil'], then='quantity'),
                    default=0,
                    output_field=FloatField()
                )
            ),
        ).order_by('hour')
        
        # Initialize result arrays
        result = {
            'wind': [0] * 24,
            'solar': [0] * 24,
            'battery': [0] * 24,
            'fossil': [0] * 24,
            'dpv': [0] * 24,
            'price': [0] * 24,
        }
        
        # Populate facility data
        for agg in hourly_facility_data:
            h = agg['hour']
            result['wind'][h] = round(float(agg['avg_wind'] or 0), 2)
            result['solar'][h] = round(float(agg['avg_solar'] or 0), 2)
            result['battery'][h] = round(float(agg['avg_battery'] or 0), 2)
            result['fossil'][h] = round(float(agg['avg_fossil'] or 0), 2)
        
        # Query DPV generation data (YTD)
        dpv_data = DPVGeneration.objects.filter(
            trading_date__year=year,
            trading_date__month__lte=month
        ).annotate(
            hour=ExtractHour('trading_interval')
        ).values('hour').annotate(
            avg_dpv=Avg('estimated_generation')
        ).order_by('hour')
        
        for agg in dpv_data:
            h = agg['hour']
            result['dpv'][h] = round(float(agg['avg_dpv'] or 0), 2)
        
        # Query trading price data for all months YTD
        trading_months = [f"{year}-{m:02d}" for m in range(1, month + 1)]
        
        price_data = TradingPrice.objects.filter(
            trading_month__in=trading_months
        )
        
        # Group by hour
        price_by_hour = [[] for _ in range(24)]
        
        # Determine interval type from first record
        sample_record = price_data.order_by('-trading_interval').first()
        intervals_per_hour = 12  # Default to 5-min intervals
        
        if sample_record and sample_record.trading_interval:
            if sample_record.trading_interval <= 100:  # Likely 30-min intervals (48)
                intervals_per_hour = 2
        
        for price_record in price_data:
            interval_num = price_record.trading_interval
            if interval_num:
                hour = (interval_num - 1) // intervals_per_hour
                
                if 0 <= hour < 24:
                    price_by_hour[hour].append(price_record.reference_price)
        
        # Calculate average price per hour
        for h in range(24):
            if price_by_hour[h]:
                result['price'][h] = round(sum(price_by_hour[h]) / len(price_by_hour[h]), 2)
        
        return {
            'hours': hours,
            'wind': result['wind'],
            'solar': result['solar'],
            'dpv': result['dpv'],
            'battery': result['battery'],
            'fossil': result['fossil'],
            'price': result['price']
        }

    def create_technology_breakdown_pies(self, monthly_summary, ytd_summary):
        """
        Create 4 pie charts showing technology breakdown:
        - Monthly Operational Demand
        - Monthly Underlying Demand  
        - YTD Operational Demand
        - YTD Underlying Demand
        """
        fig = make_subplots(
            rows=2, cols=2,
            specs=[[{'type': 'pie'}, {'type': 'pie'}],
                   [{'type': 'pie'}, {'type': 'pie'}]],
            subplot_titles=(
                'Monthly: Operational Demand',
                'Monthly: Underlying Demand',
                'YTD: Operational Demand', 
                'YTD: Underlying Demand'
            )
        )
        
        # Monthly Operational - shows what met operational demand
        fig.add_trace(go.Pie(
            labels=['Wind', 'Solar', 'BESS', 'Fossil', 'Other'],
            values=[
                monthly_summary.wind_generation,
                monthly_summary.solar_generation,
                monthly_summary.battery_discharge,
                monthly_summary.fossil_generation,
                max(0, monthly_summary.operational_demand - 
                    (monthly_summary.wind_generation + 
                     monthly_summary.solar_generation + 
                     monthly_summary.battery_discharge + 
                     monthly_summary.fossil_generation))
            ],
            marker=dict(colors=[
                self.COLORS['wind'],
                self.COLORS['solar'],
                self.COLORS['battery'],
                self.COLORS['fossil'],
                self.COLORS['other']
            ]),
            textinfo='label+percent',
            hovertemplate='<b>%{label}</b><br>%{value:.1f} GWh<br>%{percent}<extra></extra>'
        ), row=1, col=1)
        
        # Monthly Underlying - includes DPV
        fig.add_trace(go.Pie(
            labels=['Wind', 'Solar', 'DPV', 'BESS', 'Fossil', 'Other'],
            values=[
                monthly_summary.wind_generation,
                monthly_summary.solar_generation,
                monthly_summary.dpv_generation,
                monthly_summary.battery_discharge,
                monthly_summary.fossil_generation,
                max(0, monthly_summary.underlying_demand - 
                    (monthly_summary.wind_generation + 
                     monthly_summary.solar_generation + 
                     monthly_summary.dpv_generation +
                     monthly_summary.battery_discharge + 
                     monthly_summary.fossil_generation))
            ],
            marker=dict(colors=[
                self.COLORS['wind'],
                self.COLORS['solar'],
                self.COLORS['dpv'],
                self.COLORS['battery'],
                self.COLORS['fossil'],
                self.COLORS['other']
            ]),
            textinfo='label+percent',
            hovertemplate='<b>%{label}</b><br>%{value:.1f} GWh<br>%{percent}<extra></extra>'
        ), row=1, col=2)
        
        # YTD Operational
        fig.add_trace(go.Pie(
            labels=['Wind', 'Solar', 'BESS', 'Fossil', 'Other'],
            values=[
                ytd_summary['wind_generation'],
                ytd_summary['solar_generation'],
                ytd_summary['battery_discharge'],
                ytd_summary['fossil_generation'],
                max(0, ytd_summary['operational_demand'] - 
                    (ytd_summary['wind_generation'] + 
                     ytd_summary['solar_generation'] + 
                     ytd_summary['battery_discharge'] + 
                     ytd_summary['fossil_generation']))
            ],
            marker=dict(colors=[
                self.COLORS['wind'],
                self.COLORS['solar'],
                self.COLORS['battery'],
                self.COLORS['fossil'],
                self.COLORS['other']
            ]),
            textinfo='label+percent',
            hovertemplate='<b>%{label}</b><br>%{value:.1f} GWh<br>%{percent}<extra></extra>'
        ), row=2, col=1)
        
        # YTD Underlying
        fig.add_trace(go.Pie(
            labels=['Wind', 'Solar', 'DPV', 'BESS', 'Fossil', 'Other'],
            values=[
                ytd_summary['wind_generation'],
                ytd_summary['solar_generation'],
                ytd_summary['dpv_generation'],
                ytd_summary['battery_discharge'],
                ytd_summary['fossil_generation'],
                max(0, ytd_summary['underlying_demand'] - 
                    (ytd_summary['wind_generation'] + 
                     ytd_summary['solar_generation'] + 
                     ytd_summary['dpv_generation'] +
                     ytd_summary['battery_discharge'] + 
                     ytd_summary['fossil_generation']))
            ],
            marker=dict(colors=[
                self.COLORS['wind'],
                self.COLORS['solar'],
                self.COLORS['dpv'],
                self.COLORS['battery'],
                self.COLORS['fossil'],
                self.COLORS['other']
            ]),
            textinfo='label+percent',
            hovertemplate='<b>%{label}</b><br>%{value:.1f} GWh<br>%{percent}<extra></extra>'
        ), row=2, col=2)
        
        fig.update_layout(
            height=700,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.15,
                xanchor="center",
                x=0.5
            )
        )
        
        return fig.to_html(full_html=False, include_plotlyjs='cdn')

class FacilityManager:
    """Manage facility data and performance metrics"""
    
    # Technology to color mapping
    FUEL_COLORS = {
        'wind': '#2E86AB',
        'solar': '#F6AE2D',
        'battery': '#33658A',
        'gas': '#E63946',
        'coal': '#6C757D',
        'other': '#95a5a6'
    }
    
    def get_all_facilities_with_performance(self, year, month):
        """
        Get all facilities with their performance metrics for the given month
        
        Optimized to use bulk queries instead of N+1 pattern.
        Returns list of dicts with facility info and monthly performance.
        """
        from django.db.models import Sum, Count, Q, F, FloatField
        from django.db.models.functions import Coalesce
        import calendar
        
        # Calculate hours in the month for capacity factor calculation
        days_in_month = calendar.monthrange(year, month)[1]
        hours_in_month = days_in_month * 24
        
        # Get all active facilities with their monthly generation in ONE query
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
        # This avoids N+1 queries when accessing fuel_type for each facility
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
        """Get top performing facilities by generation or capacity factor"""
        facilities = self.get_all_facilities_with_performance(year, month)
        
        # Sort by generation
        sorted_facilities = sorted(
            facilities, 
            key=lambda x: x.get('monthly_generation', 0), 
            reverse=True
        )
        
        return sorted_facilities[:limit]