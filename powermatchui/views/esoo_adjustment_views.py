"""
Django views for WEM ESOO forecast adjustments.
CRUD for EsooForecastAdjustment, mirroring demand_factor_views.py's
pattern for DemandFactorType/DemandFactor.

An adjustment can come from two places: automatically computed by
powermatchui.utils.esoo_forecast_adjustment.build_adjusted_anchors (when
building a Powermatch scenario with "Apply ESOO bias correction" checked
-- see esoo_scenario_views.py), or entered/edited by hand here. Editing
an existing row always flips its `source` to 'manual' so a later
automatic recompute never silently overwrites it.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST

from powermatchui.utils.esoo_forecast_adjustment import compute_bias_correction, load_figures_and_actuals
from powerplotui.services.esoo_bias_analysis import align_forecast_actual_pairs
from siren_web.models import (
    ESOO_ADJUSTMENT_CATEGORY_CHOICES,
    ESOO_ADJUSTMENT_SOURCE_CHOICES,
    ESOO_ADJUSTMENT_VERDICT_CHOICES,
    EsooFigure,
    EsooForecastAdjustment,
    EsooVintage,
)


@login_required
def adjustment_list(request):
    """List all ESOO forecast adjustments, with filters."""
    vintage_filter = request.GET.get('vintage', '')
    metric_filter = request.GET.get('metric', '')
    category_filter = request.GET.get('category', '')
    verdict_filter = request.GET.get('verdict', '')
    source_filter = request.GET.get('source', '')
    applied_only = request.GET.get('applied_only', 'false') == 'true'

    adjustments = EsooForecastAdjustment.objects.select_related(
        'source_figure', 'source_figure__vintage', 'applied_to_scenario'
    ).all()

    if vintage_filter:
        adjustments = adjustments.filter(source_figure__vintage__idesoovintage=vintage_filter)
    if metric_filter:
        adjustments = adjustments.filter(source_figure__metric=metric_filter)
    if category_filter:
        adjustments = adjustments.filter(category=category_filter)
    if verdict_filter:
        adjustments = adjustments.filter(verdict=verdict_filter)
    if source_filter:
        adjustments = adjustments.filter(source=source_filter)
    if applied_only:
        adjustments = adjustments.filter(applied_to_scenario__isnull=False)

    paginator = Paginator(adjustments, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'vintages': EsooVintage.objects.order_by('-year'),
        'metric_choices': EsooFigure.objects.filter(domain='demand').values_list('metric', flat=True).distinct(),
        'category_choices': ESOO_ADJUSTMENT_CATEGORY_CHOICES,
        'verdict_choices': ESOO_ADJUSTMENT_VERDICT_CHOICES,
        'source_choices': ESOO_ADJUSTMENT_SOURCE_CHOICES,
        'vintage_filter': vintage_filter,
        'metric_filter': metric_filter,
        'category_filter': category_filter,
        'verdict_filter': verdict_filter,
        'source_filter': source_filter,
        'applied_only': applied_only,
    }
    return render(request, 'esoo_adjustments/adjustment_list.html', context)


@login_required
def adjustment_create(request):
    """Manually create an adjustment against one EsooFigure anchor --
    the only way to enter a correction for a category that isn't
    computed automatically yet (weather_normalization, pv_recalibration,
    block_load_removal, industrial_load_survey)."""
    if request.method == 'POST':
        try:
            source_figure = get_object_or_404(EsooFigure, pk=request.POST.get('source_figure'))
            category = request.POST.get('category', '')
            adjustment_value = float(request.POST.get('adjustment_value', 0.0))
            methodology_notes = request.POST.get('methodology_notes', '').strip()

            if not category:
                messages.error(request, 'Category is required.')
                return redirect('powermatchui:esoo_adjustment_create')

            if EsooForecastAdjustment.objects.filter(source_figure=source_figure, category=category).exists():
                messages.error(
                    request,
                    f'An adjustment for "{category}" already exists against this figure. Edit it instead.'
                )
                return redirect('powermatchui:esoo_adjustment_list')

            EsooForecastAdjustment.objects.create(
                source_figure=source_figure,
                category=category,
                horizon=source_figure.forecast_year - source_figure.vintage.year,
                original_value=source_figure.value,
                adjustment_value=adjustment_value,
                adjusted_value=source_figure.value + adjustment_value,
                unit=source_figure.unit,
                methodology_notes=methodology_notes,
                source='manual',
            )
            messages.success(request, f'Adjustment created for {source_figure}.')
            return redirect('powermatchui:esoo_adjustment_list')

        except (ValueError, TypeError) as e:
            messages.error(request, f'Error creating adjustment: {e}')
            return redirect('powermatchui:esoo_adjustment_create')

    context = {
        'figures': EsooFigure.objects.filter(domain='demand').select_related('vintage').order_by(
            '-vintage__year', 'forecast_year', 'metric'
        ),
        'category_choices': ESOO_ADJUSTMENT_CATEGORY_CHOICES,
    }
    return render(request, 'esoo_adjustments/adjustment_form.html', context)


@login_required
def adjustment_edit(request, pk):
    """Edit an adjustment's value/notes. source_figure and category are
    fixed once created (mirrors demand_factor_views.factor_edit's
    treatment of factor_type) since they're the row's identity
    (unique_together). Saving always sets source='manual', regardless of
    how the row started, so a later automatic recompute leaves it alone."""
    adjustment = get_object_or_404(
        EsooForecastAdjustment.objects.select_related('source_figure', 'source_figure__vintage'), pk=pk
    )

    if request.method == 'POST':
        try:
            adjustment.adjustment_value = float(request.POST.get('adjustment_value', 0.0))
            adjustment.adjusted_value = adjustment.original_value + adjustment.adjustment_value
            adjustment.methodology_notes = request.POST.get('methodology_notes', '').strip()
            adjustment.source = 'manual'
            adjustment.save()

            messages.success(request, f'Adjustment for {adjustment.source_figure} updated.')
            return redirect('powermatchui:esoo_adjustment_list')

        except (ValueError, TypeError) as e:
            messages.error(request, f'Error updating adjustment: {e}')
            return redirect('powermatchui:esoo_adjustment_edit', pk=pk)

    context = {'adjustment': adjustment, 'editing': True}
    return render(request, 'esoo_adjustments/adjustment_form.html', context)


@require_POST
@login_required
def adjustment_delete(request, pk):
    """Delete an adjustment."""
    adjustment = get_object_or_404(EsooForecastAdjustment, pk=pk)
    label = str(adjustment)
    adjustment.delete()
    messages.success(request, f'Adjustment "{label}" deleted.')
    return redirect('powermatchui:esoo_adjustment_list')


@require_POST
@login_required
def adjustment_recompute(request, pk):
    """Re-run compute_bias_correction for a `computed` row against the
    current EsooFigure/AnnualDemandActual archive -- picks up newly
    arrived actuals or a growing sample size without rebuilding a whole
    scenario. Refuses to run on a `manual` row: that value was set (or
    overridden) by a person and recomputing it would silently discard
    their input, which is exactly what the `source` flag exists to
    prevent."""
    adjustment = get_object_or_404(
        EsooForecastAdjustment.objects.select_related('source_figure', 'source_figure__vintage'), pk=pk
    )
    if adjustment.source == 'manual':
        messages.error(
            request,
            'This adjustment was manually entered or overridden — recompute is disabled to avoid '
            'discarding it. Delete and let it be recomputed instead if that\'s what you intend.'
        )
        return redirect('powermatchui:esoo_adjustment_list')

    figures, actuals = load_figures_and_actuals()
    pairs, _refused = align_forecast_actual_pairs(figures, actuals)
    figure = adjustment.source_figure
    result = compute_bias_correction(
        pairs, metric=figure.metric, demand_growth_scenario=figure.demand_growth_scenario,
        poe_level=figure.poe_level, horizon=adjustment.horizon,
        original_value=figure.value, unit=figure.unit, category=adjustment.category,
    )
    adjustment.adjustment_value = result.adjustment_value
    adjustment.adjusted_value = result.adjusted_value
    adjustment.verdict = result.verdict
    adjustment.p_value = result.p_value
    adjustment.n = result.n
    adjustment.methodology_notes = '; '.join(result.notes)
    adjustment.save()

    messages.success(request, f'Adjustment for {figure} recomputed: {result.verdict}.')
    return redirect('powermatchui:esoo_adjustment_list')
