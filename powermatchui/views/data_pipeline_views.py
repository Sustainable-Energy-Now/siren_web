"""
powermatchui "Data Pipelines" facility.

- ``data_pipeline_dashboard``  : freshness cards + a per-command run form + run history
- ``submit_pipeline_command``  : validate params, kick off a background thread
- ``pipeline_run_status``      : JSON poll for one run's live status
- ``pipeline_run_detail``      : full captured output of one run
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from siren_web.models import CommandRun
from powermatchui.services.pipeline_registry import (
    GROUP_LABELS,
    PIPELINE_COMMANDS,
    PipelineParamError,
    commands_by_group,
)
from powermatchui.services.pipeline_runner import (
    PipelineBusyError,
    active_run_for,
    reap_stale_runs,
    start_background_run,
)
from powermatchui.services.pipeline_status import all_cards, recent_runs

staff_required = user_passes_test(lambda u: u.is_active and u.is_staff)


def _command_view_models():
    """The registry shaped for the template, with each command's active run (if any)."""
    groups = []
    for group, cmds in commands_by_group().items():
        entries = []
        for cmd in cmds:
            if not cmd.runnable_from_ui:
                continue
            active = active_run_for(cmd.key)
            entries.append({
                'key': cmd.key,
                'label': cmd.label,
                'note': cmd.note,
                'runtime_hint': cmd.runtime_hint,
                'cron_safe': cmd.cron_safe,
                'params': [
                    {
                        'name': p.name,
                        'kind': p.kind,
                        'label': p.label or p.name,
                        'flag': p.flag,
                        'required': p.required,
                        'help_text': p.help_text,
                        'default': p.resolved_default(),
                        'choices': p.resolved_choices() if p.kind == 'choice' else [],
                    }
                    for p in cmd.params
                ],
                'active_run_id': active.pk if active else None,
            })
        if entries:
            groups.append({'key': group, 'label': GROUP_LABELS.get(group, group), 'commands': entries})
    return groups


@login_required
def data_pipeline_dashboard(request):
    reap_stale_runs()
    context = {
        'cards': all_cards(),
        'command_groups': _command_view_models(),
        'runs': recent_runs(25),
        'can_run': request.user.is_active and request.user.is_staff,
    }
    return render(request, 'data_pipeline/dashboard.html', context)


@login_required
@staff_required
@require_POST
def submit_pipeline_command(request):
    command_key = request.POST.get('command_key', '')
    cmd = PIPELINE_COMMANDS.get(command_key)
    if cmd is None or not cmd.runnable_from_ui:
        messages.error(request, f"'{command_key}' is not a runnable pipeline command.")
        return redirect('powermatchui:data_pipeline_dashboard')

    raw_params = {
        p.name: request.POST.get(f'param_{p.name}', '')
        for p in cmd.params
    }
    # unchecked checkboxes don't post — treat a missing flag field as "off"
    for p in cmd.params:
        if p.kind == 'flag':
            raw_params[p.name] = f'param_{p.name}' in request.POST

    try:
        run = start_background_run(command_key, raw_params, user=request.user)
    except PipelineParamError as e:
        messages.error(request, str(e))
    except PipelineBusyError as e:
        messages.warning(request, str(e))
    else:
        messages.success(request, f"Started '{run.label}' (run #{run.pk}). It will run in the background.")
    return redirect('powermatchui:data_pipeline_dashboard')


@login_required
def pipeline_run_status(request, pk):
    run = get_object_or_404(CommandRun, pk=pk)
    return JsonResponse({
        'id': run.pk,
        'status': run.status,
        'status_display': run.get_status_display(),
        'return_code': run.return_code,
        'error_summary': run.error_summary,
        'duration_seconds': run.duration_seconds,
        'is_active': run.is_active,
        'finished_at': run.finished_at.isoformat() if run.finished_at else None,
    })


@login_required
def pipeline_run_detail(request, pk):
    run = get_object_or_404(CommandRun.objects.select_related('triggered_by'), pk=pk)
    return render(request, 'data_pipeline/run_detail.html', {'run': run})
