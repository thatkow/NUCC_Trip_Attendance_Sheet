"""Syncs membership_expiry from ANU Sport's "ClubsAdmin" Orders/Users
exports for the caving club into this site's own users table.

Membership expiry doesn't appear as its own column on the Users export (its
"Est. Expiry" column reflects whatever ANU Sport product was last bought --
including the unrelated general "ANU Sport Membership", not specifically
caving club membership) -- so, like ANUMC's own sync, the real expiry has to
be parsed out of the Orders export's free-text Items column, picking out
just the line item whose name contains "Caving". The Users export is only
used to map an order's numeric UserId to an email address.

A caving-club order with no matching local account gets a new account
created for them here (password_hash left NULL, same as a host's "+ add
guest" row -- see schema.sql) -- mirroring ANUMC's own sync, which creates a
Keycloak account for unmatched orders. Registering with that same email
later claims the account (see app.py's handle_register_submit).
"""

import io
import re
import smtplib
import tempfile
import time as time_module
from datetime import date, datetime, timedelta
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import openpyxl
import pymysql

import config

REPORTS_DIR = Path(__file__).resolve().parent / "anusport_reports"

BASE_DIR = Path(__file__).resolve().parent
STORAGE_STATE_PATH = BASE_DIR / "anusport_storage_state.json"

LOGIN_URL = "https://anu-sport.com.au/Account/CommunityLogin"
JOB_DETAILS_RE = re.compile(r"/Account/Jobs/Details/(\d+)", re.IGNORECASE)
JOB_POLL_TIMEOUT_SECONDS = 900
JOB_POLL_INTERVAL_SECONDS = 10.0

_STUDENT_ID_RE = re.compile(r"^u(\d+)", re.IGNORECASE)
_CLUB_KEYWORD = "caving"
_ITEM_EXPIRY_RE = re.compile(
    r"([^|]*?)\s*x\s*\d+\s*Membership Expiry:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})[^|]*"
)
_RENEWAL_THRESHOLD_DAYS = 183  # ~6 months -- a "renewal" email vs. a minor adjustment
_LOOKBACK_DAYS = 365  # only orders from the last year are worth scanning


def _expected_anusportid(raw_student_id, user_id) -> Optional[str]:
    if raw_student_id:
        m = _STUDENT_ID_RE.match(str(raw_student_id).strip())
        if m:
            return f"u{m.group(1)}".lower()
    return f"a{user_id}" if user_id is not None else None


def _parse_order_date(raw) -> Optional[date]:
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    raw = str(raw or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %I:%M:%S %p", "%Y-%m-%d %I:%M %p", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %I:%M %p", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _parse_caving_expiry(items_text) -> Optional[date]:
    """The latest "Membership Expiry" date among this order's line items
    whose name mentions "Caving" -- ignores other items on the same order
    (e.g. a bundled general "ANU Sport Membership")."""
    best = None
    for label, date_str in _ITEM_EXPIRY_RE.findall(str(items_text or "")):
        if _CLUB_KEYWORD not in label.lower():
            continue
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        if best is None or d > best:
            best = d
    return best


def _read_sheet_rows(file_bytes: bytes) -> Tuple[List[str], List[Tuple]]:
    workbook = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
    worksheet = workbook.active
    rows_iter = worksheet.iter_rows(values_only=True)
    header = [str(h).strip() if h is not None else "" for h in next(rows_iter)]
    return header, list(rows_iter)


# -- export fetch (Playwright) -----------------------------------------------

def _export_log_in(page, email, password) -> None:
    page.goto(LOGIN_URL, timeout=60000, wait_until="domcontentloaded")
    page.fill("#Email", email)
    if page.locator("#next-btn").is_visible():
        page.click("#next-btn")
        page.wait_for_selector("#Password", state="visible", timeout=10000)
    page.fill("#Password", password)
    page.click("#login-btn")
    try:
        page.wait_for_url(
            lambda url: "/account/login" not in url.lower() and "/account/communitylogin" not in url.lower(),
            timeout=20000,
        )
    except Exception as exc:
        raise RuntimeError(f"ANU Sport login failed (still on {page.url}): {exc}")


def _export_ensure_logged_in(context, page, email, password) -> None:
    if STORAGE_STATE_PATH.exists():
        page.goto(config.ANUSPORT_ORDERS_URL, timeout=60000, wait_until="domcontentloaded")
        if "/account/" not in page.url.lower():
            return
    _export_log_in(page, email, password)
    context.storage_state(path=str(STORAGE_STATE_PATH))


# The Users page's "Membership Status" filter defaults to only "Current"
# checked -- a club member can be missing from the export entirely if their
# status isn't Current (observed: an Expired/Inactive member silently
# dropped). These exact ids/selector were taken from a saved debug snapshot
# of the real page (anusport_debug/, see _save_debug_snapshot) -- the
# checkboxes are a standard Bootstrap accordion + checkbox-list, not
# anything dynamic, so hardcoding them is more reliable than guessing at
# label-text-based locators (which silently matched nothing useful before).
_ADVANCED_SEARCH_TOGGLE_SELECTOR = 'button[data-bs-target="#advancedSearchFilter"]'
_MEMBERSHIP_STATUS_CHECKBOX_IDS = {
    "Incomplete Application": "PostedItems_Items1",
    "Pending": "PostedItems_Items2",
    "Current": "PostedItems_Items3",
    "Expired": "PostedItems_Items4",
    "Inactive": "PostedItems_Items5",
}
_ADV_SEARCH_SUBMIT_SELECTOR = "#adv_search_btn"


def _apply_users_status_filter(page) -> None:
    """Expands the "Advanced Search" accordion (Bootstrap collapse -- its
    content exists in the DOM but isn't interactable while collapsed, which
    is why earlier attempts silently failed to check most of the boxes),
    checks every Membership Status checkbox, then clicks the Advanced
    Search's own Search button (#adv_search_btn, not the page's main quick
    search) so the filter is actually applied before the export is
    triggered -- checking the boxes alone doesn't filter anything until
    submitted, same as the manual UI."""
    toggle = page.locator(_ADVANCED_SEARCH_TOGGLE_SELECTOR)
    if toggle.count() and toggle.first.get_attribute("aria-expanded") != "true":
        toggle.first.click()
        page.wait_for_timeout(500)

    checked = 0
    for label, checkbox_id in _MEMBERSHIP_STATUS_CHECKBOX_IDS.items():
        box = page.locator(f"#{checkbox_id}")
        if box.count() == 0:
            print(f"[anusport_sync] Membership Status checkbox #{checkbox_id} ({label!r}) not found on the page.")
            continue
        try:
            if not box.is_checked():
                box.check()
            checked += 1
        except Exception as exc:
            print(f"[anusport_sync] Couldn't check {label!r} (#{checkbox_id}): {exc}")

    if checked == 0:
        raise RuntimeError(
            "Could not check any 'Membership Status' checkboxes on the Users export page -- "
            "ANU Sport's markup may have changed (see anusport_debug/ for the last snapshot). "
            "Aborting rather than exporting with whatever filter was already set."
        )

    search_btn = page.locator(_ADV_SEARCH_SUBMIT_SELECTOR)
    if search_btn.count() == 0:
        print(f"[anusport_sync] Couldn't find the Advanced Search submit button ({_ADV_SEARCH_SUBMIT_SELECTOR}) -- "
              "the filter may not actually have been applied.")
        return

    search_btn.first.click()
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass
    page.wait_for_timeout(5000)


def _export_trigger(page, admin_url: str, kind: str) -> Tuple[str, Any]:
    page.goto(admin_url, timeout=60000, wait_until="domcontentloaded")
    if kind == "users":
        _apply_users_status_filter(page)
    export_btn = page.locator("#export-button")
    if export_btn.count() == 0:
        raise RuntimeError(f"No #export-button found on {admin_url} -- ANU Sport's markup may have changed.")

    page.once("dialog", lambda d: d.accept())
    with page.context.expect_page(timeout=20000) as new_page_info:
        export_btn.click()
    job_page = new_page_info.value
    job_page.wait_for_load_state()

    m = JOB_DETAILS_RE.search(job_page.url)
    if not m:
        raise RuntimeError(f"Expected a Jobs/Details/<id> tab, got {job_page.url} instead.")
    return m.group(1), job_page


def _export_wait_and_download(job_page, job_id, dest_dir: Path) -> Path:
    deadline = time_module.monotonic() + JOB_POLL_TIMEOUT_SECONDS
    download_link = job_page.get_by_role("link", name=re.compile("download", re.IGNORECASE))

    while True:
        body = job_page.inner_text("body")
        lines = [l.strip() for l in body.splitlines() if l.strip()]
        status = None
        if "Status" in lines:
            idx = lines.index("Status")
            status = lines[idx + 1] if idx + 1 < len(lines) else None

        if status and status.lower() == "succeeded":
            break
        if status and status.lower() in ("failed", "cancelled", "canceled"):
            raise RuntimeError(f"ANU Sport export job #{job_id} ended with status {status!r}.")
        if time_module.monotonic() >= deadline:
            raise RuntimeError(f"Timed out waiting for ANU Sport export job #{job_id} to succeed (last status={status!r}).")
        time_module.sleep(JOB_POLL_INTERVAL_SECONDS)
        job_url = f"https://anu-sport.com.au/Account/Jobs/Details/{job_id}"
        for attempt in range(3):
            try:
                job_page.goto(job_url, timeout=60000, wait_until="domcontentloaded")
                break
            except Exception:
                if attempt == 2:
                    raise
                time_module.sleep(5.0)
        download_link = job_page.get_by_role("link", name=re.compile("download", re.IGNORECASE))

    if download_link.count() == 0:
        raise RuntimeError(f"ANU Sport export job #{job_id} succeeded but no Download link was found.")

    dest_dir.mkdir(parents=True, exist_ok=True)
    with job_page.expect_download(timeout=30000) as download_info:
        download_link.first.click()
    download = download_info.value
    dest_path = dest_dir / download.suggested_filename
    download.save_as(str(dest_path))
    return dest_path


def _export_one(page, kind: str, dest_dir: Path) -> Path:
    # Always queue a fresh export rather than reusing one already run today
    # (an earlier version reused same-day jobs to avoid "queuing a
    # duplicate" -- but that meant a stale job triggered before a filter
    # fix, or with different Membership Status checkboxes, silently kept
    # getting reused instead of picking up the fix. Correctness here matters
    # more than avoiding an extra ANU Sport export job.)
    admin_url = config.ANUSPORT_ORDERS_URL if kind == "orders" else config.ANUSPORT_USERS_URL
    job_id, job_page = _export_trigger(page, admin_url, kind)
    return _export_wait_and_download(job_page, job_id, dest_dir)


def fetch_orders_and_users_exports() -> Tuple[bytes, bytes]:
    """Logs into ANU Sport and downloads the caving club's Orders and Users
    exports via Playwright (synchronous API -- run this on a worker thread,
    never on an asyncio loop thread). Returns (orders_bytes, users_bytes)."""
    from playwright.sync_api import sync_playwright

    email, password = config.ANUSPORT_EMAIL, config.ANUSPORT_PASSWORD
    if not email or not password:
        raise RuntimeError("ANUSPORT_EMAIL / ANUSPORT_PASSWORD are not set.")

    with tempfile.TemporaryDirectory(prefix="anusport_export_") as tmp_dir:
        dest_dir = Path(tmp_dir)
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True, channel="chrome")
            except Exception:
                browser = p.chromium.launch(headless=True)
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()
            _export_ensure_logged_in(context, page, email, password)

            orders_path = _export_one(page, "orders", dest_dir)
            users_path = _export_one(page, "users", dest_dir)

            browser.close()

        return orders_path.read_bytes(), users_path.read_bytes()


# -- matching + apply ---------------------------------------------------------

def _read_club_orders(orders_bytes: bytes, users_bytes: bytes) -> List[Dict[str, Any]]:
    """Returns one dict per qualifying ("Caving"-item, within the lookback
    window) order row: email (resolved via the Users sheet's UserId ->
    Email mapping), names, candidate anusportid, and the parsed expiry."""
    order_header, order_rows = _read_sheet_rows(orders_bytes)
    order_idx = {name: i for i, name in enumerate(order_header)}
    required = ["Order ID", "First name", "Last name", "Order Date", "Items", "UserId"]
    missing = [c for c in required if c not in order_idx]
    if missing:
        raise ValueError(f"Orders export is missing expected column(s): {', '.join(missing)}")
    student_id_col = order_idx.get("Student ID")

    user_header, user_rows = _read_sheet_rows(users_bytes)
    user_idx = {name: i for i, name in enumerate(user_header)}
    email_col, id_col = user_idx.get("Email"), user_idx.get("#")
    email_by_user_id: Dict[int, str] = {}
    if email_col is not None and id_col is not None:
        for row in user_rows:
            uid, email = row[id_col], row[email_col]
            if uid is None or not email:
                continue
            try:
                email_by_user_id[int(uid)] = str(email).strip()
            except (TypeError, ValueError):
                continue

    cutoff = date.today() - timedelta(days=_LOOKBACK_DAYS)
    out = []
    for row in order_rows:
        items_text = row[order_idx["Items"]] or ""
        if _CLUB_KEYWORD not in str(items_text).lower():
            continue
        order_date = _parse_order_date(row[order_idx["Order Date"]])
        if order_date is None or order_date < cutoff:
            continue
        new_expiry = _parse_caving_expiry(items_text)
        if new_expiry is None:
            continue

        uid = row[order_idx["UserId"]]
        try:
            email = email_by_user_id.get(int(uid)) if uid is not None else None
        except (TypeError, ValueError):
            email = None

        out.append({
            "first_name": row[order_idx["First name"]],
            "last_name": row[order_idx["Last name"]],
            "email": email,
            "student_id": row[student_id_col] if student_id_col is not None else None,
            "user_id": uid,
            "new_expiry": new_expiry,
            "order_date": order_date,
        })
    return out


def run_sync(conn) -> Dict[str, Any]:
    """Fetches the Orders/Users exports, matches each qualifying caving-club
    order to an existing local account (anusportid -> email -> exact
    first+last name), updates membership_expiry to the latest matched
    order's expiry if it changed, and creates a new (passwordless, claimable
    via /register) account for anyone with no match but a known email.
    Returns a summary dict."""
    orders_bytes, users_bytes = fetch_orders_and_users_exports()
    club_orders = _read_club_orders(orders_bytes, users_bytes)

    with conn.cursor() as cur:
        cur.execute("SELECT id, name, email, membership_expiry, anusportid FROM users")
        db_users = list(cur.fetchall())

    by_anusportid = {u["anusportid"]: u for u in db_users if u["anusportid"]}
    by_email = {u["email"].strip().lower(): u for u in db_users if u["email"]}
    by_name: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for u in db_users:
        parts = (u["name"] or "").strip().lower().split(None, 1)
        if len(parts) == 2:
            by_name.setdefault((parts[0], parts[1]), []).append(u)

    # Aggregate every qualifying order per matched local account, keeping
    # the single best (latest) expiry seen across all of them. Orders with
    # no match are grouped by their expected anusportid into one
    # new-account candidate per real person.
    best_expiry_by_user_id: Dict[int, date] = {}
    anusportid_by_user_id: Dict[int, str] = {}
    new_candidates: Dict[str, Dict[str, Any]] = {}
    no_email, ambiguous = [], []

    for order in club_orders:
        expected_id = _expected_anusportid(order["student_id"], order["user_id"])
        db_user = by_anusportid.get(expected_id) if expected_id else None
        if db_user is None and order["email"]:
            db_user = by_email.get(order["email"].strip().lower())
        if db_user is None:
            first = str(order["first_name"] or "").strip().lower()
            last = str(order["last_name"] or "").strip().lower()
            candidates = by_name.get((first, last), []) if first and last else []
            if len(candidates) == 1:
                db_user = candidates[0]
            elif len(candidates) > 1:
                ambiguous.append({"name": f"{order['first_name']} {order['last_name']}", "email": order["email"]})
                continue

        if db_user is None:
            if not expected_id:
                continue
            candidate = new_candidates.get(expected_id)
            if candidate is None or order["order_date"] > candidate["order_date"]:
                new_candidates[expected_id] = {
                    "anusportid": expected_id,
                    "name": f"{order['first_name'] or ''} {order['last_name'] or ''}".strip(),
                    "email": order["email"],
                    "order_date": order["order_date"],
                    "new_expiry": order["new_expiry"],
                }
            else:
                candidate["new_expiry"] = max(candidate["new_expiry"], order["new_expiry"])
            continue

        uid = db_user["id"]
        if expected_id:
            anusportid_by_user_id[uid] = expected_id
        if uid not in best_expiry_by_user_id or order["new_expiry"] > best_expiry_by_user_id[uid]:
            best_expiry_by_user_id[uid] = order["new_expiry"]

    db_user_by_id = {u["id"]: u for u in db_users}
    updated, unchanged = [], []

    for uid, new_expiry in best_expiry_by_user_id.items():
        db_user = db_user_by_id[uid]
        current_expiry = db_user["membership_expiry"]
        expected_id = anusportid_by_user_id.get(uid)

        with conn.cursor() as cur:
            if expected_id and db_user["anusportid"] != expected_id:
                cur.execute("UPDATE users SET anusportid = %s WHERE id = %s", (expected_id, uid))

        if new_expiry == current_expiry:
            unchanged.append({"name": db_user["name"], "email": db_user["email"]})
            continue

        with conn.cursor() as cur:
            cur.execute("UPDATE users SET membership_expiry = %s WHERE id = %s", (new_expiry, uid))

        is_new_member = current_expiry is None
        is_renewal = is_new_member or (new_expiry - current_expiry).days > _RENEWAL_THRESHOLD_DAYS
        email_sent = False
        if is_renewal and db_user["email"]:
            email_sent = send_membership_email(db_user["email"], db_user["name"], new_expiry, is_new_member)

        updated.append({
            "name": db_user["name"], "email": db_user["email"],
            "previous_expiry": current_expiry, "new_expiry": new_expiry,
            "is_new_member": is_new_member, "email_sent": email_sent,
        })

    created, no_email = [], []
    for candidate in new_candidates.values():
        if not candidate["email"]:
            no_email.append({"name": candidate["name"], "email": None, "anusportid": candidate["anusportid"]})
            continue

        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (email, name, membership_expiry, anusportid) VALUES (%s, %s, %s, %s)",
                    (candidate["email"].strip().lower(), candidate["name"] or candidate["email"],
                     candidate["new_expiry"], candidate["anusportid"]),
                )
        except pymysql.err.IntegrityError:
            # Someone already holds this email/anusportid -- shouldn't
            # happen (by_email above should've caught it), but don't let
            # one collision abort the whole run.
            no_email.append({"name": candidate["name"], "email": candidate["email"], "anusportid": candidate["anusportid"]})
            continue

        email_sent = send_membership_email(candidate["email"], candidate["name"], candidate["new_expiry"], True)
        created.append({
            "name": candidate["name"], "email": candidate["email"],
            "new_expiry": candidate["new_expiry"], "email_sent": email_sent,
        })

    return {
        "ran_at": datetime.now(),
        "updated": updated,
        "unchanged": unchanged,
        "created": created,
        "no_email": no_email,
        "ambiguous": ambiguous,
    }


def summarize(result: Dict[str, Any]) -> str:
    return (
        f"{len(result['updated'])} updated, {len(result['created'])} created, "
        f"{len(result['unchanged'])} unchanged, {len(result['no_email'])} skipped (no email), "
        f"{len(result['ambiguous'])} ambiguous"
    )


# -- email notification -------------------------------------------------------

def send_membership_email(to_email: str, name: str, new_expiry: date, is_new_member: bool) -> bool:
    """Sends a plain membership renewal/creation notice via SMTP if
    config.SMTP_HOST is set; otherwise just prints it to stdout so the
    notification is still visible (e.g. in dev, or before SMTP is
    configured). Returns whether an actual SMTP send was attempted."""
    first_name = (name or "").split(None, 1)[0] or "there"
    if is_new_member:
        subject = "Welcome to NUCC -- your membership is now active"
        body = (
            f"Hi {first_name},\n\n"
            f"Your National University Caving Club membership is now active, "
            f"expiring {new_expiry:%d %b %Y}.\n\nSee you underground!\n"
        )
    else:
        subject = "Your NUCC membership has been renewed"
        body = (
            f"Hi {first_name},\n\n"
            f"Your National University Caving Club membership has been renewed, "
            f"now expiring {new_expiry:%d %b %Y}.\n\nThanks for renewing!\n"
        )

    if not config.SMTP_HOST:
        print(f"[anusport_sync] SMTP not configured -- would send to {to_email}:\nSubject: {subject}\n{body}")
        return False

    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = formataddr(("NUCC", config.SMTP_SENDER))
    msg["To"] = to_email

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as server:
            server.starttls()
            if config.SMTP_USERNAME:
                server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            server.sendmail(config.SMTP_SENDER, [to_email], msg.as_string())
        return True
    except Exception:
        return False


# -- sync report (spreadsheet) ------------------------------------------------

def build_report_workbook(result: Dict[str, Any]) -> bytes:
    """One sheet per section of the sync result."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    def add_sheet(title, headers, rows):
        ws = wb.create_sheet(title)
        ws.append(headers)
        for row in rows:
            ws.append(row)

    add_sheet("Updated", ["Name", "Email", "Previous expiry", "New expiry", "New member?", "Email sent"], [
        [r["name"], r["email"], r["previous_expiry"], r["new_expiry"], r["is_new_member"], r["email_sent"]]
        for r in result["updated"]
    ])
    add_sheet("Created", ["Name", "Email", "Membership expiry", "Email sent"], [
        [r["name"], r["email"], r["new_expiry"], r["email_sent"]] for r in result["created"]
    ])
    add_sheet("Unchanged", ["Name", "Email"], [[r["name"], r["email"]] for r in result["unchanged"]])
    add_sheet("Skipped (no email)", ["Name", "ANU Sport ID"], [[r["name"], r["anusportid"]] for r in result["no_email"]])
    add_sheet("Ambiguous", ["Name", "Email"], [[r["name"], r["email"]] for r in result["ambiguous"]])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def deliver_report(result: Dict[str, Any]) -> str:
    """Emails the report spreadsheet to config.ANUSPORT_REPORT_EMAIL (as an
    attachment) if SMTP and that address are both configured; otherwise
    saves it under anusport_reports/ and returns where. Returns a short
    human-readable description of what happened."""
    workbook_bytes = build_report_workbook(result)
    filename = f"anusport-sync-{result['ran_at']:%Y%m%d-%H%M%S}.xlsx"

    if config.SMTP_HOST and config.ANUSPORT_REPORT_EMAIL:
        msg = MIMEMultipart()
        msg["Subject"] = f"NUCC ANU Sport sync report -- {result['ran_at']:%d %b %Y}"
        msg["From"] = formataddr(("NUCC", config.SMTP_SENDER))
        msg["To"] = config.ANUSPORT_REPORT_EMAIL
        msg.attach(MIMEText(summarize(result), "plain"))
        attachment = MIMEApplication(workbook_bytes, _subtype="xlsx")
        attachment.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(attachment)
        try:
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as server:
                server.starttls()
                if config.SMTP_USERNAME:
                    server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
                server.sendmail(config.SMTP_SENDER, [config.ANUSPORT_REPORT_EMAIL], msg.as_string())
            return f"emailed to {config.ANUSPORT_REPORT_EMAIL}"
        except Exception as exc:
            print(f"[anusport_sync] Failed to email report, saving locally instead: {exc}")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / filename
    report_path.write_bytes(workbook_bytes)
    return f"saved to {report_path}"
