import csv
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from siren_web.models import facilities, Scenarios, ScenariosFacilities

from common.decorators import settings_required


def _get_session_context(request):
    weather_year = request.session.get('weather_year', '')
    demand_year = request.session.get('demand_year', '')
    scenario = request.session.get('scenario', '')
    config_file = request.session.get('config_file')
    return {
        'weather_year': weather_year,
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
    }


def _traffic_light(value, field):
    """
    Return a Bootstrap colour class (text-success / text-warning / text-danger)
    for a given field value, matching the external framework's traffic-light logic.
    """
    GREEN = 'success'
    AMBER = 'warning'
    RED = 'danger'

    mapping = {
        'ppa_status':               {'signed': GREEN, 'hoa': AMBER, 'none': RED},
        'epc_status':               {'locked': GREEN, 'progressing': AMBER, 'none': RED},
        'developer_strength':       {'very_strong': GREEN, 'strong': GREEN, 'moderate': AMBER, 'weak': RED},
        'revenue_stack':            {'capacity': GREEN, 'ppa_cis': GREEN, 'ppa': GREEN,
                                     'cis_merchant': AMBER, 'merchant': RED},
        'community_fn_status':      {'active': GREEN, 'typical': GREEN, 'unknown': AMBER, 'opposition': RED},
        'portfolio_priority':       {'high': GREEN, 'medium': AMBER, 'low': RED},
        'coal_retirement_alignment': {'critical': GREEN, 'strong': GREEN, 'good': GREEN,
                                      'ok': AMBER, 'none': RED},
        'tech_complexity':          {'simple': GREEN, 'moderate': AMBER, 'hybrid': AMBER, 'high': RED},
        'approvals':                {'approved': GREEN, 'advanced': GREEN, 'progressing': AMBER, 'early': RED},
    }
    colour = mapping.get(field, {}).get(value, AMBER)
    return f'text-{colour}'


def _score_colour(score):
    if score is None:
        return 'text-muted'
    if score >= 0.65:
        return 'text-success fw-bold'
    if score >= 0.40:
        return 'text-warning fw-bold'
    return 'text-danger fw-bold'


def _build_facility_row(f):
    """Build a dict of display data for a single facility."""
    mfbp = f.multi_factor_build_probability
    ecp = f.effective_commissioning_probability
    best_cel = f.best_cel_alignment
    cel_score = best_cel.viability_score if best_cel else None

    def tl(field):
        return _traffic_light(getattr(f, field, ''), field)

    return {
        'pk': f.idfacilities,
        'facility_name': f.facility_name or '',
        'status': f.get_status_display(),
        'capacity': f.capacity,
        # Factor values + colours
        'ppa_status_display': f.get_ppa_status_display(),
        'ppa_status_colour': tl('ppa_status'),
        'ppa_counterparty': f.ppa_counterparty,
        'fid_expected_date': f.fid_expected_date,
        'epc_status_display': f.get_epc_status_display(),
        'epc_status_colour': tl('epc_status'),
        'developer_strength_display': f.get_developer_strength_display(),
        'developer_strength_colour': tl('developer_strength'),
        'revenue_stack_display': f.get_revenue_stack_display(),
        'revenue_stack_colour': tl('revenue_stack'),
        'community_fn_status_display': f.get_community_fn_status_display(),
        'community_fn_status_colour': tl('community_fn_status'),
        'portfolio_priority_display': f.get_portfolio_priority_display(),
        'portfolio_priority_colour': tl('portfolio_priority'),
        'coal_retirement_alignment_display': f.get_coal_retirement_alignment_display(),
        'coal_retirement_alignment_colour': tl('coal_retirement_alignment'),
        'tech_complexity_display': f.get_tech_complexity_display(),
        'tech_complexity_colour': tl('tech_complexity'),
        'approvals_display': f.get_approvals_display(),
        'approvals_colour': tl('approvals'),
        # Probability scores
        'commissioning_probability': f.commissioning_probability,
        'commissioning_probability_colour': _score_colour(f.commissioning_probability),
        'cel_viability_score': round(cel_score, 3) if cel_score is not None else None,
        'cel_viability_colour': _score_colour(cel_score),
        'multi_factor_build_probability': mfbp,
        'multi_factor_colour': _score_colour(mfbp),
        'effective_commissioning_probability': ecp,
        'effective_colour': _score_colour(ecp),
    }


@login_required
@settings_required(redirect_view='powermapui:powermapui_home')
def project_viability_dashboard(request):
    """Sortable, colour-coded build probability dashboard for proposed/planned facilities."""
    ctx = _get_session_context(request)
    all_scenarios = Scenarios.objects.all().order_by('title')

    scenario_filter = request.GET.get('scenario_filter', '')
    sort_by = request.GET.get('sort', 'multi_factor_build_probability')
    sort_dir = request.GET.get('dir', 'desc')

    fac_qs = facilities.objects.filter(
        status__in=('proposed', 'planned', 'under_construction')
    ).prefetch_related('cel_alignments')

    if scenario_filter:
        try:
            scenario_obj = Scenarios.objects.get(idscenarios=scenario_filter)
            facility_ids = ScenariosFacilities.objects.filter(
                idscenarios=scenario_obj
            ).values_list('idfacilities', flat=True)
            fac_qs = fac_qs.filter(idfacilities__in=facility_ids)
        except Scenarios.DoesNotExist:
            pass

    rows = [_build_facility_row(f) for f in fac_qs]

    # Sort
    reverse = (sort_dir == 'desc')
    if sort_by in ('multi_factor_build_probability', 'commissioning_probability',
                   'cel_viability_score', 'effective_commissioning_probability', 'capacity'):
        rows.sort(key=lambda r: (r[sort_by] is None, r[sort_by] or 0), reverse=reverse)
    elif sort_by == 'facility_name':
        rows.sort(key=lambda r: r['facility_name'].lower(), reverse=reverse)
    else:
        rows.sort(key=lambda r: r.get(sort_by, ''), reverse=reverse)

    # CSV export
    if request.GET.get('export') == 'csv':
        return _export_csv(rows)

    ctx.update({
        'rows': rows,
        'all_scenarios': all_scenarios,
        'scenario_filter': scenario_filter,
        'sort_by': sort_by,
        'sort_dir': sort_dir,
        'row_count': len(rows),
    })
    return render(request, 'project_viability_dashboard.html', ctx)


def _export_csv(rows):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="project_viability.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'Facility', 'Status', 'Capacity (MW)',
        'PPA Status', 'PPA Counterparty', 'FID Expected',
        'EPC Status', 'Developer Strength', 'Revenue Stack',
        'Approvals', 'Community/FN Status', 'Portfolio Priority',
        'Coal Retirement Alignment', 'Tech Complexity',
        'Commissioning Probability', 'CEL Viability Score',
        'Effective Commissioning Probability', 'Multi-Factor Build Probability',
    ])
    for r in rows:
        writer.writerow([
            r['facility_name'], r['status'], r['capacity'],
            r['ppa_status_display'], r['ppa_counterparty'], r['fid_expected_date'],
            r['epc_status_display'], r['developer_strength_display'], r['revenue_stack_display'],
            r['approvals_display'], r['community_fn_status_display'], r['portfolio_priority_display'],
            r['coal_retirement_alignment_display'], r['tech_complexity_display'],
            r['commissioning_probability'], r['cel_viability_score'],
            r['effective_commissioning_probability'], r['multi_factor_build_probability'],
        ])
    return response
