"""
The single execution path for a whitelisted data-pipeline command.

``execute_run`` is called both by the background thread that
``start_background_run`` spawns (web UI) and, synchronously, by
``manage.py run_pipeline_command`` (cron). Either way one CommandRun row
records the whole invocation.
"""
from __future__ import annotations

import io
import logging
import threading
import traceback

from django.core.management import call_command
from django.db import connection
from django.utils import timezone

from siren_web.models import CommandRun
from powermatchui.services.pipeline_registry import (
    PIPELINE_COMMANDS,
    PipelineCommand,
    PipelineParamError,
    resolve_args,
)

logger = logging.getLogger(__name__)

OUTPUT_TAIL_BYTES = 256_000
STALE_RUN_AFTER_SECONDS = 3600


class PipelineBusyError(RuntimeError):
    """A run for this command is already queued or running."""


def _tail(text: str, limit: int = OUTPUT_TAIL_BYTES) -> str:
    if len(text) <= limit:
        return text
    return "...[output truncated]...\n" + text[-limit:]


def active_run_for(command_key: str) -> CommandRun | None:
    return (
        CommandRun.objects
        .filter(command_key=command_key, status__in=('queued', 'running'))
        .order_by('-created_at')
        .first()
    )


def reap_stale_runs() -> int:
    """Mark as failed any run stuck 'running'/'queued' past STALE_RUN_AFTER_SECONDS
    (its worker process almost certainly died). Returns how many were reaped."""
    cutoff = timezone.now() - timezone.timedelta(seconds=STALE_RUN_AFTER_SECONDS)
    stale = CommandRun.objects.filter(status__in=('queued', 'running'), created_at__lt=cutoff)
    n = stale.count()
    for run in stale:
        run.status = 'failed'
        run.error_summary = 'Reaped: still active after 1 h — the worker process likely stopped.'
        run.finished_at = timezone.now()
        run.save(update_fields=['status', 'error_summary', 'finished_at'])
    return n


def execute_run(run_id: int) -> int:
    """Run one CommandRun to completion. Returns its return code (0 = success)."""
    connection.close()  # a freshly-spawned thread must not reuse a pooled connection

    run = CommandRun.objects.get(pk=run_id)
    run.status = 'running'
    run.started_at = timezone.now()
    run.save(update_fields=['status', 'started_at'])

    buf = io.StringIO()
    return_code = 1
    try:
        call_command(run.management_command, *run.args, stdout=buf, stderr=buf)
        return_code = 0
        run.status = 'success'
    except SystemExit as exc:  # some commands sys.exit(non-zero) on failure
        return_code = exc.code if isinstance(exc.code, int) else 1
        run.status = 'success' if return_code == 0 else 'failed'
        if return_code != 0:
            run.error_summary = f'Command exited with status {return_code}.'
    except Exception as exc:  # noqa: BLE001 - we record everything
        return_code = 1
        run.status = 'failed'
        run.error_summary = f'{type(exc).__name__}: {exc}'[:500]
        buf.write('\n' + traceback.format_exc())
        logger.exception('Pipeline command %s failed', run.command_key)
    finally:
        run.return_code = return_code
        run.output = _tail(buf.getvalue())
        run.finished_at = timezone.now()
        run.save(update_fields=['status', 'return_code', 'output', 'error_summary', 'finished_at'])
        connection.close()

    return return_code


def create_run(cmd: PipelineCommand, raw_params: dict | None, *, trigger_source: str,
               user=None) -> CommandRun:
    """Validate params and create a queued CommandRun. Raises PipelineParamError
    or PipelineBusyError; does not start anything."""
    if active_run_for(cmd.key):
        raise PipelineBusyError(f"'{cmd.label}' is already running — wait for it to finish.")
    args = resolve_args(cmd, raw_params)
    return CommandRun.objects.create(
        command_key=cmd.key,
        management_command=cmd.management_command,
        args=args,
        label=cmd.label,
        trigger_source=trigger_source,
        triggered_by=user if (user and getattr(user, 'is_authenticated', False)) else None,
    )


def start_background_run(command_key: str, raw_params: dict | None, user=None) -> CommandRun:
    """Web-UI entry point: create the row and run it on a daemon thread."""
    cmd = PIPELINE_COMMANDS.get(command_key)
    if cmd is None or not cmd.runnable_from_ui:
        raise PipelineParamError(f"'{command_key}' is not a runnable pipeline command.")

    reap_stale_runs()
    run = create_run(cmd, raw_params, trigger_source='web', user=user)

    thread = threading.Thread(target=execute_run, args=(run.pk,), daemon=True,
                              name=f'pipeline-{command_key}-{run.pk}')
    thread.start()
    return run
