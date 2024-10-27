# views.py
from django.shortcuts import render, get_object_or_404, redirect
from siren_web.models import TradingPrice
from ..forms import TradingPriceForm

# View for listing all trading prices
def trading_price_list(request):
    prices = TradingPrice.objects.all()
    return render(request, 'trading_price_list.html', {'prices': prices})

# View for updating a trading price
def update_trading_price(request, pk):
    price = get_object_or_404(TradingPrice, pk=pk)
    if request.method == 'POST':
        form = TradingPriceForm(request.POST, instance=price)
        if form.is_valid():
            form.save()
            return redirect('trading_price_list')
    else:
        form = TradingPriceForm(instance=price)
    return render(request, 'update_trading_price.html', {'form': form, 'price': price})
