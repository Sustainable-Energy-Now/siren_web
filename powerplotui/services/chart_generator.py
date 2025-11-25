# powerplot/services/chart_generator.py
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

class ChartGenerator:
    
    def create_demand_breakdown_pie(self, summary, ytd_summary):
        """Create pie charts showing demand breakdown"""
        # Get month and year from summary for titles
        month_name = summary.period_date.strftime('%B')
        year = summary.period_date.year
        
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                f'Operational Demand - {month_name} {year}',
                f'Underlying Demand - {month_name} {year}',
                f'Operational Demand - YTD {year}',
                f'Underlying Demand - YTD {year}'
            ),
            specs=[[{'type': 'pie'}, {'type': 'pie'}],
                   [{'type': 'pie'}, {'type': 'pie'}]]
        )
        
        # Monthly Operational Demand (row 1, col 1)
        fig.add_trace(
            go.Pie(
                labels=['Wind', 'Solar', 'Fossil', 'Battery Net'],
                values=[
                    summary.wind_generation,
                    summary.solar_generation,
                    summary.fossil_generation,
                    summary.storage_discharge - summary.storage_charge
                ],
                name="Monthly Operational"
            ),
            row=1, col=1
        )
        
        # Monthly Underlying Demand (row 1, col 2)
        fig.add_trace(
            go.Pie(
                labels=['Wind', 'Solar', 'DPV', 'Fossil', 'Battery Net'],
                values=[
                    summary.wind_generation,
                    summary.solar_generation,
                    summary.dpv_generation,
                    summary.fossil_generation,
                    summary.storage_discharge - summary.storage_charge
                ],
                name="Monthly Underlying"
            ),
            row=1, col=2
        )
        
        # YTD Operational Demand (row 2, col 1)
        fig.add_trace(
            go.Pie(
                labels=['Wind', 'Solar', 'Fossil', 'Battery Net'],
                values=[
                    ytd_summary['wind_generation'],
                    ytd_summary['solar_generation'],
                    ytd_summary.get('fossil_generation', 0),
                    ytd_summary['storage_discharge'] - ytd_summary.get('storage_charge', 0)
                ],
                name="YTD Operational"
            ),
            row=2, col=1
        )
        
        # YTD Underlying Demand (row 2, col 2)
        fig.add_trace(
            go.Pie(
                labels=['Wind', 'Solar', 'DPV', 'Fossil', 'Battery Net'],
                values=[
                    ytd_summary['wind_generation'],
                    ytd_summary['solar_generation'],
                    ytd_summary['dpv_generation'],
                    ytd_summary.get('fossil_generation', 0),
                    ytd_summary['storage_discharge'] - ytd_summary.get('storage_charge', 0)
                ],
                name="YTD Underlying"
            ),
            row=2, col=2
        )
        
        fig.update_layout(height=800, showlegend=True)
        return fig.to_html(include_plotlyjs='cdn')
    
    def create_diurnal_profile(self, diurnal_data, prices=None):
        """Create average diurnal profile chart"""
        df = pd.DataFrame(diurnal_data)
        
        if df.empty:
            return "<p>No diurnal profile data available</p>"
        
        fig = go.Figure()
        
        # Plot underlying demand (includes DPV)
        fig.add_trace(go.Scatter(
            x=df['time_of_day'],
            y=df['underlying_demand'],
            name='Underlying Demand',
            line=dict(color='blue', width=2)
        ))
        
        # Plot operational demand
        fig.add_trace(go.Scatter(
            x=df['time_of_day'],
            y=df['operational_demand'],
            name='Operational Demand',
            line=dict(color='red', width=2, dash='dash')
        ))
        
        # Plot DPV generation if available
        if 'dpv_generation' in df.columns and df['dpv_generation'].sum() > 0:
            fig.add_trace(go.Scatter(
                x=df['time_of_day'],
                y=df['dpv_generation'],
                name='DPV Generation',
                line=dict(color='orange', width=2, dash='dot')
            ))
        
        if prices is not None:
            fig.add_trace(go.Scatter(
                x=prices['time_of_day'],
                y=prices['price'],
                name='Average Price',
                yaxis='y2',
                line=dict(color='#49C2A9', width=2)
            ))
        
        fig.update_layout(
            title='Average Diurnal Profile',
            xaxis_title='Hour of Day',
            yaxis_title='Demand (MW)',
            yaxis2=dict(
                title='Price ($/MWh)',
                overlaying='y',
                side='right'
            ) if prices is not None else None,
            height=480,
            hovermode='x unified',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        return fig.to_html(include_plotlyjs='cdn')