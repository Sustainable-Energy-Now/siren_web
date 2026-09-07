import datetime as dt

from django.test import SimpleTestCase

from powermatchui.services.pipeline_registry import (
    PIPELINE_COMMANDS,
    Param,
    PipelineCommand,
    PipelineParamError,
    current_capacity_year,
    resolve_args,
)


class ResolveArgsTests(SimpleTestCase):
    def _cmd(self, *params, fixed=()):
        return PipelineCommand(key='t', label='t', group='g', management_command='noop',
                               fixed_args=fixed, params=params)

    def test_fixed_args_passthrough(self):
        cmd = self._cmd(fixed=('--previous-month',))
        self.assertEqual(resolve_args(cmd, {}), ['--previous-month'])

    def test_year_valid_and_flagged(self):
        cmd = self._cmd(Param('year', 'year', '--year'))
        self.assertEqual(resolve_args(cmd, {'year': '2024'}), ['--year', '2024'])

    def test_year_rejects_non_numeric(self):
        cmd = self._cmd(Param('year', 'year', '--year'))
        with self.assertRaises(PipelineParamError):
            resolve_args(cmd, {'year': '2024; rm -rf /'})

    def test_year_rejects_out_of_range(self):
        cmd = self._cmd(Param('year', 'year', '--year'))
        with self.assertRaises(PipelineParamError):
            resolve_args(cmd, {'year': '1990'})

    def test_required_missing_raises(self):
        cmd = self._cmd(Param('year', 'year', '--year', required=True))
        with self.assertRaises(PipelineParamError):
            resolve_args(cmd, {})

    def test_optional_missing_is_omitted(self):
        cmd = self._cmd(Param('year', 'year', '--year', required=False))
        self.assertEqual(resolve_args(cmd, {}), [])

    def test_year_range_ok(self):
        cmd = self._cmd(Param('years', 'year_range', '--years'))
        self.assertEqual(resolve_args(cmd, {'years': '2018-2024'}), ['--years', '2018-2024'])

    def test_year_range_reversed_raises(self):
        cmd = self._cmd(Param('years', 'year_range', '--years'))
        with self.assertRaises(PipelineParamError):
            resolve_args(cmd, {'years': '2024-2018'})

    def test_year_range_dynamic_default(self):
        cmd = self._cmd(Param('years', 'year_range', '--years',
                              default=lambda: f"{current_capacity_year()}-{current_capacity_year()}"))
        n = current_capacity_year()
        self.assertEqual(resolve_args(cmd, {}), ['--years', f'{n}-{n}'])

    def test_flag_default_true_and_unchecked(self):
        cmd = self._cmd(Param('force', 'flag', '--force', default=True))
        self.assertEqual(resolve_args(cmd, {}), ['--force'])
        self.assertEqual(resolve_args(cmd, {'force': False}), [])

    def test_choice_validates_membership(self):
        cmd = self._cmd(Param('doc_type', 'choice', '--doc-type', choices=('report', 'data_register')))
        self.assertEqual(resolve_args(cmd, {'doc_type': 'report'}), ['--doc-type', 'report'])
        with self.assertRaises(PipelineParamError):
            resolve_args(cmd, {'doc_type': 'evil'})

    def test_capacity_year_boundary(self):
        # sanity: October flips the label forward
        self.assertIn(current_capacity_year(), (dt.date.today().year, dt.date.today().year - 1))


class RegistryIntegrityTests(SimpleTestCase):
    def test_every_command_resolves_with_defaults(self):
        for key, cmd in PIPELINE_COMMANDS.items():
            has_required = any(p.required and p.resolved_default() in (None, '') for p in cmd.params)
            if has_required:
                continue
            args = resolve_args(cmd, {})
            self.assertIsInstance(args, list, key)

    def test_keys_match_dict(self):
        for key, cmd in PIPELINE_COMMANDS.items():
            self.assertEqual(key, cmd.key)
