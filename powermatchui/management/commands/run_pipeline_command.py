"""
Cron / CLI wrapper that runs one whitelisted data-pipeline command and
records it in the same CommandRun history the powermatchui "Data Pipelines"
page shows.

    python manage.py run_pipeline_command fetch_scada
    python manage.py run_pipeline_command compute_annual_demand_actuals --param years=2018-2024
    python manage.py run_pipeline_command validate_ev_data --param vintage=2024-Q3
    python manage.py run_pipeline_command --list

Exit status is the wrapped command's return code, so cron/monitoring sees
failures.
"""
from django.core.management.base import BaseCommand, CommandError

from powermatchui.services.pipeline_registry import (
    GROUP_LABELS,
    PIPELINE_COMMANDS,
    PipelineParamError,
    commands_by_group,
)
from powermatchui.services.pipeline_runner import (
    PipelineBusyError,
    create_run,
    execute_run,
)


class Command(BaseCommand):
    help = 'Run one whitelisted data-pipeline command, logging it to CommandRun'

    def add_arguments(self, parser):
        parser.add_argument('command_key', nargs='?', help='Registry key, e.g. fetch_scada')
        parser.add_argument(
            '--param', action='append', default=[], metavar='name=value',
            help='A parameter for the wrapped command (repeatable), e.g. --param year=2024',
        )
        parser.add_argument('--list', action='store_true', help='List the available command keys and exit')

    def handle(self, *args, **options):
        if options['list'] or not options['command_key']:
            self._list()
            return

        key = options['command_key']
        cmd = PIPELINE_COMMANDS.get(key)
        if cmd is None:
            raise CommandError(
                f"Unknown pipeline command '{key}'. Run with --list to see the {len(PIPELINE_COMMANDS)} available keys."
            )

        raw_params = {}
        for item in options['param']:
            if '=' not in item:
                raise CommandError(f"--param must be name=value, got '{item}'")
            name, _, value = item.partition('=')
            raw_params[name.strip()] = value.strip()

        try:
            run = create_run(cmd, raw_params, trigger_source='cli')
        except PipelineParamError as e:
            raise CommandError(str(e))
        except PipelineBusyError as e:
            raise CommandError(str(e))

        self.stdout.write(f"[{run.pk}] {cmd.label}: {cmd.management_command} {' '.join(run.args)}")
        return_code = execute_run(run.pk)

        run.refresh_from_db()
        self.stdout.write(run.output or '(no output)')
        style = self.style.SUCCESS if return_code == 0 else self.style.ERROR
        self.stdout.write(style(f"[{run.pk}] {run.status} (exit {return_code}) in {run.duration_seconds:.1f}s"))

        if return_code != 0:
            raise SystemExit(return_code)

    def _list(self):
        self.stdout.write('Available pipeline commands:\n')
        for group, cmds in commands_by_group().items():
            self.stdout.write(self.style.MIGRATE_HEADING(GROUP_LABELS.get(group, group)))
            for cmd in cmds:
                params = ' '.join(
                    f"[{p.name}={p.resolved_default() if p.resolved_default() not in (None, '') else '?'}]"
                    for p in cmd.params
                )
                cron = '' if cmd.cron_safe else '  (not cron-safe — CPU heavy)'
                self.stdout.write(f"  {cmd.key:<32} {params}{cron}")
            self.stdout.write('')
