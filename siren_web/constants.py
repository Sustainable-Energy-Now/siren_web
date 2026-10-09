"""Project-wide constants."""

# The one SIREN preferences file every view uses. Not user-selectable and
# never carried in the session (siren_web/views/config_views.py can still
# edit other .ini files via ?filename=, but nothing else reads them).
DEFAULT_CONFIG_FILE = 'siren.ini'
