# powermatchui/views/gencost_views.py
"""
CSIRO GenCost cost-data pipeline: upload/inspect vintages, trigger parsing,
review technology-name mappings, and apply a chosen cost case onto the
live TechnologyYears table. The primary ingest path is auto-fetch
(fetch_gencost_vintages, surfaced on the Data Pipelines dashboard); the
upload form here is a manual fallback -- see gencost_vintage_fetcher.py's
module docstring.
"""
import hashlib
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.views.decorators.http import require_POST

from powermatchui.forms import GencostUploadForm
from powermatchui.services.pipeline_registry import PipelineParamError
from powermatchui.services.pipeline_runner import PipelineBusyError, start_background_run
from siren_web.models import (
    GENCOST_COST_CASE_CHOICES,
    CommandRun,
    GencostCostFigure,
    GencostTechnologyMapping,
    GencostVintage,
    SourceDocument,
    Technologies,
)

GENCOST_COMMAND_KEYS = ('extract_gencost_figures', 'apply_gencost_cost_case')


def _recent_runs_for(vintage, limit=10):
    """CommandRun rows for this vintage's extract/apply commands, newest
    first. args is a JSONField argv list (e.g. ['--vintage', '2025-26',
    '--case', 'current_policies']) -- filtered in Python rather than via
    a JSON-contains lookup, since MariaDB's Django backend doesn't support
    __contains on JSONField the way Postgres does."""
    candidates = CommandRun.objects.filter(command_key__in=GENCOST_COMMAND_KEYS).order_by('-created_at')[:100]
    return [r for r in candidates if vintage.edition in r.args][:limit]


def _checksum(fileobj) -> str:
    hasher = hashlib.sha256()
    for chunk in fileobj.chunks():
        hasher.update(chunk)
    return hasher.hexdigest()


@login_required
def gencost_upload(request):
    if request.method == 'POST':
        form = GencostUploadForm(request.POST, request.FILES)
        if form.is_valid():
            edition = form.cleaned_data['edition']
            doc_type = form.cleaned_data['doc_type']
            uploaded_file = form.cleaned_data['file']

            archive_dir = Path(settings.GENCOST_ARCHIVE_DIR) / edition
            archive_dir.mkdir(parents=True, exist_ok=True)
            file_path = archive_dir / uploaded_file.name
            with open(file_path, 'wb') as dest:
                for chunk in uploaded_file.chunks():
                    dest.write(chunk)
            checksum = hashlib.sha256(file_path.read_bytes()).hexdigest()

            vintage, _ = GencostVintage.objects.get_or_create(
                edition=edition,
                defaults={
                    'publication_date': form.cleaned_data.get('publication_date'),
                    'uploaded_by': request.user,
                },
            )
            SourceDocument.objects.update_or_create(
                gencost_vintage=vintage, doc_type=doc_type,
                defaults={
                    'checksum': checksum,
                    'local_file_path': file_path.relative_to(Path(settings.GENCOST_ARCHIVE_DIR)).as_posix(),
                    'dap_file_id': None,
                    'retrieved_at': timezone.now(),
                },
            )
            messages.success(request, f"Registered GenCost {edition} {doc_type}.")
            return redirect('powermatchui:gencost_vintage_detail', vintage_id=vintage.pk)
    else:
        form = GencostUploadForm()

    vintages = GencostVintage.objects.prefetch_related('source_documents').all()
    return render(request, 'gencost/upload.html', {'form': form, 'vintages': vintages})


@login_required
def gencost_vintage_detail(request, vintage_id):
    vintage = get_object_or_404(GencostVintage, pk=vintage_id)
    documents = vintage.source_documents.all()
    figures = GencostCostFigure.objects.filter(vintage=vintage)

    cases = []
    for key, label in GENCOST_COST_CASE_CHOICES:
        case_figures = figures.filter(cost_case=key)
        if not case_figures.exists():
            continue
        labels = set(case_figures.values_list('raw_technology_label', flat=True))
        # "Resolved" = either mapped to a Technology or explicitly marked
        # ignored (not applicable to this project) -- either way, reviewed.
        # A merely-pending label (technology=None, ignored=False) is what
        # actually blocks the Apply button below.
        resolved = set(
            GencostTechnologyMapping.objects.filter(raw_technology_label__in=labels)
            .filter(Q(technology__isnull=False) | Q(ignored=True))
            .values_list('raw_technology_label', flat=True)
        )
        cases.append({
            'key': key, 'label': label,
            'figure_count': case_figures.count(),
            'unmapped_count': len(labels - resolved),
        })

    context = {
        'vintage': vintage,
        'documents': documents,
        'figure_count': figures.count(),
        'cases': cases,
        'runs': _recent_runs_for(vintage),
    }
    return render(request, 'gencost/vintage_detail.html', context)


@login_required
@require_POST
def gencost_extract(request, vintage_id):
    vintage = get_object_or_404(GencostVintage, pk=vintage_id)
    try:
        run = start_background_run('extract_gencost_figures', {'vintage': vintage.edition}, user=request.user)
    except (PipelineParamError, PipelineBusyError) as e:
        messages.error(request, str(e))
    else:
        messages.success(request, format_html(
            'Started parsing (<a href="{}">run #{}</a>) — see "Recent runs" below, it updates live.',
            reverse('powermatchui:pipeline_run_detail', args=[run.pk]), run.pk,
        ))
    return redirect('powermatchui:gencost_vintage_detail', vintage_id=vintage.pk)


@login_required
@require_POST
def gencost_apply(request, vintage_id):
    vintage = get_object_or_404(GencostVintage, pk=vintage_id)
    case = request.POST.get('case', '')
    premium_pct = request.POST.get('premium_pct', '0')
    try:
        run = start_background_run(
            'apply_gencost_cost_case',
            {'vintage': vintage.edition, 'case': case, 'premium_pct': premium_pct},
            user=request.user,
        )
    except (PipelineParamError, PipelineBusyError) as e:
        messages.error(request, str(e))
    else:
        premium_note = f' with a {premium_pct}% capex premium' if premium_pct not in ('0', '0.0', '', None) else ''
        messages.success(request, format_html(
            'Started applying \'{}\'{} (<a href="{}">run #{}</a>) — see "Recent runs" below, it updates live.',
            case, premium_note, reverse('powermatchui:pipeline_run_detail', args=[run.pk]), run.pk,
        ))
    return redirect('powermatchui:gencost_vintage_detail', vintage_id=vintage.pk)


IGNORE_SENTINEL = '__ignore__'


@login_required
def gencost_mapping_review(request):
    if request.method == 'POST':
        mapping_id = request.POST.get('mapping_id')
        mapping = get_object_or_404(GencostTechnologyMapping, pk=mapping_id)
        selection = request.POST.get('technology', '')
        if selection == IGNORE_SENTINEL:
            mapping.technology = None
            mapping.ignored = True
        elif selection:
            mapping.technology = Technologies.objects.filter(pk=selection).first()
            mapping.ignored = False
        else:
            mapping.technology = None
            mapping.ignored = False
        mapping.save(update_fields=['technology', 'ignored', 'updated_at'])
        messages.success(request, f"Updated mapping for '{mapping.raw_technology_label}'.")
        return redirect('powermatchui:gencost_mapping_review')

    # Pending rows (technology IS NULL, ignored=False) first -- they're the
    # ones that actually need attention -- then mapped, then ignored last.
    mappings = GencostTechnologyMapping.objects.select_related('technology').order_by(
        'ignored', 'technology', 'raw_technology_label',
    )
    context = {
        'mappings': mappings,
        'technologies': Technologies.objects.order_by('technology_name'),
        'ignore_sentinel': IGNORE_SENTINEL,
    }
    return render(request, 'gencost/mapping_review.html', context)
