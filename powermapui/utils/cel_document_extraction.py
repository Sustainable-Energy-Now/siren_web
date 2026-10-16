"""
Rule-based extraction of CEL progress facts from published text.

No authority publishes Clean Energy Link progress as data — it appears only
as prose in Western Power / EPWA / DPC pages and PDFs.  This module turns
sentences from that text into candidate CELStage field values, each with
the sentence it came from as evidence.  It never writes to the database;
`cel_proposals.create_proposal` decides what becomes a CELProposedUpdate.

Deliberately conservative: a sentence must name a program/stage (or the
whole document must be about a single program) and match a narrow phrase
pattern.  Missing a fact is cheap (the reviewer still sees the change on the
Sources table); a wrong proposal costs a reviewer's attention.

Pure functions only — everything here is unit-testable without a DB.
"""
from __future__ import annotations

import calendar
import datetime as dt
import re
from dataclasses import dataclass

# Funding-status order, lowest to highest (mirrors CEL_FUNDING_STATUS_CHOICES).
STATUS_RANK = {
    'planning': 0,
    'environmental_approval': 1,
    'funded': 2,
    'under_construction': 3,
    'operational': 4,
}

# A sentence talking about the future can't evidence that something
# has *already* happened ("will be energised by 2027").
_FUTURE_RE = re.compile(
    r"\b(will|would|expected|expects|scheduled|planned|plans?|due|anticipated|aims?|"
    r"targets?|forecast|proposed|once|when|on track|on schedule|set to)\b",
    re.I,
)

_STATUS_PATTERNS = [
    ('operational', re.compile(
        r"\b(has been|was|were|now|successfully|recently)\s+(fully\s+)?"
        r"(energi[sz]ed|commissioned|completed|connected|switched on)\b"
        r"|\bis now (operational|in service|energi[sz]ed|complete)\b"
        r"|\bentered service\b",
        re.I)),
    ('under_construction', re.compile(
        r"\bconstruction\s+(has\s+)?(now\s+)?(started|commenced|begun|began|kicked off|is underway|"
        r"is under way|underway|is progressing|works? (have|has) started)\b"
        r"|\b(started|commenced|began|begun|kicked off)\s+construction\b"
        r"|\bunder construction\b"
        r"|\bconstruction (is|was) (well )?underway\b"
        r"|\bsod[- ]turning\b",
        re.I)),
    ('funded', re.compile(
        r"\$\s?[\d.,]+\s?(m|million|b|bn|billion)\b[^.]{0,60}?\b(committed|allocated|approved|invested|funding)\b"
        r"|\b(committed|allocated|approved)\b[^.]{0,30}\$\s?[\d.,]+\s?(m|million|b|bn|billion)\b"
        r"|\bfinal investment decision\b"
        r"|\b(fully|now)\s+funded\b"
        r"|\bfunding (has been )?(approved|committed|secured)\b"
        r"|\bcontracts? (has been |have been |was |were )?(awarded|signed)\b",
        re.I)),
    ('environmental_approval', re.compile(
        r"\b(environmental|EPA|EPBC)\s+(approvals?|assessments?|referrals?|clearances?)\b"
        r"[^.]{0,40}\b(granted|received|obtained|approved|completed|underway|submitted|lodged)\b"
        r"|\b(granted|received|obtained)\b[^.]{0,30}\benvironmental approvals?\b",
        re.I)),
]

_MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
_MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})

_WHEN = (
    r"(?P<qual>end of|end-|mid-?|mid |early |late |start of |beginning of |first half of |second half of )?\s*"
    r"(?:(?P<q>Q[1-4])\s+|(?P<month>January|February|March|April|May|June|July|August|September|"
    r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+)?"
    r"(?P<year>20\d\d)\b"
)
_COMPLETION_DATE_RE = re.compile(
    r"\b(complet\w*|deliver\w*|operational|in service|online|on-line|energi[sz]\w*|finish\w*|"
    r"commission\w*|in operation|ready)\b"
    r"[^.;]{0,60}?\b(by|in|from|during|before|around)\s+(?:the\s+)?" + _WHEN,
    re.I,
)

_MW_RE = re.compile(
    r"(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>GW|MW|gigawatts?|megawatts?)\b"
    r"(?=(?P<tail>[^.;]{0,50}))",            # lookahead, so the next figure can still match
    re.I,
)

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9$“\"'(])|\n+")
_DASHES_RE = re.compile(r"[‐-―−]")


@dataclass
class StageRef:
    """What the extractor needs to know about one CELStage."""
    stage_id: int
    program_id: int
    aliases: tuple[str, ...]          # lower-cased; matched on word boundaries


@dataclass
class ProgramRef:
    program_id: int
    aliases: tuple[str, ...]
    stage_ids: tuple[int, ...]


@dataclass
class Finding:
    program_id: int
    stage_id: int | None              # None = program named but stage ambiguous
    field_name: str
    value: object                     # str status, date, or float MW
    evidence: str


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def normalise(text: str) -> str:
    """Unify dash variants and whitespace so 'Clean Energy Link – North'
    and 'Clean Energy Link - North' match the same alias."""
    text = _DASHES_RE.sub('-', text or '')
    text = text.replace(' ', ' ').replace('’', "'")
    return re.sub(r'[ \t]+', ' ', text)


def split_sentences(text: str) -> list[str]:
    out = []
    for chunk in _SENTENCE_SPLIT_RE.split(normalise(text)):
        s = chunk.strip()
        if len(s) >= 12:
            out.append(s)
    return out


def program_aliases(name: str, code: str) -> tuple[str, ...]:
    """'Clean Energy Link - North' / 'CEL-N' → names a sentence may use:
    the full name, 'CEL-North', 'CEL North', 'CEL North' and the code."""
    aliases = set()
    name_n = normalise(name).strip().lower()
    if name_n:
        aliases.add(name_n)
        aliases.add(re.sub(r'\s*-\s*', ' ', name_n))           # 'clean energy link north'
        m = re.match(r'clean energy link\s*-?\s*(.+)$', name_n)
        if m:
            suffix = m.group(1).strip()
            aliases.update({f'cel-{suffix}', f'cel {suffix}', f'cel - {suffix}'})
    code_n = (code or '').strip().lower()
    if len(code_n) >= 4:                                       # 'CEL' alone is too generic
        aliases.add(code_n)
    return tuple(sorted(a for a in aliases if a))


def _mentions(sentence_lc: str, alias: str) -> bool:
    return re.search(r'(?<![a-z0-9])' + re.escape(alias) + r'(?![a-z0-9])', sentence_lc) is not None


def parse_when(qual: str | None, quarter: str | None, month: str | None, year: str) -> dt.date:
    """Turn 'end of 2027' / 'mid-2028' / 'March 2027' / 'Q3 2026' into the
    latest date the phrase allows (a deadline reading)."""
    y = int(year)
    qual = (qual or '').strip().lower().rstrip('-').strip()
    if quarter:
        qm = int(quarter[1]) * 3
        return dt.date(y, qm, calendar.monthrange(y, qm)[1])
    if month:
        key = month.lower().rstrip('.')
        mm = _MONTHS.get(key) or _MONTHS[key[:3]]                # 'Sept' → 'sep'
        return dt.date(y, mm, calendar.monthrange(y, mm)[1])
    if qual in ('mid', 'first half of'):
        return dt.date(y, 6, 30)
    if qual in ('early', 'start of', 'beginning of'):
        return dt.date(y, 3, 31)
    return dt.date(y, 12, 31)                                   # 'end of', 'late', bare year


# ---------------------------------------------------------------------------
# Sentence-level rules
# ---------------------------------------------------------------------------

def detect_status(sentence: str) -> str | None:
    """Highest funding status the sentence evidences as already true."""
    future = bool(_FUTURE_RE.search(sentence))
    for status, pattern in _STATUS_PATTERNS:
        if not pattern.search(sentence):
            continue
        # 'operational' must be past tense; the others survive future phrasing
        # in the same sentence ("construction has started and will finish by…").
        if status == 'operational' and future:
            continue
        return status
    return None


def detect_completion_date(sentence: str) -> dt.date | None:
    m = _COMPLETION_DATE_RE.search(sentence)
    if not m:
        return None
    return parse_when(m.group('qual'), m.group('q'), m.group('month'), m.group('year'))


def detect_capacity(sentence: str) -> dict[str, float]:
    """MW figures qualified as new vs existing generation.  Figures about
    transformers (MVA), jobs or money don't match the unit pattern."""
    out: dict[str, float] = {}
    for m in _MW_RE.finditer(sentence):
        mw = float(m.group('num').replace(',', ''))
        if m.group('unit').lower().startswith('g'):
            mw *= 1000.0
        tail = m.group('tail').lower()
        if re.match(r'^\s*(of\s+)?(existing|current)\b', tail):
            out.setdefault('capacity_unlocked_existing_mw', mw)
        elif re.match(r'^\s*(of\s+)?(new|additional|extra|more)\b', tail):
            out.setdefault('capacity_new_mw', mw)
        else:
            # "another 1 GW of new renewable" puts the qualifier before the number
            head = sentence[max(0, m.start() - 25):m.start()].lower()
            if re.search(r'\b(another|additional|new|extra)\s*$', head):
                out.setdefault('capacity_new_mw', mw)
    return out


# ---------------------------------------------------------------------------
# Document-level extraction
# ---------------------------------------------------------------------------

def _resolve_target(sentence_lc, programs, stages, default_program_id):
    """Return (program_id, stage_id|None) the sentence is about, or None."""
    stage_hits = [s for s in stages if any(_mentions(sentence_lc, a) for a in s.aliases)]
    if len(stage_hits) == 1:
        return stage_hits[0].program_id, stage_hits[0].stage_id

    prog_hits = [p for p in programs if any(_mentions(sentence_lc, a) for a in p.aliases)]
    if len(prog_hits) > 1:
        return None                                   # sentence compares programs — too risky
    program = prog_hits[0] if prog_hits else next(
        (p for p in programs if p.program_id == default_program_id), None)
    if program is None:
        return None
    if stage_hits:
        in_prog = [s for s in stage_hits if s.program_id == program.program_id]
        if len(in_prog) == 1:
            return program.program_id, in_prog[0].stage_id
    if len(program.stage_ids) == 1:
        return program.program_id, program.stage_ids[0]
    return program.program_id, None


def document_default_program(text: str, programs: list[ProgramRef], watch_program_id=None):
    """The program a document is 'about' when a sentence names none: the
    watch's own program if set, else the only program the document names."""
    if watch_program_id:
        return watch_program_id
    lc = normalise(text).lower()
    named = [p.program_id for p in programs if any(_mentions(lc, a) for a in p.aliases)]
    return named[0] if len(named) == 1 else None


def extract_findings(text: str, programs: list[ProgramRef], stages: list[StageRef],
                     default_program_id: int | None = None) -> list[Finding]:
    """All candidate field values in `text`, one Finding per (target, field)
    — the first sentence that evidences it wins, except funding_status where
    the highest status found wins."""
    found: dict[tuple, Finding] = {}
    for sentence in split_sentences(text):
        lc = sentence.lower()
        target = _resolve_target(lc, programs, stages, default_program_id)
        if target is None:
            continue
        program_id, stage_id = target
        evidence = sentence[:600]

        status = detect_status(sentence)
        if status:
            key = (program_id, stage_id, 'funding_status')
            prev = found.get(key)
            if prev is None or STATUS_RANK[status] > STATUS_RANK[prev.value]:
                found[key] = Finding(program_id, stage_id, 'funding_status', status, evidence)

        when = detect_completion_date(sentence)
        if when:
            if status == 'operational':
                field = 'actual_operational_date'
            else:
                field = 'expected_operational_date'
            found.setdefault((program_id, stage_id, field),
                             Finding(program_id, stage_id, field, when, evidence))

        for field, mw in detect_capacity(sentence).items():
            found.setdefault((program_id, stage_id, field),
                             Finding(program_id, stage_id, field, mw, evidence))
    return list(found.values())
