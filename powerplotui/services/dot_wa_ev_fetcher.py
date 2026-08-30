# powerplotui/services/dot_wa_ev_fetcher.py
"""
FR-19 — retrieve the WA Department of Transport and Major Infrastructure
quarterly "electric vehicle licensing data" PDFs and store them, with
checksum and provenance, under settings.EV_ARCHIVE_DIR/dot_wa_actuals/.

Mirrors powerplotui.services.esoo_vintage_fetcher: DoT's CMS serves the
PDFs from GUID `getmedia/<uuid>/…` URLs that cannot be guessed for a
future quarter, so new reports are discovered by scraping the index page
rather than formatting a URL pattern. A default `requests` User-Agent is
fine here (no Cloudflare), but a browser-like one is sent anyway for
parity with the ESOO fetcher and resilience to future WAF changes.
"""
import hashlib
import logging
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

ARCHIVE_SUBDIR = 'dot_wa_actuals'

DEFAULT_INDEX_URL = (
    'https://www.transport.wa.gov.au/projects/'
    'western-australian-electric-vehicle-registrations.asp'
)

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/124.0 Safari/537.36'
    )
}
REQUEST_TIMEOUT = 60

# The quarterly report PDFs, but NOT PROJ_P_WA_EV_Notes_on_methodology.pdf
# or other non-summary attachments on the same page.
_PDF_HREF_RE = re.compile(
    r'href=["\']([^"\']*getmedia/[^"\']*analysis_summary[^"\']*\.pdf)["\']',
    re.IGNORECASE,
)


def _normalise_url(url: str) -> str:
    """Drop the explicit `:443` port and lower-case the host so the same
    report is not fetched twice under two spellings."""
    parts = urlsplit(url)
    netloc = parts.netloc.lower()
    if netloc.endswith(':443'):
        netloc = netloc[:-4]
    return urlunsplit((parts.scheme or 'https', netloc, parts.path, parts.query, ''))


def _checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def archive_dir() -> Path:
    return Path(settings.EV_ARCHIVE_DIR) / ARCHIVE_SUBDIR


def discover_report_urls(index_url: str = None, session: requests.Session = None) -> list:
    """Scrape the DoT EV licensing-data index page for quarterly-report
    PDF URLs. Returns a de-duplicated, normalised list (order preserved)."""
    index_url = index_url or getattr(settings, 'DOT_WA_EV_INDEX_URL', DEFAULT_INDEX_URL)
    getter = session or requests
    resp = getter.get(index_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()

    seen, urls = set(), []
    for href in _PDF_HREF_RE.findall(resp.text):
        url = _normalise_url(urljoin(index_url, href))
        if url not in seen:
            seen.add(url)
            urls.append(url)
    logger.info("Discovered %d DoT WA EV report PDF(s) at %s", len(urls), index_url)
    return urls


def fetch_report(url: str, force: bool = False, session: requests.Session = None) -> dict:
    """
    Download one report PDF into the archive (skipping the download if an
    identical file is already there, unless force=True).

    Returns {'url', 'filename', 'path' (absolute), 'local_file_path'
    (relative to EV_ARCHIVE_DIR), 'checksum', 'downloaded' (bool)}.
    """
    url = _normalise_url(url)
    filename = Path(urlsplit(url).path).name or 'dot_wa_ev_report.pdf'
    dest_dir = archive_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename

    if dest.exists() and not force:
        data = dest.read_bytes()
        logger.info("DoT WA EV report already archived: %s", filename)
        return _result(url, filename, dest, _checksum(data), downloaded=False)

    getter = session or requests
    logger.info("Fetching DoT WA EV report %s", url)
    resp = getter.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    content = resp.content

    if not content[:5] == b'%PDF-':
        raise ValueError(f"{url} did not return a PDF (got {content[:16]!r})")

    checksum = _checksum(content)
    if dest.exists() and _checksum(dest.read_bytes()) == checksum and not force:
        return _result(url, filename, dest, checksum, downloaded=False)

    dest.write_bytes(content)
    logger.info("Stored %s: %d bytes, sha256=%s…", filename, len(content), checksum[:12])
    return _result(url, filename, dest, checksum, downloaded=True)


def _result(url, filename, dest: Path, checksum, downloaded) -> dict:
    return {
        'url': url,
        'filename': filename,
        'path': dest,
        # .as_posix(): local_file_path is read back on whatever host serves
        # the site, which may not be the one that fetched it (see the same
        # note in esoo_vintage_fetcher).
        'local_file_path': dest.relative_to(Path(settings.EV_ARCHIVE_DIR)).as_posix(),
        'checksum': checksum,
        'downloaded': downloaded,
    }


def register_local_report(path) -> dict:
    """Register a report downloaded by hand and dropped into the archive
    dir (or anywhere) — copies it into the archive if it is not already
    there and returns the same dict shape as fetch_report."""
    src = Path(path)
    if not src.exists():
        raise FileNotFoundError(src)
    data = src.read_bytes()
    dest_dir = archive_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if src.resolve() != dest.resolve():
        dest.write_bytes(data)
    return _result(_normalise_url('https://local/' + src.name), src.name, dest,
                   _checksum(data), downloaded=False)
