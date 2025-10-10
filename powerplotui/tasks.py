# powerplot/tasks.py
from celery import shared_task
from powerplotui.services.aemo_scada_fetcher import AEMOScadaFetcher
from powerplotui.services.dpv_fetcher import DPVDataFetcher
from powerplotui.services.load_analyzer import LoadAnalyzer
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@shared_task
def fetch_daily_scada():
    """Scheduled task to fetch daily SCADA data at 12:00 AWST"""
    try:
        fetcher = AEMOScadaFetcher()
        count = fetcher.fetch_latest_data()
        logger.info(f"Daily SCADA fetch completed: {count} records")
        return count
    except Exception as e:
        logger.error(f"Error in daily SCADA fetch: {e}")
        raise

@shared_task
def calculate_monthly_analysis():
    """Calculate monthly analysis for the previous month"""
    try:
        now = datetime.now()
        # Calculate for previous month
        if now.month == 1:
            year, month = now.year - 1, 12
        else:
            year, month = now.year, now.month - 1
        
        analyzer = LoadAnalyzer()
        summary = analyzer.calculate_monthly_summary(year, month)
        logger.info(f"Monthly analysis completed for {year}-{month:02d}")
        return str(summary.period_date) if summary else None
    except Exception as e:
        logger.error(f"Error in monthly analysis: {e}")
        raise

@shared_task
def fetch_monthly_dpv():
    """Fetch DPV data for the previous month"""
    try:
        fetcher = DPVDataFetcher()
        now = datetime.now()
        
        # Fetch for previous month
        if now.month == 1:
            year, month = now.year - 1, 12
        else:
            year, month = now.year, now.month - 1
        
        count = fetcher.fetch_dpv_data(year, month)
        logger.info(f"Monthly DPV fetch completed: {count} records for {year}-{month:02d}")
        return count
    except Exception as e:
        logger.error(f"Error in monthly DPV fetch: {e}")
        raise

@shared_task
def backfill_dpv_data(start_year, start_month, end_year, end_month):
    """
    Backfill DPV data for a date range
    Usage: backfill_dpv_data.delay(2023, 1, 2025, 9)
    """
    try:
        fetcher = DPVDataFetcher()
        start_date = datetime(start_year, start_month, 1)
        end_date = datetime(end_year, end_month, 1)
        
        total = fetcher.fetch_date_range(start_date, end_date)
        logger.info(f"DPV backfill completed: {total} total records")
        return total
    except Exception as e:
        logger.error(f"Error in DPV backfill: {e}")
        raise