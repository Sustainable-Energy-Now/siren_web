# powerplotui/services/gencost_vintage_fetcher.py
"""
Auto-fetch for CSIRO GenCost report editions.

Unlike AEMO's ESOO downloads, GenCost's entire publication history lives
in one evergreen CSIRO Data Access Portal (DAP) collection
(csiro:44228 / internal id 76027) that CSIRO updates in place every year
-- there's no per-year URL to guess and no login/click-through. Confirmed
against the live API (2026-09-15):

  GET https://data.csiro.au/dap/ws/v2/collections/csiro:44228
    -> JSON metadata, including a "data" link.
  GET https://data.csiro.au/dap/ws/v2/collections/76027/data
    -> {"file": [{"id", "filename", "fileSize", "lastUpdated",
                  "link": {"href": ".../data/<fileId>"}, ...}, ...]}

Each file's stable link.href 302-redirects to a fresh presigned S3 URL on
every request (no auth needed) -- requests.get(href) with allow_redirects
follows it transparently. Like AEMO, the DAP site sits behind Cloudflare
and returns a non-200 to a bare urllib/requests default User-Agent, so a
browser-like one is required (same dodge as esoo_vintage_fetcher.py).

Filenames aren't perfectly uniform across editions -- the "Consult"/"Final"
stage tag isn't consistently placed relative to "ApxTables":
  GenCost2025-26FinalApxTables_20260714.xlsx                 (stage before "ApxTables")
  GenCost2025-26ConsultApxTables_20251216.xlsx                (stage before "ApxTables")
  GenCost2020-21ApxTables_Consultdraft_11-12-2020.xlsx        (stage AFTER "ApxTables")
  GenCost2020-21ApxTables_11-06-2021.xlsx                     (no stage tag at all -> final)
parse_filename() extracts the edition from the front of the name and
classifies the stage by searching the whole filename for "consult",
rather than anchoring to a fixed position, so it isn't tripped up by
either convention.
"""
import hashlib
import logging
import re
from pathlib import Path

import requests
from django.conf import settings
from django.utils import timezone

from siren_web.models import GencostVintage, SourceDocument

logger = logging.getLogger(__name__)

COLLECTION_METADATA_URL = "https://data.csiro.au/dap/ws/v2/collections/csiro:44228"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}
REQUEST_TIMEOUT = 60

_EDITION_RE = re.compile(r'^GenCost(?P<edition>\d{4}(?:-\d{2})?)', re.IGNORECASE)


def parse_filename(filename: str):
    """
    Extract (edition, doc_type) from a GenCost Appendix Tables filename.
    Returns (None, None) if the filename doesn't match the expected
    pattern (e.g. a future file type CSIRO adds to the collection).

    The "Consult"/"Final" stage tag's position relative to "ApxTables"
    isn't consistent across editions (see module docstring), so it's
    found by searching the whole filename rather than a fixed position.
    """
    m = _EDITION_RE.match(filename)
    if not m:
        return None, None
    edition = m.group('edition')
    doc_type = 'gencost_workbook_consult' if 'consult' in filename.lower() else 'gencost_workbook_final'
    return edition, doc_type


def list_dap_files() -> list[dict]:
    """
    Fetch the GenCost DAP collection's file listing. Returns the raw
    `file[]` array from the collection's `data` endpoint.
    """
    response = requests.get(COLLECTION_METADATA_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    data_url = response.json()['data']

    response = requests.get(data_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json().get('file', [])


def fetch_all_vintages(force=False) -> dict:
    """
    List every file in the GenCost DAP collection, download and register
    (as a GencostVintage + SourceDocument) any not already retrieved
    (matched by SourceDocument.dap_file_id), skip the rest. Idempotent.
    Returns {'fetched': [...], 'skipped': [...], 'unrecognised': [...]}.
    """
    archive_dir = Path(settings.GENCOST_ARCHIVE_DIR)
    results = {'fetched': [], 'skipped': [], 'unrecognised': []}

    for entry in list_dap_files():
        filename = entry['filename']
        edition, doc_type = parse_filename(filename)
        if edition is None:
            logger.warning(f"GenCost DAP file '{filename}' doesn't match the expected naming pattern; skipped")
            results['unrecognised'].append(filename)
            continue

        file_id = entry['id']
        already = SourceDocument.objects.filter(dap_file_id=file_id).first()
        if already is not None and not force:
            results['skipped'].append(filename)
            continue

        vintage, _ = GencostVintage.objects.get_or_create(
            edition=edition,
            defaults={'source_url': 'https://data.csiro.au/collection/csiro:44228'},
        )

        href = entry['link']['href']
        logger.info(f"Fetching GenCost {edition} ({doc_type}) from {href}")
        response = requests.get(href, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        content = response.content
        checksum = hashlib.sha256(content).hexdigest()

        edition_dir = archive_dir / edition
        edition_dir.mkdir(parents=True, exist_ok=True)
        file_path = edition_dir / filename
        file_path.write_bytes(content)

        doc, _ = SourceDocument.objects.update_or_create(
            gencost_vintage=vintage, doc_type=doc_type,
            defaults={
                'source_url': href,
                'checksum': checksum,
                # .as_posix() always yields forward slashes, regardless of
                # the OS this runs on -- see esoo_vintage_fetcher.py's
                # equivalent comment for why str(Path) would be wrong here.
                'local_file_path': file_path.relative_to(archive_dir).as_posix(),
                'dap_file_id': file_id,
                'retrieved_at': timezone.now(),
            },
        )
        logger.info(f"Stored GenCost {edition} {doc_type}: {len(content):,} bytes, sha256={checksum[:12]}...")
        results['fetched'].append(filename)

    return results
