# powermatchui/views/supply_matrix_views.py
"""
Supply Trace Years: list the years stored in SupplyFactorMatrix, show
which facilities each year holds, download a year as CSV, and delete a
year.

SupplyFactorMatrix holds one row per weather year (written by Run Power
under the selected Demand's reference_year). Rows for years no Demand
refers to any more, or whose facilities have all been deleted, are stale
and can be removed here.

Deleting is the only write. It is refused for a year an active Demand
uses as its reference_year unless the user ticks an explicit override,
since that Demand's Run Power / dispatch would then find no supply data.
"""
import calendar
import csv

import numpy as np
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from siren_web.models import Demand, SupplyFactorMatrix, facilities
from siren_web.services import supply_matrix
from siren_web.services.supply_matrix import TRACE_KW_PER_MW


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _interval_hours(year, n_hours):
    """Length of one matrix column in hours: 0.5 when the row is half-hourly
    (more columns than hours in the year), otherwise 1."""
    hours_in_year = 8784 if calendar.isleap(year) else 8760
    return 0.5 if n_hours > hours_in_year else 1.0


def _resolution_label(interval_hours):
    return 'half-hourly' if interval_hours == 0.5 else 'hourly'


def demands_by_reference_year():
    """{year: [Demand, ...]} for active Demands, keyed on reference_year."""
    out = {}
    for d in Demand.objects.filter(is_active=True, reference_year__isnull=False).order_by('name'):
        out.setdefault(int(d.reference_year), []).append(d)
    return out


def summarise_years():
    """One dict per SupplyFactorMatrix row, oldest year first."""
    users = demands_by_reference_year()
    rows = list(SupplyFactorMatrix.objects.order_by('year'))
    all_ids = {fid for r in rows for fid in r.facility_ids}
    live_ids = set(facilities.objects.filter(idfacilities__in=all_ids).values_list('idfacilities', flat=True))

    years = []
    for r in rows:
        ids, matrix = r.unpack()
        n_live = sum(1 for fid in ids if fid in live_ids)
        cells = matrix.size
        coverage = (float(np.count_nonzero(~np.isnan(matrix))) / cells * 100) if cells else 0.0
        demands = users.get(r.year, [])
        if not ids:
            status = 'Empty'
        elif n_live == 0:
            status = 'Orphaned: every facility has been deleted'
        elif not demands:
            status = 'No active Demand uses this year'
        else:
            status = 'In use'
        years.append({
            'year': r.year,
            'n_facilities': len(ids),
            'n_live': n_live,
            'n_deleted': len(ids) - n_live,
            'n_hours': r.n_hours,
            'resolution': _resolution_label(_interval_hours(r.year, r.n_hours)),
            'coverage_pct': coverage,
            'size_mb': len(r.data) / (1024 * 1024) if r.data else 0.0,
            'updated_at': r.updated_at,
            'demands': demands,
            'in_use': bool(demands),
            'status': status,
        })
    return years


def facility_breakdown(year):
    """Per-facility rows for one year: name, technology, hours with data, energy, capacity factor."""
    row = SupplyFactorMatrix.objects.get(year=year)
    ids, matrix = row.unpack()
    step = _interval_hours(year, row.n_hours)
    objs = facilities.objects.select_related('idtechnologies').in_bulk(list(ids))

    out = []
    for i, fid in enumerate(ids):
        trace = matrix[i]
        n_data = int(np.count_nonzero(~np.isnan(trace)))
        energy_mwh = float(np.nansum(trace)) * step / TRACE_KW_PER_MW if n_data else 0.0
        f = objs.get(fid)
        capacity = getattr(f, 'capacity', None) if f else None
        cf = None
        if capacity and n_data:
            cf = energy_mwh / (float(capacity) * n_data * step) * 100
        out.append({
            'id': fid,
            'name': f.facility_name if f else None,
            'technology': (f.idtechnologies.technology_name if f and f.idtechnologies else ''),
            'capacity_mw': capacity,
            'hours_with_data': n_data * step,
            'energy_gwh': energy_mwh / 1000.0,
            'capacity_factor_pct': cf,
            'deleted': f is None,
        })
    out.sort(key=lambda r: (r['deleted'], r['technology'], r['name'] or ''))
    return out, _resolution_label(step)


def download_year_csv(year):
    """The whole year as CSV: one column per facility, values in kW as stored."""
    row = SupplyFactorMatrix.objects.get(year=year)
    ids, matrix = row.unpack()
    names = dict(facilities.objects.filter(idfacilities__in=ids).values_list('idfacilities', 'facility_name'))

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="supply_factor_matrix_{year}.csv"'
    writer = csv.writer(response)
    writer.writerow(['interval'] + [f"{fid}: {names.get(fid, 'deleted facility')}" for fid in ids])
    for h in range(matrix.shape[1]):
        col = matrix[:, h]
        writer.writerow([h] + ['' if np.isnan(v) else f"{float(v):.6g}" for v in col])
    return response


@login_required
def supply_matrix_years(request):
    """GET: ?year=<yyyy> shows that year's facilities; add &download=csv to download it."""
    selected_year = _int_or_none(request.GET.get('year'))
    years = summarise_years()
    known = {y['year'] for y in years}

    if selected_year is not None and selected_year in known and request.GET.get('download') == 'csv':
        return download_year_csv(selected_year)

    context = {'years': years, 'selected_year': None, 'breakdown': None, 'error': None}
    if selected_year is not None:
        if selected_year not in known:
            context['error'] = f"There is no stored supply trace year {selected_year}."
        else:
            breakdown, resolution = facility_breakdown(selected_year)
            context.update({
                'selected_year': selected_year,
                'selected': next(y for y in years if y['year'] == selected_year),
                'breakdown': breakdown,
                'breakdown_resolution': resolution,
            })
    return render(request, 'supply_matrix_years.html', context)


@login_required
@require_POST
def delete_supply_matrix_year(request, year):
    """Delete one year's SupplyFactorMatrix row.

    Refused when an active Demand uses this year as its reference_year,
    unless the form's confirm_in_use box was ticked.
    """
    row = SupplyFactorMatrix.objects.filter(year=year).first()
    if row is None:
        messages.error(request, f"There is no stored supply trace year {year}.")
        return redirect('powermatchui:supply_matrix_years')

    users = demands_by_reference_year().get(year, [])
    if users and request.POST.get('confirm_in_use') != '1':
        names = ', '.join(d.name or f"Demand {d.iddemand}" for d in users)
        messages.error(
            request,
            f"Not deleted: {year} is the weather year for {names}. Tick the override box to delete it anyway. "
            "Those forecasts will then have no supply traces until Run Power is run again."
        )
        return redirect(f"{reverse('powermatchui:supply_matrix_years')}?year={year}")

    n = len(row.facility_ids)
    row.delete()
    supply_matrix._cache.pop(year, None)
    messages.success(request, f"Deleted supply trace year {year} ({n} facility traces).")
    return redirect('powermatchui:supply_matrix_years')
