import os

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
