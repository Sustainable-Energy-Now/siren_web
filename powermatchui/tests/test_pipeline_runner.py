from unittest import mock

from django.test import TestCase
from django.utils import timezone

from siren_web.models import CommandRun
from powermatchui.services import pipeline_runner
from powermatchui.services.pipeline_registry import PipelineCommand
from powermatchui.services.pipeline_runner import (
    PipelineBusyError,
    create_run,
    execute_run,
    reap_stale_runs,
)

CMD = PipelineCommand(key='t', label='Test command', group='g', management_command='noop')


def _fake_call_command(behaviour):
    """Return a call_command stand-in that writes to stdout then does `behaviour`."""
    def _inner(name, *args, stdout=None, stderr=None, **kw):
        if stdout is not None:
            stdout.write('ran %s %s' % (name, ' '.join(args)))
        if behaviour == 'ok':
            return
        if behaviour == 'raise':
            raise RuntimeError('kaboom')
        if behaviour == 'exit2':
            raise SystemExit(2)
        if behaviour == 'exit0':
            raise SystemExit(0)
    return _inner


class ExecuteRunTests(TestCase):
    def _run(self, behaviour):
        run = create_run(CMD, {}, trigger_source='cli')
        with mock.patch.object(pipeline_runner, 'call_command', _fake_call_command(behaviour)):
            rc = execute_run(run.pk)
        run.refresh_from_db()
        return rc, run

    def test_success_path(self):
        rc, run = self._run('ok')
        self.assertEqual(rc, 0)
        self.assertEqual(run.status, 'success')
        self.assertEqual(run.return_code, 0)
        self.assertIn('ran noop', run.output)
        self.assertIsNotNone(run.finished_at)

    def test_exception_is_captured(self):
        rc, run = self._run('raise')
        self.assertEqual(rc, 1)
        self.assertEqual(run.status, 'failed')
        self.assertIn('kaboom', run.error_summary)
        self.assertIn('Traceback', run.output)

    def test_systemexit_nonzero_is_failure(self):
        rc, run = self._run('exit2')
        self.assertEqual(rc, 2)
        self.assertEqual(run.status, 'failed')

    def test_systemexit_zero_is_success(self):
        rc, run = self._run('exit0')
        self.assertEqual(rc, 0)
        self.assertEqual(run.status, 'success')

    def test_busy_guard(self):
        CommandRun.objects.create(command_key='t', management_command='noop',
                                  args=[], label='x', status='running')
        with self.assertRaises(PipelineBusyError):
            create_run(CMD, {}, trigger_source='cli')

    def test_reap_stale_runs(self):
        old = CommandRun.objects.create(command_key='z', management_command='z', args=[],
                                        label='z', status='running')
        CommandRun.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timezone.timedelta(hours=2))
        self.assertEqual(reap_stale_runs(), 1)
        old.refresh_from_db()
        self.assertEqual(old.status, 'failed')

    def test_output_tail_capping(self):
        big = 'x' * (pipeline_runner.OUTPUT_TAIL_BYTES + 5000)
        self.assertLessEqual(len(pipeline_runner._tail(big)), pipeline_runner.OUTPUT_TAIL_BYTES + 50)
