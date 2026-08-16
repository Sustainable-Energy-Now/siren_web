# powerplotui/services/esoo_vintage_fetcher.py
"""
FR-F01 — retrieve WEM ESOO vintages and record them (with checksum and
provenance) in the acquisition manifest (EsooVintage).
"""
import hashlib
import logging
from pathlib import Path

import requests
from django.conf import settings
from django.utils import timezone

from siren_web.models import EsooVintage, EsooSourceDocument

logger = logging.getLogger(__name__)


class EsooVintageFetcher:
    """
    Downloads WEM ESOO annual editions and stores them under
    settings.ESOO_ARCHIVE_DIR/{year}/, checksummed and recorded on the
    corresponding EsooVintage row (main report) or EsooSourceDocument
    (Data Register, Demand Traces, and any other per-vintage document).

    URL_PATTERN / DOC_TYPE_URL_PATTERNS reflect AEMO's current per-year
    publication convention (confirmed against the 2022/2025/2026
    editions). AEMO occasionally changes file naming between years, so
    pass url= to override for a specific vintage.

    Note: AEMO's site is behind Cloudflare. A default `requests` User-Agent
    gets a 403; HEADERS below uses a browser-like one, which is sufficient
    for the report PDF and Data Register workbook. The Demand Traces
    workbook (.xlsb) has been observed returning a Cloudflare JS challenge
    page even with this header from some network paths — if fetch_source_document
    raises for doc_type='demand_traces', download it manually via a browser
    and place it at ESOO_ARCHIVE_DIR/{year}/, then register it with
    register_local_file() below.
    """

    URL_PATTERN = (
        "https://www.aemo.com.au/-/media/files/electricity/wem/"
        "planning_and_forecasting/esoo/{year}/{year}-wem-electricity-"
        "statement-of-opportunities.pdf"
    )
    DOC_TYPE_URL_PATTERNS = {
        'data_register': (
            "https://www.aemo.com.au/-/media/files/electricity/wem/"
            "planning_and_forecasting/esoo/{year}/{year}-wem-esoo-data-register.xlsx"
        ),
        'demand_traces': (
            "https://www.aemo.com.au/-/media/files/electricity/wem/"
            "planning_and_forecasting/esoo/{year}/{year}-wem-esoo-demand-traces.xlsb"
        ),
    }
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        )
    }
    REQUEST_TIMEOUT = 60

    def __init__(self):
        self.archive_dir = Path(settings.ESOO_ARCHIVE_DIR)

    def fetch_vintage(self, year, tier='modern_comparable', url=None, force=False):
        """
        Download one ESOO vintage document, checksum it, store it, and
        create/update its EsooVintage row. Returns the EsooVintage instance.
        Idempotent: skips re-downloading an already-retrieved vintage unless
        force=True.
        """
        vintage, _ = EsooVintage.objects.get_or_create(
            year=year, defaults={'tier': tier}
        )

        if vintage.ingestion_status in ('retrieved', 'validated') and not force:
            logger.info(
                f"ESOO {year} already retrieved (status={vintage.ingestion_status}); "
                f"skipping. Pass force=True to re-fetch."
            )
            return vintage

        source_url = url or self.URL_PATTERN.format(year=year)
        logger.info(f"Fetching WEM ESOO {year} from {source_url}")

        response = requests.get(source_url, headers=self.HEADERS, timeout=self.REQUEST_TIMEOUT)
        response.raise_for_status()
        content = response.content

        checksum = hashlib.sha256(content).hexdigest()

        year_dir = self.archive_dir / str(year)
        year_dir.mkdir(parents=True, exist_ok=True)
        filename = source_url.rstrip('/').split('/')[-1] or f"{year}-wem-esoo.pdf"
        file_path = year_dir / filename
        file_path.write_bytes(content)

        vintage.tier = tier
        vintage.source_url = source_url
        vintage.checksum = checksum
        # .as_posix() always yields forward slashes, regardless of the OS
        # this runs on — local_file_path is read back on whatever host is
        # serving the site, which may not be the one that fetched it, and
        # a raw str(Path) would embed OS-native (e.g. Windows backslash)
        # separators that break path joins on a different OS at read time.
        vintage.local_file_path = file_path.relative_to(self.archive_dir).as_posix()
        vintage.ingestion_status = 'retrieved'
        vintage.save()

        logger.info(
            f"Stored ESOO {year}: {len(content):,} bytes, sha256={checksum[:12]}..."
        )
        return vintage

    def fetch_vintages(self, years, tier='modern_comparable', force=False):
        """Fetch multiple vintages, continuing past individual failures."""
        results = {'succeeded': [], 'failed': []}
        for year in years:
            try:
                self.fetch_vintage(year, tier=tier, force=force)
                results['succeeded'].append(year)
            except Exception as e:
                logger.error(f"Failed to fetch ESOO {year}: {e}")
                results['failed'].append((year, str(e)))
        return results

    def fetch_source_document(self, year, doc_type, url=None, force=False):
        """
        Download one additional per-vintage document (data_register,
        demand_traces, ...) and record it on EsooSourceDocument. Raises
        requests.HTTPError (e.g. 403 from a Cloudflare challenge) rather
        than swallowing it — see class docstring for the demand_traces
        caveat and the register_local_file() manual fallback.
        """
        try:
            vintage = EsooVintage.objects.get(year=year)
        except EsooVintage.DoesNotExist:
            raise ValueError(f"No EsooVintage for {year}; fetch the main report first.")

        doc, _ = EsooSourceDocument.objects.get_or_create(vintage=vintage, doc_type=doc_type)
        if doc.local_file_path and not force:
            logger.info(f"ESOO {year} {doc_type} already retrieved; skipping. Pass force=True to re-fetch.")
            return doc

        source_url = url or self.DOC_TYPE_URL_PATTERNS.get(doc_type, '').format(year=year)
        if not source_url:
            raise ValueError(f"No known URL pattern for doc_type={doc_type!r}; pass url= explicitly.")

        logger.info(f"Fetching ESOO {year} {doc_type} from {source_url}")
        response = requests.get(source_url, headers=self.HEADERS, timeout=self.REQUEST_TIMEOUT)
        response.raise_for_status()
        content = response.content

        checksum = hashlib.sha256(content).hexdigest()
        year_dir = self.archive_dir / str(year)
        year_dir.mkdir(parents=True, exist_ok=True)
        filename = source_url.rstrip('/').split('/')[-1] or f"{year}-{doc_type}"
        file_path = year_dir / filename
        file_path.write_bytes(content)

        doc.source_url = source_url
        doc.checksum = checksum
        doc.local_file_path = file_path.relative_to(self.archive_dir).as_posix()  # see fetch_vintage() comment
        doc.retrieved_at = timezone.now()
        doc.save()

        logger.info(f"Stored ESOO {year} {doc_type}: {len(content):,} bytes, sha256={checksum[:12]}...")
        return doc

    def register_local_file(self, year, doc_type, file_path):
        """
        Register a document that was downloaded manually (e.g. via a
        browser, for a file blocked by a Cloudflare challenge from this
        environment) and copied into ESOO_ARCHIVE_DIR/{year}/.
        """
        vintage = EsooVintage.objects.get(year=year)
        file_path = Path(file_path)
        content = file_path.read_bytes()
        checksum = hashlib.sha256(content).hexdigest()

        doc, _ = EsooSourceDocument.objects.get_or_create(vintage=vintage, doc_type=doc_type)
        doc.checksum = checksum
        doc.local_file_path = file_path.relative_to(self.archive_dir).as_posix()  # see fetch_vintage() comment
        doc.retrieved_at = timezone.now()
        doc.save()
        logger.info(f"Registered manually-fetched ESOO {year} {doc_type}: {file_path}")
        return doc
