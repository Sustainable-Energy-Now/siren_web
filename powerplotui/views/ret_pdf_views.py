"""
RET Dashboard PDF Generation and Publishing Views

This module handles:
- PDF generation from quarterly and annual reports
- Publishing reports (saving PDFs)
- Viewing published report history
- Downloading published reports
"""

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, FileResponse, Http404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string
from django.core.files.base import ContentFile
from django.contrib import messages
from django.urls import reverse
from datetime import datetime
import logging
import io
import base64

from siren_web.models import (
    MonthlyREPerformance,
    PublishedReport,
    ReportComment,
    NewCapacityCommissioned,
    TargetScenario
)

logger = logging.getLogger(__name__)

# Try to import WeasyPrint, log warning if not available
try:
    from weasyprint import HTML, CSS
    from weasyprint.fonts import FontConfiguration
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False
    logger.warning("WeasyPrint not installed. PDF generation will not work. Install with: pip install WeasyPrint")

# Try to import Plotly for chart generation
try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    logger.warning("Plotly not installed. Chart generation will not work. Install with: pip install plotly")


def generate_annual_generation_chart_image(annual_data):
    """Generate annual generation chart as base64-encoded PNG"""
    if not PLOTLY_AVAILABLE:
        return None

    from calendar import month_name

    months = [month_name[record.month] for record in annual_data]

    fig = go.Figure()

    # Add traces for each technology
    fig.add_trace(go.Bar(
        name='Wind',
        x=months,
        y=[record.wind_generation for record in annual_data],
        marker_color='#27ae60'
    ))

    fig.add_trace(go.Bar(
        name='Solar (Utility)',
        x=months,
        y=[record.solar_generation for record in annual_data],
        marker_color='#f39c12'
    ))

    fig.add_trace(go.Bar(
        name='Solar (Rooftop)',
        x=months,
        y=[record.dpv_generation for record in annual_data],
        marker_color='#f1c40f'
    ))

    fig.add_trace(go.Bar(
        name='Biomass',
        x=months,
        y=[record.biomass_generation for record in annual_data],
        marker_color='#16a085'
    ))

    fig.add_trace(go.Bar(
        name='Gas',
        x=months,
        y=[record.gas_generation for record in annual_data],
        marker_color='#95a5a6'
    ))

    fig.update_layout(
        title='Monthly Generation by Technology (Storage excluded)',
        xaxis_title='Month',
        yaxis_title='Generation (GWh)',
        barmode='stack',
        height=400,
        width=800,
        hovermode='x unified'
    )

    # Convert to PNG bytes and encode as base64
    try:
        img_bytes = fig.to_image(format="png", engine="kaleido")
        img_base64 = base64.b64encode(img_bytes).decode('utf-8')
        return f"data:image/png;base64,{img_base64}"
    except Exception as e:
        logger.warning(f"Failed to generate annual generation chart: {str(e)}")
        return None

def generate_annual_trends_chart_image(year):
    """Generate multi-year trends chart as base64-encoded PNG"""
    if not PLOTLY_AVAILABLE:
        return None

    from calendar import month_name

    # Get data for past 3 years
    start_year = year - 2
    historical = MonthlyREPerformance.objects.filter(
        year__gte=start_year,
        year__lte=year
    ).order_by('year', 'month')

    if not historical.exists():
        return None

    # Group by year
    years_data = {}
    for record in historical:
        if record.year not in years_data:
            years_data[record.year] = []
        years_data[record.year].append(record)

    fig = go.Figure()

    # Add line for each year
    for y in sorted(years_data.keys()):
        records = years_data[y]
        months = [record.month for record in records]
        re_pcts = [record.re_percentage_operational for record in records]

        fig.add_trace(go.Scatter(
            name=str(y),
            x=months,
            y=re_pcts,
            mode='lines+markers',
            line=dict(width=2),
            marker=dict(size=6)
        ))

    # Add target line if available
    try:
        target = TargetScenario.objects.filter(
            year=year,
            target_type__in=['major', 'interim']
        ).first()
        if target:
            fig.add_trace(go.Scatter(
                name=f'{year} Target',
            x=list(range(1, 13)),
                y=[target.target_re_percentage] * 12,
            mode='lines',
            line=dict(color='red', width=2, dash='dash'),
            showlegend=True
        ))
    except Exception:
        pass

    fig.update_layout(
        title='Multi-Year RE% Trends (Operational)',
        xaxis_title='Month',
        yaxis_title='Renewable Energy %',
        height=400,
        width=800,
        hovermode='x unified',
        xaxis=dict(
            tickmode='array',
            tickvals=list(range(1, 13)),
            ticktext=[month_name[i][:3] for i in range(1, 13)]
        )
    )

    # Convert to PNG bytes and encode as base64
    try:
        img_bytes = fig.to_image(format="png", engine="kaleido")
        img_base64 = base64.b64encode(img_bytes).decode('utf-8')
        return f"data:image/png;base64,{img_base64}"
    except Exception as e:
        logger.warning(f"Failed to generate annual trends chart: {str(e)}")
        return None

def generate_scenario_comparison_chart_image(scenarios):
    """Generate scenario comparison chart as base64-encoded PNG"""
    if not PLOTLY_AVAILABLE or not scenarios:
        return None

    scenario_names = [s.scenario_name for s in scenarios]
    re_percentages = [s.target_re_percentage for s in scenarios]

    # Color code based on meeting 75% target
    colors = ['#27ae60' if pct >= 75 else '#e74c3c' for pct in re_percentages]

    fig = go.Figure(data=[
        go.Bar(
            x=scenario_names,
            y=re_percentages,
            marker_color=colors,
            text=[f"{pct:.1f}%" for pct in re_percentages],
            textposition='auto',
        )
    ])

    # Add 75% target line
    fig.add_hline(y=75, line_dash="dash", line_color="red",
                  annotation_text="75% Target", annotation_position="right")

    fig.update_layout(
        title='2040 Scenario Comparison',
        xaxis_title='Scenario',
        yaxis_title='Projected RE%',
        height=400,
        width=800,
        yaxis=dict(range=[0, 100])
    )

    # Convert to PNG bytes and encode as base64
    try:
        img_bytes = fig.to_image(format="png", engine="kaleido")
        img_base64 = base64.b64encode(img_bytes).decode('utf-8')
        return f"data:image/png;base64,{img_base64}"
    except Exception as e:
        logger.warning(f"Failed to generate scenario comparison chart: {str(e)}")
        return None

def generate_pdf_from_html(html_content, base_url):
    """
    Generate PDF from HTML content using WeasyPrint.

    Args:
        html_content: HTML string to convert
        base_url: Base URL for resolving relative paths

    Returns:
        bytes: PDF file content
    """
    if not WEASYPRINT_AVAILABLE:
        raise ImportError("WeasyPrint is not installed")

    from django.conf import settings
    from django.contrib.staticfiles import finders
    import os
    from urllib.parse import urlparse, unquote

    # Font configuration for better rendering
    font_config = FontConfiguration()

    # Custom URL fetcher to handle static files
    def url_fetcher(url):
        """Custom fetcher to resolve Django static files"""
        parsed = urlparse(url)

        # Handle static files
        if parsed.path.startswith(settings.STATIC_URL):
            # Remove STATIC_URL prefix to get the relative path
            relative_path = parsed.path[len(settings.STATIC_URL):]
            relative_path = unquote(relative_path)

            # Try to find the static file
            if hasattr(settings, 'STATIC_ROOT') and settings.STATIC_ROOT:
                # In production, use STATIC_ROOT
                full_path = os.path.join(settings.STATIC_ROOT, relative_path)
            else:
                # In development, use finders
                full_path = finders.find(relative_path)

            if full_path and os.path.exists(full_path):
                with open(full_path, 'rb') as f:
                    return {'string': f.read(), 'mime_type': None}

        # Fall back to default fetcher for other URLs
        from weasyprint import default_url_fetcher
        return default_url_fetcher(url)

    # Additional CSS for PDF-specific styling
    pdf_css = CSS(string='''
        @page {
            size: A4;
            margin: 2cm;
        }

        /* Hide navigation and buttons in PDF */
        nav, .no-print, button, form {
            display: none !important;
        }

        /* Ensure proper page breaks */
        .section {
            page-break-inside: avoid;
        }

        /* Better table rendering */
        table {
            page-break-inside: auto;
        }

        tr {
            page-break-inside: avoid;
            page-break-after: auto;
        }

        /* Preserve colors in print */
        * {
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
        }
    ''', font_config=font_config)

    # Generate PDF with custom URL fetcher
    html = HTML(string=html_content, base_url=base_url, url_fetcher=url_fetcher)
    pdf_bytes = html.write_pdf(stylesheets=[pdf_css], font_config=font_config)

    return pdf_bytes

@require_POST
@login_required
def publish_quarterly_report(request, year, quarter):
    """
    Publish a quarterly report as PDF.
    Generates the PDF and saves it to the database.
    """
    try:
        year = int(year)
        quarter = int(quarter)

        # Get the report context (reuse the same logic as the view)
        from powerplotui.views.ret_dashboard_views import (
            quarterly_report,
            get_available_years,
            aggregate_wholesale_price_stats
        )

        # Get quarterly data
        start_month = (quarter - 1) * 3 + 1
        end_month = quarter * 3

        quarterly_data = MonthlyREPerformance.objects.filter(
            year=year,
            month__gte=start_month,
            month__lte=end_month
        ).order_by('month')

        if not quarterly_data.exists():
            messages.error(request, f"No data available for Q{quarter} {year}")
            return HttpResponse(status=404)

        # Build context for template
        quarterly_summary = MonthlyREPerformance.aggregate_summary(quarterly_data)
        quarterly_wholesale_stats = aggregate_wholesale_price_stats(quarterly_data)
        if quarterly_wholesale_stats and quarterly_summary:
            quarterly_summary.update(quarterly_wholesale_stats)

        # Previous quarter comparison
        prev_quarter_data = MonthlyREPerformance.objects.filter(
            year=year-1,
            month__gte=start_month,
            month__lte=end_month
        )
        prev_quarter_summary = MonthlyREPerformance.aggregate_summary(prev_quarter_data)

        # YTD summary
        try:
            end_month_record = MonthlyREPerformance.objects.get(year=year, month=end_month)
            ytd_summary = end_month_record.calculate_ytd_summary()
        except MonthlyREPerformance.DoesNotExist:
            ytd_data = MonthlyREPerformance.objects.filter(year=year, month__lte=end_month)
            ytd_summary = MonthlyREPerformance.aggregate_summary(ytd_data)

        ytd_data = MonthlyREPerformance.objects.filter(year=year, month__lte=end_month)
        ytd_wholesale_stats = aggregate_wholesale_price_stats(ytd_data)
        if ytd_wholesale_stats and ytd_summary:
            ytd_summary.update(ytd_wholesale_stats)

        # Previous YTD
        try:
            prev_end_month_record = MonthlyREPerformance.objects.get(year=year-1, month=end_month)
            prev_ytd_summary = prev_end_month_record.calculate_ytd_summary()
        except MonthlyREPerformance.DoesNotExist:
            prev_ytd_data = MonthlyREPerformance.objects.filter(year=year-1, month__lte=end_month)
            prev_ytd_summary = MonthlyREPerformance.aggregate_summary(prev_ytd_data)

        # Get target
        try:
            target = TargetScenario.objects.filter(
                year=year,
                target_type__in=['major', 'interim']
            ).first()
        except Exception:
            target = None

        # Get new capacity for this quarter
        from datetime import date
        quarter_start_date = date(year, start_month, 1)
        if end_month == 12:
            quarter_end_date = date(year, 12, 31)
        else:
            # Last day of end_month
            import calendar
            last_day = calendar.monthrange(year, end_month)[1]
            quarter_end_date = date(year, end_month, last_day)

        new_capacity = NewCapacityCommissioned.objects.filter(
            commissioned_date__gte=quarter_start_date,
            commissioned_date__lte=quarter_end_date,
            status='commissioned'
        ).select_related('facility').order_by('commissioned_date')

        from calendar import month_name
        context = {
            'year': year,
            'quarter': quarter,
            'quarter_start_month': month_name[start_month],
            'quarter_end_month': month_name[end_month],
            'quarterly_data': quarterly_data,
            'quarterly_summary': quarterly_summary,
            'prev_quarter_summary': prev_quarter_summary,
            'ytd_summary': ytd_summary,
            'prev_ytd_summary': prev_ytd_summary,
            'target': target,
            'new_capacity': new_capacity,
            'comments': ReportComment.get_comments_for_report('quarterly', year, quarter=quarter),
            'executive_summary': ReportComment.get_comments_for_report('quarterly', year, quarter=quarter).filter(category='executive_summary').first(),
            'report_type': 'quarterly',
        }

        # Render HTML version (with interactive Plotly charts - uses regular template)
        html_context = context.copy()
        html_context['is_published_version'] = True  # Flag to hide edit/comment features
        html_content_interactive = render_to_string('ret_dashboard/quarterly_report.html', html_context, request)

        # Render PDF version (with static chart images - uses PDF template)
        html_content_pdf = render_to_string('ret_dashboard/quarterly_report_pdf.html', context, request)

        # Generate PDF
        base_url = request.build_absolute_uri('/')
        pdf_bytes = generate_pdf_from_html(html_content_pdf, base_url)

        # Save to database (will replace existing if any)
        pdf_filename = f"SWIS_Quarterly_Report_Q{quarter}_{year}.pdf"
        html_filename = f"SWIS_Quarterly_Report_Q{quarter}_{year}.html"

        # Delete existing report if any (this also deletes the files from media folder)
        PublishedReport.objects.filter(
            report_type='quarterly',
            year=year,
            quarter=quarter
        ).delete()

        # Create new published report
        report = PublishedReport(
            report_type='quarterly',
            year=year,
            quarter=quarter,
            published_by=request.user
        )

        # Save both PDF and HTML files
        report.pdf_file.save(pdf_filename, ContentFile(pdf_bytes), save=False)
        report.html_file.save(html_filename, ContentFile(html_content_interactive.encode('utf-8')), save=True)

        messages.success(request, f"Successfully published Q{quarter} {year} Quarterly Report (PDF + HTML)")

        # Redirect back to the report page
        from django.shortcuts import redirect
        return redirect('quarterly_report', year=year, quarter=quarter)

    except Exception as e:
        logger.error(f"Error publishing quarterly report: {str(e)}")
        messages.error(request, f"Error publishing report: {str(e)}")
        return HttpResponse(status=500)

@require_POST
@login_required
def publish_annual_report(request, year):
    """
    Publish an annual review as PDF.
    Generates the PDF and saves it to the database.
    """
    try:
        year = int(year)

        # Get annual data
        annual_data = MonthlyREPerformance.objects.filter(year=year).order_by('month')

        if not annual_data.exists():
            messages.error(request, f"No data available for {year}")
            return HttpResponse(status=404)

        # Calculate annual totals (from annual_review view logic)
        total_generation = sum(r.total_generation for r in annual_data)
        total_renewable_operational = sum(r.renewable_gen_operational for r in annual_data)
        total_renewable = sum(r.total_renewable_generation for r in annual_data)
        total_emissions = sum(r.total_emissions_tonnes for r in annual_data)
        total_operational_demand = sum(r.operational_demand for r in annual_data)
        total_underlying_demand = sum(r.underlying_demand for r in annual_data)
        total_dpv = sum(r.dpv_generation for r in annual_data)
        total_wind = sum(r.wind_generation for r in annual_data)
        total_solar = sum(r.solar_generation for r in annual_data)
        total_biomass = sum(r.biomass_generation for r in annual_data)
        total_gas = sum(r.gas_generation for r in annual_data)
        total_coal = sum(r.coal_generation or 0 for r in annual_data)

        re_pct_operational = (total_renewable_operational / total_operational_demand * 100) if total_operational_demand > 0 else 0
        re_pct_underlying = (total_renewable / total_underlying_demand * 100) if total_underlying_demand > 0 else 0

        annual_summary = {
            'total_generation': total_generation,
            'renewable_generation': total_renewable,
            'total_emissions': total_emissions,
            'operational_demand': total_operational_demand,
            'underlying_demand': total_underlying_demand,
            're_percentage_operational': re_pct_operational,
            're_percentage_underlying': re_pct_underlying,
            'wind_generation': total_wind,
            'solar_generation': total_solar,
            'dpv_generation': total_dpv,
            'biomass_generation': total_biomass,
            'gas_generation': total_gas,
            'coal_generation': total_coal,
        }

        from powerplotui.views.ret_dashboard_views import aggregate_wholesale_price_stats
        annual_wholesale_stats = aggregate_wholesale_price_stats(annual_data)
        if annual_wholesale_stats:
            annual_summary.update(annual_wholesale_stats)

        # Get target
        try:
            target = TargetScenario.objects.filter(
                year=year,
                target_type__in=['major', 'interim']
            ).first()
        except Exception:
            target = None

        # Calculate target status
        target_status = None
        if target:
            diff = re_pct_underlying - target.target_percentage
            if diff >= 0:
                target_status = {
                    'status': 'ahead',
                    'message': f'✓ {diff:.1f} pp above target'
                }
            else:
                target_status = {
                    'status': 'behind',
                    'message': f'⚠ {abs(diff):.1f} pp below target'
                }

        # Get previous year data
        prev_annual_data = MonthlyREPerformance.objects.filter(year=year-1).order_by('month')
        prev_annual_summary = None
        yoy_changes = {}

        if prev_annual_data.exists():
            prev_total_renewable_operational = sum(r.renewable_gen_operational for r in prev_annual_data)
            prev_total_generation = sum(r.total_generation for r in prev_annual_data)
            prev_total_renewable = sum(r.total_renewable_generation for r in prev_annual_data)
            prev_total_emissions = sum(r.total_emissions_tonnes for r in prev_annual_data)
            prev_operational_demand = sum(r.operational_demand for r in prev_annual_data)
            prev_underlying_demand = sum(r.underlying_demand for r in prev_annual_data)

            prev_re_pct_operational = (prev_total_renewable_operational / prev_operational_demand * 100) if prev_operational_demand > 0 else 0
            prev_re_pct_underlying = (prev_total_renewable / prev_underlying_demand * 100) if prev_underlying_demand > 0 else 0

            prev_annual_summary = {
                'total_generation': prev_total_generation,
                'renewable_generation': prev_total_renewable,
                'total_emissions': prev_total_emissions,
                'operational_demand': prev_operational_demand,
                'underlying_demand': prev_underlying_demand,
                're_percentage_operational': prev_re_pct_operational,
                're_percentage_underlying': prev_re_pct_underlying,
            }

            yoy_changes = {
                'emissions': ((total_emissions - prev_total_emissions) / prev_total_emissions * 100) if prev_total_emissions > 0 else None,
                'underlying_demand': ((total_underlying_demand - prev_underlying_demand) / prev_underlying_demand * 100) if prev_underlying_demand > 0 else None,
                're_percentage': re_pct_underlying - prev_re_pct_underlying,
                'renewable_generation': ((total_renewable - prev_total_renewable) / prev_total_renewable * 100) if prev_total_renewable > 0 else None,
            }

        # New capacity
        new_capacity = NewCapacityCommissioned.objects.filter(
            report_year=year,
            status='commissioned'
        ).select_related('facility').order_by('commissioned_date')

        total_new_capacity = sum(nc.capacity_mw for nc in new_capacity) if new_capacity else 0

        # Scenarios
        scenarios = TargetScenario.objects.filter(is_active=True)

        from datetime import date
        today = date.today()
        current_year = today.year
        current_quarter = (today.month - 1) // 3 + 1

        if year < current_year:
            completed_quarters = [1, 2, 3, 4]
        elif year == current_year:
            completed_quarters = list(range(1, current_quarter))
        else:
            completed_quarters = []

        # Generate chart images for PDF
        annual_generation_chart_img = generate_annual_generation_chart_image(annual_data)
        annual_trends_chart_img = generate_annual_trends_chart_image(year)
        scenario_comparison_chart_img = generate_scenario_comparison_chart_image(scenarios)

        context = {
            'year': year,
            'annual_data': annual_data,
            'annual_summary': annual_summary,
            'prev_annual_summary': prev_annual_summary,
            'yoy_changes': yoy_changes,
            'target': target,
            'target_status': target_status,
            'new_capacity': new_capacity,
            'total_new_capacity': total_new_capacity,
            'scenarios': scenarios,
            'completed_quarters': completed_quarters,
            'comments': ReportComment.get_comments_for_report('annual', year),
            'executive_summary': ReportComment.get_comments_for_report('annual', year).filter(category='executive_summary').first(),
            'report_type': 'annual',
            # Chart images for PDF
            'annual_generation_chart_img': annual_generation_chart_img,
            'annual_trends_chart_img': annual_trends_chart_img,
            'scenario_comparison_chart_img': scenario_comparison_chart_img,
        }

        # Generate HTML version (with interactive Plotly charts)
        from powerplotui.views.ret_dashboard_views import (
            generate_annual_generation_chart,
            generate_annual_trends_chart,
            generate_scenario_comparison_chart
        )

        # Generate interactive charts for HTML version
        html_context = context.copy()
        html_context['is_published_version'] = True  # Flag to hide edit/comment features
        html_context['annual_generation_chart'] = generate_annual_generation_chart(annual_data)
        html_context['annual_trends_chart'] = generate_annual_trends_chart(year)
        html_context['scenario_chart'] = generate_scenario_comparison_chart(scenarios) if scenarios else ''

        # Render HTML version (using the regular template, not PDF template)
        html_content_interactive = render_to_string('ret_dashboard/annual_review.html', html_context, request)

        # Render PDF version (with static chart images)
        html_content_pdf = render_to_string('ret_dashboard/annual_review_pdf.html', context, request)

        # Generate PDF
        base_url = request.build_absolute_uri('/')
        pdf_bytes = generate_pdf_from_html(html_content_pdf, base_url)

        # Save to database
        pdf_filename = f"SWIS_Annual_Review_{year}.pdf"
        html_filename = f"SWIS_Annual_Review_{year}.html"

        # Delete existing report if any (this also deletes the files from media folder)
        PublishedReport.objects.filter(
            report_type='annual',
            year=year
        ).delete()

        # Create new published report
        report = PublishedReport(
            report_type='annual',
            year=year,
            published_by=request.user
        )

        # Save both PDF and HTML files
        report.pdf_file.save(pdf_filename, ContentFile(pdf_bytes), save=False)
        report.html_file.save(html_filename, ContentFile(html_content_interactive.encode('utf-8')), save=True)

        messages.success(request, f"Successfully published {year} Annual Review (PDF + HTML)")

        # Redirect back to the report page
        from django.shortcuts import redirect
        return redirect('annual_review', year=year)

    except Exception as e:
        logger.error(f"Error publishing annual report: {str(e)}")
        messages.error(request, f"Error publishing report: {str(e)}")
        return HttpResponse(status=500)

def published_reports_list(request):
    """
    Display list of all published reports with options to view/download.
    """
    # Get all published reports
    reports = PublishedReport.objects.all()

    # Separate by type
    quarterly_reports = reports.filter(report_type='quarterly')
    annual_reports = reports.filter(report_type='annual')

    context = {
        'quarterly_reports': quarterly_reports,
        'annual_reports': annual_reports,
    }

    return render(request, 'ret_dashboard/published_reports_list.html', context)

def download_published_report(request, report_id):
    """
    Download a published report PDF.
    """
    report = get_object_or_404(PublishedReport, pk=report_id)

    try:
        # Return the file
        response = FileResponse(report.pdf_file.open('rb'), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{report.get_filename()}"'
        return response
    except Exception as e:
        logger.error(f"Error downloading report {report_id}: {str(e)}")
        raise Http404("Report file not found")

def view_published_report(request, report_id):
    """
    View a published report PDF in browser.
    """
    report = get_object_or_404(PublishedReport, pk=report_id)

    try:
        # Return the file for inline viewing
        response = FileResponse(report.pdf_file.open('rb'), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{report.get_filename()}"'
        return response
    except Exception as e:
        logger.error(f"Error viewing report {report_id}: {str(e)}")
        raise Http404("Report file not found")

def view_published_html(request, report_id):
    """
    View a published report HTML in browser (with interactive charts).
    """
    report = get_object_or_404(PublishedReport, pk=report_id)

    if not report.html_file:
        raise Http404("HTML file not available for this report")

    try:
        # Return the file for inline viewing
        response = FileResponse(report.html_file.open('rb'), content_type='text/html')
        response['Content-Disposition'] = f'inline; filename="{report.get_html_filename()}"'
        return response
    except Exception as e:
        logger.error(f"Error viewing HTML report {report_id}: {str(e)}")
        raise Http404("HTML file not found")
