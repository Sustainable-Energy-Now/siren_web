from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from siren_web.models import Scenarios
from siren_web.services.facilities_takeup import BAND_CHOICES, generate_takeup_scenarios


@login_required
def facilities_scenarios(request):
    """Create or update Facilities Take-up scenarios (Low/Expected/High) for chosen years."""
    results = []
    years_text = request.POST.get('years', '')
    selected_bands = request.POST.getlist('bands') or list(BAND_CHOICES)
    threshold_text = request.POST.get('threshold', '0.5')

    if request.method == 'POST':
        try:
            years = sorted({int(y) for y in years_text.replace(',', ' ').split()})
            threshold = float(threshold_text)
            if not years:
                raise ValueError("Enter at least one year.")
            if not 0.0 <= threshold <= 1.0:
                raise ValueError("Probability threshold must be between 0 and 1.")
            bands = [b for b in BAND_CHOICES if b in selected_bands]
            if not bands:
                raise ValueError("Select at least one band.")
        except ValueError as e:
            messages.error(request, f"Invalid input: {e}")
        else:
            results = generate_takeup_scenarios(years, bands, threshold)
            failed = [r for r in results if not r.ok]
            if failed:
                messages.warning(request, f"{len(failed)} scenario(s) were not updated -- see details below.")
            else:
                messages.success(request, f"Created/updated {len(results)} Facilities Take-up scenario(s).")

    existing = Scenarios.objects.filter(is_auto_generated=True).select_related('scenario_type').order_by(
        'forecast_year', 'probability_band'
    )
    context = {
        'results': results,
        'existing': existing,
        'years_text': years_text,
        'selected_bands': selected_bands,
        'threshold': threshold_text,
        'band_choices': [(b, b.title()) for b in BAND_CHOICES],
        'config_file': request.session.get('config_file'),
    }
    return render(request, 'facilities_scenarios.html', context)
