"""
Whitelist of the periodic ESOO / EV / SCADA management commands that the
powermatchui "Data Pipelines" facility (and `manage.py run_pipeline_command`)
are allowed to run.

Nothing outside PIPELINE_COMMANDS can be launched from the web UI, and every
user-supplied parameter is validated/coerced by ``resolve_args`` before it
reaches ``django.core.management.call_command`` -- the argv list is never
built from a raw request string.

Commands deliberately NOT registered (they need per-release URLs, manual
downloads, or a CSV path, so they stay guided-manual on the CLI):
``ingest_ev_vintage``, ``extract_ev_figures``, ``load_ev_charging_profile``,
``import_ev_actuals``, ``register_local_esoo_files``, ``register_local_ev_files``,
and ``fetch_scada --historical``.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence


class PipelineParamError(ValueError):
    """A user-supplied parameter failed validation. The message is safe to
    show back to the user and names the offending field."""


# --- dynamic default helpers ------------------------------------------------

def current_capacity_year() -> int:
    """WEM Capacity Year start-label currently in progress. A Capacity Year
    starts 1 October, so before October we are still in the previous
    start-label's year (see compute_annual_demand_actuals)."""
    today = _dt.date.today()
    return today.year if today.month >= 10 else today.year - 1


def _current_capacity_year_range() -> str:
    n = current_capacity_year()
    return f"{n}-{n}"


def ev_vintage_versions() -> list[str]:
    from siren_web.models import EvVintage
    return list(EvVintage.objects.order_by('-version').values_list('version', flat=True))


def esoo_vintage_years() -> list[str]:
    from siren_web.models import EsooVintage
    return [str(y) for y in EsooVintage.objects.order_by('-year').values_list('year', flat=True)]


# --- param spec -----------------------------------------------------------

_MIN_YEAR, _MAX_YEAR = 2000, _dt.date.today().year + 2


@dataclass(frozen=True)
class Param:
    name: str                       # form field name
    kind: str                       # 'flag' | 'year' | 'year_range' | 'choice' | 'int'
    flag: str = ''                  # CLI flag, e.g. '--year'; '' for a positional
    label: str = ''
    default: Any = None             # value, or a zero-arg callable
    choices: Sequence | Callable = ()
    required: bool = False
    help_text: str = ''

    def resolved_default(self):
        return self.default() if callable(self.default) else self.default

    def resolved_choices(self):
        return list(self.choices() if callable(self.choices) else self.choices)


@dataclass(frozen=True)
class PipelineCommand:
    key: str
    label: str
    group: str
    management_command: str
    fixed_args: tuple[str, ...] = ()
    params: tuple[Param, ...] = ()
    runnable_from_ui: bool = True
    cron_safe: bool = True
    runtime_hint: str = ''
    note: str = ''


GROUP_LABELS = {
    'scada': 'SCADA & DPV feeds',
    'esoo': 'WEM ESOO forecast pipeline',
    'esoo_actuals': 'ESOO actuals (SCADA-derived)',
    'ev': 'EV uptake & charging pipeline',
    'ev_actuals': 'EV actuals (WA DoT)',
}


PIPELINE_COMMANDS: dict[str, PipelineCommand] = {c.key: c for c in [
    PipelineCommand(
        key='fetch_scada',
        label='Fetch SCADA (yesterday)',
        group='scada',
        management_command='fetch_scada',
        runtime_hint='seconds–minutes',
        note="Downloads yesterday's AEMO half-hourly SCADA JSON. Idempotent "
             "(skips days already stored). The base feed everything else derives from.",
    ),
    PipelineCommand(
        key='fetch_dpv_prev_month',
        label='Fetch DPV (previous month)',
        group='scada',
        management_command='fetch_dpv',
        fixed_args=('--previous-month',),
        runtime_hint='minutes',
        note="Downloads last month's AEMO distributed-PV generation. Built for a monthly schedule.",
    ),
    PipelineCommand(
        key='refresh_ev_actuals',
        label='Refresh WA EV actuals (DoT)',
        group='ev_actuals',
        management_command='refresh_ev_actuals',
        runtime_hint='seconds–minutes',
        note="Scrapes the DoT WA index, downloads any new quarterly licensing PDFs, "
             "re-parses Figure 1b and rebuilds EvActualsDocument / EvActualsQuarter / "
             "EvActualsRecord. Idempotent; fails loudly if the PDF layout changed.",
    ),
    PipelineCommand(
        key='compute_annual_demand_actuals',
        label='Compute annual demand actuals',
        group='esoo_actuals',
        management_command='compute_annual_demand_actuals',
        params=(
            Param('years', 'year_range', '--years', label='Capacity-year range',
                  default=_current_capacity_year_range,
                  help_text='Start-label range, e.g. 2018-2024. Default: the Capacity Year in progress.'),
            Param('force', 'flag', '--force', label='Recompute existing rows', default=True),
        ),
        runtime_hint='seconds–minutes',
        note="Aggregates FacilityScada into AnnualDemandActual (operational basis) per WEM "
             "Capacity Year. Re-run with force to refresh the in-progress year as SCADA fills in.",
    ),
    PipelineCommand(
        key='validate_esoo_data',
        label='Validate ESOO figures',
        group='esoo',
        management_command='validate_esoo_data',
        params=(
            Param('year', 'year', '--year', label='Vintage year (optional)', required=False,
                  help_text='Leave blank to validate every vintage.'),
        ),
        runtime_hint='seconds',
        note="FR-F08 completeness / range / consistency checks over EsooFigure; quarantines failures.",
    ),
    PipelineCommand(
        key='apply_esoo_demand_basis_crosswalk',
        label='ESOO underlying→operational crosswalk',
        group='esoo',
        management_command='apply_esoo_demand_basis_crosswalk',
        params=(
            Param('year', 'year', '--year', label='Vintage year (optional)', required=False),
        ),
        runtime_hint='seconds–minutes',
        note="FR-F07/D13: derives operational-basis energy figures from published underlying ones "
             "wherever real DPV coverage allows. Only does work when figures or DPV data changed.",
    ),
    PipelineCommand(
        key='validate_ev_data',
        label='Validate EV uptake figures',
        group='ev',
        management_command='validate_ev_data',
        params=(
            Param('vintage', 'choice', '--vintage', label='EV vintage (optional)', required=False,
                  choices=ev_vintage_versions,
                  help_text='Leave blank to validate every vintage. Backcast gates need a vintage.'),
        ),
        runtime_hint='seconds',
        note="FR-20 completeness / range checks over EvUptakePostcodeFigure; quarantines failures. "
             "(The FR-07 backcast gates need extra flags — run those from the CLI.)",
    ),
    PipelineCommand(
        key='extract_esoo_figures',
        label='Extract ESOO figures (one vintage)',
        group='esoo',
        management_command='extract_esoo_figures',
        params=(
            Param('year', 'year', '--year', label='Vintage year', required=True,
                  choices=esoo_vintage_years),
        ),
        cron_safe=False,
        runtime_hint='minutes — CPU-heavy',
        note="Structured-workbook + PDF-fallback extraction into EsooFigure. Heavy (128-page PDF / "
             "20 MB workbook); prefer running this from the CLI rather than the web process.",
    ),
    PipelineCommand(
        key='ingest_esoo_vintage',
        label='Ingest ESOO vintage (download from AEMO)',
        group='esoo',
        management_command='ingest_esoo_vintage',
        params=(
            Param('year', 'year', '--year', label='Publication year', required=True),
            Param('doc_type', 'choice', '--doc-type', label='Document',
                  choices=('report', 'data_register'), default='report'),
        ),
        cron_safe=False,
        runtime_hint='seconds–minutes',
        note="Downloads AEMO's per-year ESOO report or Data Register workbook. The Demand Traces "
             "(.xlsb) is often Cloudflare-blocked — download it by hand and use register_local_esoo_files.",
    ),
]}


def commands_by_group() -> dict[str, list[PipelineCommand]]:
    out: dict[str, list[PipelineCommand]] = {}
    for cmd in PIPELINE_COMMANDS.values():
        out.setdefault(cmd.group, []).append(cmd)
    return out


# --- validation / argv construction --------------------------------------

def _coerce_year(raw: str, field_name: str) -> int:
    try:
        year = int(str(raw).strip())
    except (TypeError, ValueError):
        raise PipelineParamError(f"{field_name}: '{raw}' is not a year.")
    if not (_MIN_YEAR <= year <= _MAX_YEAR):
        raise PipelineParamError(f"{field_name}: {year} is outside {_MIN_YEAR}–{_MAX_YEAR}.")
    return year


def _coerce_year_range(raw: str, field_name: str) -> str:
    text = str(raw).strip()
    if '-' not in text:
        raise PipelineParamError(f"{field_name}: '{raw}' must look like 2018-2024.")
    start_s, _, end_s = text.partition('-')
    start = _coerce_year(start_s, field_name)
    end = _coerce_year(end_s, field_name)
    if start > end:
        raise PipelineParamError(f"{field_name}: start year {start} is after end year {end}.")
    return f"{start}-{end}"


def resolve_args(cmd: PipelineCommand, raw_params: dict | None) -> list[str]:
    """Validate raw_params against cmd.params and return the concrete argv
    list for call_command. Raises PipelineParamError on any bad input."""
    raw_params = raw_params or {}
    args: list[str] = list(cmd.fixed_args)

    for p in cmd.params:
        raw = raw_params.get(p.name, None)
        provided = raw not in (None, '', [])

        if p.kind == 'flag':
            on = raw if isinstance(raw, bool) else str(raw).lower() in ('1', 'true', 'on', 'yes')
            if not provided:
                on = bool(p.resolved_default())
            if on:
                args.append(p.flag)
            continue

        if not provided:
            default = p.resolved_default()
            if default in (None, ''):
                if p.required:
                    raise PipelineParamError(f"{p.label or p.name} is required.")
                continue
            raw = default

        if p.kind == 'year':
            value = str(_coerce_year(raw, p.label or p.name))
        elif p.kind == 'year_range':
            value = _coerce_year_range(raw, p.label or p.name)
        elif p.kind == 'int':
            try:
                value = str(int(str(raw).strip()))
            except (TypeError, ValueError):
                raise PipelineParamError(f"{p.label or p.name}: '{raw}' is not a number.")
        elif p.kind == 'choice':
            value = str(raw).strip()
            valid = [str(c) for c in p.resolved_choices()]
            if value not in valid:
                raise PipelineParamError(
                    f"{p.label or p.name}: '{value}' is not one of {valid or '[none available]'}."
                )
        else:
            raise PipelineParamError(f"Unknown parameter kind '{p.kind}' for {p.name}.")

        if p.flag:
            args.extend([p.flag, value])
        else:
            args.append(value)

    return args
