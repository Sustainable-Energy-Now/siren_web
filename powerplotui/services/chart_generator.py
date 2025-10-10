# powerplot/services/chart_generator.py
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

class ChartGenerator:
    
    def create_demand_breakdown_pie(self, summary):
        """Create pie charts showing demand breakdown"""
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                'Operational Demand - September 2025',
                'Underlying Demand - September 2025',
                'Operational Demand - YTD 2025',
                'Underlying Demand - YTD 2025'
            ),
            specs=[[{'type': 'pie'}, {'type': 'pie'}],
                   [{'type': 'pie'}, {'type': 'pie'}]]
        )
        
        # Example for first pie chart (you'll calculate actual values)
        fig.add_trace(
            go.Pie(
                labels=['RE', 'Fossil', 'Battery Net'],
                values=[summary.wind_generation + summary.solar_generation,
                       summary.fossil_generation,
                       summary.battery_discharge - summary.battery_charge],
                name="Operational"
            ),
            row=1, col=1
        )
        
        # Add other pies similarly...
        
        fig.update_layout(height=800, showlegend=True)
        return fig.to_html(include_plotlyjs='cdn')
    
    def create_diurnal_profile(self, diurnal_data, prices=None):
        """Create average diurnal profile chart"""
        df = pd.DataFrame(diurnal_data)
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df['time_of_day'],
            y=df['quantity'],
            name='Average Demand',
            line=dict(color='blue', width=2)
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
            ),
            height=480,
            width=640
        )
        
        return fig.to_html(include_plotlyjs='cdn')