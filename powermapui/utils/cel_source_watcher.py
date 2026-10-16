"""
CEL document watcher: polls the published Clean Energy Link sources
(CELSourceWatch rows), stores a normalised-text snapshot whenever one
changes, runs rule-based extraction over the *new* text and raises
CELProposedUpdate rows for review.

Watches flagged discover_links=True also add CEL-looking links they carry
(news items, gazette notices, determination PDFs) as new watches — one hop
only and only on the allow-listed government / Western Power domains, so
this never turns into a crawler.

Driven by `manage.py check_cel_sources` (registered as a Data Pipelines
command, built for a weekly schedule).
"""
from __future__ import annotations

import hashlib
import io
import logging
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from django.db import transaction
from django.utils import timezone

from siren_web.models import CELSourceSnapshot, CELSourceWatch, CELStage

from .cel_document_extraction import document_default_program, extract_findings, program_aliases
from .cel_proposals import build_refs, create_proposal, is_improvement

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) siren-web CEL source watcher',
    'Accept': 'text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8',
}
REQUEST_TIMEOUT = 45
MAX_BYTES = 40 * 1024 * 1024
MAX_DISCOVERED_PER_PAGE = 25

# (url, label, program name hint or None, discover_links)
DEFAULT_SOURCES = [
    ('https://stateofenergy.wa.gov.au/Projects-and-Initiatives/clean-energy-link',
     'State of Energy — Clean Energy Link (SWIS)', None, True),
    ('https://www.wa.gov.au/organisation/energy-policy-wa/the-south-west-interconnected-system-transmission-plan-future-ready-transmission-network-was-main-electricity-system',
     'EPWA — SWIS Transmission Plan', None, True),
    ('https://www.wa.gov.au/organisation/energy-policy-wa/the-south-west-interconnected-system-transmission-plan-faq',
     'EPWA — SWIS Transmission Plan FAQ', None, False),
    ('https://www.wa.gov.au/organisation/department-of-the-premier-and-cabinet/clean-energy-link-north-and-regans-reinforcement',
     'DPC priority project — CEL North and Regans Reinforcement', 'Clean Energy Link - North', True),
    ('https://www.wa.gov.au/organisation/department-of-the-premier-and-cabinet/clean-energy-link-east-stage-1',
     'DPC priority project — CEL East Stage 1', 'Clean Energy Link - East', True),
    ('https://www.wa.gov.au/organisation/department-of-the-premier-and-cabinet/clean-energy-link-kwinana',
     'DPC priority project — CEL Kwinana', 'Clean Energy Link - Kwinana', True),
    ('https://letstalkpower.westernpower.com.au/clean-energy-link-north',
     "Western Power Let's Talk — CEL North", 'Clean Energy Link - North', True),
    ('https://letstalkpower.westernpower.com.au/clean-energy-link/clean-energy-link-east',
     "Western Power Let's Talk — CEL East", 'Clean Energy Link - East', True),
    ('https://www.wa.gov.au/system/files/2026-08/reasons-for-priority-project-determination-clean-energy-link-east-stage-one_0.pdf',
     'Reasons for priority project determination — CEL East Stage One', 'Clean Energy Link - East', False),
]

ALLOWED_DOMAINS = (
    'wa.gov.au', 'westernpower.com.au', 'legislation.wa.gov.au', 'aemo.com.au',
)
_DISCOVER_RE = re.compile(
    r'clean[\s_-]*energy[\s_-]*link|\bCEL\b|transmission[\s_-]*plan|priority[\s_-]*project|'
    r'regans|three[\s_-]*springs|eneabba|neerabup|designation[\s_-]*notice|gazette',
    re.I,
)
_SKIP_HREF_RE = re.compile(
    r'^(mailto:|tel:|javascript:)|sharer|intent/tweet|linkedin\.com/share|/login|/register|sign[_-]?up',
    re.I,
)
_TRACKING_PARAMS_RE = re.compile(r'^(_gl|utm_\w+|fbclid|gclid|_ga)$', re.I)
_DROP_TAGS = ('script', 'style', 'noscript', 'nav', 'header', 'footer', 'form', 'svg', 'button', 'template')
_BLOCK_TAGS = {'p', 'div', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'tr', 'td', 'th', 'br',
               'section', 'article', 'dd', 'dt', 'blockquote', 'figcaption', 'summary'}


# ---------------------------------------------------------------------------
# Fetching and text extraction
# ---------------------------------------------------------------------------

def clean_url(url: str) -> str:
    """Drop fragments and analytics parameters so the same document isn't
    watched twice under different tracking links."""
    parts = urlsplit(url.strip())
    # Filter the raw pieces rather than re-encoding, so bare flags such as
    # Lotus Notes' '?OpenElement' survive unchanged.
    query = '&'.join(piece for piece in parts.query.split('&')
                     if piece and not _TRACKING_PARAMS_RE.match(piece.split('=', 1)[0]))
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path, query, ''))


def _domain_allowed(url: str) -> bool:
    host = urlsplit(url).hostname or ''
    return any(host == d or host.endswith('.' + d) for d in ALLOWED_DOMAINS)


def html_to_text(html: str, base_url: str = ''):
    """(normalised text, list of (anchor text, absolute href)) for an HTML page.
    Text comes from the page's <main>/<article> where there is one, so
    navigation menus and language pickers don't register as changes."""
    import lxml.html

    doc = lxml.html.fromstring(html)
    if base_url:
        doc.make_links_absolute(base_url, resolve_base_href=True)
    links = [((a.text_content() or '').strip(), a.get('href') or '') for a in doc.iter('a')]

    for el in doc.xpath('|'.join(f'//{t}' for t in _DROP_TAGS)):
        el.drop_tree()
    roots = doc.xpath('//main') or doc.xpath('//*[@role="main"]') or doc.xpath('//article')
    root = roots[0] if roots else (doc.find('body') if doc.find('body') is not None else doc)

    for el in root.iter():
        if isinstance(el.tag, str) and el.tag.lower() in _BLOCK_TAGS:
            el.tail = '\n' + (el.tail or '')
            if el.tag.lower() != 'br':
                el.text = '\n' + (el.text or '')
    return _normalise_lines(root.text_content()), links


def pdf_to_text(data: bytes) -> str:
    import pdfplumber

    pages = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or '')
    return _normalise_lines('\n'.join(pages))


def _normalise_lines(text: str) -> str:
    lines = (re.sub(r'\s+', ' ', ln).strip() for ln in text.splitlines())
    return '\n'.join(ln for ln in lines if ln)


def fetch(url: str, session=None):
    """Download one source.  Returns (status_code, kind, text, links); links
    include the post-redirect page URL as ('', url) so discover() treats it
    as the page itself."""
    getter = session or requests
    resp = getter.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, stream=True)
    status = resp.status_code
    resp.raise_for_status()
    data = resp.raw.read(MAX_BYTES + 1, decode_content=True)
    if len(data) > MAX_BYTES:
        raise ValueError(f'larger than {MAX_BYTES // (1024 * 1024)} MB')
    ctype = (resp.headers.get('content-type') or '').lower()
    if 'pdf' in ctype or data[:5] == b'%PDF-':
        return status, 'pdf', pdf_to_text(data), []
    html = data.decode(resp.encoding or 'utf-8', errors='replace')
    text, links = html_to_text(html, resp.url)
    return status, 'html', text, [('', resp.url)] + links


def added_lines(old_text: str, new_text: str) -> str:
    """Lines present in new_text but not old_text (order kept).  Set-based
    rather than a positional diff so re-ordered page sections don't count."""
    seen = set(old_text.splitlines())
    return '\n'.join(ln for ln in new_text.splitlines() if ln not in seen)


def discover(links, source_url: str) -> list[tuple[str, str]]:
    """CEL-looking (url, label) links worth watching, from one page.  A
    leading ('', url) entry is the page's own post-redirect URL."""
    out, seen = [], {clean_url(source_url)}
    if links and links[0][0] == '':
        seen.add(clean_url(links[0][1]))
        links = links[1:]
    for text, href in links:
        if not href or _SKIP_HREF_RE.search(href):
            continue
        url = clean_url(urljoin(source_url, href))
        if url in seen or not url.startswith('http') or not _domain_allowed(url):
            continue
        if not (_DISCOVER_RE.search(text) or _DISCOVER_RE.search(urlsplit(url).path)):
            continue
        seen.add(url)
        out.append((url, re.sub(r'\s+', ' ', text).strip()[:200]))
        if len(out) >= MAX_DISCOVERED_PER_PAGE:
            break
    return out


# ---------------------------------------------------------------------------
# Watches
# ---------------------------------------------------------------------------

def default_watches() -> list[CELSourceWatch]:
    """DEFAULT_SOURCES as unsaved CELSourceWatch instances, each linked to
    its program where the hint names one."""
    from siren_web.models import CELProgram

    programs = list(CELProgram.objects.all())
    watches = []
    for url, label, program_hint, discover_links in DEFAULT_SOURCES:
        program = None
        if program_hint:
            hint = program_aliases(program_hint, '')
            program = next((p for p in programs
                            if set(hint) & set(program_aliases(p.name, p.code))), None)
        watches.append(CELSourceWatch(
            url=clean_url(url), label=label, origin='seed', cel_program=program,
            discover_links=discover_links,
            source_kind='pdf' if url.lower().endswith('.pdf') else 'html',
        ))
    return watches


def seed_default_sources() -> int:
    """Create any DEFAULT_SOURCES watch that doesn't exist yet.  Existing
    rows are left alone, so a watch a user deactivated stays deactivated."""
    existing = set(CELSourceWatch.objects.values_list('url', flat=True))
    new = [w for w in default_watches() if w.url not in existing]
    for w in new:
        w.save()
    return len(new)


def check_watch(watch: CELSourceWatch, session=None, refs=None, dry_run=False) -> dict:
    """Fetch one watch; on a content change store a snapshot and raise
    proposals.  Returns a summary dict for the command's output."""
    result = {'watch': watch, 'changed': False, 'initial': False, 'proposals': [],
              'discovered': [], 'error': ''}
    now = timezone.now()
    try:
        status, kind, text, links = fetch(watch.url, session=session)
    except (requests.RequestException, ValueError, OSError) as e:
        status = getattr(getattr(e, 'response', None), 'status_code', None)
        result['error'] = str(e)[:500]
        if not dry_run:
            watch.last_checked_at, watch.last_status_code, watch.last_error = now, status, result['error']
            watch.save(update_fields=['last_checked_at', 'last_status_code', 'last_error'])
        return result
    except Exception as e:                       # malformed PDF/HTML — record and carry on
        logger.exception('CEL source %s could not be parsed', watch.url)
        result['error'] = f'parse failed: {e}'[:500]
        if not dry_run:
            watch.last_checked_at, watch.last_error = now, result['error']
            watch.save(update_fields=['last_checked_at', 'last_error'])
        return result

    if watch.discover_links and links:
        known = set(CELSourceWatch.objects.values_list('url', flat=True))
        result['discovered'] = [(u, lbl) for u, lbl in discover(links, watch.url) if u not in known]

    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    result['changed'] = digest != watch.content_hash
    result['initial'] = not watch.content_hash

    if dry_run:
        if result['changed']:
            programs, stages = refs or build_refs()
            previous = watch.snapshots.first() if watch.pk else None     # --url watches aren't saved
            new_text = added_lines(previous.text, text) if previous else text
            default_pid = document_default_program(text, programs, watch.cel_program_id)
            findings = extract_findings(new_text, programs, stages, default_pid)
            # Same "is it actually a change?" filter create_proposal applies on a real run.
            stage_map = CELStage.objects.in_bulk([f.stage_id for f in findings if f.stage_id])
            result['proposals'] = [
                f for f in findings
                if f.stage_id is None or is_improvement(
                    f.field_name, getattr(stage_map[f.stage_id], f.field_name), f.value)
            ]
        return result

    with transaction.atomic():
        for url, label in result['discovered']:
            CELSourceWatch.objects.get_or_create(
                url=url,
                defaults={'label': label or url, 'origin': 'discovered',
                          'cel_program': watch.cel_program,
                          'source_kind': 'pdf' if urlsplit(url).path.lower().endswith('.pdf') else 'html'},
            )

        watch.last_checked_at, watch.last_status_code, watch.last_error = now, status, ''
        watch.source_kind = kind
        if result['changed']:
            previous = watch.snapshots.first()
            new_text = added_lines(previous.text, text) if previous else text
            snapshot = CELSourceSnapshot.objects.create(
                watch=watch, content_hash=digest, text=text, added_text=new_text,
                is_initial=previous is None,
            )
            watch.content_hash, watch.last_changed_at = digest, now
            result['proposals'] = _raise_proposals(watch, snapshot, text, new_text, refs)
        watch.save()
    return result


def _raise_proposals(watch, snapshot, full_text, new_text, refs):
    programs, stages = refs or build_refs()
    default_pid = document_default_program(full_text, programs, watch.cel_program_id)
    stage_map = CELStage.objects.in_bulk([s.stage_id for s in stages])
    created = []
    for f in extract_findings(new_text, programs, stages, default_pid):
        p = create_proposal(
            program_id=f.program_id, stage=stage_map.get(f.stage_id) if f.stage_id else None,
            field_name=f.field_name, value=f.value, evidence=f.evidence,
            source='document', source_url=watch.url, snapshot=snapshot,
        )
        if p:
            created.append(p)
    return created
