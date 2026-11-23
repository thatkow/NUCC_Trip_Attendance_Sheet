"""Background thread that periodically runs anusport_sync.run_sync(), on the
interval configured in site_settings (anusport_sync_enabled/_minutes). Mirrors
ANUMC's AnusportSyncDaemon, but as a plain threading.Thread against this
project's PyMySQL connection rather than SQLAlchemy."""

import threading
import time
import traceback
from datetime import datetime, timedelta

import anusport_sync
import db

_POLL_SECONDS = 60  # how often the loop wakes to check whether it's time yet


class AnusportSyncDaemon:
    def __init__(self):
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def _run(self):
        while not self._stop_event.is_set():
            try:
                self._maybe_run_once()
            except Exception:
                traceback.print_exc()
            self._stop_event.wait(_POLL_SECONDS)

    def _maybe_run_once(self):
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT anusport_sync_enabled, anusport_sync_minutes, anusport_sync_next_at, "
                    "anusport_sync_send_emails FROM site_settings WHERE id = 1"
                )
                settings = cur.fetchone() or {}
            if not settings.get("anusport_sync_enabled"):
                return
            next_at = settings.get("anusport_sync_next_at")
            now = datetime.now()
            if next_at is not None and next_at > now:
                return

            try:
                result = anusport_sync.run_sync(conn, send_emails=bool(settings.get("anusport_sync_send_emails")))
                summary = f"{anusport_sync.summarize(result)} ({anusport_sync.deliver_report(result)})"
            except Exception as exc:
                summary = f"Sync failed: {exc}"

            minutes = settings.get("anusport_sync_minutes") or 1440
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE site_settings SET anusport_sync_next_at = %s, "
                    "anusport_sync_last_run_at = %s, anusport_sync_last_summary = %s WHERE id = 1",
                    (now + timedelta(minutes=minutes), now, summary),
                )
        finally:
            conn.close()


_daemon_instance = None


def start():
    global _daemon_instance
    if _daemon_instance is None:
        _daemon_instance = AnusportSyncDaemon()
    return _daemon_instance
