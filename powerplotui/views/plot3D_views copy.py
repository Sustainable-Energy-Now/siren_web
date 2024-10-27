import plotly.graph_objs as go
from django.shortcuts import render
from siren_web.database_operations import get_monthly_average_reference_price

def wem_price_history(request):
    # Get data from the database
    prices = get_monthly_average_reference_price()
    
    # Extract data for Plotly
    trading_intervals = [price.trading_interval.strftime("%Y-%m-%d %H:%M:%S") for price in prices]
    reference_prices = [price.reference_price for price in prices]
    
    # Create Plotly data
    plot_div = go.Figure([go.Scatter(x=trading_intervals, y=reference_prices, mode='lines', name='Price')])

    plot_div.update_layout(title='WEM Price History', 
                           xaxis_title='Trading Interval', 
                           yaxis_title='Reference Price')

    plot_div = plot_div.to_html(full_html=False)  # Convert plotly figure to HTML string

    # Pass data and plot to the template
    context = {
        'prices': prices,
        'plot_div': plot_div
    }
    return render(request, 'wem_price_history_avg_mthly.html', context)