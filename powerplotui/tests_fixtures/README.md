# Test fixtures — DoT WA EV actuals

`test_dot_wa_ev_parser.py`'s `PdfParseIntegrationTests` runs against any
real DoT WA quarterly report PDF placed here as:

    PROJ_P_WA_EV_analysis_summary_*.pdf

The PDFs themselves are `.gitignore`d (Crown copyright, ~0.5 MB each). To
populate this directory:

    python manage.py refresh_ev_actuals
    cp siren_web/siren_files/ev_archive/dot_wa_actuals/PROJ_P_WA_EV_analysis_summary_*.pdf \
       powerplotui/tests_fixtures/

If the directory has no PDF, the integration test is skipped (the pure
helper tests still run).
