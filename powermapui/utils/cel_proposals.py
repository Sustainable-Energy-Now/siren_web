"""
CELProposedUpdate lifecycle: turning findings (from documents, Western
Power GIS or derived calculations) into pending proposals, and applying an
accepted proposal to its CELStage.

Proposals are the only route by which the automated CEL feeds touch
CELStage — every change is reviewed on /cel/proposals/ first.
"""
from __future__ import annotations

import datetime as dt
import re

from django.db import transaction
from django.utils import timezone

from siren_web.models import CELProgram, CELProposedUpdate, CELStage

from .cel_document_extraction import STATUS_RANK, ProgramRef, StageRef, normalise, program_aliases

DATE_FIELDS = {'expected_operational_date', 'actual_operational_date'}
MW_FIELDS = {'capacity_new_mw', 'capacity_unlocked_existing_mw', 'reserved_capacity_mw'}
# Fields whose change alters viability scores, so accepting one triggers a recompute.
SCORING_FIELDS = {'funding_status'} | MW_FIELDS


# ---------------------------------------------------------------------------
# Reference data for the extractor
# ---------------------------------------------------------------------------

def stage_aliases(stage: CELStage) -> tuple[str, ...]:
    """Lower-cased names a sentence may use for this specific stage: its full
    name, and the part after the program prefix when that's distinctive
    (e.g. 'malaga to three springs', 'east stage 1')."""
    name = normalise(stage.name).strip().lower()
    aliases = {name} if name else set()
    parts = re.split(r'\s+-\s+', name, maxsplit=1)
    if len(parts) == 2 and len(parts[1]) >= 8:
        aliases.add(parts[1])
    return tuple(sorted(aliases))


def build_refs():
    """(programs, stages) for cel_document_extraction.extract_findings."""
    stages = list(CELStage.objects.filter(is_active=True, cel_program__is_active=True))
    by_program: dict[int, list[int]] = {}
    for s in stages:
        by_program.setdefault(s.cel_program_id, []).append(s.cel_stage_id)
    programs = [
        ProgramRef(p.cel_program_id, program_aliases(p.name, p.code), tuple(by_program.get(p.cel_program_id, ())))
        for p in CELProgram.objects.filter(is_active=True)
    ]
    stage_refs = [StageRef(s.cel_stage_id, s.cel_program_id, stage_aliases(s)) for s in stages]
    return programs, stage_refs


# ---------------------------------------------------------------------------
# Value formatting / comparison
# ---------------------------------------------------------------------------

def format_value(field_name: str, value) -> str:
    if value is None or value == '':
        return ''
    if field_name in DATE_FIELDS:
        return value.isoformat() if isinstance(value, dt.date) else str(value)
    if field_name in MW_FIELDS:
        return f'{float(value):.1f}'
    return str(value)


def parse_value(field_name: str, text: str):
    if field_name in DATE_FIELDS:
        return dt.date.fromisoformat(text)
    if field_name in MW_FIELDS:
        return float(text)
    if field_name == 'funding_status':
        if text not in STATUS_RANK:
            raise ValueError(f'Unknown funding status {text!r}')
        return text
    raise ValueError(f'Field {field_name!r} is not proposable')


def is_improvement(field_name: str, current, proposed) -> bool:
    """Should `proposed` be put to the reviewer, given the stage's `current`?"""
    if field_name == 'funding_status':
        # Only forward moves; a regression (e.g. a project paused) is rare
        # enough that a person should make it deliberately.
        return STATUS_RANK.get(proposed, -1) > STATUS_RANK.get(current, -1)
    if current in (None, ''):
        return True
    if field_name in MW_FIELDS:
        cur = float(current)
        return abs(float(proposed) - cur) > max(1.0, 0.01 * abs(cur))
    return proposed != current


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

def create_proposal(*, program_id: int, stage: CELStage | None, field_name: str, value,
                    evidence: str, source: str, source_url: str = '', snapshot=None):
    """Create a pending CELProposedUpdate unless it would be noise: no change
    from the stage's current value, an identical one already pending, or an
    identical one a reviewer already rejected.  Returns the row or None."""
    proposed = format_value(field_name, value)
    current = format_value(field_name, getattr(stage, field_name)) if stage else ''

    if stage is not None and not is_improvement(field_name, getattr(stage, field_name), value):
        return None

    dupes = CELProposedUpdate.objects.filter(
        cel_program_id=program_id, cel_stage=stage, field_name=field_name,
        proposed_value=proposed, status__in=('pending', 'rejected'),
    )
    if dupes.exists():
        return None

    return CELProposedUpdate.objects.create(
        cel_program_id=program_id, cel_stage=stage, source=source, snapshot=snapshot,
        source_url=source_url[:500], field_name=field_name, current_value=current,
        proposed_value=proposed, evidence=evidence,
    )


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------

def accept_proposal(proposal: CELProposedUpdate, user=None, stage: CELStage | None = None) -> CELStage:
    """Write the proposed value onto its stage, note the provenance in the
    stage notes, supersede other pending proposals for the same field and
    recompute viability if the field feeds the score.  `stage` is required
    when the proposal was raised at program level."""
    from powermapui.utils.cel_viability_service import CELViabilityService

    target = proposal.cel_stage or stage
    if target is None:
        raise ValueError('Choose the stage this proposal applies to.')
    if target.cel_program_id != proposal.cel_program_id:
        raise ValueError('That stage belongs to a different program.')

    value = parse_value(proposal.field_name, proposal.proposed_value)
    now = timezone.now()
    with transaction.atomic():
        old = format_value(proposal.field_name, getattr(target, proposal.field_name)) or '—'
        setattr(target, proposal.field_name, value)
        line = (f'[{now:%Y-%m-%d}] {proposal.field_name}: {old} → {proposal.proposed_value} '
                f'(accepted {proposal.get_source_display().lower()} proposal'
                f'{": " + proposal.source_url if proposal.source_url else ""})')
        target.notes = f'{target.notes}\n{line}'.strip()
        target.save()

        proposal.cel_stage = target
        proposal.status = 'accepted'
        proposal.reviewed_at = now
        proposal.reviewed_by = user if getattr(user, 'is_authenticated', False) else None
        proposal.save()

        CELProposedUpdate.objects.filter(
            cel_stage=target, field_name=proposal.field_name, status='pending',
        ).exclude(pk=proposal.pk).update(status='superseded', reviewed_at=now)

    if proposal.field_name in SCORING_FIELDS:
        CELViabilityService.score_facilities_for_stage(target)
    return target


def reject_proposal(proposal: CELProposedUpdate, user=None):
    proposal.status = 'rejected'
    proposal.reviewed_at = timezone.now()
    proposal.reviewed_by = user if getattr(user, 'is_authenticated', False) else None
    proposal.save(update_fields=['status', 'reviewed_at', 'reviewed_by'])
