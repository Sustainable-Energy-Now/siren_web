"""
Read-only freshness / completeness summary of every data pipeline, built
straight from the existing manifest and figure tables (no new bookkeeping).

Every function returns plain dicts/lists ready for the template; each card
carries a ``staleness`` of 'ok' | 'warn' | 'stale' for badge colouring.
"""
from __future__ import annotations

import datetime as _dt

from django.db.models import Count, Max, Q
from django.utils import timezone

from siren_web.models import (
    AnnualDemandActual,
    CommandRun,
    DPVGeneration,
    EsooFigure,
    EsooVintage,
    EvActualsDocument,
    EvActualsRecord,
    EvChargingProfile,
    EvUptakePostcodeFigure,
    EvVintage,
    FacilityScada,
    SourceDocument,
)


def _staleness(age_days, warn, stale):
    if age_days is None:
        return 'stale'
    if age_days >= stale:
        return 'stale'
    if age_days >= warn:
        return 'warn'
    return 'ok'


def _age_days(value):
    if value is None:
        return None
    if isinstance(value, _dt.datetime):
        value = timezone.localtime(value).date() if timezone.is_aware(value) else value.date()
    return (_dt.date.today() - value).days


# --- SCADA / DPV ---------------------------------------------------------

def scada_card():
    latest = FacilityScada.objects.aggregate(m=Max('dispatch_interval'))['m']
    latest_date = timezone.localtime(latest).date() if latest else None
    age = _age_days(latest_date)

    missing_recent = None
    if latest_date:
        window_start = _dt.date.today() - _dt.timedelta(days=30)
        present = set(
            FacilityScada.objects
            .filter(dispatch_interval__date__gte=window_start)
            .dates('dispatch_interval', 'day')
        )
        expected = {
            window_start + _dt.timedelta(days=i)
            for i in range((_dt.date.today() - window_start).days)
        }
        missing_recent = sorted(expected - present)

    return {
        'key': 'scada',
        'title': 'SCADA half-hourly feed',
        'latest': latest_date,
        'age_days': age,
        'missing_last_30d': missing_recent,
        'detail': f"{len(missing_recent)} missing day(s) in the last 30" if missing_recent else 'complete for the last 30 days',
        'staleness': _staleness(age, warn=2, stale=5),
        'commands': ['fetch_scada'],
    }


def dpv_card():
    latest = DPVGeneration.objects.aggregate(m=Max('trading_date'))['m']
    age = _age_days(latest)
    return {
        'key': 'dpv',
        'title': 'Distributed-PV generation',
        'latest': latest,
        'age_days': age,
        'detail': f"latest interval {latest}" if latest else 'no DPV data loaded',
        'staleness': _staleness(age, warn=45, stale=75),
        'commands': ['fetch_dpv_prev_month'],
    }


# --- ESOO ---------------------------------------------------------------

_ESOO_DOC_TYPES = ('report', 'data_register', 'data_register_tables', 'demand_traces')


def esoo_card():
    vintages = list(EsooVintage.objects.order_by('-year'))
    docs_by_vintage: dict[int, set[str]] = {}
    for row in SourceDocument.objects.filter(esoo_vintage__isnull=False).values('esoo_vintage', 'doc_type'):
        docs_by_vintage.setdefault(row['esoo_vintage'], set()).add(row['doc_type'])

    fig_counts: dict[int, dict[str, int]] = {}
    for row in (EsooFigure.objects.values('vintage', 'validation_status')
                .annotate(n=Count('idesoofigure'))):
        fig_counts.setdefault(row['vintage'], {})[row['validation_status']] = row['n']
    last_extract = EsooFigure.objects.aggregate(m=Max('extraction_date'))['m']

    rows = []
    for v in vintages:
        counts = fig_counts.get(v.pk, {})
        rows.append({
            'year': v.year,
            'tier': v.get_tier_display(),
            'ingestion_status': v.ingestion_status,
            'has_report': bool(v.local_file_path),
            'docs': sorted(docs_by_vintage.get(v.pk, set())),
            'figures_total': sum(counts.values()),
            'figures_passed': counts.get('passed', 0),
            'figures_quarantined': counts.get('quarantined', 0) + counts.get('failed', 0),
            'figures_pending': counts.get('pending', 0) + counts.get('', 0),
        })

    quarantined = sum(r['figures_quarantined'] for r in rows)
    with_figures = [r for r in rows if r['figures_total']]
    age = _age_days(last_extract)
    return {
        'key': 'esoo',
        'title': 'WEM ESOO forecast figures',
        'vintages': rows,
        'n_vintages': len(rows),
        'n_with_figures': len(with_figures),
        'quarantined': quarantined,
        'last_extraction': last_extract,
        'detail': f"{len(with_figures)}/{len(rows)} vintages extracted"
                  + (f", {quarantined} quarantined figure(s)" if quarantined else ''),
        'staleness': 'warn' if quarantined else ('ok' if with_figures else 'stale'),
        'commands': ['ingest_esoo_vintage', 'extract_esoo_figures', 'validate_esoo_data',
                     'apply_esoo_demand_basis_crosswalk'],
    }


def esoo_actuals_card():
    by_basis = {
        row['demand_basis']: row['m']
        for row in AnnualDemandActual.objects.values('demand_basis').annotate(m=Max('year'))
    }
    latest_year = by_basis.get('operational')
    current_cy = _dt.date.today().year if _dt.date.today().month >= 10 else _dt.date.today().year - 1
    behind = None if latest_year is None else (current_cy - 1) - latest_year
    return {
        'key': 'esoo_actuals',
        'title': 'Annual demand actuals (SCADA-derived)',
        'latest_operational_year': latest_year,
        'detail': f"operational basis computed through Capacity Year {latest_year}"
                  if latest_year else 'not yet computed',
        'staleness': _staleness(None if behind is None else behind * 365, warn=1, stale=730),
        'commands': ['compute_annual_demand_actuals'],
    }


# --- EV ---------------------------------------------------------------

def ev_uptake_card():
    vintages = list(EvVintage.objects.order_by('-version'))
    docs_by_vintage: dict[int, set[str]] = {}
    for row in SourceDocument.objects.filter(ev_vintage__isnull=False).values('ev_vintage', 'doc_type'):
        docs_by_vintage.setdefault(row['ev_vintage'], set()).add(row['doc_type'])

    fig_counts: dict[int, dict[str, int]] = {}
    for row in (EvUptakePostcodeFigure.objects.values('vintage', 'validation_status')
                .annotate(n=Count('idevuptakepostcodefigure'))):
        fig_counts.setdefault(row['vintage'], {})[row['validation_status']] = row['n']

    profile_count = EvChargingProfile.objects.count()

    rows = []
    for v in vintages:
        counts = fig_counts.get(v.pk, {})
        rows.append({
            'version': v.version,
            'ingestion_status': v.ingestion_status,
            'release_date': v.release_date,
            'docs': sorted(docs_by_vintage.get(v.pk, set())),
            'figures_total': sum(counts.values()),
            'figures_passed': counts.get('passed', 0),
            'figures_failed': counts.get('failed', 0) + counts.get('quarantined', 0),
        })

    failed = sum(r['figures_failed'] for r in rows)
    with_figures = [r for r in rows if r['figures_total']]
    return {
        'key': 'ev',
        'title': 'EV uptake & charging figures',
        'vintages': rows,
        'n_vintages': len(rows),
        'n_with_figures': len(with_figures),
        'failed': failed,
        'charging_profiles': profile_count,
        'detail': f"{len(with_figures)}/{len(rows)} vintages extracted, "
                  f"{profile_count} charging-profile row(s)"
                  + (f", {failed} failed figure(s)" if failed else ''),
        'staleness': 'warn' if failed else ('ok' if with_figures else 'stale'),
        'commands': ['validate_ev_data'],
    }


def ev_actuals_card():
    latest_doc = EvActualsDocument.objects.order_by('-period_end').first()
    latest_record_year = EvActualsRecord.objects.aggregate(m=Max('year'))['m']
    age = _age_days(latest_doc.retrieved_at) if latest_doc else None
    return {
        'key': 'ev_actuals',
        'title': 'WA EV fleet actuals (DoT)',
        'latest_period_end': latest_doc.period_end if latest_doc else None,
        'latest_retrieved_at': latest_doc.retrieved_at if latest_doc else None,
        'latest_annual_year': latest_record_year,
        'detail': (f"latest report {latest_doc.quarter_label}, annual series through {latest_record_year}"
                   if latest_doc else 'no DoT reports ingested'),
        'staleness': _staleness(age, warn=100, stale=200),
        'commands': ['refresh_ev_actuals'],
    }


# --- everything ---------------------------------------------------------

def all_cards():
    return [
        scada_card(),
        dpv_card(),
        esoo_card(),
        esoo_actuals_card(),
        ev_uptake_card(),
        ev_actuals_card(),
    ]


def recent_runs(limit=25):
    return list(CommandRun.objects.select_related('triggered_by')[:limit])
