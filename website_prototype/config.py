import os
from pathlib import Path


def _load_dotenv():
    """Minimal .env loader (KEY=VALUE per line, '#' comments) -- values
    already set in the real environment take priority. Avoids a dependency
    on python-dotenv for something this small."""
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv()

DB_HOST = os.environ.get("TRIP_DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("TRIP_DB_PORT", "3306"))
DB_USER = os.environ.get("TRIP_DB_USER", "root")
DB_PASSWORD = os.environ.get("TRIP_DB_PASSWORD", "")
DB_NAME = os.environ.get("TRIP_DB_NAME", "trip_events")

HOST = os.environ.get("TRIP_HOST", "0.0.0.0")
PORT = int(os.environ.get("TRIP_PORT", "8000"))

SESSION_COOKIE_NAME = "trip_session"
SESSION_LIFETIME_HOURS = 24 * 7

# The driven_distance pricing formula is admin-configurable at runtime (see
# the Admin page and site_settings.distance_formula / formula.py) rather than
# a fixed constant here.

# ANU Sport ("ClubsAdmin") credentials for the caving club's Orders/Users
# exports, used by anusport_sync.py to poll membership_expiry for existing
# accounts. Membership expiry only appears in the Orders export's Items
# text (there's no usable expiry column on the Users export) -- Users is
# only used to map each order's UserId to an email address.
ANUSPORT_EMAIL = os.environ.get("ANUSPORT_EMAIL", "")
ANUSPORT_PASSWORD = os.environ.get("ANUSPORT_PASSWORD", "")
ANUSPORT_ORDERS_URL = os.environ.get(
    "ANUSPORT_ORDERS_URL", "https://anu-sport.com.au/ClubsAdmin/caving/Orders"
)
ANUSPORT_USERS_URL = os.environ.get(
    "ANUSPORT_USERS_URL", "https://anu-sport.com.au/ClubsAdmin/caving/Users"
)

# SMTP settings for the membership renewal/creation notification email (see
# anusport_sync.send_membership_email). Blank SMTP_HOST means that email is
# printed to stdout instead of actually being sent.
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_SENDER = os.environ.get("SMTP_SENDER", "no-reply@nucc.anumc.org.au")

# Who the sync-run report (spreadsheet) is emailed to, as an attachment, when
# SMTP_HOST is set. If either this or SMTP_HOST is blank, the report is
# written to the anusport_reports/ directory instead.
ANUSPORT_REPORT_EMAIL = os.environ.get("ANUSPORT_REPORT_EMAIL", "")
