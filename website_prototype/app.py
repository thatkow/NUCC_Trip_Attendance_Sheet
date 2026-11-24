#!/usr/bin/env python3
"""
Trip Events prototype: plain-stdlib Python webserver + MySQL backend.

Run:
    pip install -r requirements.txt
    mysql -u root -p < schema.sql
    python3 app.py
"""

import base64
import csv
import io
import json
import html
import mimetypes
import os
import re
import secrets
import uuid
from datetime import datetime
from decimal import Decimal
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import urllib.request
from urllib.parse import parse_qs, quote_plus, unquote_plus, urlparse

import pymysql

import accounting
import bank_accounting
import formula
import auth
import anusport_daemon
import anusport_sync
import config
import email_notify
import db
import markdown

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------

CLUB_NAME = "National University Caving Club"

PAGE_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  :root {{
    --fb-blue: #1877f2;
    --fb-blue-dark: #166fe5;
    --fb-bg: #f0f2f5;
    --fb-text: #050505;
    --fb-muted: #65676b;
    --fb-border: #ced0d4;
    --fb-red: #e41e3f;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: Helvetica, Arial, "Segoe UI", sans-serif;
    background: var(--fb-bg);
    color: var(--fb-text);
    margin: 0;
    padding-bottom: 3em;
  }}
  .topbar {{
    background: #fff;
    border-bottom: 1px solid var(--fb-border);
    padding: 0.7em 1.2em;
    display: flex;
    justify-content: space-between;
    align-items: center;
    position: sticky;
    top: 0;
    z-index: 10;
  }}
  .topbar .brand {{ font-weight: 700; font-size: 1.1em; color: var(--fb-text); text-decoration: none; }}
  .topbar a {{ text-decoration: none; color: var(--fb-blue); margin-left: 1.2em; font-weight: 600; }}
  .page {{ max-width: 940px; margin: 1.5em auto; padding: 0 1em; }}
  .card {{
    background: #fff;
    border: 1px solid var(--fb-border);
    border-radius: 8px;
    padding: 1em 1.2em;
    margin-bottom: 1em;
    box-shadow: 0 1px 2px rgba(0,0,0,0.08);
  }}
  .card img {{ max-width: 100%; border-radius: 6px; }}
  h1 {{ font-size: 1.5em; margin-top: 0; }}
  h3 {{ font-size: 1.1em; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
  th, td {{ border-bottom: 1px solid #eee; padding: 0.5em 0.6em; text-align: left; }}
  th {{ color: var(--fb-muted); font-weight: 600; font-size: 0.9em; }}
  .owe-positive {{ color: var(--fb-red); font-weight: 600; }}
  .owe-negative {{ color: #15803d; font-weight: 600; }}
  form.inline {{ display: inline; }}
  .error {{ color: var(--fb-red); margin-bottom: 1em; }}
  .muted {{ color: var(--fb-muted); font-size: 0.92em; }}
  input, select, textarea {{
    padding: 0.55em 0.7em; margin: 0.3em 0; width: 100%;
    border: 1px solid var(--fb-border); border-radius: 6px; font-size: 0.95em;
    background: #f0f2f5;
  }}
  label {{ display: block; margin-bottom: 0.6em; font-weight: 600; font-size: 0.92em; }}

  button, .btn {{
    padding: 0.5em 1.1em; cursor: pointer; border-radius: 6px; border: 1px solid var(--fb-border);
    background: #e4e6eb; font-weight: 600; font-size: 0.95em; color: var(--fb-text);
    text-decoration: none; display: inline-block;
  }}
  button[type="submit"], .btn-primary {{ background: var(--fb-blue); color: #fff; border-color: var(--fb-blue); }}
  button[type="submit"]:hover, .btn-primary:hover {{ background: var(--fb-blue-dark); }}
  button:disabled, .btn:disabled {{
    opacity: 0.5; cursor: not-allowed; background: #e4e6eb; color: var(--fb-muted); border-color: var(--fb-border);
  }}
  button:disabled:hover, .btn:disabled:hover {{ background: #e4e6eb; }}

  .avatar {{
    display: inline-flex; align-items: center; justify-content: center;
    width: 36px; height: 36px; border-radius: 50%; color: #fff; font-weight: 700;
    font-size: 0.85em; flex-shrink: 0;
  }}
  .avatar-row {{ display: flex; gap: -8px; }}
  .avatar-row .avatar {{ margin-right: -8px; border: 2px solid #fff; }}

  .event-card {{ padding: 0; overflow: hidden; }}
  .event-card .thumb {{ width: 100%; height: 160px; object-fit: cover; display: block; }}
  .event-card .body {{ padding: 1em 1.2em; }}
  .event-card .date-line {{ color: var(--fb-red); font-weight: 600; font-size: 0.9em; margin-bottom: 0.2em; }}
  .event-card h2 {{ font-size: 1.15em; margin: 0.1em 0 0.3em; }}
  .event-card-link {{ display: block; text-decoration: none; color: inherit; }}
  .event-card-link:hover .event-card {{ box-shadow: 0 2px 8px rgba(0,0,0,0.18); }}
  .pill-row {{ display: flex; gap: 0.5em; margin-top: 0.8em; }}
  .pill-row form, .pill-row .btn {{ flex: 1; }}
  .pill-row button {{ width: 100%; }}

  .trip-list {{ padding: 0; }}
  .trip-row {{ display: flex; gap: 1em; padding: 1em 0; border-bottom: 1px solid var(--fb-border); }}
  .trip-row:last-child {{ border-bottom: none; padding-bottom: 0.2em; }}
  .trip-row:first-child {{ padding-top: 0.2em; }}
  .trip-row .thumb {{ width: 96px; height: 96px; object-fit: cover; border-radius: 8px; flex-shrink: 0; display: block; background: #ced0d4; }}
  .trip-row .trip-body {{ flex: 1; min-width: 0; }}
  .trip-row .date-line {{ color: var(--fb-red); font-weight: 600; font-size: 0.9em; margin-bottom: 0.1em; }}
  .trip-row h2 {{ font-size: 1.1em; margin: 0.1em 0 0.3em; }}
  .trip-row-link {{ text-decoration: none; color: inherit; }}
  .trip-row-link:hover h2 {{ text-decoration: underline; }}
  .trip-actions {{ display: flex; flex-wrap: wrap; gap: 0.5em; margin-top: 0.6em; }}
  .trip-actions button, .trip-actions .btn {{ padding: 0.4em 0.9em; font-size: 0.88em; }}
  .see-more {{ display: block; text-align: center; padding: 0.8em 0; font-weight: 600; }}

  .info-tooltip {{ position: relative; display: inline-block; }}
  .info-tooltip-content {{
    display: none;
    position: absolute;
    left: 50%;
    top: 100%;
    transform: translateX(-50%);
    z-index: 20;
    background: #fff;
    border: 1px solid #ddd;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.15);
    padding: 0.5em 0.75em;
    min-width: 220px;
    width: max-content;
    max-width: 90vw;
    white-space: normal;
    text-align: left;
    font-weight: normal;
  }}
  .info-tooltip:hover .info-tooltip-content,
  .info-tooltip:focus-within .info-tooltip-content {{ display: block; }}

  .hero {{ position: relative; margin-bottom: 0; }}
  .hero .hero-img-wrap {{ border-radius: 8px; overflow: hidden; }}
  .hero img {{ width: 100%; height: 280px; object-fit: cover; display: block; }}
  .date-badge {{
    position: absolute; left: 1.2em; bottom: -1.6em; background: #fff; border-radius: 8px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.25); text-align: center; width: 64px; overflow: hidden;
  }}
  .date-badge .mon {{ background: var(--fb-red); color: #fff; font-size: 0.75em; font-weight: 700; padding: 0.2em 0; text-transform: uppercase; }}
  .date-badge .day {{ font-size: 1.5em; font-weight: 700; padding: 0.2em 0; }}
  .event-header-card {{ padding-top: 2.4em; }}

  .event-layout {{ display: grid; grid-template-columns: 1.4fr 1fr; gap: 1em; align-items: start; }}
  @media (max-width: 760px) {{ .event-layout {{ grid-template-columns: 1fr; }} }}

  .map-embed {{ width: 100%; height: 220px; border: 0; border-radius: 8px 8px 0 0; display: block; }}
  .guest-row {{ display: flex; align-items: center; gap: 0.7em; padding: 0.5em 0; }}
  .guest-row .name {{ flex: 1; font-weight: 600; font-size: 0.95em; }}
  .guest-row .status {{ font-size: 0.85em; color: var(--fb-muted); }}
  .description-body {{ line-height: 1.5; }}
  .description-body img {{ max-width: 100%; cursor: zoom-in; }}

  .role-dropdown {{ position: relative; display: inline-block; }}
  .role-dropdown-menu {{
    display: none; position: absolute; top: 100%; left: 0; z-index: 50; margin-top: 0.2em;
    background: #fff; border: 1px solid var(--fb-border); border-radius: 6px; padding: 0.5em 0.7em;
    box-shadow: 0 2px 10px rgba(0,0,0,0.15); white-space: nowrap;
  }}
  .role-dropdown-menu.show {{ display: block; }}
  .role-dropdown-menu label {{ display: flex; align-items: center; gap: 0.4em; font-weight: normal; margin: 0.3em 0; }}

  #lightbox-overlay {{
    display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.85);
    z-index: 2000; align-items: center; justify-content: center; cursor: zoom-out;
    padding: 2em; overflow: auto; overscroll-behavior: contain;
  }}
  #lightbox-overlay.show {{ display: flex; }}
  #lightbox-overlay img {{
    margin: auto; border-radius: 6px; box-shadow: 0 4px 24px rgba(0,0,0,0.5); display: block;
  }}
  .tabs {{ display: flex; gap: 1.5em; border-bottom: 1px solid var(--fb-border); margin-bottom: 1em; padding-bottom: 0; }}
  .tabs a {{ padding: 0.8em 0.2em; text-decoration: none; color: var(--fb-muted); font-weight: 600; font-size: 0.95em; border-bottom: 3px solid transparent; }}
  .tabs a.active {{ color: var(--fb-blue); border-bottom-color: var(--fb-blue); }}

  dialog {{ background: #fff; }}
  dialog::backdrop {{ background: rgba(0,0,0,0.5); }}

  .cover-banner {{ border-radius: 8px; overflow: hidden; margin-bottom: 0.8em; }}
  .cover-banner img {{ width: 100%; height: 320px; object-fit: cover; display: block; }}
  .club-header {{ margin-bottom: 1em; }}
  .club-header h1 {{ margin-bottom: 0.1em; }}

  #toast {{
    position: fixed; bottom: 1.5em; left: 50%; transform: translateX(-50%) translateY(0.5em);
    background: #1c1e21; color: #fff; padding: 0.7em 1.1em; border-radius: 8px;
    font-size: 0.9em; max-width: min(90vw, 480px); box-shadow: 0 2px 10px rgba(0,0,0,0.25);
    opacity: 0; pointer-events: none; transition: opacity 0.2s, transform 0.2s; z-index: 1000;
    word-break: break-word;
  }}
  #toast.show {{ opacity: 1; transform: translateX(-50%) translateY(0); }}
</style>
</head>
<body>
<div class="topbar">
  <a class="brand" href="/">{club_name}</a>
  <div>{page_links}{user_nav}</div>
</div>
<div class="page">
{body}
</div>
<div id="toast"></div>
<div id="lightbox-overlay"><img id="lightbox-img"></div>
<script>
  let toastTimer = null;
  function showToast(message) {{
    const el = document.getElementById('toast');
    el.textContent = message;
    el.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove('show'), 2500);
  }}

  (function() {{
    const overlay = document.getElementById('lightbox-overlay');
    const overlayImg = document.getElementById('lightbox-img');
    let zoom = 1, naturalW = 0, naturalH = 0, baseScale = 1;

    function applySize() {{
      overlayImg.style.width = (naturalW * baseScale * zoom) + 'px';
      overlayImg.style.height = 'auto';
      overlay.style.cursor = zoom > 1 ? 'default' : 'zoom-in';
    }}

    function setZoom(z) {{
      zoom = Math.min(Math.max(z, 1), 6);
      applySize();
    }}

    overlayImg.addEventListener('load', function() {{
      naturalW = overlayImg.naturalWidth || 1;
      naturalH = overlayImg.naturalHeight || 1;
      baseScale = Math.min((window.innerWidth * 0.9) / naturalW, (window.innerHeight * 0.9) / naturalH, 1);
      setZoom(1);
    }});

    function openLightbox(src) {{
      overlayImg.src = src;
      overlay.classList.add('show');
      document.body.style.overflow = 'hidden';
    }}

    function closeLightbox() {{
      overlay.classList.remove('show');
      document.body.style.overflow = '';
    }}

    document.querySelectorAll('.description-body img').forEach(function(img) {{
      img.addEventListener('click', function() {{ openLightbox(img.src); }});
    }});
    overlay.addEventListener('click', function(e) {{
      if (e.target === overlay) closeLightbox();
    }});
    overlayImg.addEventListener('dblclick', function() {{
      setZoom(zoom > 1 ? 1 : 2.5);
    }});
    // Plain scroll/trackpad pans the (possibly larger-than-viewport) image via the
    // overlay's own overflow:auto -- only a pinch gesture or Ctrl+wheel zooms.
    overlay.addEventListener('wheel', function(e) {{
      if (!e.ctrlKey) return;
      e.preventDefault();
      setZoom(zoom - e.deltaY * 0.01);
    }}, {{ passive: false }});
    document.addEventListener('keydown', function(e) {{
      if (e.key === 'Escape') closeLightbox();
    }});
  }})();

  // Shared checkbox-dropdown widget (e.g. the "Visible to" roles picker on /admin):
  // a button toggles a hidden checkbox menu; clicking elsewhere closes any open one.
  document.addEventListener('click', function(e) {{
    const toggle = e.target.closest('.role-dropdown-toggle');
    document.querySelectorAll('.role-dropdown-menu.show').forEach(function(menu) {{
      if (!toggle || menu !== toggle.nextElementSibling) menu.classList.remove('show');
    }});
    if (toggle) {{
      e.preventDefault();
      toggle.nextElementSibling.classList.toggle('show');
    }}
  }});
</script>
</body>
</html>"""


AVATAR_COLORS = ["#1877f2", "#e41e3f", "#f5a623", "#15803d", "#8e44ad", "#16a085", "#d35400", "#2c3e50"]

SIGNUP_MODE_LABELS = {
    "fcfs": "First come, first served",
    "host_picks": "Host picks",
}

# Options for a content page's visible_roles (see handle_content_page and
# the Pages card on /admin). "anonymous" is a logged-out visitor; "member"
# matches anyone logged in regardless of other roles.
PAGE_ROLE_CHOICES = [
    ("anonymous", "Not logged in"),
    ("member", "Member"),
    ("admin", "Admin"),
    ("treasurer", "Treasurer"),
    ("assessor", "Assessor"),
]


def _viewer_role_keys(user):
    """Which of PAGE_ROLE_CHOICES' keys this viewer (user dict, or None for
    a logged-out visitor) matches, for checking a page's visible_roles."""
    if not user:
        return {"anonymous"}
    keys = {"member"}
    for key in ("admin", "treasurer", "assessor"):
        if user.get(f"is_{key}"):
            keys.add(key)
    return keys


def _page_visible_to(page, user):
    """A page with no visible_roles set is visible to everyone (the
    default, unrestricted) -- otherwise the viewer needs at least one
    matching role."""
    allowed = (page.get("visible_roles") or "").strip()
    if not allowed:
        return True
    allowed_keys = {k.strip() for k in allowed.split(",") if k.strip()}
    return bool(allowed_keys & _viewer_role_keys(user))


def avatar(name, picture_url=None, size=36):
    if picture_url:
        return (
            f'<img class="avatar" src="{html.escape(picture_url)}" '
            f'style="width:{size}px;height:{size}px;object-fit:cover;">'
        )
    initial = (name or "?").strip()[:1].upper()
    color = AVATAR_COLORS[sum(ord(c) for c in name) % len(AVATAR_COLORS)] if name else "#999"
    return (
        f'<span class="avatar" style="background:{color};width:{size}px;height:{size}px;">'
        f'{html.escape(initial)}</span>'
    )


# Content pages marked show_in_nav, cached in-process so render_page (which
# isn't a method and has no conn) doesn't need a DB round-trip on every
# single page render. Refreshed by _refresh_nav_links_cache whenever an
# admin creates/edits/deletes a page; lazily populated on first use
# otherwise (e.g. right after a restart). Fine for a prototype -- lost on
# restart, not shared across workers, same tradeoff as the other in-process
# caches in this file (_pending_import_summary and friends).
_NAV_LINKS_CACHE = None


def _refresh_nav_links_cache(conn):
    global _NAV_LINKS_CACHE
    with conn.cursor() as cur:
        cur.execute(
            "SELECT slug, title, nav_label, visible_roles FROM content_pages WHERE show_in_nav = 1 ORDER BY nav_order, title"
        )
        _NAV_LINKS_CACHE = [
            {"slug": r["slug"], "label": r["nav_label"] or r["title"], "visible_roles": r["visible_roles"]}
            for r in cur.fetchall()
        ]


def render_page(title, body, user=None):
    if user:
        pic = avatar(user["name"], user.get("profile_picture_url"), size=28)
        admin_link = '<a href="/admin">Admin</a> &middot; ' if user.get("is_admin") else ""
        accounting_link = (
            '<a href="/accounting">Accounting</a> &middot; '
            if user.get("is_admin") or user.get("is_treasurer") else ""
        )
        assess_link = (
            '<a href="/assess">Assess skills</a> &middot; '
            if user.get("is_admin") or user.get("is_assessor") else ""
        )
        user_nav = (
            f'{admin_link}{accounting_link}{assess_link}'
            f'<a href="/profile" style="color:inherit; text-decoration:none; display:inline-flex; align-items:center; gap:0.5em;">'
            f'{pic} {html.escape(user["name"])}</a> &middot; <a href="/logout">Log out</a>'
        )
    else:
        user_nav = '<a href="/login">Log in</a>'
    if _NAV_LINKS_CACHE is None:
        _refresh_nav_links_cache(db.get_connection())
    page_links = "".join(
        f'<a href="/pages/{html.escape(link["slug"])}">{html.escape(link["label"])}</a>'
        for link in (_NAV_LINKS_CACHE or [])
        if _page_visible_to(link, user)
    )
    return PAGE_TEMPLATE.format(
        title=html.escape(title), body=body, user_nav=user_nav, club_name=html.escape(CLUB_NAME),
        page_links=page_links,
    )


def redirect(handler, location):
    handler.send_response(302)
    handler.send_header("Location", location)
    handler.end_headers()


def money(d):
    return f"${d:,.2f}"


def signed_money(d):
    """Like money(), but for a negative amount puts the "-" before the "$"
    (e.g. "-$5.00") instead of money()'s "$-5.00"."""
    return f"-{money(-d)}" if d < 0 else money(d)


def location_info(location, location_label=None, with_embed=False):
    """Returns (display_name, maps_url, maps_embed_url_or_None).

    `location` can be a plain address/place name (turned into a Google Maps
    search link), or a Google Maps link itself (e.g. a maps.app.goo.gl share
    link), in which case it's used directly and we skip the iframe embed
    (short links/arbitrary Maps URLs are often blocked from framing).
    `location_label`, if given, overrides whatever display name we'd
    otherwise show. `with_embed` controls whether we do a (slow, network)
    geocode lookup for the embeddable map -- callers that only need the
    display name/link (e.g. an events list) should leave this off.
    """
    is_url = location.lower().startswith("http://") or location.lower().startswith("https://")
    if is_url:
        maps_url = location
        # we can't embed the share link itself (framing is usually blocked),
        # but a place name to search for still gets us a widget: prefer an
        # explicit label, falling back to resolving the share link's
        # redirect to pull the place name Google Maps put in its own URL
        embed_query = location_label or (_resolve_maps_place_name(location) if with_embed else None)
        maps_embed_url = f"https://maps.google.com/maps?q={quote_plus(embed_query)}&output=embed" if embed_query else None
        display_name = location_label or "View location on Google Maps"
    else:
        query = quote_plus(location)
        maps_url = f"https://www.google.com/maps?q={query}"
        maps_embed_url = f"https://maps.google.com/maps?q={query}&output=embed" if with_embed else None
        display_name = location_label or location
    return display_name, maps_url, maps_embed_url


_MAPS_PLACE_NAME_CACHE = {}
_MAPS_PLACE_RE = re.compile(r"/maps/place/([^/]+)/")


def _resolve_maps_place_name(share_url):
    """Follows a Google Maps share link's redirect (e.g.
    maps.app.goo.gl/...) to its resolved maps.google.com/maps/place/<name>/
    URL and pulls out the place name, for use as an embed search query --
    the share link itself can't be framed, but the plain name usually can
    be. Returns None if it doesn't redirect to a /place/ URL or the request
    fails (e.g. no network, or Google blocks the request)."""
    if share_url in _MAPS_PLACE_NAME_CACHE:
        return _MAPS_PLACE_NAME_CACHE[share_url]
    place_name = None
    try:
        req = urllib.request.Request(share_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            resolved_url = resp.geturl()
        m = _MAPS_PLACE_RE.search(resolved_url)
        if m:
            place_name = unquote_plus(m.group(1).replace("+", " "))
    except Exception:
        place_name = None
    _MAPS_PLACE_NAME_CACHE[share_url] = place_name
    return place_name


class FormData:
    """Thin wrapper around parse_qs's {key: [values]} so handlers can use
    both the common form.get(key, default) single-value style and, for
    checkbox groups sharing one name, form.getlist(key)."""

    def __init__(self, parsed):
        self._parsed = parsed

    def get(self, key, default=""):
        values = self._parsed.get(key)
        return values[0] if values else default

    def getlist(self, key):
        return self._parsed.get(key, [])

    def keys(self):
        return self._parsed.keys()


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------


class Handler(BaseHTTPRequestHandler):
    server_version = "TripEventsPrototype/0.1"

    # Summary of the transactions inserted by the most recent CSV import
    # (the ones that weren't already in the system), shown once as a dialog
    # on the next /accounting page load. Keyed by treasurer user id; cleared
    # after being shown. Fine to keep in-process for a prototype (lost on
    # restart, not shared across workers).
    _pending_import_summary = {}

    # -- helpers --------------------------------------------------------

    def _conn(self):
        if not hasattr(self.server, "_shared_conn") or self.server._shared_conn is None:
            self.server._shared_conn = db.get_connection()
        try:
            self.server._shared_conn.ping()
        except Exception:
            self.server._shared_conn = db.get_connection()
        return self.server._shared_conn

    def _cookies(self):
        cookie_header = self.headers.get("Cookie")
        jar = SimpleCookie()
        if cookie_header:
            jar.load(cookie_header)
        return jar

    def _current_user(self, conn):
        jar = self._cookies()
        token = jar[config.SESSION_COOKIE_NAME].value if config.SESSION_COOKIE_NAME in jar else None
        return auth.get_user_for_token(conn, token)

    def _read_form(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length else ""
        return FormData(parse_qs(body, keep_blank_values=True))

    def _send_html(self, body_html, status=200, set_cookie=None, clear_cookie=False):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        if set_cookie:
            self.send_header(
                "Set-Cookie",
                f"{config.SESSION_COOKIE_NAME}={set_cookie}; Path=/; HttpOnly; Max-Age={config.SESSION_LIFETIME_HOURS * 3600}",
            )
        if clear_cookie:
            self.send_header("Set-Cookie", f"{config.SESSION_COOKIE_NAME}=; Path=/; HttpOnly; Max-Age=0")
        encoded = body_html.encode("utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    # Default BaseHTTPRequestHandler logging (access logs + tracebacks on
    # unhandled exceptions) is left enabled and redirected to a log file by
    # the run script, so issues can be diagnosed by tailing that file.

    def handle_static(self, path):
        rel_path = path[len("/static/"):]
        full_path = os.path.normpath(os.path.join(STATIC_DIR, rel_path))
        if not full_path.startswith(STATIC_DIR + os.sep) or not os.path.isfile(full_path):
            self.send_response(404)
            self.end_headers()
            return
        content_type, _ = mimetypes.guess_type(full_path)
        with open(full_path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(data)

    # -- routing ----------------------------------------------------------

    def do_GET(self):
        path = urlparse(self.path).path

        if path.startswith("/static/"):
            return self.handle_static(path)

        conn = self._conn()
        user = self._current_user(conn)

        try:
            if path == "/":
                return self.handle_events_list(conn, user)

            m = re.fullmatch(r"/pages/([a-z0-9-]+)/edit", path)
            if m:
                return self.handle_content_page_edit_form(conn, user, m.group(1))

            m = re.fullmatch(r"/pages/([a-z0-9-]+)", path)
            if m:
                return self.handle_content_page(conn, user, m.group(1))
            if path == "/login":
                next_url = parse_qs(urlparse(self.path).query).get("next", [""])[0]
                return self.handle_login_form(user, next_url=next_url if next_url.startswith("/") else None)
            if path == "/forgot-password":
                return self.handle_forgot_password_form(user)
            m = re.fullmatch(r"/reset-password/([0-9a-f]{64})", path)
            if m:
                return self.handle_reset_password_form(conn, user, m.group(1))
            if path == "/logout":
                return self.handle_logout(conn)
            if path == "/events/new":
                return self.handle_event_new_form(conn, user)
            if path == "/profile":
                return self.handle_profile_form(conn, user)
            if path == "/admin":
                return self.handle_admin_page(conn, user)
            if path == "/admin/site":
                return self.handle_admin_site_page(conn, user)
            if path == "/admin/gear":
                return self.handle_admin_gear_page(conn, user)
            if path == "/admin/checklist-items":
                return self.handle_admin_checklist_page(conn, user)
            if path == "/admin/pages":
                return self.handle_admin_pages_page(conn, user)
            if path == "/admin/members":
                return self.handle_admin_members_page(conn, user)
            if path == "/admin/distance-formula/test":
                return self.handle_distance_formula_test(user)
            if path == "/assess":
                return self.handle_assess_page(conn, user)
            if path == "/admin/anusport-sync":
                return self.handle_anusport_sync_page(conn, user)

            if path == "/accounting":
                return self.handle_accounting_page(conn, user)
            if path == "/accounting/transactions":
                return self.handle_accounting_transactions_page(conn, user)
            if path == "/accounting/export":
                return self.handle_accounting_export(conn, user)
            if path == "/accounting/export-fees":
                return self.handle_accounting_export_fees(conn, user)
            m = re.fullmatch(r"/accounting/balances/(\d+)", path)
            if m:
                return self.handle_accounting_user_balance_page(conn, user, int(m.group(1)))
            if path == "/accounting/users":
                return self.handle_accounting_users_page(conn, user)
            if path == "/accounting/ledger":
                return self.handle_accounting_ledger_page(conn, user)
            m = re.fullmatch(r"/accounting/ledger/(\d+)/edit", path)
            if m:
                return self.handle_accounting_ledger_edit_form(conn, user, int(m.group(1)))
            m = re.fullmatch(r"/accounting/ledger/(\d+)", path)
            if m:
                return self.handle_accounting_ledger_detail_page(conn, user, int(m.group(1)))

            m = re.fullmatch(r"/events/(\d+)", path)
            if m:
                return self.handle_event_detail(conn, user, int(m.group(1)))

            m = re.fullmatch(r"/events/(\d+)/edit", path)
            if m:
                return self.handle_event_edit_form(conn, user, int(m.group(1)))

            m = re.fullmatch(r"/events/(\d+)/map-embed", path)
            if m:
                return self.handle_event_map_embed(conn, user, int(m.group(1)))

            m = re.fullmatch(r"/events/(\d+)/contributions", path)
            if m:
                return self.handle_contributions_page(conn, user, int(m.group(1)))

            m = re.fullmatch(r"/events/(\d+)/contributions/(\d+)/edit", path)
            if m:
                return self.handle_contribution_edit_form(conn, user, int(m.group(1)), int(m.group(2)))

            m = re.fullmatch(r"/share/([A-Za-z0-9_-]{32,64})", path)
            if m:
                return self.handle_share_link(conn, user, m.group(1))

            m = re.fullmatch(r"/share/([A-Za-z0-9_-]{32,64})/contributions/(\d+)/edit", path)
            if m:
                token = m.group(1)
                event, host = self._get_event_and_host_by_edit_token(conn, token)
                if not event:
                    return self._send_html(render_page("Not found", "<h1>404</h1>", user), status=404)
                return self.handle_contribution_edit_form(
                    conn, None, event["id"], int(m.group(2)), effective_user=host, event_base=f"/share/{token}"
                )

            self._send_html(render_page("Not found", "<h1>404</h1>", user), status=404)
        except PermissionErrorRedirect as e:
            redirect(self, e.location)

    def do_POST(self):
        path = urlparse(self.path).path
        conn = self._conn()
        user = self._current_user(conn)
        form = self._read_form()

        try:
            if path == "/login":
                return self.handle_login_submit(conn, form)
            if path == "/forgot-password":
                return self.handle_forgot_password_submit(conn, form)
            m = re.fullmatch(r"/reset-password/([0-9a-f]{64})", path)
            if m:
                return self.handle_reset_password_submit(conn, m.group(1), form)
            if path == "/events/new":
                return self.handle_event_new_submit(conn, user, form)
            if path == "/profile":
                return self.handle_profile_submit(conn, user, form)
            if path == "/admin/banner":
                return self.handle_banner_submit(conn, user, form)
            if path == "/admin/distance-formula":
                return self.handle_distance_formula_submit(conn, user, form)
            if path == "/admin/bank-details":
                return self.handle_bank_details_submit(conn, user, form)
            if path == "/admin/gear":
                return self.handle_gear_type_add(conn, user, form)

            m = re.fullmatch(r"/admin/gear/(\d+)/update", path)
            if m:
                return self.handle_gear_type_update(conn, user, int(m.group(1)), form)

            m = re.fullmatch(r"/admin/gear/(\d+)/delete", path)
            if m:
                return self.handle_gear_type_delete(conn, user, int(m.group(1)))

            if path == "/admin/checklist-items":
                return self.handle_checklist_item_add(conn, user, form)

            m = re.fullmatch(r"/admin/checklist-items/(\d+)/delete", path)
            if m:
                return self.handle_checklist_item_delete(conn, user, int(m.group(1)))

            m = re.fullmatch(r"/pages/([a-z0-9-]+)/edit", path)
            if m:
                return self.handle_content_page_edit_submit(conn, user, m.group(1), form)

            m = re.fullmatch(r"/pages/([a-z0-9-]+)/upload-image", path)
            if m:
                return self.handle_content_page_image_upload(conn, user, m.group(1), form)

            if path == "/admin/upload-image":
                return self.handle_admin_image_upload(conn, user, form)

            if path == "/admin/pages":
                return self.handle_admin_page_create(conn, user, form)

            m = re.fullmatch(r"/admin/pages/([a-z0-9-]+)/nav", path)
            if m:
                return self.handle_admin_page_nav_update(conn, user, m.group(1), form)

            m = re.fullmatch(r"/admin/pages/([a-z0-9-]+)/delete", path)
            if m:
                return self.handle_admin_page_delete(conn, user, m.group(1))

            m = re.fullmatch(r"/admin/users/(\d+)/toggle-admin", path)
            if m:
                return self.handle_toggle_admin(conn, user, int(m.group(1)))

            m = re.fullmatch(r"/admin/users/(\d+)/toggle-treasurer", path)
            if m:
                return self.handle_toggle_treasurer(conn, user, int(m.group(1)))

            m = re.fullmatch(r"/admin/users/(\d+)/toggle-assessor", path)
            if m:
                return self.handle_toggle_assessor(conn, user, int(m.group(1)))

            if path == "/admin/anusport-sync/run":
                return self.handle_anusport_sync_run(conn, user, form)

            if path == "/admin/anusport-sync/settings":
                return self.handle_anusport_sync_settings_submit(conn, user, form)

            m = re.fullmatch(r"/users/(\d+)/skills/(\d+)/toggle", path)
            if m:
                return self.handle_user_skill_toggle(conn, user, int(m.group(1)), int(m.group(2)))

            m = re.fullmatch(r"/users/(\d+)/skill-notes", path)
            if m:
                return self.handle_user_skill_notes_submit(conn, user, int(m.group(1)), form)

            if path == "/accounting/import":
                return self.handle_accounting_import(conn, user, form)

            if path == "/accounting/transactions/bulk-update":
                return self.handle_accounting_bulk_update(conn, user, form)

            if path == "/accounting/users/bulk-update":
                return self.handle_accounting_user_aliases_bulk_submit(conn, user, form)

            m = re.fullmatch(r"/accounting/users/(\d+)", path)
            if m:
                return self.handle_accounting_user_aliases_submit(conn, user, int(m.group(1)), form)

            if path == "/accounting/transactions/delete-all":
                return self.handle_accounting_delete_all(conn, user)

            m = re.fullmatch(r"/accounting/transactions/(\d+)/delete", path)
            if m:
                return self.handle_accounting_delete_transaction(conn, user, int(m.group(1)))

            if path == "/accounting/ledger":
                return self.handle_accounting_ledger_submit(conn, user, form)

            m = re.fullmatch(r"/accounting/ledger/(\d+)/delete", path)
            if m:
                return self.handle_accounting_ledger_delete(conn, user, int(m.group(1)))

            m = re.fullmatch(r"/accounting/ledger/(\d+)/edit", path)
            if m:
                return self.handle_accounting_ledger_edit_submit(conn, user, int(m.group(1)), form)

            m = re.fullmatch(r"/events/(\d+)/edit", path)
            if m:
                return self.handle_event_edit_submit(conn, user, int(m.group(1)), form)

            m = re.fullmatch(r"/events/(\d+)/signup", path)
            if m:
                return self.handle_signup(conn, user, int(m.group(1)))

            m = re.fullmatch(r"/events/(\d+)/signup/leave", path)
            if m:
                return self.handle_signup_leave(conn, user, int(m.group(1)))

            m = re.fullmatch(r"/events/(\d+)/signup/(\d+)/(approve|reject)", path)
            if m:
                return self.handle_signup_decision(
                    conn, user, int(m.group(1)), int(m.group(2)), m.group(3)
                )

            m = re.fullmatch(r"/events/(\d+)/discussion", path)
            if m:
                return self.handle_discussion_post(conn, user, int(m.group(1)), form)

            m = re.fullmatch(r"/events/(\d+)/contributions", path)
            if m:
                return self.handle_contribution_submit(conn, user, int(m.group(1)), form)

            m = re.fullmatch(r"/events/(\d+)/contributions/drove", path)
            if m:
                return self.handle_contribution_drove_submit(conn, user, int(m.group(1)), form)

            m = re.fullmatch(r"/events/(\d+)/contributions/(\d+)/edit", path)
            if m:
                return self.handle_contribution_edit_submit(conn, user, int(m.group(1)), int(m.group(2)), form)

            m = re.fullmatch(r"/events/(\d+)/contributions/(\d+)/delete", path)
            if m:
                return self.handle_contribution_delete(conn, user, int(m.group(1)), int(m.group(2)))

            m = re.fullmatch(r"/events/(\d+)/gear-use", path)
            if m:
                return self.handle_gear_use_submit(conn, user, int(m.group(1)), form)

            m = re.fullmatch(r"/events/(\d+)/gear-use/(\d+)/delete", path)
            if m:
                return self.handle_gear_use_delete(conn, user, int(m.group(1)), int(m.group(2)))

            m = re.fullmatch(r"/events/(\d+)/fees/lodge", path)
            if m:
                return self.handle_fees_lodge(conn, user, int(m.group(1)))

            m = re.fullmatch(r"/events/(\d+)/fees/amend", path)
            if m:
                return self.handle_fees_amend(conn, user, int(m.group(1)))

            m = re.fullmatch(r"/share/([A-Za-z0-9_-]{32,64})/(contributions(?:/drove)?|contributions/(\d+)/(?:edit|delete)|gear-use(?:/(\d+)/delete)?|fees/(?:lodge|amend))", path)
            if m:
                token = m.group(1)
                sub = m.group(2)
                event, host = self._get_event_and_host_by_edit_token(conn, token)
                if not event:
                    return self._send_html(render_page("Not found", "<h1>404</h1>", user), status=404)
                event_id = event["id"]
                base = f"/share/{token}"
                if sub == "contributions":
                    return self.handle_contribution_submit(conn, None, event_id, form, effective_user=host, event_base=base)
                if sub == "contributions/drove":
                    return self.handle_contribution_drove_submit(conn, None, event_id, form, effective_user=host, event_base=base)
                if sub.startswith("contributions/") and sub.endswith("/edit"):
                    return self.handle_contribution_edit_submit(conn, None, event_id, int(m.group(3)), form, effective_user=host, event_base=base)
                if sub.startswith("contributions/") and sub.endswith("/delete"):
                    return self.handle_contribution_delete(conn, None, event_id, int(m.group(3)), effective_user=host, event_base=base)
                if sub == "gear-use":
                    return self.handle_gear_use_submit(conn, None, event_id, form, effective_user=host, event_base=base)
                if sub.startswith("gear-use/"):
                    return self.handle_gear_use_delete(conn, None, event_id, int(m.group(4)), effective_user=host, event_base=base)
                if sub == "fees/lodge":
                    return self.handle_fees_lodge(conn, None, event_id, effective_user=host, event_base=base)
                if sub == "fees/amend":
                    return self.handle_fees_amend(conn, None, event_id, effective_user=host, event_base=base)
                return self._send_html(render_page("Not found", "<h1>404</h1>", user), status=404)

            m = re.fullmatch(r"/events/(\d+)/checklist", path)
            if m:
                return self.handle_event_checklist_submit(conn, user, int(m.group(1)), form)

            m = re.fullmatch(r"/events/(\d+)/guests", path)
            if m:
                return self.handle_event_guest_add(conn, user, int(m.group(1)), form)

            m = re.fullmatch(r"/events/(\d+)/guests/existing", path)
            if m:
                return self.handle_event_guest_add_existing(conn, user, int(m.group(1)), form)

            m = re.fullmatch(r"/events/(\d+)/guests/(\d+)/remove", path)
            if m:
                return self.handle_event_guest_remove(conn, user, int(m.group(1)), int(m.group(2)))

            self._send_html(render_page("Not found", "<h1>404</h1>", user), status=404)
        except PermissionErrorRedirect as e:
            redirect(self, e.location)

    # -- auth ---------------------------------------------------------------

    def _site_base_url(self):
        """Best-effort absolute origin for building links in emails (there's
        no admin-configured site URL setting) -- uses the request's own Host
        header, guessing http for local dev hosts and https otherwise."""
        host = self.headers.get("Host", "localhost")
        scheme = "http" if host.split(":")[0] in ("localhost", "127.0.0.1") else "https"
        return f"{scheme}://{host}"

    def handle_login_form(self, user, error=None, success=None, next_url=None):
        error_html = f'<p class="error">{html.escape(error)}</p>' if error else ""
        success_html = f'<p style="color:#15803d;">{html.escape(success)}</p>' if success else ""
        next_field = f'<input type="hidden" name="next" value="{html.escape(next_url)}">' if next_url else ""
        body = f"""
        <div class="card" style="max-width:380px; margin:3em auto;">
        <h1>Log in</h1>
        {error_html}{success_html}
        <form method="post" action="/login">
          {next_field}
          <label>Email<input name="email" type="email" required></label>
          <label>Password<input name="password" type="password" required></label>
          <button type="submit" class="btn-primary" style="width:100%;">Log in</button>
        </form>
        <p style="margin-top:1em; text-align:center;"><a href="/forgot-password">Forgot your password?</a></p>
        </div>"""
        self._send_html(render_page("Log in", body, user))

    def handle_forgot_password_form(self, user, sent=False):
        body_inner = (
            '<p style="color:#15803d;">If that email has an account, we\'ve sent a password reset link to it.</p>'
            '<p class="muted"><a href="/login">Back to log in</a></p>'
        ) if sent else f"""
        <form method="post" action="/forgot-password">
          <label>Email<input name="email" type="email" required></label>
          <button type="submit" class="btn-primary" style="width:100%;">Send reset link</button>
        </form>
        <p style="margin-top:1em; text-align:center;"><a href="/login">Back to log in</a></p>"""
        body = f"""
        <div class="card" style="max-width:380px; margin:3em auto;">
        <h1>Forgot your password?</h1>
        <p class="muted">Enter the email you think your account uses. If it has an account, we'll email a link to set a new password.</p>
        {body_inner}
        </div>"""
        self._send_html(render_page("Forgot password", body, user))

    def handle_forgot_password_submit(self, conn, form):
        email = form.get("email", "").strip().lower()
        if email:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM users WHERE email = %s", (email,))
                existing = cur.fetchone()
            if existing:
                token = auth.create_password_reset(conn, existing["id"])
                reset_url = f"{self._site_base_url()}/reset-password/{token}"
                email_notify.send_password_reset_email(email, reset_url)
        # Always the same response, whether or not the email matched an
        # account -- otherwise this page could be used to check who has one.
        return self.handle_forgot_password_form(None, sent=True)

    def handle_reset_password_form(self, conn, user, token, error=None):
        target = auth.get_user_for_reset_token(conn, token)
        if not target:
            body = """
            <div class="card" style="max-width:380px; margin:3em auto;">
            <h1>Link expired</h1>
            <p>This password reset link is invalid or has expired.</p>
            <p><a href="/forgot-password">Request a new one</a></p>
            </div>"""
            return self._send_html(render_page("Link expired", body, user), status=400)

        error_html = f'<p class="error">{html.escape(error)}</p>' if error else ""
        body = f"""
        <div class="card" style="max-width:380px; margin:3em auto;">
        <h1>Choose a new password</h1>
        {error_html}
        <form method="post" action="/reset-password/{token}">
          <label>New password<input name="password" type="password" required minlength="8"></label>
          <button type="submit" class="btn-primary" style="width:100%;">Set password</button>
        </form>
        </div>"""
        self._send_html(render_page("Reset password", body, user))

    def handle_reset_password_submit(self, conn, token, form):
        password = form.get("password", "")
        if len(password) < 8:
            return self.handle_reset_password_form(conn, None, token, error="Password must be at least 8 characters.")
        target = auth.get_user_for_reset_token(conn, token)
        if not target:
            return self.handle_reset_password_form(conn, None, token)
        auth.consume_password_reset(conn, token, password)
        session_token = auth.create_session(conn, target["id"])
        self.send_response(302)
        self.send_header("Location", "/")
        self.send_header(
            "Set-Cookie",
            f"{config.SESSION_COOKIE_NAME}={session_token}; Path=/; HttpOnly; Max-Age={config.SESSION_LIFETIME_HOURS * 3600}",
        )
        self.end_headers()

    def handle_login_submit(self, conn, form):
        email = form.get("email", "")
        password = form.get("password", "")
        next_url = form.get("next", "")
        next_url = next_url if next_url.startswith("/") else None
        user = auth.authenticate(conn, email, password)
        if not user:
            return self.handle_login_form(None, error="Invalid email or password.", next_url=next_url)
        token = auth.create_session(conn, user["id"])
        self.send_response(302)
        self.send_header("Location", next_url or "/")
        self.send_header(
            "Set-Cookie",
            f"{config.SESSION_COOKIE_NAME}={token}; Path=/; HttpOnly; Max-Age={config.SESSION_LIFETIME_HOURS * 3600}",
        )
        self.end_headers()

    def handle_logout(self, conn):
        jar = self._cookies()
        if config.SESSION_COOKIE_NAME in jar:
            auth.destroy_session(conn, jar[config.SESSION_COOKIE_NAME].value)
        self.send_response(302)
        self.send_header("Location", "/")
        self.send_header("Set-Cookie", f"{config.SESSION_COOKIE_NAME}=; Path=/; HttpOnly; Max-Age=0")
        self.end_headers()

    def _require_login(self, user):
        if not user:
            raise PermissionErrorRedirect(f"/login?next={quote_plus(self.path)}")
        return user

    def _get_distance_formula(self, conn):
        with conn.cursor() as cur:
            cur.execute("SELECT distance_formula FROM site_settings WHERE id = 1")
            row = cur.fetchone()
        return (row or {}).get("distance_formula") or "km * 0.025"

    def _resolve_distance_formula(self, conn, event):
        """An event's own distance_formula, if it set one, else the global default."""
        return event.get("distance_formula") or self._get_distance_formula(conn)

    def _get_bank_details(self, conn):
        with conn.cursor() as cur:
            cur.execute("SELECT bank_account_name, bank_bsb, bank_account_number, bank_logo_url FROM site_settings WHERE id = 1")
            return cur.fetchone() or {}

    def _contributions_intro_note(self):
        """One-line context shown at the top of every contributions view
        (the real page, its edit share-link rendering, and the read-only
        view share-link) explaining that money doesn't change hands
        directly between members -- it all goes through the club's own
        bank account."""
        return (
            '<p class="muted">Money for this trip goes through the club\'s bank account, not directly between '
            'members: gear hire fees are collected into it, and trip expenses -- petrol, vehicle maintenance, '
            'food, etc. -- are paid back out of it to whoever covered them. The numbers below are each '
            'person\'s share of that.</p>'
        )

    def _maintenance_info_tooltip(self, distance_formula):
        """Explains the "Maintenance" line item next to the Contributions
        heading -- it's easy to mistake for an unrelated charge, since it's
        really just the driven-distance (per-km) contribution, separate
        from any Petrol contribution the same driver also logs. Includes
        this trip's actual distance formula (events can override the
        site-wide default -- see _resolve_distance_formula)."""
        return f"""<span class="info-tooltip">
          <button type="button" class="info-icon" style="border:none; background:none; cursor:pointer; color:var(--fb-blue); font-size:1em; padding:0 0.2em;">&#9432;</button>
          <span class="info-tooltip-content" style="left:0; transform:none; width:260px; max-width:70vw;">
            <p style="margin:0; text-align:left;">"Maintenance" is the driven-distance contribution -- a per-km
            amount covering wear and tear on the driver's own car, separate from any "Petrol" contribution they
            also log for fuel.</p>
            <p style="margin:0.5em 0 0; text-align:left;">This trip's formula: <code>{html.escape(distance_formula)}</code></p>
          </span>
        </span>"""

    def _render_info_tooltip(self, items):
        """A hoverable breakdown icon for a Fee/Contributions cell on the
        "who owes what" table, listing each item and its amount -- used on
        both the real contributions page and the public view share link."""
        description_counts = {}
        for i in items:
            description_counts[i["description"]] = description_counts.get(i["description"], 0) + 1

        def label(i):
            text = i["description"]
            if description_counts[text] > 1 and i.get("paid_by"):
                text = f"{text} (paid by {i['paid_by']})"
            return html.escape(text)

        rows = "".join(
            f"<tr><td>{label(i)}</td><td style='text-align:right; white-space:nowrap;'>{money(i['amount'])}</td></tr>"
            for i in items
        ) or "<tr><td class='muted'>Nothing yet.</td></tr>"
        total = money(sum(i["amount"] for i in items))
        return f"""<span class="info-tooltip">
          <button type="button" class="info-icon" style="border:none; background:none; cursor:pointer; color:var(--fb-blue); font-size:1em; padding:0 0.2em;">&#9432;</button>
          <span class="info-tooltip-content">
            <table style="width:100%; margin:0;">
              {rows}
              <tr><th style="text-align:left;">Total</th><th style="text-align:right;">{total}</th></tr>
            </table>
          </span>
        </span>"""

    def _pay_button(self, bank_details, amount, dialog_id="pay-dialog"):
        """A "Pay" button that opens the shared pay dialog with this
        amount. Builds the onclick as JSON-encoded JS arguments, then
        html.escape()s the whole thing so the JSON strings' own double
        quotes don't prematurely close the (double-quoted) attribute."""
        args = ", ".join(json.dumps(v) for v in (
            dialog_id,
            bank_details.get("bank_account_name") or "",
            bank_details.get("bank_bsb") or "",
            bank_details.get("bank_account_number") or "",
            str(amount),
        ))
        onclick = html.escape(f"openPayDialog({args})", quote=True)
        return f'<button type="button" class="btn-primary" style="padding:0.2em 0.6em;" onclick="{onclick}">Pay</button>'

    def _render_pay_dialog_and_script(self, bank_details, dialog_id="pay-dialog"):
        """A single shared dialog (populated by JS per row) for the "who
        owes what" Pay button -- same markup/script used on both the real
        contributions page and the public view share-link page."""
        logo_url = (bank_details or {}).get("bank_logo_url")
        logo_html = f'<img src="{html.escape(logo_url)}" style="max-height:48px; display:block; margin-bottom:0.8em;">' if logo_url else ""
        return f"""
        <dialog id="{dialog_id}" style="border:none; border-radius:8px; padding:0; max-width:380px; width:90%;">
          <div class="card" style="margin:0; box-shadow:none; border:none;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <h3 style="margin:0;">Pay the club</h3>
              <button type="button" class="btn" onclick="document.getElementById('{dialog_id}').close()">&times;</button>
            </div>
            {logo_html}
            <div style="display:flex; flex-direction:column; gap:0.5em;">
              <div style="display:flex; align-items:center; gap:0.6em;">
                <label class="muted" style="width:90px; flex:0 0 auto;">Account name</label>
                <input readonly id="{dialog_id}-name" style="flex:1; min-width:0;">
                <button type="button" class="btn" title="Copy" style="padding:0.2em 0.5em; flex:0 0 auto;" onclick="payDialogCopy('{dialog_id}-name')">&#10697;</button>
              </div>
              <div style="display:flex; align-items:center; gap:0.6em;">
                <label class="muted" style="width:90px; flex:0 0 auto;">BSB</label>
                <input readonly id="{dialog_id}-bsb" style="flex:1; min-width:0;">
                <button type="button" class="btn" title="Copy" style="padding:0.2em 0.5em; flex:0 0 auto;" onclick="payDialogCopy('{dialog_id}-bsb')">&#10697;</button>
              </div>
              <div style="display:flex; align-items:center; gap:0.6em;">
                <label class="muted" style="width:90px; flex:0 0 auto;">Account no.</label>
                <input readonly id="{dialog_id}-acc" style="flex:1; min-width:0;">
                <button type="button" class="btn" title="Copy" style="padding:0.2em 0.5em; flex:0 0 auto;" onclick="payDialogCopy('{dialog_id}-acc')">&#10697;</button>
              </div>
              <div style="display:flex; align-items:center; gap:0.6em;">
                <label class="muted" style="width:90px; flex:0 0 auto;">Amount</label>
                <input readonly id="{dialog_id}-amount" style="flex:1; min-width:0;">
                <button type="button" class="btn" title="Copy" style="padding:0.2em 0.5em; flex:0 0 auto;" onclick="payDialogCopy('{dialog_id}-amount')">&#10697;</button>
              </div>
            </div>
            <p class="muted" style="margin-top:1em; margin-bottom:0;">The website isn't notified when you pay --
            your balance will update once the treasurer processes the bank transactions, and you'll be contacted
            about anything still outstanding.</p>
          </div>
        </dialog>
        <script>
          function payDialogCopy(id) {{
            var el = document.getElementById(id);
            navigator.clipboard.writeText(el.value).then(() => showToast('Copied to clipboard')).catch(() => showToast('Could not copy'));
          }}
          function openPayDialog(dialogId, name, bsb, acc, amount) {{
            document.getElementById(dialogId + '-name').value = name;
            document.getElementById(dialogId + '-bsb').value = bsb;
            document.getElementById(dialogId + '-acc').value = acc;
            document.getElementById(dialogId + '-amount').value = amount;
            document.getElementById(dialogId).showModal();
          }}
        </script>
        """

    def _get_gear_types(self, conn):
        """The club-wide gear types an admin manages (name + default
        per-person rate + a description of when to charge it), e.g.
        "Horizontal Gear": $5, "Any members hired club horizontal gear
        (helmets, headtorches, etc.)."."""
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, rate, description FROM gear_types ORDER BY name")
            return list(cur.fetchall())

    def _seed_event_gear_rates(self, conn, event_id):
        """Snapshots the current club-wide gear rates into this new event's
        own event_gear_rates row per gear type, so later admin changes to
        the global defaults don't retroactively change this trip's rates."""
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO event_gear_rates (event_id, gear_type_id, rate) SELECT %s, id, rate FROM gear_types",
                (event_id,),
            )

    def _resolve_event_gear_rates(self, conn, event_id):
        """This event's effective gear rates: its own override if it has
        one (see event_gear_rates), else the current club-wide default --
        covering a gear type added globally after this event was created."""
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT gt.id, gt.name, gt.description, COALESCE(egr.rate, gt.rate) AS rate
                FROM gear_types gt
                LEFT JOIN event_gear_rates egr ON egr.gear_type_id = gt.id AND egr.event_id = %s
                ORDER BY gt.name
                """,
                (event_id,),
            )
            return list(cur.fetchall())

    def _require_admin(self, user):
        self._require_login(user)
        if not user.get("is_admin"):
            raise PermissionErrorRedirect("/")
        return user

    def _require_treasurer(self, user):
        self._require_login(user)
        if not user.get("is_admin") and not user.get("is_treasurer"):
            raise PermissionErrorRedirect("/")
        return user

    def _require_assessor(self, user):
        self._require_login(user)
        if not user.get("is_admin") and not user.get("is_assessor"):
            raise PermissionErrorRedirect("/")
        return user

    # -- admin ---------------------------------------------------------------

    def _admin_nav(self, active):
        items = [
            ("/admin", "Overview"),
            ("/admin/site", "Site settings"),
            ("/admin/gear", "Gear types"),
            ("/admin/checklist-items", "Required skills & items"),
            ("/admin/pages", "Pages"),
            ("/admin/members", "Members"),
            ("/admin/anusport-sync", "ANU Sport sync"),
        ]
        links = "".join(
            f'<a href="{href}" style="padding:0.4em 0.8em; border-radius:6px; text-decoration:none;'
            f'{" background:var(--fb-blue); color:#fff;" if href == active else " color:inherit;"}">{label}</a>'
            for href, label in items
        )
        return f'<nav style="display:flex; gap:0.3em; flex-wrap:wrap; margin-bottom:1.2em;">{links}</nav>'

    def handle_admin_page(self, conn, user):
        self._require_admin(user)
        body = f"""
        <p><a href="/">&larr; back to trips</a></p>
        <h1>Admin</h1>
        {self._admin_nav("/admin")}
        <div class="card"><h3><a href="/admin/site">Site settings</a></h3>
        <p class="muted">Site banner, image uploads, and the driven-distance pricing formula.</p></div>
        <div class="card"><h3><a href="/admin/gear">Gear types</a></h3>
        <p class="muted">Club-wide gear and their default per-person rate.</p></div>
        <div class="card"><h3><a href="/admin/checklist-items">Required skills &amp; items</a></h3>
        <p class="muted">The catalog a trip leader can pick from when building a trip's checklist.</p></div>
        <div class="card"><h3><a href="/admin/pages">Pages</a></h3>
        <p class="muted">Admin-editable content pages and their header-nav/visibility settings.</p></div>
        <div class="card"><h3><a href="/admin/members">Members</a></h3>
        <p class="muted">Roles (admin/treasurer/assessor) and membership status.</p></div>
        <div class="card"><h3><a href="/admin/anusport-sync">ANU Sport sync</a></h3>
        <p class="muted">Poll ANU Sport's caving club orders to keep membership_expiry up to date.</p></div>
        """
        self._send_html(render_page("Admin", body, user))

    def handle_admin_site_page(self, conn, user, formula_error=None):
        self._require_admin(user)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT banner_url, distance_formula, bank_account_name, bank_bsb, bank_account_number, bank_logo_url "
                "FROM site_settings WHERE id = 1"
            )
            settings_row = cur.fetchone()
        banner_url = (settings_row or {}).get("banner_url") or "/static/banner.jpg"
        distance_formula = (settings_row or {}).get("distance_formula") or "km * 0.88"
        bank_account_name = (settings_row or {}).get("bank_account_name") or ""
        bank_bsb = (settings_row or {}).get("bank_bsb") or ""
        bank_account_number = (settings_row or {}).get("bank_account_number") or ""
        bank_logo_url = (settings_row or {}).get("bank_logo_url") or ""

        body = f"""
        <p><a href="/admin">&larr; back to admin</a></p>
        <h1>Site settings</h1>
        {self._admin_nav("/admin/site")}

        <div class="card">
        <h3>Site banner</h3>
        <img src="{html.escape(banner_url)}" style="max-width:100%; max-height:200px; border-radius:6px; display:block; margin-bottom:0.8em;">
        <form method="post" action="/admin/banner" id="banner-form">
          <input type="file" id="banner-file" accept="image/*">
          <input type="hidden" name="banner_data" id="banner-data">
          <button type="submit" class="btn-primary">Update banner</button>
        </form>
        </div>

        <div class="card">
        <h3>Upload image</h3>
        <p class="muted">Upload any image to get a permanent <code>/static/pages/...</code> URL for it, to use in a
        content page's Markdown, a trip description, or anywhere else that takes a URL.</p>
        <input type="file" id="admin-upload-image-file" accept="image/*">
        <div id="admin-upload-image-result" style="display:none; margin-top:0.8em;">
          <img id="admin-upload-image-preview" style="max-width:200px; max-height:150px; border-radius:6px; display:block; margin-bottom:0.6em;">
          <div style="display:flex; gap:0.5em;">
            <input id="admin-upload-image-url" readonly style="flex:1;">
            <button type="button" class="btn" id="admin-upload-image-copy">Copy URL</button>
          </div>
        </div>
        <p id="admin-upload-image-status" class="muted" style="margin-top:0.6em;"></p>
        </div>

        <div class="card">
        <h3>Driven distance pricing</h3>
        <p class="muted">The formula used to price a <code>driven_distance</code> contribution. Use the
        variable <code>km</code>, numbers, <code>+ - *</code> (or <code>x</code> for multiply), and
        <code>max(...)</code>/<code>min(...)</code> with any number of arguments. Example:
        <code>max(km * 0.45, 20)</code> for 45c/km with a $20 minimum.</p>
        {f'<p class="error">{html.escape(formula_error)}</p>' if formula_error else ''}
        <form method="post" action="/admin/distance-formula">
          <label>Formula<input name="distance_formula" id="distance-formula-input" value="{html.escape(distance_formula)}" required></label>
          <button type="submit" class="btn-primary">Save formula</button>
        </form>
        <div style="margin-top:1em;">
          <label>Try it: km<input type="number" id="formula-test-km" value="10" step="0.1" style="display:inline-block; width:100px;"></label>
          <p>Result: <strong id="formula-test-result">--</strong></p>
        </div>
        </div>

        <div class="card">
        <h3>Bank details</h3>
        <p class="muted">Shown to members on the contributions page's "Pay" dialog, for anyone who owes money.</p>
        {f'<img src="{html.escape(bank_logo_url)}" style="max-height:60px; display:block; margin-bottom:0.8em;">' if bank_logo_url else ''}
        <form method="post" action="/admin/bank-details" id="bank-details-form">
          <label>Bank logo<input type="file" id="bank-logo-file" accept="image/*"></label>
          <input type="hidden" name="logo_data" id="bank-logo-data">
          <label>Account name<input name="bank_account_name" value="{html.escape(bank_account_name)}"></label>
          <label>BSB<input name="bank_bsb" value="{html.escape(bank_bsb)}"></label>
          <label>Account number<input name="bank_account_number" value="{html.escape(bank_account_number)}"></label>
          <button type="submit" class="btn-primary">Save bank details</button>
        </form>
        </div>

        <script>
        document.getElementById('bank-logo-file').addEventListener('change', function() {{
          var file = this.files[0];
          if (!file) return;
          var reader = new FileReader();
          reader.onload = function(e) {{
            document.getElementById('bank-logo-data').value = e.target.result;
          }};
          reader.readAsDataURL(file);
        }});

        document.getElementById('banner-file').addEventListener('change', function() {{
          var file = this.files[0];
          if (!file) return;
          var reader = new FileReader();
          reader.onload = function(e) {{
            document.getElementById('banner-data').value = e.target.result;
          }};
          reader.readAsDataURL(file);
        }});

        document.getElementById('admin-upload-image-file').addEventListener('change', function() {{
          var file = this.files[0];
          if (!file) return;
          var status = document.getElementById('admin-upload-image-status');
          var result = document.getElementById('admin-upload-image-result');
          status.textContent = 'Uploading...';
          result.style.display = 'none';
          var reader = new FileReader();
          reader.onload = function(e) {{
            fetch('/admin/upload-image', {{
              method: 'POST',
              headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
              body: 'image_data=' + encodeURIComponent(e.target.result)
            }}).then(function(r) {{ return r.json(); }}).then(function(data) {{
              if (data.url) {{
                document.getElementById('admin-upload-image-preview').src = data.url;
                document.getElementById('admin-upload-image-url').value = window.location.origin + data.url;
                result.style.display = 'block';
                status.textContent = 'Uploaded.';
              }} else {{
                status.textContent = 'Upload failed.';
              }}
            }}).catch(function() {{ status.textContent = 'Upload failed.'; }});
          }};
          reader.readAsDataURL(file);
        }});

        document.getElementById('admin-upload-image-copy').addEventListener('click', function() {{
          var input = document.getElementById('admin-upload-image-url');
          navigator.clipboard.writeText(input.value);
          showToast('Copied: ' + input.value);
        }});

        (function() {{
          var formulaInput = document.getElementById('distance-formula-input');
          var kmInput = document.getElementById('formula-test-km');
          var resultEl = document.getElementById('formula-test-result');

          function runTest() {{
            var params = new URLSearchParams({{formula: formulaInput.value, km: kmInput.value}});
            fetch('/admin/distance-formula/test?' + params.toString())
              .then(function(r) {{ return r.json(); }})
              .then(function(data) {{
                if (data.error) {{
                  resultEl.textContent = 'Error: ' + data.error;
                  resultEl.style.color = '#b91c1c';
                }} else {{
                  resultEl.textContent = '$' + data.result.toFixed(2);
                  resultEl.style.color = '';
                }}
              }})
              .catch(function() {{ resultEl.textContent = '--'; }});
          }}
          formulaInput.addEventListener('input', runTest);
          kmInput.addEventListener('input', runTest);
          runTest();
        }})();
        </script>
        """
        self._send_html(render_page("Site settings", body, user))

    def handle_admin_gear_page(self, conn, user):
        self._require_admin(user)
        gear_types = self._get_gear_types(conn)
        gear_rows = "".join(
            f"""<tr>
              <td><input name="name" form="gear-form-{g['id']}" value="{html.escape(g['name'])}" required></td>
              <td><input name="rate" form="gear-form-{g['id']}" type="number" step="0.01" min="0" value="{g['rate']}" style="width:100px;"></td>
              <td><input name="description" form="gear-form-{g['id']}" value="{html.escape(g['description'] or '')}" placeholder="When to charge this" style="min-width:240px;"></td>
              <td style="display:flex; gap:0.4em;">
                <form id="gear-form-{g['id']}" class="inline" method="post" action="/admin/gear/{g['id']}/update"></form>
                <button type="submit" form="gear-form-{g['id']}" class="btn" style="padding:0.3em 0.7em;">Save</button>
                <form class="inline" method="post" action="/admin/gear/{g['id']}/delete" onsubmit="return confirm('Delete this gear type? Existing trips keep their own rate for it.');">
                  <button type="submit" class="btn" style="padding:0.3em 0.7em; color:#b91c1c; border-color:#b91c1c;">Delete</button>
                </form>
              </td>
            </tr>"""
            for g in gear_types
        )
        body = f"""
        <p><a href="/admin">&larr; back to admin</a></p>
        <h1>Gear types</h1>
        {self._admin_nav("/admin/gear")}
        <div class="card">
        <p class="muted">Club-wide gear and their default per-person rate (e.g. "Horizontal Gear": $5). A new
        trip inherits these rates; the host can override them for their own trip from the trip's Edit page.</p>
        <table>
          <tr><th>Name</th><th>Rate ($/person)</th><th>Description</th><th></th></tr>
          {gear_rows or '<tr><td colspan="4" class="muted">None yet.</td></tr>'}
        </table>
        <form method="post" action="/admin/gear" style="display:flex; gap:0.5em; margin-top:1em;">
          <input name="name" placeholder="e.g. Wetsuit" required style="flex:1;">
          <input name="rate" type="number" step="0.01" min="0" placeholder="Rate ($)" required style="width:120px;">
          <input name="description" placeholder="When to charge this" style="flex:2;">
          <button type="submit" class="btn-primary">Add gear type</button>
        </form>
        </div>
        """
        self._send_html(render_page("Gear types", body, user))

    def handle_admin_checklist_page(self, conn, user):
        self._require_admin(user)
        checklist_items = self._get_checklist_items(conn)
        checklist_rows = "".join(
            f"""<tr>
              <td>{html.escape(c['name'])}</td>
              <td>{"Skill" if c['kind'] == 'skill' else "Item"}</td>
              <td>
                <form class="inline" method="post" action="/admin/checklist-items/{c['id']}/delete" onsubmit="return confirm('Delete this checklist entry? It will be removed from any trip that currently requires it.');">
                  <button type="submit" class="btn" style="padding:0.3em 0.7em; color:#b91c1c; border-color:#b91c1c;">Delete</button>
                </form>
              </td>
            </tr>"""
            for c in checklist_items
        )
        body = f"""
        <p><a href="/admin">&larr; back to admin</a></p>
        <h1>Required skills &amp; items</h1>
        {self._admin_nav("/admin/checklist-items")}
        <div class="card">
        <p class="muted">Club-wide catalog a trip leader can pick from when building their trip's checklist
        (e.g. skill "Vertical sign-off", item "Wetsuit").</p>
        <table>
          <tr><th>Name</th><th>Kind</th><th></th></tr>
          {checklist_rows or '<tr><td colspan="3" class="muted">None yet.</td></tr>'}
        </table>
        <form method="post" action="/admin/checklist-items" style="display:flex; gap:0.5em; margin-top:1em;">
          <input name="name" placeholder="e.g. Vertical sign-off" required style="flex:1; width:auto;">
          <select name="kind" style="flex:0 0 120px; width:auto;">
            <option value="skill">Skill</option>
            <option value="item">Item</option>
          </select>
          <button type="submit" class="btn-primary" style="flex:0 0 auto;">Add</button>
        </form>
        </div>
        """
        self._send_html(render_page("Required skills & items", body, user))

    def handle_admin_pages_page(self, conn, user):
        self._require_admin(user)
        with conn.cursor() as cur:
            cur.execute("SELECT slug, title, show_in_nav, nav_label, nav_order, visible_roles FROM content_pages ORDER BY title")
            content_pages = list(cur.fetchall())

        def role_dropdown(form_id, current):
            # NULL/empty visible_roles means "everyone" (unset trips/old rows) -- show that as
            # every box checked, matching what a fresh page defaults to.
            current_keys = {k.strip() for k in (current or "").split(",") if k.strip()} or {k for k, _ in PAGE_ROLE_CHOICES}
            checkboxes = "".join(
                f'<label><input type="checkbox" name="visible_roles" form="{form_id}" value="{key}"'
                f'{" checked" if key in current_keys else ""}> {label}</label>'
                for key, label in PAGE_ROLE_CHOICES
            )
            return f"""<div class="role-dropdown">
              <button type="button" class="btn role-dropdown-toggle" style="padding:0.3em 0.6em;">Visible to &#9662;</button>
              <div class="role-dropdown-menu">{checkboxes}</div>
            </div>"""

        content_page_rows = "".join(
            f"""<tr>
              <td>
                <form id="page-nav-form-{p['slug']}" class="inline" method="post" action="/admin/pages/{p['slug']}/nav"></form>
                <a href="/pages/{p['slug']}">{html.escape(p['title'])}</a> <span class="muted">/pages/{p['slug']}</span></td>
              <td><input type="checkbox" name="show_in_nav" value="1" form="page-nav-form-{p['slug']}" style="width:auto;"{" checked" if p['show_in_nav'] else ""}></td>
              <td><input name="nav_label" form="page-nav-form-{p['slug']}" placeholder="{html.escape(p['title'])}" value="{html.escape(p['nav_label'] or '')}" style="width:140px;"></td>
              <td><input name="nav_order" form="page-nav-form-{p['slug']}" type="number" value="{p['nav_order']}" style="width:70px;"></td>
              <td>{role_dropdown(f"page-nav-form-{p['slug']}", p['visible_roles'])}</td>
              <td style="display:flex; gap:0.4em;">
                <button type="submit" form="page-nav-form-{p['slug']}" class="btn" style="padding:0.3em 0.7em;">Save</button>
                <a class="btn" style="padding:0.3em 0.7em;" href="/pages/{p['slug']}/edit">Edit</a>
                <form class="inline" method="post" action="/admin/pages/{p['slug']}/delete" onsubmit="return confirm('Delete the page \\'{html.escape(p['title'])}\\'? This can\\'t be undone.');">
                  <button type="submit" class="btn" style="padding:0.3em 0.7em; color:#b91c1c; border-color:#b91c1c;">Delete</button>
                </form>
              </td>
            </tr>"""
            for p in content_pages
        )

        body = f"""
        <p><a href="/admin">&larr; back to admin</a></p>
        <h1>Pages</h1>
        {self._admin_nav("/admin/pages")}
        <div class="card">
        <p class="muted">Admin-editable content pages (Markdown). Any page can optionally get a link in the
        site header -- set its label and where it sits in the link order below. "Visible to" restricts who can
        open the page at all.</p>
        <table>
          <tr><th>Page</th><th>In header</th><th>Link label</th><th>Order</th><th>Visible to</th><th></th></tr>
          {content_page_rows or '<tr><td colspan="6" class="muted">None yet.</td></tr>'}
        </table>
        <form method="post" action="/admin/pages" id="new-page-form" style="display:flex; gap:0.5em; margin-top:1em; flex-wrap:wrap; align-items:center;">
          <input name="title" id="new-page-title" placeholder="Page title, e.g. About Us" required style="flex:1; min-width:160px; width:auto;">
          <input name="slug" id="new-page-slug" placeholder="url-slug" required style="width:160px;">
          <label style="display:flex; align-items:center; gap:0.4em; font-weight:normal; width:auto;">
            <input type="checkbox" name="show_in_nav" value="1" style="width:auto;"> Show in header
          </label>
          <input name="nav_label" placeholder="Link label (optional)" style="width:160px;">
          {role_dropdown("new-page-form", None)}
          <button type="submit" class="btn-primary" style="flex:0 0 auto;">+ New page</button>
        </form>
        <script>
        document.getElementById('new-page-title').addEventListener('input', function() {{
          var slugField = document.getElementById('new-page-slug');
          if (slugField.dataset.touched) return;
          slugField.value = this.value.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
        }});
        document.getElementById('new-page-slug').addEventListener('input', function() {{ this.dataset.touched = '1'; }});
        </script>
        </div>
        """
        self._send_html(render_page("Pages", body, user))

    def handle_admin_members_page(self, conn, user):
        self._require_admin(user)
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, email, is_admin, is_treasurer, is_assessor, membership_expiry FROM users ORDER BY name")
            members = cur.fetchall()

        def role_label(m):
            roles = [
                r for r, held in (
                    ("Admin", m["is_admin"]), ("Treasurer", m["is_treasurer"]), ("Assessor", m["is_assessor"]),
                ) if held
            ]
            return ", ".join(roles) if roles else "User"
        member_rows = "".join(
            f"""<tr>
              <td>{html.escape(m['name'])}</td>
              <td>{html.escape(m['email'] or '')}</td>
              <td>{role_label(m)}</td>
              <td>{f"{m['membership_expiry']:%d %b %Y}" if m['membership_expiry'] else '<span class="muted">&mdash;</span>'}</td>
              <td style="white-space:nowrap;">
                {'' if m['id'] == user['id'] else f'''<form class="inline" method="post" action="/admin/users/{m['id']}/toggle-admin">
                  <button type="submit" class="btn" style="padding:0.3em 0.6em;">{"Revoke admin" if m['is_admin'] else "Grant admin"}</button>
                </form>'''}
                <form class="inline" method="post" action="/admin/users/{m['id']}/toggle-treasurer">
                  <button type="submit" class="btn" style="padding:0.3em 0.6em;">{"Revoke treasurer" if m['is_treasurer'] else "Grant treasurer"}</button>
                </form>
                <form class="inline" method="post" action="/admin/users/{m['id']}/toggle-assessor">
                  <button type="submit" class="btn" style="padding:0.3em 0.6em;">{"Revoke assessor" if m['is_assessor'] else "Grant assessor"}</button>
                </form>
              </td>
            </tr>"""
            for m in members
        )

        body = f"""
        <p><a href="/admin">&larr; back to admin</a></p>
        <h1>Members</h1>
        {self._admin_nav("/admin/members")}
        <p class="muted">{len(members)} member{'' if len(members) == 1 else 's'}</p>
        <div class="card" style="overflow-x:auto;">
        <table>
          <tr><th>Name</th><th>Email</th><th>Role</th><th>Membership expiry</th><th></th></tr>
          {member_rows}
        </table>
        </div>
        """
        self._send_html(render_page("Members", body, user))

    def handle_toggle_admin(self, conn, user, target_user_id):
        self._require_admin(user)
        with conn.cursor() as cur:
            cur.execute("SELECT is_admin FROM users WHERE id = %s", (target_user_id,))
            target = cur.fetchone()
            if target:
                cur.execute(
                    "UPDATE users SET is_admin = %s WHERE id = %s",
                    (0 if target["is_admin"] else 1, target_user_id),
                )
        redirect(self, "/admin/members")

    def handle_toggle_treasurer(self, conn, user, target_user_id):
        self._require_admin(user)
        with conn.cursor() as cur:
            cur.execute("SELECT is_treasurer FROM users WHERE id = %s", (target_user_id,))
            target = cur.fetchone()
            if target:
                cur.execute(
                    "UPDATE users SET is_treasurer = %s WHERE id = %s",
                    (0 if target["is_treasurer"] else 1, target_user_id),
                )
        redirect(self, "/admin/members")

    def handle_toggle_assessor(self, conn, user, target_user_id):
        self._require_admin(user)
        with conn.cursor() as cur:
            cur.execute("SELECT is_assessor FROM users WHERE id = %s", (target_user_id,))
            target = cur.fetchone()
            if target:
                cur.execute(
                    "UPDATE users SET is_assessor = %s WHERE id = %s",
                    (0 if target["is_assessor"] else 1, target_user_id),
                )
        redirect(self, "/admin/members")

    # -- skills assessment ----------------------------------------------------

    def handle_assess_page(self, conn, user):
        """Overview matrix of every member against every skill, so an
        assessor (or admin) can see who's acquired what at a glance, and do
        all their editing right here: a "Notes" column before the skill
        columns opens a dialog to edit that member's free-text notes, and
        every skill cell opens a dialog to toggle that skill for that
        member. Replaces the old per-member /users/<id>/skills page."""
        self._require_assessor(user)
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, skill_notes FROM users ORDER BY name")
            members = list(cur.fetchall())
            cur.execute("SELECT id, name FROM checklist_items WHERE kind = 'skill' ORDER BY name")
            skills = list(cur.fetchall())
            cur.execute(
                """
                SELECT us.user_id, us.checklist_item_id, us.assessed_at, a.name AS assessor_name
                FROM user_skills us JOIN users a ON a.id = us.assessor_id
                """
            )
            acquired = {(r["user_id"], r["checklist_item_id"]): r for r in cur.fetchall()}

        dialogs = []

        def notes_cell(m):
            dialog_id = f"notes-dialog-{m['id']}"
            preview = (m["skill_notes"] or "").strip()
            label = (preview[:24] + "&hellip;") if len(preview) > 24 else (html.escape(preview) if preview else "Add notes")
            dialogs.append(f"""
            <dialog id="{dialog_id}" style="border:none; border-radius:8px; padding:0; max-width:420px; width:90%;">
              <div class="card" style="margin:0; box-shadow:none; border:none;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                  <h3 style="margin:0;">Notes for {html.escape(m['name'])}</h3>
                  <button type="button" class="btn" onclick="document.getElementById('{dialog_id}').close()">&times;</button>
                </div>
                <form method="post" action="/users/{m['id']}/skill-notes">
                  <textarea name="skill_notes" rows="5" placeholder="Notes for assessors about this member's skills...">{html.escape(m['skill_notes'] or '')}</textarea>
                  <button type="submit" class="btn-primary">Save notes</button>
                </form>
              </div>
            </dialog>""")
            style = "text-align:left; max-width:160px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;"
            if not preview:
                style += " color:var(--fb-muted);"
            return f'<td><button type="button" class="btn" style="{style}" onclick="document.getElementById(\'{dialog_id}\').showModal()">{label}</button></td>'

        def skill_cell(m, s):
            entry = acquired.get((m["id"], s["id"]))
            dialog_id = f"skill-dialog-{m['id']}-{s['id']}"
            status_html = (
                f"Signed off by {html.escape(entry['assessor_name'])} on {entry['assessed_at']:%d %b %Y}"
                if entry else '<span class="muted">Not yet acquired</span>'
            )
            dialogs.append(f"""
            <dialog id="{dialog_id}" style="border:none; border-radius:8px; padding:0; max-width:380px; width:90%;">
              <div class="card" style="margin:0; box-shadow:none; border:none;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                  <h3 style="margin:0;">{html.escape(s['name'])}</h3>
                  <button type="button" class="btn" onclick="document.getElementById('{dialog_id}').close()">&times;</button>
                </div>
                <p class="muted">{html.escape(m['name'])}</p>
                <p>{status_html}</p>
                <form method="post" action="/users/{m['id']}/skills/{s['id']}/toggle">
                  <button type="submit" class="btn{' btn-primary' if not entry else ''}">{"Unmark" if entry else "Mark acquired"}</button>
                </form>
              </div>
            </dialog>""")
            if entry:
                return f'<td style="text-align:center;"><button type="button" class="btn" style="color:#15803d; padding:0.2em 0.6em;" title="{html.escape(status_html)}" onclick="document.getElementById(\'{dialog_id}\').showModal()">&#10003;</button></td>'
            return f'<td style="text-align:center;"><button type="button" class="btn" style="padding:0.2em 0.6em; color:var(--fb-muted);" onclick="document.getElementById(\'{dialog_id}\').showModal()">&mdash;</button></td>'

        header_cells = "".join(
            f'''<th style="height:140px; width:2em; vertical-align:bottom; padding-bottom:0.5em;">
              <div style="writing-mode:vertical-rl; transform:rotate(180deg); white-space:nowrap; margin:0 auto;">{html.escape(s["name"])}</div>
            </th>'''
            for s in skills
        )
        member_rows = "".join(
            f"""<tr>
              <td>{html.escape(m['name'])}</td>
              {notes_cell(m)}
              {"".join(skill_cell(m, s) for s in skills)}
            </tr>"""
            for m in members
        )
        body = f"""
        <p><a href="/">&larr; back to trips</a></p>
        <h1>Assess skills</h1>
        <p class="muted">Click a member's notes to edit them, or any cell to mark a skill acquired/not.</p>
        <div class="card" style="overflow-x:auto;">
        <table>
          <tr><th>Name</th><th>Notes</th>{header_cells}</tr>
          {member_rows or f'<tr><td colspan="{len(skills) + 2}" class="muted">No members yet.</td></tr>'}
        </table>
        </div>
        {"".join(dialogs)}
        """
        self._send_html(render_page("Assess skills", body, user))

    # -- ANU Sport membership sync --------------------------------------------

    def handle_anusport_sync_page(self, conn, user, result=None, error=None):
        self._require_admin(user)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT anusport_sync_enabled, anusport_sync_minutes, anusport_sync_next_at, "
                "anusport_sync_last_run_at, anusport_sync_last_summary, anusport_sync_send_emails "
                "FROM site_settings WHERE id = 1"
            )
            settings = cur.fetchone() or {}

        error_html = f'<p class="error">{html.escape(error)}</p>' if error else ""

        def person_row(p, extra=""):
            return f"""<tr><td>{html.escape(p['name'] or '')}</td><td class="muted">{html.escape(p['email'] or '')}</td><td>{extra}</td></tr>"""

        result_html = ""
        if result:
            updated_rows = "".join(
                person_row(u, f"{'New member' if u['is_new_member'] else 'Renewed'}: "
                               f"{u['previous_expiry'] or '&mdash;'} &rarr; {u['new_expiry']:%d %b %Y}"
                               f"{' (email sent)' if u['email_sent'] else ''}")
                for u in result["updated"]
            ) or '<tr><td colspan="3" class="muted">None</td></tr>'
            created_rows = "".join(
                person_row(c, f"Member until {c['new_expiry']:%d %b %Y}{' (email sent)' if c['email_sent'] else ''}")
                for c in result["created"]
            ) or '<tr><td colspan="3" class="muted">None</td></tr>'
            no_email_rows = "".join(
                person_row(p, f"ANU Sport ID: {html.escape(p['anusportid'] or '?')}") for p in result["no_email"]
            ) or '<tr><td colspan="3" class="muted">None</td></tr>'
            result_html = f"""
            <div class="card">
              <h3>Updated ({len(result['updated'])})</h3>
              <table><tr><th>Name</th><th>Email</th><th>Change</th></tr>{updated_rows}</table>
            </div>
            <div class="card">
              <h3>New accounts created ({len(result['created'])})</h3>
              <p class="muted">No password set yet &mdash; registering with the same email claims the account.</p>
              <table><tr><th>Name</th><th>Email</th><th></th></tr>{created_rows}</table>
            </div>
            <div class="card">
              <h3>Skipped, no email on file ({len(result['no_email'])})</h3>
              <p class="muted">Couldn't create an account for these without an email to identify them by.</p>
              <table><tr><th>Name</th><th>Email</th><th></th></tr>{no_email_rows}</table>
            </div>"""

        enabled = bool(settings.get("anusport_sync_enabled"))
        send_emails_default = bool(settings.get("anusport_sync_send_emails"))
        minutes = settings.get("anusport_sync_minutes") or 1440
        last_run_at = settings.get("anusport_sync_last_run_at")
        last_summary = settings.get("anusport_sync_last_summary")

        body = f"""
        <p><a href="/admin">&larr; back to admin</a></p>
        <h1>ANU Sport membership sync</h1>
        {error_html}

        <div class="card">
        <h3>Run now</h3>
        <p class="muted">Fetches the caving club's Orders/Users exports from ANU Sport, updates membership_expiry
        for matching accounts, and creates a new account for anyone unmatched with a known email.
        Takes a little while &mdash; ANU Sport's export can take a minute or two to generate.</p>
        <form method="post" action="/admin/anusport-sync/run" id="anusport-sync-run-form">
          <label><input type="checkbox" name="send_emails" value="1" style="width:auto;"> Send renewal/welcome emails for this run</label>
          <button type="submit" class="btn-primary" id="anusport-sync-run-btn">
            <span id="anusport-sync-run-spinner" style="width:0.9em; height:0.9em; border:2px solid rgba(255,255,255,0.4); border-top-color:#fff; border-radius:50%; vertical-align:middle; margin-right:0.5em; animation:anusport-spin 0.7s linear infinite; display:none;"></span>
            <span id="anusport-sync-run-label">Sync now</span>
          </button>
        </form>
        <style>@keyframes anusport-spin {{ to {{ transform: rotate(360deg); }} }}</style>
        <script>
        document.getElementById('anusport-sync-run-form').addEventListener('submit', function() {{
          document.getElementById('anusport-sync-run-btn').disabled = true;
          document.getElementById('anusport-sync-run-spinner').style.display = 'inline-block';
          document.getElementById('anusport-sync-run-label').textContent = 'Syncing… this can take a minute or two';
        }});
        </script>
        </div>

        <div class="card">
        <h3>Automatic sync</h3>
        <form method="post" action="/admin/anusport-sync/settings">
          <label><input type="checkbox" name="enabled" value="1" style="width:auto;"{" checked" if enabled else ""}> Run automatically in the background</label>
          <label><input type="checkbox" name="send_emails" value="1" style="width:auto;"{" checked" if send_emails_default else ""}> Send renewal/welcome emails</label>
          <label>Interval (minutes)<input name="minutes" type="number" min="5" value="{minutes}"></label>
          <button type="submit" class="btn-primary">Save</button>
        </form>
        <p class="muted" style="margin-top:0.8em;">
          Last run: {last_run_at.strftime('%d %b %Y %H:%M') if last_run_at else 'never'}
          {f" &mdash; {html.escape(last_summary)}" if last_summary else ""}
        </p>
        <p class="muted">Renewal/creation emails are {"sent via SMTP" if config.SMTP_HOST else
        "currently just printed to the server log (SMTP_HOST isn't set)"}.</p>
        </div>

        {result_html}
        """
        self._send_html(render_page("ANU Sport sync", body, user))

    def handle_anusport_sync_run(self, conn, user, form):
        self._require_admin(user)
        send_emails = form.get("send_emails") == "1"
        try:
            result = anusport_sync.run_sync(conn, send_emails=send_emails)
            delivery = anusport_sync.deliver_report(result)
        except Exception as exc:
            return self.handle_anusport_sync_page(conn, user, error=str(exc))
        now = datetime.now()
        summary = f"{anusport_sync.summarize(result)} ({delivery})"
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE site_settings SET anusport_sync_last_run_at = %s, anusport_sync_last_summary = %s WHERE id = 1",
                (now, summary),
            )
        return self.handle_anusport_sync_page(conn, user, result=result)

    def handle_anusport_sync_settings_submit(self, conn, user, form):
        self._require_admin(user)
        enabled = 1 if form.get("enabled") == "1" else 0
        send_emails = 1 if form.get("send_emails") == "1" else 0
        try:
            minutes = max(5, int(form.get("minutes", "1440")))
        except ValueError:
            minutes = 1440
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE site_settings SET anusport_sync_enabled = %s, anusport_sync_minutes = %s, "
                "anusport_sync_send_emails = %s, anusport_sync_next_at = NOW() WHERE id = 1",
                (enabled, minutes, send_emails),
            )
        redirect(self, "/admin/anusport-sync")

    def handle_user_skill_toggle(self, conn, user, target_user_id, checklist_item_id):
        self._require_assessor(user)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM user_skills WHERE user_id = %s AND checklist_item_id = %s",
                (target_user_id, checklist_item_id),
            )
            if cur.fetchone():
                cur.execute(
                    "DELETE FROM user_skills WHERE user_id = %s AND checklist_item_id = %s",
                    (target_user_id, checklist_item_id),
                )
            else:
                cur.execute(
                    "INSERT INTO user_skills (user_id, checklist_item_id, assessor_id) VALUES (%s, %s, %s)",
                    (target_user_id, checklist_item_id, user["id"]),
                )
        redirect(self, "/assess")

    def handle_user_skill_notes_submit(self, conn, user, target_user_id, form):
        self._require_assessor(user)
        skill_notes = form.get("skill_notes", "").strip() or None
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET skill_notes = %s WHERE id = %s", (skill_notes, target_user_id))
        redirect(self, "/assess")

    def handle_banner_submit(self, conn, user, form):
        self._require_admin(user)
        data_url = form.get("banner_data", "").strip()
        if data_url:
            try:
                banner_url = self._save_data_url_image(data_url, "site", "banner")
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO site_settings (id, banner_url) VALUES (1, %s) "
                        "ON DUPLICATE KEY UPDATE banner_url = VALUES(banner_url)",
                        (banner_url,),
                    )
            except ValueError:
                pass
        redirect(self, "/admin/site")

    def handle_distance_formula_submit(self, conn, user, form):
        self._require_admin(user)
        expr = form.get("distance_formula", "").strip()
        try:
            formula.validate(expr)
        except formula.FormulaError as e:
            return self.handle_admin_site_page(conn, user, formula_error=str(e))

        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO site_settings (id, distance_formula) VALUES (1, %s) "
                "ON DUPLICATE KEY UPDATE distance_formula = VALUES(distance_formula)",
                (expr,),
            )
        redirect(self, "/admin/site")

    def handle_bank_details_submit(self, conn, user, form):
        self._require_admin(user)
        logo_data_url = form.get("logo_data", "").strip()
        logo_url = None
        if logo_data_url:
            try:
                logo_url = self._save_data_url_image(logo_data_url, "site", "bank-logo")
            except ValueError:
                pass
        account_name = form.get("bank_account_name", "").strip()
        bsb = form.get("bank_bsb", "").strip()
        account_number = form.get("bank_account_number", "").strip()

        with conn.cursor() as cur:
            if logo_url:
                cur.execute(
                    "INSERT INTO site_settings (id, bank_account_name, bank_bsb, bank_account_number, bank_logo_url) "
                    "VALUES (1, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE "
                    "bank_account_name = VALUES(bank_account_name), bank_bsb = VALUES(bank_bsb), "
                    "bank_account_number = VALUES(bank_account_number), bank_logo_url = VALUES(bank_logo_url)",
                    (account_name, bsb, account_number, logo_url),
                )
            else:
                cur.execute(
                    "INSERT INTO site_settings (id, bank_account_name, bank_bsb, bank_account_number) "
                    "VALUES (1, %s, %s, %s) ON DUPLICATE KEY UPDATE "
                    "bank_account_name = VALUES(bank_account_name), bank_bsb = VALUES(bank_bsb), "
                    "bank_account_number = VALUES(bank_account_number)",
                    (account_name, bsb, account_number),
                )
        redirect(self, "/admin/site")

    def handle_gear_type_add(self, conn, user, form):
        self._require_admin(user)
        name = form.get("name", "").strip()
        rate_raw = form.get("rate", "").strip()
        description = form.get("description", "").strip() or None
        if name and rate_raw:
            try:
                rate = Decimal(rate_raw).quantize(Decimal("0.01"))
            except Exception:
                return redirect(self, "/admin/gear")
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT IGNORE INTO gear_types (name, rate, description) VALUES (%s, %s, %s)",
                    (name, str(rate), description),
                )
        redirect(self, "/admin/gear")

    def handle_gear_type_update(self, conn, user, gear_type_id, form):
        self._require_admin(user)
        name = form.get("name", "").strip()
        rate_raw = form.get("rate", "").strip()
        description = form.get("description", "").strip() or None
        if name and rate_raw:
            try:
                rate = Decimal(rate_raw).quantize(Decimal("0.01"))
            except Exception:
                return redirect(self, "/admin/gear")
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE gear_types SET name = %s, rate = %s, description = %s WHERE id = %s",
                    (name, str(rate), description, gear_type_id),
                )
        redirect(self, "/admin/gear")

    def handle_gear_type_delete(self, conn, user, gear_type_id):
        self._require_admin(user)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM gear_types WHERE id = %s", (gear_type_id,))
        redirect(self, "/admin/gear")

    def _get_checklist_items(self, conn):
        """The club-wide catalog of required skills/items a trip leader can
        pick from when building a trip's checklist (see
        event_checklist_items), managed by an admin."""
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, kind FROM checklist_items ORDER BY kind, name")
            return list(cur.fetchall())

    def _render_checklist_form_section(self, catalog_checklist_items, required_ids, dom_id="checklist"):
        """"Required skills & items" widget embedded in the trip create/edit
        form and the trip-detail checklist dialog: the trip's current
        selections as a removable chip list, with an "Add" button that
        either picks an existing club-wide catalog entry (a <select>, kept
        in sync so an already-added one can't be picked twice) or types a
        brand new one (added to the catalog on save, parsed by
        _parse_checklist_form_submission). `dom_id` must be unique if more
        than one of these widgets is ever rendered on the same page."""
        required_ids = set(required_ids)
        selected = [c for c in catalog_checklist_items if c["id"] in required_ids]
        unselected = [c for c in catalog_checklist_items if c["id"] not in required_ids]

        chips_html = "".join(
            f"""<span class="checklist-chip" data-id="{c['id']}" style="display:inline-flex; align-items:center; gap:0.4em; background:#e4e6eb; border-radius:14px; padding:0.3em 0.7em; font-size:0.9em;">
                <input type="hidden" name="checklist_item_ids" value="{c['id']}">
                {("&#129497; " if c['kind'] == 'skill' else "&#127890; ")}{html.escape(c['name'])}
                <button type="button" class="checklist-chip-remove" style="border:none; background:none; cursor:pointer; font-size:1.1em; line-height:1; padding:0;">&times;</button>
              </span>"""
            for c in selected
        )
        catalog_options = "".join(
            f'<option value="{c["id"]}" data-kind="{c["kind"]}" data-name="{html.escape(c["name"])}">'
            f'{"Skill" if c["kind"] == "skill" else "Item"}: {html.escape(c["name"])}</option>'
            for c in unselected
        )

        return f"""
          <label>Required skills &amp; items <a href="/pages/skills" style="font-weight:normal; font-size:0.85em;">(what do these mean?)</a></label>
          <div id="{dom_id}-list" style="display:flex; flex-wrap:wrap; gap:0.4em; margin-bottom:0.6em;">{chips_html}</div>
          <div style="display:flex; gap:0.5em; margin-bottom:0.4em; flex-wrap:wrap;">
            <select id="{dom_id}-catalog-select" style="flex:1; min-width:160px;">
              <option value="">Pick an existing skill/item&hellip;</option>
              {catalog_options}
            </select>
            <button type="button" id="{dom_id}-add-existing-btn" class="btn">Add</button>
          </div>
          <div style="display:flex; gap:0.5em; margin-bottom:0.9em; flex-wrap:wrap;">
            <input id="{dom_id}-custom-input" placeholder="Or type a new one" style="flex:1; min-width:160px;">
            <select id="{dom_id}-custom-kind" style="width:110px;">
              <option value="skill">Skill</option>
              <option value="item">Item</option>
            </select>
            <button type="button" id="{dom_id}-add-custom-btn" class="btn">Add new</button>
          </div>
          <script>
          (function() {{
            var list = document.getElementById('{dom_id}-list');
            var catalogSelect = document.getElementById('{dom_id}-catalog-select');
            var customInput = document.getElementById('{dom_id}-custom-input');
            var customKind = document.getElementById('{dom_id}-custom-kind');

            function makeChip(label, kind, inputName, inputValue, catalogOption) {{
              var chip = document.createElement('span');
              chip.className = 'checklist-chip';
              chip.style.cssText = 'display:inline-flex; align-items:center; gap:0.4em; background:#e4e6eb; border-radius:14px; padding:0.3em 0.7em; font-size:0.9em;';
              var hidden = document.createElement('input');
              hidden.type = 'hidden';
              hidden.name = inputName;
              hidden.value = inputValue;
              chip.appendChild(hidden);
              chip.appendChild(document.createTextNode((kind === 'skill' ? '\\u{{1F9D7}} ' : '\\u{{1F392}} ') + label));
              var removeBtn = document.createElement('button');
              removeBtn.type = 'button';
              removeBtn.textContent = '\\u00d7';
              removeBtn.style.cssText = 'border:none; background:none; cursor:pointer; font-size:1.1em; line-height:1; padding:0;';
              removeBtn.addEventListener('click', function() {{
                chip.remove();
                if (catalogOption) catalogOption.disabled = false;
              }});
              chip.appendChild(removeBtn);
              list.appendChild(chip);
            }}

            document.getElementById('{dom_id}-add-existing-btn').addEventListener('click', function() {{
              var opt = catalogSelect.options[catalogSelect.selectedIndex];
              if (!opt || !opt.value) return;
              makeChip(opt.dataset.name, opt.dataset.kind, 'checklist_item_ids', opt.value, opt);
              opt.disabled = true;
              catalogSelect.value = '';
            }});

            document.getElementById('{dom_id}-add-custom-btn').addEventListener('click', function() {{
              var name = customInput.value.trim();
              if (!name) return;
              var kind = customKind.value;
              makeChip(name, kind, kind === 'skill' ? 'new_skill_names' : 'new_item_names', name, null);
              customInput.value = '';
            }});
          }})();
          </script>
        """

    def _parse_checklist_form_submission(self, conn, form):
        """Combines the checked existing catalog ids with any brand-new
        skill/item names added via the create/edit form's "Add new" button
        -- new names are added to the club-wide checklist_items catalog (so
        they're available for other trips too) and included in the
        returned id set."""
        checklist_item_ids = {int(v) for v in form.getlist("checklist_item_ids")}
        with conn.cursor() as cur:
            for field, kind in (("new_skill_names", "skill"), ("new_item_names", "item")):
                for name in form.getlist(field):
                    name = name.strip()
                    if not name:
                        continue
                    cur.execute("INSERT IGNORE INTO checklist_items (name, kind) VALUES (%s, %s)", (name, kind))
                    cur.execute("SELECT id FROM checklist_items WHERE name = %s AND kind = %s", (name, kind))
                    row = cur.fetchone()
                    if row:
                        checklist_item_ids.add(row["id"])
        return checklist_item_ids

    def _save_event_checklist(self, conn, event_id, checklist_item_ids):
        with conn.cursor() as cur:
            cur.execute("DELETE FROM event_checklist_items WHERE event_id = %s", (event_id,))
            if checklist_item_ids:
                cur.executemany(
                    "INSERT INTO event_checklist_items (event_id, checklist_item_id) VALUES (%s, %s)",
                    [(event_id, cid) for cid in checklist_item_ids],
                )

    def handle_checklist_item_add(self, conn, user, form):
        self._require_admin(user)
        name = form.get("name", "").strip()
        kind = form.get("kind", "").strip()
        if name and kind in ("skill", "item"):
            with conn.cursor() as cur:
                cur.execute("INSERT IGNORE INTO checklist_items (name, kind) VALUES (%s, %s)", (name, kind))
        redirect(self, "/admin/checklist-items")

    def handle_checklist_item_delete(self, conn, user, checklist_item_id):
        self._require_admin(user)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM checklist_items WHERE id = %s", (checklist_item_id,))
        redirect(self, "/admin/checklist-items")

    # -- content pages (admin-editable, CKEditor) -----------------------------

    def _get_content_page(self, conn, slug):
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM content_pages WHERE slug = %s", (slug,))
            return cur.fetchone()

    def handle_content_page(self, conn, user, slug):
        """Public: any admin-editable reference page (e.g. the club's skill
        levels writeup), viewable by anyone, editable by an admin. Content
        is written in Markdown (see markdown.py) and rendered to HTML here."""
        page = self._get_content_page(conn, slug)
        if not page:
            return self._send_html(render_page("Not found", "<h1>Page not found</h1>", user), status=404)
        if not _page_visible_to(page, user):
            if not user:
                raise PermissionErrorRedirect("/login")
            return self._send_html(render_page("Forbidden", "<h1>You don't have access to this page.</h1>", user), status=403)
        edit_link = f'<a class="btn" href="/pages/{slug}/edit">Edit page</a>' if user and user.get("is_admin") else ""
        body = f"""
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.6em;">
          <h1 style="margin:0;">{html.escape(page['title'])}</h1>
          {edit_link}
        </div>
        <p class="muted">Last updated {page['updated_at']:%d %b %Y}</p>
        <div class="card description-body">{markdown.render(page['content_markdown'])}</div>
        """
        self._send_html(render_page(page["title"], body, user))

    def handle_content_page_edit_form(self, conn, user, slug):
        self._require_admin(user)
        page = self._get_content_page(conn, slug)
        if not page:
            return self._send_html(render_page("Not found", "<h1>Page not found</h1>", user), status=404)
        body = f"""
        <p><a href="/pages/{slug}">&larr; back to {html.escape(page['title'])}</a></p>
        <div class="card">
        <h1>Edit: {html.escape(page['title'])}</h1>
        <form method="post" action="/pages/{slug}/edit">
          <label>Title<input name="title" value="{html.escape(page['title'])}" required></label>
          <label>Content (Markdown)
            <div style="display:flex; gap:0.5em; margin-bottom:0.4em;">
              <input type="file" id="page-image-file" accept="image/*" style="flex:1;">
              <span id="page-image-status" class="muted"></span>
            </div>
            <textarea name="content_markdown" id="content-markdown" rows="26"
                      style="font-family:monospace; font-size:0.9em;">{html.escape(page['content_markdown'])}</textarea>
          </label>
          <p class="muted" style="margin-top:-0.6em;">Headings with <code>#</code>/<code>##</code>, <code>**bold**</code>,
          <code>*italic*</code>, <code>[link](url)</code>, <code>![alt](url)</code> for images, and <code>- item</code>
          bullet lists. Uploading a file above inserts its <code>![]()</code> markdown at the cursor.</p>
          <button type="submit" class="btn-primary">Save</button>
          <a class="btn" href="/pages/{slug}">Discard</a>
        </form>
        </div>
        <script>
        (function() {{
          var textarea = document.getElementById('content-markdown');
          var fileInput = document.getElementById('page-image-file');
          var status = document.getElementById('page-image-status');

          function insertAtCursor(text) {{
            var start = textarea.selectionStart, end = textarea.selectionEnd;
            textarea.value = textarea.value.slice(0, start) + text + textarea.value.slice(end);
            var pos = start + text.length;
            textarea.focus();
            textarea.setSelectionRange(pos, pos);
          }}

          fileInput.addEventListener('change', function() {{
            var file = this.files[0];
            if (!file) return;
            status.textContent = 'Uploading...';
            var reader = new FileReader();
            reader.onload = function(e) {{
              fetch('/pages/{slug}/upload-image', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                body: 'image_data=' + encodeURIComponent(e.target.result)
              }}).then(function(r) {{ return r.json(); }}).then(function(data) {{
                if (data.url) {{
                  insertAtCursor('![' + file.name.replace(/\\.[^.]+$/, '') + '](' + data.url + ')\\n');
                  status.textContent = 'Inserted.';
                }} else {{
                  status.textContent = 'Upload failed.';
                }}
              }}).catch(function() {{ status.textContent = 'Upload failed.'; }});
            }};
            reader.readAsDataURL(file);
          }});
        }})();
        </script>
        """
        self._send_html(render_page(f"Edit: {page['title']}", body, user))

    def handle_content_page_edit_submit(self, conn, user, slug, form):
        self._require_admin(user)
        title = form.get("title", "").strip()
        content_markdown = form.get("content_markdown", "")
        if not title:
            return redirect(self, f"/pages/{slug}/edit")
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE content_pages SET title = %s, content_markdown = %s WHERE slug = %s",
                (title, content_markdown, slug),
            )
        _refresh_nav_links_cache(conn)  # a title change can affect the header link's fallback label
        redirect(self, f"/pages/{slug}")

    def _parse_visible_roles(self, form):
        valid_keys = {key for key, _ in PAGE_ROLE_CHOICES}
        selected = [v for v in form.getlist("visible_roles") if v in valid_keys]
        return ",".join(selected) or None

    def handle_admin_page_create(self, conn, user, form):
        self._require_admin(user)
        title = form.get("title", "").strip()
        slug = form.get("slug", "").strip().lower()
        slug = re.sub(r"[^a-z0-9-]+", "-", slug).strip("-")
        show_in_nav = 1 if form.get("show_in_nav") == "1" else 0
        nav_label = form.get("nav_label", "").strip() or None
        visible_roles = self._parse_visible_roles(form)
        if title and slug:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT IGNORE INTO content_pages (slug, title, content_markdown, show_in_nav, nav_label, visible_roles) "
                    "VALUES (%s, %s, '', %s, %s, %s)",
                    (slug, title, show_in_nav, nav_label, visible_roles),
                )
            _refresh_nav_links_cache(conn)
            if show_in_nav:
                return redirect(self, f"/pages/{slug}/edit")
        redirect(self, "/admin/pages")

    def handle_admin_page_nav_update(self, conn, user, slug, form):
        self._require_admin(user)
        show_in_nav = 1 if form.get("show_in_nav") == "1" else 0
        nav_label = form.get("nav_label", "").strip() or None
        nav_order_raw = form.get("nav_order", "").strip()
        nav_order = int(nav_order_raw) if nav_order_raw.lstrip("-").isdigit() else 0
        visible_roles = self._parse_visible_roles(form)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE content_pages SET show_in_nav = %s, nav_label = %s, nav_order = %s, visible_roles = %s WHERE slug = %s",
                (show_in_nav, nav_label, nav_order, visible_roles, slug),
            )
        _refresh_nav_links_cache(conn)
        redirect(self, "/admin/pages")

    def handle_admin_page_delete(self, conn, user, slug):
        self._require_admin(user)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM content_pages WHERE slug = %s", (slug,))
        _refresh_nav_links_cache(conn)
        redirect(self, "/admin/pages")

    def _send_image_upload_json(self, form, id_prefix):
        """Shared by every "upload an image, get a /static/... URL back as
        JSON" endpoint (the Markdown editor's inline uploader and the
        general-purpose admin image uploader)."""
        data_url = form.get("image_data", "")
        try:
            url = self._save_data_url_image(data_url, "pages", id_prefix)
        except ValueError:
            return self._send_html('{"error": "invalid image"}', status=400)
        payload = json.dumps({"url": url})
        encoded = payload.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def handle_content_page_image_upload(self, conn, user, slug, form):
        """Admin-only: uploads an image picked in the Markdown editor and
        returns its URL as JSON, for the editor's JS to insert as ![]()
        markdown at the cursor."""
        self._require_admin(user)
        self._send_image_upload_json(form, f"{slug}-{user['id']}")

    def handle_admin_image_upload(self, conn, user, form):
        """Admin-only: general-purpose image upload, independent of any one
        content page -- for grabbing a /static/pages/... URL to use
        anywhere (another page's Markdown, a trip description, etc)."""
        self._require_admin(user)
        self._send_image_upload_json(form, f"upload-{user['id']}")

    def handle_distance_formula_test(self, user):
        self._require_admin(user)
        query = parse_qs(urlparse(self.path).query)
        expr = query.get("formula", [""])[0]
        km_raw = query.get("km", [""])[0]
        try:
            km = float(km_raw)
            result = formula.evaluate(expr, km)
            payload = json.dumps({"result": round(result, 2)})
        except (formula.FormulaError, ValueError) as e:
            payload = json.dumps({"error": str(e)})
        encoded = payload.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    # -- accounting (club bank account reconciliation) -----------------------

    def handle_accounting_transactions_page(self, conn, user, error=None, success=None):
        self._require_treasurer(user)
        query = parse_qs(urlparse(self.path).query)
        if not success and not error:
            msg = query.get("msg", [""])[0]
            if msg == "deleted":
                success = "All bank transactions deleted."
            elif msg == "txn_deleted":
                success = "Transaction deleted."
            elif msg == "saved":
                count = query.get("count", [""])[0]
                success = f"Saved changes to {count} transaction(s)." if count else "Changes saved."
            elif msg == "imported":
                inserted = query.get("inserted", [""])[0]
                total = query.get("total", [""])[0]
                success = f"Imported {inserted} new transaction(s) out of {total} in the file."
            elif msg == "no_file":
                error = "Choose a CSV file first."
            elif msg == "bad_csv":
                error = "Couldn't parse that CSV."

        import_summary_rows = self._pending_import_summary.pop(user["id"], None)

        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM users ORDER BY name")
            all_users = list(cur.fetchall())
            cur.execute("SELECT id, description FROM ledger_entries ORDER BY entry_date DESC")
            all_ledger_entries = list(cur.fetchall())
            cur.execute(
                """
                SELECT b.id, b.txn_date, b.amount, b.description, b.user_id, b.ledger_entry_id,
                       u.name AS matched_user_name
                FROM bank_transactions b LEFT JOIN users u ON u.id = b.user_id
                """
            )
            all_txns = list(cur.fetchall())
            txns = sorted(all_txns, key=lambda t: t["txn_date"], reverse=True)

        def user_options(selected_id):
            opts = '<option value=""></option>'
            for u in all_users:
                opts += f'<option value="{u["id"]}" {"selected" if u["id"] == selected_id else ""}>{html.escape(u["name"])}</option>'
            return opts

        def ledger_options(selected_id):
            opts = '<option value="">&mdash;</option>'
            for le in all_ledger_entries:
                opts += f'<option value="{le["id"]}" {"selected" if le["id"] == selected_id else ""}>{html.escape(le["description"])}</option>'
            return opts

        def txn_row(t):
            return f"""<tr class="txn-row" data-search="{html.escape((t['description'] + ' ' + str(t['amount'])).lower())}">
              <td>{t['txn_date']:%d %b %Y}</td>
              <td>{html.escape(t['description'])}</td>
              <td class="{'owe-negative' if t['amount'] >= 0 else 'owe-positive'}">{money(t['amount'])}</td>
              <td>
                <select name="user_{t['id']}" style="min-width:150px;">{user_options(t['user_id'])}</select>
              </td>
              <td>
                <select name="ledger_{t['id']}" style="min-width:150px;">{ledger_options(t['ledger_entry_id'])}</select>
              </td>
              <td>
                <button type="submit" class="btn" style="padding:0.3em 0.7em; color:#b91c1c; border-color:#b91c1c;"
                        formaction="/accounting/transactions/{t['id']}/delete" formmethod="post"
                        onclick="return confirm('Delete this transaction? This can\'t be undone.');">Delete</button>
              </td>
            </tr>"""

        unmatched_txns = [t for t in txns if not t["user_id"] and not t["ledger_entry_id"]]
        matched_txns = [t for t in txns if t["user_id"] or t["ledger_entry_id"]]
        unmatched_rows = "".join(txn_row(t) for t in unmatched_txns)
        matched_rows = "".join(txn_row(t) for t in matched_txns)

        error_html = f'<p class="error">{html.escape(error)}</p>' if error else ""
        success_html = f'<p style="color:#15803d;">{html.escape(success)}</p>' if success else ""

        import_summary_dialog_html = ""
        if import_summary_rows:
            def summary_row(r):
                return f"""<tr>
                  <td style="white-space:nowrap;">{r['date']:%d %b %y}</td>
                  <td>{html.escape(r['description'])}</td>
                  <td style="text-align:right; white-space:nowrap;">{money(r['amount'])}</td>
                  <td>{html.escape(r['user_name']) if r['user_name'] else '<em class="muted">Unmatched</em>'}</td>
                </tr>"""

            summary_matched = [r for r in import_summary_rows if r["user_name"]]
            summary_unmatched = [r for r in import_summary_rows if not r["user_name"]]

            import_summary_dialog_html = f"""
            <dialog id="import-summary-dialog" style="border:none; border-radius:8px; padding:0; max-width:680px; width:90%;">
              <div class="card" style="margin:0; box-shadow:none; border:none;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                  <h3 style="margin:0;">Newly imported transactions</h3>
                  <button type="button" class="btn" onclick="document.getElementById('import-summary-dialog').close()">&times;</button>
                </div>
                <p class="muted">{len(import_summary_rows)} transaction(s) weren't already in the system. Here's how each was matched:</p>
                <div style="max-height:400px; overflow-y:auto;">
                {f'''<h4 style="margin-bottom:0.3em;">Matched ({len(summary_matched)})</h4>
                <table>
                  <tr><th>Date</th><th>Description</th><th style="text-align:right;">Amount</th><th>User</th></tr>
                  {"".join(summary_row(r) for r in summary_matched)}
                </table>''' if summary_matched else ''}
                {f'''<h4 style="margin-bottom:0.3em; margin-top:{'1em' if summary_matched else '0'};">Unmatched ({len(summary_unmatched)})</h4>
                <table>
                  <tr><th>Date</th><th>Description</th><th style="text-align:right;">Amount</th><th>User</th></tr>
                  {"".join(summary_row(r) for r in summary_unmatched)}
                </table>''' if summary_unmatched else ''}
                </div>
              </div>
            </dialog>
            <script>document.getElementById('import-summary-dialog').showModal();</script>
            """

        body = f"""
        {self._accounting_header("transactions")}
        {error_html}{success_html}

        <div class="card">
        <h3>Bank transactions</h3>
        <div style="display:flex; gap:0.6em; flex-wrap:wrap;">
          <button type="button" class="btn-primary" onclick="document.getElementById('import-dialog').showModal()">Import</button>
          <button type="button" class="btn" onclick="document.getElementById('import-paste-dialog').showModal()">Import (Paste)</button>
          <a class="btn" href="/accounting/export">Export</a>
          <form method="post" action="/accounting/transactions/delete-all"
                onsubmit="return confirm('WARNING: This will permanently delete ALL {len(all_txns)} bank transactions. This action is IRREVERSIBLE and cannot be undone. Export a backup first if you need one.\\n\\nAre you sure you want to continue?');">
            <button type="submit" class="btn" style="color:#b91c1c; border-color:#b91c1c;">Delete all transactions</button>
          </form>
        </div>
        </div>

        <dialog id="import-dialog" style="border:none; border-radius:8px; padding:0; max-width:460px; width:90%;">
          <div class="card" style="margin:0; box-shadow:none; border:none;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <h3 style="margin:0;">Import bank transactions</h3>
              <button type="button" class="btn" onclick="document.getElementById('import-dialog').close()">&times;</button>
            </div>
            <p class="muted">Upload the bank's CSV export (date, amount, description -- no header row; any extra
            columns are ignored). Importing is safe to repeat: transactions already in the system (matched on date,
            amount and description) are skipped.</p>
            <form method="post" action="/accounting/import" id="import-form">
              <input type="file" id="csv-file" accept=".csv,text/csv">
              <input type="hidden" name="csv_text" id="csv-text">
              <button type="submit" class="btn-primary">Import CSV</button>
            </form>
          </div>
        </dialog>

        <dialog id="import-paste-dialog" style="border:none; border-radius:8px; padding:0; max-width:520px; width:90%;">
          <div class="card" style="margin:0; box-shadow:none; border:none;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <h3 style="margin:0;">Import bank transactions (paste)</h3>
              <button type="button" class="btn" onclick="document.getElementById('import-paste-dialog').close()">&times;</button>
            </div>
            <p class="muted">Paste raw CSV text (date, amount, description -- no header row; any extra columns
            are ignored). Importing is safe to repeat: transactions already in the system (matched on date,
            amount and description) are skipped.</p>
            <form method="post" action="/accounting/import">
              <textarea name="csv_text" rows="10" placeholder="26/10/2026,17.39,Fast Transfer From..." required style="font-family:monospace; font-size:0.85em;"></textarea>
              <button type="submit" class="btn-primary">Import CSV</button>
            </form>
          </div>
        </dialog>

        {import_summary_dialog_html}

        <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <h3 style="margin:0;">Transactions</h3>
          <button type="submit" form="bulk-update-form" class="btn-primary">Save all changes</button>
        </div>
        <form method="get" action="/accounting/transactions" style="margin-bottom:0.8em;" onsubmit="return false;">
          <label style="display:inline-block;">Search
            <input type="text" id="txn-search" placeholder="Search description, amount..." style="min-width:260px;">
          </label>
        </form>
        <form method="post" action="/accounting/transactions/bulk-update" id="bulk-update-form">
        {f'''<h4 style="margin-bottom:0.3em;">Unmatched ({len(unmatched_txns)})</h4>
        <table>
          <tr><th>Date</th><th>Description</th><th>Amount</th><th>User</th><th>Ledger item</th><th></th></tr>
          {unmatched_rows}
        </table>''' if unmatched_txns else ''}
        {f'''<h4 style="margin-bottom:0.3em; margin-top:{'1.5em' if unmatched_txns else '0'};">Matched ({len(matched_txns)})</h4>
        <table>
          <tr><th>Date</th><th>Description</th><th>Amount</th><th>User</th><th>Ledger item</th><th></th></tr>
          {matched_rows}
        </table>''' if matched_txns else ''}
        </form>
        </div>

        <script>
        document.getElementById('txn-search').addEventListener('input', function() {{
          var q = this.value.trim().toLowerCase();
          document.querySelectorAll('.txn-row').forEach(function(row) {{
            row.style.display = !q || row.getAttribute('data-search').indexOf(q) !== -1 ? '' : 'none';
          }});
        }});
        </script>

        <script>
        document.getElementById('csv-file').addEventListener('change', function() {{
          var file = this.files[0];
          if (!file) return;
          var reader = new FileReader();
          reader.onload = function(e) {{
            document.getElementById('csv-text').value = e.target.result;
          }};
          reader.readAsText(file);
        }});
        </script>
        """
        self._send_html(render_page("Transactions", body, user))

    def handle_accounting_import(self, conn, user, form):
        self._require_treasurer(user)
        csv_text = form.get("csv_text", "")
        if not csv_text.strip():
            return redirect(self, "/accounting/transactions?msg=no_file")
        try:
            rows = bank_accounting.parse_combank_csv(csv_text)
        except bank_accounting.CsvParseError:
            return redirect(self, "/accounting/transactions?msg=bad_csv")

        inserted = 0
        imported_rows = []
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, bank_name_aliases FROM users WHERE bank_name_aliases IS NOT NULL AND bank_name_aliases <> ''")
            users_with_aliases = list(cur.fetchall())
            names_by_id = {u["id"]: u["name"] for u in users_with_aliases}
            for r in rows:
                matched_user_id = bank_accounting.match_user(r["description"], users_with_aliases)
                cur.execute(
                    "INSERT IGNORE INTO bank_transactions (txn_date, amount, description, user_id) "
                    "VALUES (%s, %s, %s, %s)",
                    (r["date"], r["amount"], r["description"], matched_user_id),
                )
                if cur.rowcount:
                    inserted += 1
                    imported_rows.append({
                        "date": r["date"],
                        "description": r["description"],
                        "amount": r["amount"],
                        "user_name": names_by_id.get(matched_user_id),
                    })

        if imported_rows:
            self._pending_import_summary[user["id"]] = imported_rows
        return redirect(self, f"/accounting/transactions?msg=imported&inserted={inserted}&total={len(rows)}")

    def handle_accounting_export(self, conn, user):
        self._require_treasurer(user)
        with conn.cursor() as cur:
            cur.execute("SELECT txn_date AS date, amount, description FROM bank_transactions ORDER BY txn_date")
            rows = cur.fetchall()
        csv_text = bank_accounting.to_csv(rows)
        encoded = csv_text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", 'attachment; filename="bank_transactions.csv"')
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def handle_accounting_bulk_update(self, conn, user, form):
        self._require_treasurer(user)
        txn_ids = set()
        for key in form.keys():
            m = re.fullmatch(r"user_(\d+)", key)
            if m:
                txn_ids.add(int(m.group(1)))

        with conn.cursor() as cur:
            for txn_id in txn_ids:
                user_id_raw = form.get(f"user_{txn_id}", "").strip()
                matched_user_id = int(user_id_raw) if user_id_raw else None
                ledger_id_raw = form.get(f"ledger_{txn_id}", "").strip()
                ledger_entry_id = int(ledger_id_raw) if ledger_id_raw else None
                cur.execute(
                    "UPDATE bank_transactions SET user_id = %s, ledger_entry_id = %s WHERE id = %s",
                    (matched_user_id, ledger_entry_id, txn_id),
                )
        return redirect(self, f"/accounting/transactions?msg=saved&count={len(txn_ids)}")

    def handle_accounting_delete_all(self, conn, user):
        self._require_treasurer(user)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM bank_transactions")
        return redirect(self, "/accounting/transactions?msg=deleted")

    def handle_accounting_delete_transaction(self, conn, user, txn_id):
        self._require_treasurer(user)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM bank_transactions WHERE id = %s", (txn_id,))
        return redirect(self, "/accounting/transactions?msg=txn_deleted")

    def _accounting_header(self, active):
        """Shared header for every Accounting page: a back-link to trips,
        the "Accounting" title, and the same row of section buttons, with
        whichever one is current highlighted -- so navigating between
        Member balances/Transactions/Ledger/Member bank names looks and
        behaves the same from anywhere in the module."""
        sections = [
            ("balances", "Member balances", "/accounting"),
            ("transactions", "Transactions", "/accounting/transactions"),
            ("ledger", "Ledger", "/accounting/ledger"),
            ("users", "Member bank names", "/accounting/users"),
        ]
        buttons = "".join(
            f'<a class="btn{" btn-primary" if key == active else ""}" href="{href}">{label}</a>'
            for key, label, href in sections
        )
        return f"""
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.6em;">
          <h1 style="margin:0;">Accounting</h1>
          <div style="display:flex; gap:0.6em; flex-wrap:wrap;">{buttons}</div>
        </div>
        """

    def handle_accounting_page(self, conn, user):
        """The main Accounting landing page: for each member, how much they
        owe/are owed across ALL trips combined, vs. how much has actually
        moved through the bank account for them -- the bank account is
        treated as one shared pool settling everyone's net position, not
        something that has to balance trip-by-trip. An overpayment on one
        trip naturally offsets an underpayment on another; a single
        transaction covering several trips just adds up normally. The raw
        transaction list/import/export lives on a separate page, reached via
        the "Transactions" button here."""
        self._require_treasurer(user)
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM users ORDER BY name")
            all_users = list(cur.fetchall())
            cur.execute("SELECT user_id, description, amount, created_at FROM event_fee_lodgements")
            lodgements_by_user = {}
            for row in cur.fetchall():
                lodgements_by_user.setdefault(row["user_id"], []).append(row)
            cur.execute(
                "SELECT user_id, txn_date, description, amount, created_at FROM bank_transactions WHERE user_id IS NOT NULL"
            )
            reconciled_by_user = {}
            for row in cur.fetchall():
                reconciled_by_user.setdefault(row["user_id"], []).append(row)
            cur.execute("SELECT user_id, entry_date, description, amount, created_at FROM ledger_entries WHERE user_id IS NOT NULL")
            ledger_by_user = {}
            for row in cur.fetchall():
                ledger_by_user.setdefault(row["user_id"], []).append(row)

        owed_items_by_user = {u["id"]: [] for u in all_users}
        # dated version of the same items, plus bank transactions, used to work out
        # which items make up the *current* balance (since it was last fully settled)
        dated_entries_by_user = {u["id"]: [] for u in all_users}
        for uid, rows in lodgements_by_user.items():
            if uid in owed_items_by_user:
                for row in rows:
                    owed_items_by_user[uid].append({"description": row["description"], "amount": row["amount"]})
                    dated_entries_by_user[uid].append({"sort_at": row["created_at"], "description": row["description"], "due": row["amount"]})
        # a ledger entry assigned to a member is always a reimbursement owed
        # to them (amount is stored positive -- what the club owes back),
        # so it contributes negatively to owe (owe negative = club owes them)
        for uid, entries in ledger_by_user.items():
            if uid in owed_items_by_user:
                for le in entries:
                    owed_items_by_user[uid].append({"description": le["description"], "amount": -le["amount"]})
                    dated_entries_by_user[uid].append({"sort_at": le["created_at"], "description": le["description"], "due": -le["amount"]})
        for uid, txns in reconciled_by_user.items():
            if uid in dated_entries_by_user:
                for t in txns:
                    dated_entries_by_user[uid].append({"sort_at": t["created_at"], "description": t["description"], "transaction": t["amount"]})

        def items_since_last_settled(uid):
            """Descriptions of every entry since this member's balance was
            last exactly 0, in the order they were actually recorded (not
            the user-entered date, which has no time of day and would tie
            for same-day entries) -- what currently makes up an "Owed by
            club" credit, for the copy-to-clipboard button."""
            entries = sorted(dated_entries_by_user.get(uid, []), key=lambda e: e["sort_at"])
            running = Decimal("0")
            last_zero_at = -1
            for i, e in enumerate(entries):
                running += e["due"] if "due" in e else -e["transaction"]
                if abs(running) < Decimal("0.01"):
                    last_zero_at = i
            return [e["description"] for e in entries[last_zero_at + 1:]]

        def balance_row(u):
            owed_items = owed_items_by_user[u["id"]]
            total_owed = sum((i["amount"] for i in owed_items), Decimal("0"))
            txns = sorted(reconciled_by_user.get(u["id"], []), key=lambda t: t["txn_date"])
            total_reconciled = sum((t["amount"] for t in txns), Decimal("0"))
            remaining = total_owed - total_reconciled

            if not owed_items and not txns:
                return ""  # no activity at all -- don't clutter the table
            if abs(remaining) < Decimal("0.01"):
                label, color = "Settled", "#15803d"
            elif remaining > 0:
                label, color = "Owes club", "#b91c1c"
            else:
                label, color = "Owed by club", "#1877f2"

            net_str = f"{abs(remaining):,.2f}"
            net_onclick = html.escape(
                f"navigator.clipboard.writeText({json.dumps(net_str)}); "
                f"showToast('Copied: ' + {json.dumps(net_str)}); "
                "this.textContent='\\u2705'; setTimeout(() => this.textContent='\\ud83d\\udccb', 1500);",
                quote=True,
            )
            net_copy_btn = (
                f'<button type="button" class="btn" title="Copy net amount" '
                f'style="padding:0.2em 0.5em; margin-left:0.5em; font-size:1em; line-height:1;" '
                f'onclick="{net_onclick}">&#128203;</button>'
            )

            copy_btn = ""
            if label == "Owed by club":
                items_str = " ".join(items_since_last_settled(u["id"]))
                onclick = html.escape(
                    f"navigator.clipboard.writeText({json.dumps(items_str)}); "
                    f"showToast('Copied: ' + {json.dumps(items_str)}); "
                    "this.textContent='\\u2705'; setTimeout(() => this.textContent='\\ud83d\\udccb', 1500);",
                    quote=True,
                )
                copy_btn = (
                    f'<button type="button" class="btn" title="Copy items since last settled" '
                    f'style="padding:0.2em 0.5em; margin-left:0.5em; font-size:1em; line-height:1;" '
                    f'onclick="{onclick}">&#128203;</button>'
                )

            return f"""<tr>
              <td><a href="/accounting/balances/{u['id']}">{html.escape(u['name'])}</a></td>
              <td style="color:{color}; font-weight:600;">{money(remaining)}{net_copy_btn}</td>
              <td style="color:{color}; font-weight:600;">{label}{copy_btn}</td>
            </tr>"""

        balance_rows = "".join(balance_row(u) for u in all_users)

        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, lodged_at FROM events WHERE lodged_at IS NOT NULL ORDER BY lodged_at DESC"
            )
            lodged_events = list(cur.fetchall())

        export_fees_dialog = ""
        if lodged_events:
            trip_checkboxes = "".join(
                f"""<label style="display:flex; align-items:center; gap:0.5em; font-weight:normal;">
                    <input type="checkbox" name="event_id" value="{e['id']}" checked style="width:auto; margin:0;">
                    {html.escape(e['title'])} <span class="muted">(lodged {e['lodged_at']:%d %b %Y})</span>
                  </label>"""
                for e in lodged_events
            )
            export_fees_dialog = f"""
            <dialog id="export-fees-dialog" style="border:none; border-radius:8px; padding:0; max-width:420px; width:90%;">
              <div class="card" style="margin:0; box-shadow:none; border:none;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                  <h3 style="margin:0;">Export fees</h3>
                  <button type="button" class="btn" onclick="document.getElementById('export-fees-dialog').close()">&times;</button>
                </div>
                <p class="muted">Exports every lodged amount (including any later reversal/revision from an
                amendment) for the selected trips, as a CSV: one row per member per trip entry.</p>
                <form method="get" action="/accounting/export-fees">
                  <div style="display:flex; flex-direction:column; gap:0.4em; margin-bottom:0.8em; max-height:300px; overflow-y:auto;">
                    {trip_checkboxes}
                  </div>
                  <button type="submit" class="btn-primary">Download CSV</button>
                </form>
              </div>
            </dialog>
            """

        body = f"""
        {self._accounting_header("balances")}
        <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <h3 style="margin:0;">Member balances</h3>
          {f'<button type="button" class="btn" onclick="document.getElementById(\'export-fees-dialog\').showModal()">Export fees&hellip;</button>' if lodged_events else ''}
        </div>
        <p class="muted">Each member's net position across all trips combined, reconciled against every bank
        transaction linked to them. A credit on one trip automatically offsets a debt on another; a single payment
        covering several trips is simply totalled. Click a name for their full history.</p>
        <table>
          <tr><th>Name</th><th>Net</th><th>Status</th></tr>
          {balance_rows or '<tr><td colspan="3" class="muted">No activity yet.</td></tr>'}
        </table>
        </div>
        {export_fees_dialog}
        """
        self._send_html(render_page("Accounting", body, user))

    def handle_accounting_export_fees(self, conn, user):
        """CSV export of lodged trip fees for the trips the treasurer
        picked in the "Export fees" dialog -- one row per
        event_fee_lodgements entry (so an amendment's reversal/revision
        pair both appear, same audit trail as the per-member balance
        history), grouped by trip. Columns: Trip, Member, Date,
        Description, Amount -- not the bank-transaction CSV format (date,
        amount, description) since this is a multi-trip, multi-member
        export, not something meant to be re-imported as transactions."""
        self._require_treasurer(user)
        query = parse_qs(urlparse(self.path).query)
        event_ids = [int(v) for v in query.get("event_id", []) if v.isdigit()]
        if not event_ids:
            return redirect(self, "/accounting")

        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT e.title AS trip, u.name AS member, l.created_at, l.description, l.amount
                FROM event_fee_lodgements l
                JOIN events e ON e.id = l.event_id
                JOIN users u ON u.id = l.user_id
                WHERE l.event_id IN ({','.join(['%s'] * len(event_ids))})
                ORDER BY e.title, u.name, l.created_at
                """,
                event_ids,
            )
            rows = cur.fetchall()

        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["Trip", "Member", "Date", "Description", "Amount"])
        for r in rows:
            writer.writerow([r["trip"], r["member"], r["created_at"].strftime("%d/%m/%Y"), r["description"], r["amount"]])
        encoded = out.getvalue().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", 'attachment; filename="trip_fees_export.csv"')
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def handle_accounting_user_balance_page(self, conn, user, target_user_id):
        """One member's full historical ledger: every trip they owed/were
        owed money for, interleaved chronologically with every bank
        transaction linked to them, with a running balance -- the same
        pooled-account model as the Member balances page, but showing the
        full trail of entries that add up to that member's current net
        position rather than just the totals."""
        self._require_treasurer(user)
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, email FROM users WHERE id = %s", (target_user_id,))
            target_user = cur.fetchone()
        if not target_user:
            return self._send_html(render_page("Not found", "<h1>Member not found</h1>", user), status=404)

        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, event_id, description, amount, created_at FROM event_fee_lodgements WHERE user_id = %s ORDER BY id",
                (target_user_id,),
            )
            lodgements = list(cur.fetchall())
            cur.execute(
                "SELECT txn_date, description, amount, created_at FROM bank_transactions WHERE user_id = %s",
                (target_user_id,),
            )
            txns = list(cur.fetchall())
            cur.execute(
                "SELECT entry_date, description, amount, created_at FROM ledger_entries WHERE user_id = %s",
                (target_user_id,),
            )
            ledger_entries = list(cur.fetchall())

        entries = []  # {date (displayed), description, due (Decimal or None), transaction (Decimal or None), sort_at, seq}
        # Sorted by sort_at (when the row was actually recorded -- created_at
        # for all three types), not by the user-entered "date" shown in the
        # table: a bank txn/ledger entry only carries a plain DATE (no time
        # of day), so two rows dated the same day but recorded hours apart
        # would otherwise tie and fall back to arbitrary query order. seq is
        # a final tiebreaker for the rare case even created_at ties
        # (lodgements are id-ordered, so a reversal always precedes its
        # matching revision).
        for lodgement in lodgements:
            entries.append({
                "date": lodgement["created_at"],
                "description": lodgement["description"],
                "event_id": lodgement["event_id"],
                "due": lodgement["amount"],
                "transaction": None,
                "sort_at": lodgement["created_at"],
                "seq": len(entries),
            })
        for le in ledger_entries:
            entries.append({
                "date": le["entry_date"],
                "description": f"Ledger: {le['description']}",
                "due": -le["amount"],
                "transaction": None,
                "sort_at": le["created_at"],
                "seq": len(entries),
            })
        for t in txns:
            entries.append({
                "date": t["txn_date"],
                "description": t["description"],
                "due": None,
                "transaction": t["amount"],
                "sort_at": t["created_at"],
                "seq": len(entries),
            })

        entries.sort(key=lambda e: (e["sort_at"], e["seq"]))

        rows = []
        running = Decimal("0")
        for e in entries:
            if e["due"] is not None:
                running += e["due"]
            else:
                running -= e["transaction"]
            description_html = (
                f'<a href="/events/{e["event_id"]}/contributions?from=accounting">{html.escape(e["description"])}</a>'
                if e.get("event_id") else html.escape(e["description"])
            )
            rows.append(f"""<tr>
              <td style="white-space:nowrap;">{e['date']:%d %b %Y}</td>
              <td>{description_html}</td>
              <td style="text-align:right; white-space:nowrap;">{money(-e['due']) if e['due'] is not None else ''}</td>
              <td style="text-align:right; white-space:nowrap;">{money(e['transaction']) if e['transaction'] is not None else ''}</td>
              <td style="text-align:right; white-space:nowrap; font-weight:600;">{money(-running)}</td>
            </tr>""")

        if abs(running) < Decimal("0.01"):
            status_label, status_color = "Settled", "#15803d"
        elif running > 0:
            status_label, status_color = "Owes club", "#b91c1c"
        else:
            status_label, status_color = "Owed by club", "#1877f2"

        body = f"""
        {self._accounting_header("balances")}
        <h1>{html.escape(target_user['name'])}</h1>
        <p class="muted">{html.escape(target_user['email'] or 'No login (guest account)')}</p>
        <div class="card">
        <p>Current balance: <strong style="color:{status_color};">{money(-running)}</strong>
        &mdash; <span style="color:{status_color}; font-weight:600;">{status_label}</span></p>
        <p class="muted">Due amounts (from trips) and bank transactions, interleaved chronologically. A negative
        balance means they owe the club; a positive balance means the club owes them.</p>
        <table>
          <tr><th>Date</th><th>Description</th><th style="text-align:right;">Due</th><th style="text-align:right;">Transaction</th><th style="text-align:right;">Balance</th></tr>
          {"".join(rows) or '<tr><td colspan="5" class="muted">No activity yet.</td></tr>'}
        </table>
        </div>
        """
        self._send_html(render_page(f"{target_user['name']} — balance", body, user))

    def handle_accounting_ledger_page(self, conn, user, error=None, success=None):
        """Club income/expenses that aren't tied to a member or a trip --
        gear purchases, external funding, etc. A bank transaction can
        optionally be linked to one of these (see the Transactions page's
        "Ledger item" column) to show it's been recognised."""
        self._require_treasurer(user)
        if not success and not error:
            query = parse_qs(urlparse(self.path).query)
            if query.get("msg", [""])[0] == "added":
                success = "Entry added."
            elif query.get("msg", [""])[0] == "saved":
                success = "Entry updated."
            elif query.get("msg", [""])[0] == "deleted":
                success = "Entry deleted."

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT le.*, u.name AS created_by_name, au.name AS assigned_user_name,
                       (SELECT COUNT(*) FROM bank_transactions b WHERE b.ledger_entry_id = le.id) AS linked_count
                FROM ledger_entries le
                LEFT JOIN users u ON u.id = le.created_by
                LEFT JOIN users au ON au.id = le.user_id
                ORDER BY le.entry_date DESC, le.id DESC
                """
            )
            entries = list(cur.fetchall())
            cur.execute("SELECT id, name FROM users ORDER BY name")
            all_users = list(cur.fetchall())

        total = sum((e["amount"] for e in entries), Decimal("0"))
        error_html = f'<p class="error">{html.escape(error)}</p>' if error else ""
        success_html = f'<p style="color:#15803d;">{html.escape(success)}</p>' if success else ""

        entry_rows = "".join(
            f"""<tr>
              <td style="white-space:nowrap;">{e['entry_date']:%d %b %Y}</td>
              <td>
                {f'<img src="{html.escape(e["image_url"])}" style="width:40px; height:40px; object-fit:cover; border-radius:4px; vertical-align:middle; margin-right:0.5em;">' if e.get('image_url') else ''}
                {html.escape(e['description'])}
                {f'<a href="{html.escape(e["external_link"])}" target="_blank" rel="noopener" style="margin-left:0.5em;">&#128279;</a>' if e.get('external_link') else ''}
              </td>
              <td class="owe-positive" style="white-space:nowrap;">{money(e['amount'])}</td>
              <td>{html.escape(e['assigned_user_name']) if e.get('assigned_user_name') else '<em class="muted">Unassigned</em>'}</td>
              <td class="muted">{html.escape(e['created_by_name']) if e.get('created_by_name') else ''}</td>
              <td class="muted">{e['linked_count']} linked</td>
              <td style="display:flex; gap:0.4em;">
                <a class="btn" style="padding:0.3em 0.7em;" href="/accounting/ledger/{e['id']}">View</a>
                <form class="inline" method="post" action="/accounting/ledger/{e['id']}/delete" onsubmit="return confirm('Delete this ledger entry? This can\\'t be undone.');">
                  <button type="submit" class="btn" style="padding:0.3em 0.7em; color:#b91c1c; border-color:#b91c1c;">Delete</button>
                </form>
              </td>
            </tr>"""
            for e in entries
        )

        add_form_body = self._render_ledger_form("/accounting/ledger", all_users)

        body = f"""
        {self._accounting_header("ledger")}
        <div style="display:flex; justify-content:flex-end; margin-bottom:0.8em;">
          <button type="button" class="btn-primary" onclick="document.getElementById('add-entry-dialog').showModal()">+ Add entry</button>
        </div>
        {error_html}{success_html}

        <div class="card">
        <p class="muted">Members who paid for something out of pocket (e.g. gear, with their own card) and are owed
        that amount back by the club. Link a bank transaction to one of these from the Transactions page once
        they've been paid back, to show it's been recognised.</p>
        <table>
          <tr><th>Date</th><th>Description</th><th>Reimbursement</th><th>Member</th><th>Added by</th><th></th><th></th></tr>
          {entry_rows or '<tr><td colspan="7" class="muted">No entries yet.</td></tr>'}
          <tr><th colspan="2" style="text-align:left;">Total</th><th>{money(total)}</th><th colspan="4"></th></tr>
        </table>
        </div>

        <dialog id="add-entry-dialog" style="border:none; border-radius:8px; padding:0; max-width:460px; width:90%;">
          <div class="card" style="margin:0; box-shadow:none; border:none;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <h3 style="margin:0;">Add ledger entry</h3>
              <button type="button" class="btn" onclick="document.getElementById('add-entry-dialog').close()">&times;</button>
            </div>
            {add_form_body}
          </div>
        </dialog>
        """
        self._send_html(render_page("Ledger", body, user))

    def handle_accounting_ledger_submit(self, conn, user, form):
        self._require_treasurer(user)
        entry_date = form.get("entry_date", "").strip()
        description = form.get("description", "").strip()
        amount_raw = form.get("amount", "").strip()
        external_link = form.get("external_link", "").strip() or None
        image_data = form.get("image_data", "").strip()
        user_id_raw = form.get("user_id", "").strip()
        assigned_user_id = int(user_id_raw) if user_id_raw else None

        if not entry_date or not description or not amount_raw or not assigned_user_id:
            return redirect(self, "/accounting/ledger")
        try:
            amount = Decimal(amount_raw).quantize(Decimal("0.01"))
        except Exception:
            return redirect(self, "/accounting/ledger")
        if amount <= 0:
            return redirect(self, "/accounting/ledger")

        image_url = None
        if image_data:
            try:
                image_url = self._save_data_url_image(image_data, "ledger", f"entry-{user['id']}")
            except ValueError:
                image_url = None

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ledger_entries (entry_date, description, amount, external_link, image_url, user_id, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (entry_date, description, str(amount), external_link, image_url, assigned_user_id, user["id"]),
            )
        return redirect(self, "/accounting/ledger?msg=added")

    def _render_ledger_form(self, action, all_users, entry=None):
        entry_date_val = f"{entry['entry_date']:%Y-%m-%d}" if entry else f"{datetime.now():%Y-%m-%d}"
        description_val = html.escape(entry["description"]) if entry else ""
        amount_val = entry["amount"] if entry else ""
        link_val = html.escape(entry.get("external_link") or "") if entry else ""
        image_val = html.escape(entry.get("image_url") or "") if entry else ""
        selected_user_id = entry.get("user_id") if entry else None

        user_options = ('<option value="" disabled selected hidden>Choose a member&hellip;</option>' if not selected_user_id else '') + "".join(
            f'<option value="{u["id"]}" {"selected" if u["id"] == selected_user_id else ""}>{html.escape(u["name"])}</option>'
            for u in all_users
        )

        return f"""
        <form method="post" action="{action}" id="ledger-form">
          <label>Date
            <div style="display:flex; align-items:center; gap:0.6em;">
              <input type="date" name="entry_date" id="ledger-date-input" required value="{entry_date_val}" style="flex:1;">
              <a href="#" id="ledger-date-today" style="white-space:nowrap;">Today</a>
            </div>
          </label>
          <label>Description<input name="description" required placeholder="e.g. New rope purchase" value="{description_val}"></label>
          <label>Reimbursement amount ($)<input type="number" step="0.01" min="0.01" name="amount" required placeholder="e.g. 120.00" value="{amount_val}"></label>
          <label>Purchased by member
            <select name="user_id" required>{user_options}</select>
          </label>
          <p class="muted" style="margin-top:-0.4em;">The member who paid for this out of pocket (e.g. with their own
          card) and is owed this amount back by the club.</p>
          <label>External link (optional)<input type="url" name="external_link" placeholder="https://..." value="{link_val}"></label>
          <label>Image (optional)<input type="file" id="ledger-image-file" accept="image/*"></label>
          <img id="ledger-image-preview" src="{image_val}" style="max-width:160px; border-radius:6px; display:{'block' if image_val else 'none'}; margin-bottom:0.6em;">
          <input type="hidden" name="image_data" id="ledger-image-data" value="{image_val}">
          <button type="submit" class="btn-primary">{"Save changes" if entry else "Add entry"}</button>
        </form>

        <script>
        function loadLedgerImageFile(file) {{
          if (!file) return;
          var reader = new FileReader();
          reader.onload = function(e) {{
            var img = new Image();
            img.onload = function() {{
              var MAX = 1000;
              var scale = Math.min(1, MAX / Math.max(img.width, img.height));
              var canvas = document.createElement('canvas');
              canvas.width = img.width * scale;
              canvas.height = img.height * scale;
              canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
              var dataUrl = canvas.toDataURL('image/jpeg', 0.8);
              document.getElementById('ledger-image-data').value = dataUrl;
              var preview = document.getElementById('ledger-image-preview');
              preview.src = dataUrl;
              preview.style.display = 'block';
            }};
            img.src = e.target.result;
          }};
          reader.readAsDataURL(file);
        }}

        document.getElementById('ledger-image-file').addEventListener('change', function() {{
          loadLedgerImageFile(this.files[0]);
        }});

        document.getElementById('ledger-date-today').addEventListener('click', function(e) {{
          e.preventDefault();
          var now = new Date();
          var yyyy = now.getFullYear();
          var mm = String(now.getMonth() + 1).padStart(2, '0');
          var dd = String(now.getDate()).padStart(2, '0');
          document.getElementById('ledger-date-input').value = yyyy + '-' + mm + '-' + dd;
        }});

        document.addEventListener('paste', function(e) {{
          var dialog = document.getElementById('add-entry-dialog');
          if (dialog && !dialog.open) return;
          var items = (e.clipboardData || window.clipboardData).items;
          for (var i = 0; i < items.length; i++) {{
            if (items[i].type.indexOf('image') !== -1) {{
              loadLedgerImageFile(items[i].getAsFile());
              e.preventDefault();
              break;
            }}
          }}
        }});
        </script>
        """

    def handle_accounting_ledger_detail_page(self, conn, user, entry_id):
        self._require_treasurer(user)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT le.*, u.name AS created_by_name, au.name AS assigned_user_name
                FROM ledger_entries le
                LEFT JOIN users u ON u.id = le.created_by
                LEFT JOIN users au ON au.id = le.user_id
                WHERE le.id = %s
                """,
                (entry_id,),
            )
            entry = cur.fetchone()
            if not entry:
                return self._send_html(render_page("Not found", "<h1>Ledger entry not found</h1>", user), status=404)
            cur.execute(
                "SELECT id, txn_date, description, amount FROM bank_transactions WHERE ledger_entry_id = %s ORDER BY txn_date",
                (entry_id,),
            )
            linked_txns = list(cur.fetchall())

        success_html = ""
        if parse_qs(urlparse(self.path).query).get("msg", [""])[0] == "saved":
            success_html = '<p style="color:#15803d;">Entry updated.</p>'

        linked_rows = "".join(
            f"""<tr>
              <td style="white-space:nowrap;">{t['txn_date']:%d %b %Y}</td>
              <td>{html.escape(t['description'])}</td>
              <td style="text-align:right; white-space:nowrap;">{money(t['amount'])}</td>
            </tr>"""
            for t in linked_txns
        )

        body = f"""
        {self._accounting_header("ledger")}
        <p><a href="/accounting/ledger">&larr; back to ledger</a></p>
        {success_html}
        <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
          <h1 style="margin:0;">{html.escape(entry['description'])}</h1>
          <a class="btn btn-primary" href="/accounting/ledger/{entry_id}/edit">Edit</a>
        </div>
        {f'<img src="{html.escape(entry["image_url"])}" style="max-width:320px; border-radius:8px; margin:1em 0; display:block;">' if entry.get('image_url') else ''}
        <table style="width:auto;">
          <tr><th style="text-align:left;">Date</th><td>{entry['entry_date']:%d %b %Y}</td></tr>
          <tr><th style="text-align:left;">Reimbursement amount</th><td class="owe-positive">{money(entry['amount'])}</td></tr>
          <tr><th style="text-align:left;">Purchased by</th><td>{html.escape(entry['assigned_user_name']) if entry.get('assigned_user_name') else '<em class="muted">Unassigned</em>'}</td></tr>
          <tr><th style="text-align:left;">Added by</th><td>{html.escape(entry['created_by_name']) if entry.get('created_by_name') else '<span class="muted">&mdash;</span>'}</td></tr>
          <tr><th style="text-align:left;">External link</th><td>{f'<a href="{html.escape(entry["external_link"])}" target="_blank" rel="noopener">{html.escape(entry["external_link"])}</a>' if entry.get('external_link') else '<span class="muted">&mdash;</span>'}</td></tr>
        </table>
        </div>

        <div class="card">
        <h3>Linked bank transactions</h3>
        <table>
          <tr><th>Date</th><th>Description</th><th style="text-align:right;">Amount</th></tr>
          {linked_rows or '<tr><td colspan="3" class="muted">None linked yet.</td></tr>'}
        </table>
        </div>
        """
        self._send_html(render_page(entry["description"], body, user))

    def handle_accounting_ledger_edit_form(self, conn, user, entry_id):
        self._require_treasurer(user)
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM ledger_entries WHERE id = %s", (entry_id,))
            entry = cur.fetchone()
            if not entry:
                return self._send_html(render_page("Not found", "<h1>Ledger entry not found</h1>", user), status=404)
            cur.execute("SELECT id, name FROM users ORDER BY name")
            all_users = list(cur.fetchall())

        form_body = self._render_ledger_form(f"/accounting/ledger/{entry_id}/edit", all_users, entry=entry)
        body = f"""
        {self._accounting_header("ledger")}
        <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <h1 style="margin:0;">Edit ledger entry</h1>
          <button type="button" class="btn" onclick="if (confirm('Discard your changes?')) window.location.href = '/accounting/ledger/{entry_id}';">&larr; Back</button>
        </div>
        {form_body}
        </div>
        """
        self._send_html(render_page("Edit ledger entry", body, user))

    def handle_accounting_ledger_edit_submit(self, conn, user, entry_id, form):
        self._require_treasurer(user)
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM ledger_entries WHERE id = %s", (entry_id,))
            entry = cur.fetchone()
        if not entry:
            return redirect(self, "/accounting/ledger")

        entry_date = form.get("entry_date", "").strip()
        description = form.get("description", "").strip()
        amount_raw = form.get("amount", "").strip()
        external_link = form.get("external_link", "").strip() or None
        image_data = form.get("image_data", "").strip()
        user_id_raw = form.get("user_id", "").strip()
        assigned_user_id = int(user_id_raw) if user_id_raw else None

        if not entry_date or not description or not amount_raw or not assigned_user_id:
            return redirect(self, f"/accounting/ledger/{entry_id}/edit")
        try:
            amount = Decimal(amount_raw).quantize(Decimal("0.01"))
        except Exception:
            return redirect(self, f"/accounting/ledger/{entry_id}/edit")
        if amount <= 0:
            return redirect(self, f"/accounting/ledger/{entry_id}/edit")

        image_url = entry.get("image_url")
        if image_data and image_data.startswith("data:image/"):
            try:
                image_url = self._save_data_url_image(image_data, "ledger", f"entry-{user['id']}")
            except ValueError:
                pass
        elif not image_data:
            image_url = None  # image cleared

        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ledger_entries
                SET entry_date = %s, description = %s, amount = %s, external_link = %s,
                    image_url = %s, user_id = %s
                WHERE id = %s
                """,
                (entry_date, description, str(amount), external_link, image_url, assigned_user_id, entry_id),
            )
        return redirect(self, f"/accounting/ledger/{entry_id}?msg=saved")

    def handle_accounting_ledger_delete(self, conn, user, entry_id):
        self._require_treasurer(user)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ledger_entries WHERE id = %s", (entry_id,))
        return redirect(self, "/accounting/ledger?msg=deleted")

    def handle_accounting_users_page(self, conn, user, success=None):
        self._require_treasurer(user)
        if not success:
            query = parse_qs(urlparse(self.path).query)
            if query.get("msg", [""])[0] == "saved":
                success = "Saved."
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, email, bank_name_aliases FROM users ORDER BY name")
            members = cur.fetchall()

        success_html = f'<p style="color:#15803d;">{html.escape(success)}</p>' if success else ""
        member_rows = "".join(
            f"""<tr>
              <td>{html.escape(m['name'])}</td>
              <td class="muted">{html.escape(m['email'] or '')}</td>
              <td>
                <input name="aliases_{m['id']}" value="{html.escape(m['bank_name_aliases'] or '')}"
                       placeholder="e.g. Andrew Kowalczyk, A Kowalczyk" style="min-width:260px;">
              </td>
            </tr>"""
            for m in members
        )

        body = f"""
        {self._accounting_header("users")}
        {success_html}
        <div class="card">
        <p class="muted">Comma-separated name(s) each member appears as in bank transaction descriptions
        (usually right after "From"/"To" in the bank's export). Used to auto-match imported transactions to them.</p>
        <form method="post" action="/accounting/users/bulk-update">
        <table>
          <tr><th>Name</th><th>Email</th><th>Bank transaction name(s)</th></tr>
          {member_rows}
        </table>
        <button type="submit" class="btn-primary" style="margin-top:1em;">Save all changes</button>
        </form>
        </div>
        """
        self._send_html(render_page("Member bank names", body, user))

    def handle_accounting_user_aliases_bulk_submit(self, conn, user, form):
        self._require_treasurer(user)
        member_ids = set()
        for key in form.keys():
            m = re.fullmatch(r"aliases_(\d+)", key)
            if m:
                member_ids.add(int(m.group(1)))

        with conn.cursor() as cur:
            for member_id in member_ids:
                aliases = form.get(f"aliases_{member_id}", "").strip() or None
                cur.execute("UPDATE users SET bank_name_aliases = %s WHERE id = %s", (aliases, member_id))

                # retroactively link any already-imported transactions that
                # are still unmatched but now match this newly-saved alias
                if aliases:
                    cur.execute("SELECT id, name, bank_name_aliases FROM users WHERE id = %s", (member_id,))
                    target_user = cur.fetchone()
                    cur.execute("SELECT id, description FROM bank_transactions WHERE user_id IS NULL")
                    for txn in cur.fetchall():
                        if bank_accounting.match_user(txn["description"], [target_user]):
                            cur.execute("UPDATE bank_transactions SET user_id = %s WHERE id = %s", (member_id, txn["id"]))

        return redirect(self, "/accounting/users?msg=saved")

    def handle_accounting_user_aliases_submit(self, conn, user, target_user_id, form):
        self._require_treasurer(user)
        aliases = form.get("bank_name_aliases", "").strip() or None
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET bank_name_aliases = %s WHERE id = %s", (aliases, target_user_id))

            # retroactively link any already-imported transactions that are
            # still unmatched but now match this newly-saved alias
            if aliases:
                cur.execute("SELECT id, name, bank_name_aliases FROM users WHERE id = %s", (target_user_id,))
                target_user = cur.fetchone()
                cur.execute("SELECT id, description FROM bank_transactions WHERE user_id IS NULL")
                for txn in cur.fetchall():
                    if bank_accounting.match_user(txn["description"], [target_user]):
                        cur.execute("UPDATE bank_transactions SET user_id = %s WHERE id = %s", (target_user_id, txn["id"]))

        return redirect(self, "/accounting/users?msg=saved")

    # -- profile ---------------------------------------------------------------

    def handle_profile_form(self, conn, user, error=None, success=None):
        self._require_login(user)
        error_html = f'<p class="error">{html.escape(error)}</p>' if error else ""
        success_html = f'<p style="color:#15803d;">{html.escape(success)}</p>' if success else ""
        current_pic = avatar(user["name"], user.get("profile_picture_url"), size=120)

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ci.name, us.assessed_at, a.name AS assessor_name
                FROM user_skills us
                JOIN checklist_items ci ON ci.id = us.checklist_item_id
                JOIN users a ON a.id = us.assessor_id
                WHERE us.user_id = %s ORDER BY ci.name
                """,
                (user["id"],),
            )
            acquired_skills = list(cur.fetchall())
        skills_html = (
            "<ul style=\"padding-left:1.2em; margin:0;\">" + "".join(
                f"""<li>{html.escape(s['name'])}
                    <span class="muted">&mdash; signed off by {html.escape(s['assessor_name'])} on {s['assessed_at']:%d %b %Y}</span></li>"""
                for s in acquired_skills
            ) + "</ul>"
        ) if acquired_skills else '<p class="muted">No skills signed off yet.</p>'

        membership_html = (
            f'<p>You\'re a current NUCC member, until <strong>{user["membership_expiry"]:%d %b %Y}</strong>.</p>'
            if user.get("membership_expiry")
            else '<p class="muted">You\'re not currently a NUCC member. Membership status is synced from ANU Sport.</p>'
        )

        body = f"""
        <div class="card" style="max-width:460px; margin:2em auto;">
        <h1>Your profile</h1>
        {error_html}{success_html}

        <div style="text-align:center; margin-bottom:1em;">
          <button type="button" id="avatar-trigger" title="Click to change your profile picture"
                  style="border:none; background:none; padding:0; cursor:pointer; border-radius:50%;">
            <span id="avatar-preview">{current_pic}</span>
          </button>
          <p class="muted" style="margin-top:0.3em;">Click your picture to change it.</p>
        </div>

        <form method="post" action="/profile" id="profile-form">
          <label>Name<input name="name" required value="{html.escape(user['name'])}"></label>
          <label>Email<input value="{html.escape(user['email'])}" disabled></label>

          <input type="hidden" name="profile_picture_data" id="profile_picture_data">

          <button type="submit" class="btn-primary">Save changes</button>
        </form>
        </div>

        <div class="card" style="max-width:460px; margin:0 auto 2em;">
        <h3>Membership</h3>
        {membership_html}
        </div>

        <div class="card" style="max-width:460px; margin:0 auto 2em;">
        <h3>Skills</h3>
        {skills_html}
        </div>

        <dialog id="picture-dialog" style="border:none; border-radius:8px; padding:0; max-width:340px; width:90%;">
          <div class="card" style="margin:0; box-shadow:none; border:none;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <h3 style="margin:0;">Change profile picture</h3>
              <button type="button" class="btn" id="picture-dialog-close">&times;</button>
            </div>

            <input type="file" id="picture-input" accept="image/*">
            <p class="muted" style="margin-top:-0.4em;">Tip: you can also just paste an image (Ctrl+V / Cmd+V).</p>

            <div id="cropper-wrap" style="display:none; margin:0.8em 0;">
              <div id="cropper-stage" style="position:relative; width:260px; height:260px; margin:0 auto; overflow:hidden; background:#000; border-radius:6px; touch-action:none;">
                <img id="cropper-image" style="position:absolute; left:0; top:0; max-width:none; cursor:grab;">
                <div style="position:absolute; inset:0; pointer-events:none; border-radius:50%; box-shadow:0 0 0 2000px rgba(255,255,255,0.75);"></div>
              </div>
              <label style="margin-top:0.6em;">Zoom
                <input type="range" id="cropper-zoom" min="100" max="300" value="100">
              </label>
              <p class="muted" style="text-align:center;">Drag the image to reposition it.</p>
              <button type="button" class="btn-primary" id="use-photo-btn" style="width:100%;">Use this photo</button>
            </div>
          </div>
        </dialog>

        <script>
        (function() {{
          var dialog = document.getElementById('picture-dialog');
          var avatarTrigger = document.getElementById('avatar-trigger');
          var avatarPreview = document.getElementById('avatar-preview');
          var fileInput = document.getElementById('picture-input');
          var wrap = document.getElementById('cropper-wrap');
          var stage = document.getElementById('cropper-stage');
          var img = document.getElementById('cropper-image');
          var zoomSlider = document.getElementById('cropper-zoom');
          var hiddenInput = document.getElementById('profile_picture_data');
          var form = document.getElementById('profile-form');

          avatarTrigger.addEventListener('click', function() {{ dialog.showModal(); }});
          document.getElementById('picture-dialog-close').addEventListener('click', function() {{ dialog.close(); }});

          var STAGE_SIZE = 260;
          var naturalW = 0, naturalH = 0, baseScale = 1;
          var pos = {{x: 0, y: 0}};
          var dragging = false, dragStart = {{x: 0, y: 0}}, posStart = {{x: 0, y: 0}};

          function applyTransform() {{
            var scale = baseScale * (zoomSlider.value / 100);
            img.style.width = (naturalW * scale) + 'px';
            img.style.height = (naturalH * scale) + 'px';
            img.style.left = pos.x + 'px';
            img.style.top = pos.y + 'px';
          }}

          function loadImageFile(file) {{
            if (!file) return;
            var reader = new FileReader();
            reader.onload = function(e) {{
              img.onload = function() {{
                naturalW = img.naturalWidth;
                naturalH = img.naturalHeight;
                baseScale = STAGE_SIZE / Math.min(naturalW, naturalH);
                pos.x = (STAGE_SIZE - naturalW * baseScale) / 2;
                pos.y = (STAGE_SIZE - naturalH * baseScale) / 2;
                zoomSlider.value = 100;
                applyTransform();
                wrap.style.display = 'block';
              }};
              img.src = e.target.result;
            }};
            reader.readAsDataURL(file);
          }}

          fileInput.addEventListener('change', function() {{
            loadImageFile(fileInput.files[0]);
          }});

          document.addEventListener('paste', function(e) {{
            var items = (e.clipboardData || window.clipboardData).items;
            for (var i = 0; i < items.length; i++) {{
              if (items[i].type.indexOf('image') !== -1) {{
                if (!dialog.open) dialog.showModal();
                loadImageFile(items[i].getAsFile());
                e.preventDefault();
                break;
              }}
            }}
          }});

          zoomSlider.addEventListener('input', applyTransform);

          function startDrag(x, y) {{
            dragging = true;
            dragStart = {{x: x, y: y}};
            posStart = {{x: pos.x, y: pos.y}};
          }}
          function moveDrag(x, y) {{
            if (!dragging) return;
            pos.x = posStart.x + (x - dragStart.x);
            pos.y = posStart.y + (y - dragStart.y);
            applyTransform();
          }}
          stage.addEventListener('mousedown', function(e) {{ startDrag(e.clientX, e.clientY); }});
          window.addEventListener('mousemove', function(e) {{ moveDrag(e.clientX, e.clientY); }});
          window.addEventListener('mouseup', function() {{ dragging = false; }});
          stage.addEventListener('touchstart', function(e) {{
            var t = e.touches[0]; startDrag(t.clientX, t.clientY);
          }});
          window.addEventListener('touchmove', function(e) {{
            if (!dragging) return;
            var t = e.touches[0]; moveDrag(t.clientX, t.clientY);
          }});
          window.addEventListener('touchend', function() {{ dragging = false; }});

          document.getElementById('use-photo-btn').addEventListener('click', function() {{
            if (wrap.style.display === 'none') return; // no new picture chosen
            var scale = baseScale * (zoomSlider.value / 100);
            var canvas = document.createElement('canvas');
            var OUT = 300;
            canvas.width = OUT;
            canvas.height = OUT;
            var ctx = canvas.getContext('2d');
            ctx.beginPath();
            ctx.arc(OUT / 2, OUT / 2, OUT / 2, 0, Math.PI * 2);
            ctx.closePath();
            ctx.clip();
            var sx = -pos.x / scale;
            var sy = -pos.y / scale;
            var sSize = STAGE_SIZE / scale;
            ctx.drawImage(img, sx, sy, sSize, sSize, 0, 0, OUT, OUT);
            var dataUrl = canvas.toDataURL('image/png');
            hiddenInput.value = dataUrl;
            avatarPreview.innerHTML = '<img class="avatar" src="' + dataUrl + '" style="width:120px;height:120px;object-fit:cover;">';
            dialog.close();
          }});
        }})();
        </script>
        """
        self._send_html(render_page("Your profile", body, user))

    @staticmethod
    def _save_data_url_image(data_url, subdir, id_prefix):
        """Decodes a data:image/... URL and saves it under static/<subdir>/.
        Returns the public /static/... URL, or raises ValueError on bad input."""
        if not data_url.startswith("data:image/"):
            raise ValueError("not a data: image URL")
        header, b64data = data_url.split(",", 1)
        ext = "png" if "png" in header else "jpg"
        raw = base64.b64decode(b64data)
        target_dir = os.path.join(STATIC_DIR, subdir)
        os.makedirs(target_dir, exist_ok=True)
        filename = f"{id_prefix}-{uuid.uuid4().hex[:8]}.{ext}"
        with open(os.path.join(target_dir, filename), "wb") as f:
            f.write(raw)
        return f"/static/{subdir}/{filename}"

    def handle_profile_submit(self, conn, user, form):
        self._require_login(user)
        name = form.get("name", "").strip()
        if not name:
            return self.handle_profile_form(conn, user, error="Name can't be empty.")

        picture_url = user.get("profile_picture_url")
        data_url = form.get("profile_picture_data", "").strip()
        if data_url:
            try:
                picture_url = self._save_data_url_image(data_url, "avatars", user["id"])
            except Exception:
                return self.handle_profile_form(conn, user, error="Couldn't process that image, please try a different one.")

        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET name = %s, profile_picture_url = %s WHERE id = %s",
                (name, picture_url, user["id"]),
            )
        user = dict(user)
        user["name"] = name
        user["profile_picture_url"] = picture_url
        self.handle_profile_form(conn, user, success="Profile updated.")

    # -- events ---------------------------------------------------------------

    def handle_events_list(self, conn, user):
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.*, u.name AS host_name, u.profile_picture_url AS host_picture,
                       (SELECT COUNT(*) FROM event_signups s WHERE s.event_id = e.id AND s.status = 'approved') AS approved_count
                FROM events e
                JOIN users u ON u.id = e.host_id
                ORDER BY e.date_start ASC
                """
            )
            events = cur.fetchall()
            cur.execute("SELECT banner_url FROM site_settings WHERE id = 1")
            settings_row = cur.fetchone()
            if user:
                cur.execute("SELECT event_id, status FROM event_signups WHERE user_id = %s", (user["id"],))
                my_status_by_event = {r["event_id"]: r["status"] for r in cur.fetchall()}
            else:
                my_status_by_event = {}
        banner_url = (settings_row or {}).get("banner_url") or "/static/banner.jpg"

        now = datetime.now()
        upcoming_events = [e for e in events if e["date_end"] >= now]
        past_events = sorted((e for e in events if e["date_end"] < now), key=lambda e: e["date_start"], reverse=True)

        def render_row(e, show_actions):
            limit_text = f"{e['approved_count']} / {e['participant_limit']} going" if e["participant_limit"] else f"{e['approved_count']} going"
            location_display, _, _ = location_info(e["location"], e.get("location_label"))
            if location_display == "View location on Google Maps":
                location_display = ""
            picture = (
                f'<img class="thumb" src="{html.escape(e["picture_url"])}">'
                if e.get("picture_url")
                else '<div class="thumb"></div>'
            )

            actions = ""
            if show_actions:
                if not user:
                    going_btn = '<a class="btn btn-primary" href="/login">Log in to join</a>'
                    leave_btn = ""
                else:
                    status = my_status_by_event.get(e["id"])
                    if e["host_id"] == user["id"] or status == "approved":
                        going_btn = '<button type="button" class="btn-primary" disabled>&check; Going</button>'
                    elif status == "pending":
                        going_btn = '<button type="button" class="btn" disabled>Pending</button>'
                    else:
                        going_btn = f'''<form class="inline" method="post" action="/events/{e["id"]}/signup">
                            <button type="submit" class="btn-primary">Going</button>
                          </form>'''
                    leave_btn = ""
                    if status in ("approved", "pending") and e["host_id"] != user["id"]:
                        leave_btn = f'''<form class="inline" method="post" action="/events/{e["id"]}/signup/leave">
                            <button type="submit" class="btn">Can't Go</button>
                          </form>'''
                actions = f'<div class="trip-actions">{going_btn}{leave_btn}<a class="btn" href="/events/{e["id"]}">View trip</a></div>'

            return f"""
            <div class="trip-row">
              {picture}
              <div class="trip-body">
                <a class="trip-row-link" href="/events/{e['id']}">
                  <div class="date-line">{e['date_start']:%a, %d %b}{' - ' + format(e['date_end'], '%d %b') if e['date_end'].date() != e['date_start'].date() else ''}</div>
                  <h2>{html.escape(e['title'])}</h2>
                </a>
                <div class="muted">{avatar(e['host_name'], e.get('host_picture'), size=24)} Created by <strong>{html.escape(e['host_name'])}</strong></div>
                {f'<div class="muted" style="margin-top:0.2em;">{html.escape(location_display) + " &middot; " if location_display else ""}{limit_text}</div>' if not show_actions else ""}
                {actions}
              </div>
            </div>"""

        upcoming_rows = "".join(render_row(e, True) for e in upcoming_events) or '<p class="muted">No upcoming trips.</p>'
        past_rows = "".join(render_row(e, False) for e in past_events) or '<p class="muted">No past trips.</p>'

        body = f"""
        <div class="cover-banner">
          <img src="{html.escape(banner_url)}">
        </div>
        <div class="club-header">
          <h1>{html.escape(CLUB_NAME)}</h1>
        </div>
        <div class="tabs">
          <a class="active" href="/">Trips</a>
        </div>
        <div class="card" style="padding:1em 1.2em;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.3em;">
            <h3 style="margin:0;">Upcoming trips</h3>
            {'<a class="btn btn-primary" href="/events/new">+ Create trip</a>' if user else ''}
          </div>
          <div class="trip-list">{upcoming_rows}</div>
        </div>

        <div class="card" style="padding:1em 1.2em;">
          <h3 style="margin:0 0 0.3em;">Past trips</h3>
          <div class="trip-list">{past_rows}</div>
        </div>
        """
        self._send_html(render_page("Trips", body, user))

    def _render_event_form(self, action, heading, submit_label, global_distance_formula, event=None, is_new=False, gear_rates=None, catalog_checklist_items=None, required_checklist_ids=None):
        """Shared form for both creating and editing an event. `event` (a dict
        of current values) is provided when editing, to pre-fill the fields.
        `gear_rates` (this event's effective rates, from
        _resolve_event_gear_rates) is only given when editing -- a brand new
        event doesn't have a row in event_gear_rates yet, that's seeded
        right after it's created. `catalog_checklist_items` is the full
        club-wide skill/item catalog (see _get_checklist_items);
        `required_checklist_ids` (only set when editing) are this event's
        current selections."""
        title_val = html.escape(event["title"]) if event else ""
        description_val = (event.get("description") or "") if event else ""
        picture_val = html.escape(event.get("picture_url") or "") if event else ""
        location_val = html.escape(event["location"]) if event else ""
        location_label_val = html.escape(event.get("location_label") or "") if event else ""
        has_limit = bool(event.get("participant_limit")) if event else False
        limit_val = event.get("participant_limit") or "" if event else ""
        has_formula_override = bool(event.get("distance_formula")) if event else False
        distance_formula_val = html.escape(event.get("distance_formula") or "") if event else ""
        date_start_val = event["date_start"].strftime("%Y-%m-%dT%H:%M") if event else ""
        date_end_val = event["date_end"].strftime("%Y-%m-%dT%H:%M") if event else ""
        current_mode = event["signup_mode"] if event else "fcfs"

        mode_options = "".join(
            f'<option value="{key}"{" selected" if key == current_mode else ""}>{html.escape(label)}</option>'
            for key, label in SIGNUP_MODE_LABELS.items()
        )

        body = f"""
        <div class="card">
        <h1>{html.escape(heading)}</h1>
        <form method="post" action="{action}">
          <label>Title<input id="event-title-input" name="title" required value="{title_val}"></label>
          <label>Description
            <textarea name="description" id="description">{description_val}</textarea>
          </label>
          <label>Picture
            <input type="file" id="event-picture-file" accept="image/*">
          </label>
          {f'<img id="event-picture-preview" src="{picture_val}" style="max-width:200px;border-radius:6px;display:block;margin-bottom:0.6em;">' if picture_val else '<img id="event-picture-preview" style="max-width:200px;border-radius:6px;display:none;margin-bottom:0.6em;">'}
          <input type="hidden" name="picture_url" id="event-picture-url" value="{picture_val}">
          <label>Start<input name="date_start" type="datetime-local" required value="{date_start_val}"></label>
          <label>End<input name="date_end" type="datetime-local" required value="{date_end_val}"></label>
          <label>Location
            <div style="display:flex; gap:0.5em;">
              <input name="location" id="event-location-input" required style="flex:1;" placeholder="Address, place name, or a Google Maps link (e.g. https://maps.app.goo.gl/...)" value="{location_val}">
              <button type="button" class="btn" id="open-maps-btn" style="white-space:nowrap;">Open Google Maps</button>
            </div>
          </label>
          <label>Location label (optional)
            <input name="location_label" placeholder="Overrides the displayed location name" value="{location_label_val}">
          </label>
          <label>Signup mode
            <select name="signup_mode">
              {mode_options}
            </select>
          </label>
          <label style="display:flex; align-items:center; gap:0.5em;">
            <input type="checkbox" name="limit_enabled" id="limit-enabled" value="1" style="width:auto; margin:0;"{" checked" if has_limit else ""}>
            Limit number of participants
          </label>
          <div id="limit-row" style="display:{'block' if has_limit else 'none'};">
            <label>Participant limit<input name="participant_limit" type="number" min="1" value="{limit_val}"></label>
          </div>
          <script>
          document.getElementById('limit-enabled').addEventListener('change', function() {{
            document.getElementById('limit-row').style.display = this.checked ? 'block' : 'none';
          }});
          </script>
          <label style="display:flex; align-items:center; gap:0.5em;">
            <input type="checkbox" name="formula_enabled" id="formula-enabled" value="1" style="width:auto; margin:0;"{" checked" if has_formula_override else ""}>
            Use a custom driven-distance rate for this event
          </label>
          <div id="formula-row" style="display:{'block' if has_formula_override else 'none'};">
            <label>Distance formula<input name="distance_formula" value="{distance_formula_val}" placeholder="e.g. km * 0.025"></label>
            <p class="muted" style="margin-top:-0.4em;">Club default: <code>{html.escape(global_distance_formula)}</code>. Supports <code>km</code>, numbers, <code>+ - *</code>, and <code>max(...)</code>/<code>min(...)</code>.</p>
          </div>
          <script>
          document.getElementById('formula-enabled').addEventListener('change', function() {{
            document.getElementById('formula-row').style.display = this.checked ? 'block' : 'none';
          }});
          </script>
          {f'''<label>Gear rates for this trip</label>
          <div style="display:flex; flex-direction:column; gap:0.4em; margin-bottom:0.9em;">
            {"".join(f"""<div style="display:flex; align-items:center; gap:0.5em;" title="{html.escape(g['description'] or '')}">
              <span style="flex:1;">{html.escape(g['name'])}{f' <span class="muted">&mdash; {html.escape(g["description"])}</span>' if g['description'] else ''}</span>
              <input name="gear_rate_{g['id']}" type="number" step="0.01" min="0" value="{g['rate']}" style="width:100px; margin:0; flex-shrink:0;">
            </div>""" for g in gear_rates) or '<p class="muted">No gear types configured yet -- an admin can add some.</p>'}
          </div>''' if gear_rates is not None else ''}
          {self._render_checklist_form_section(catalog_checklist_items or [], required_checklist_ids or set())}
          {'''<label style="display:flex; align-items:center; gap:0.5em;">
            <input type="checkbox" name="attending" value="1" checked style="width:auto; margin:0;">
            I'm attending this trip
          </label>''' if is_new else ''}
          <div style="display:flex; gap:0.6em;">
            <button type="submit" class="btn-primary">{html.escape(submit_label)}</button>
            <a class="btn" href="{f'/events/{event["id"]}' if event else '/'}">Discard</a>
          </div>
        </form>
        </div>
        <script src="https://cdn.ckeditor.com/4.25.2-lts/standard/ckeditor.js"></script>
        <script>CKEDITOR.replace('description');</script>
        <script>
        function loadEventPictureFile(file) {{
          if (!file) return;
          var reader = new FileReader();
          reader.onload = function(e) {{
            document.getElementById('event-picture-url').value = e.target.result;
            var preview = document.getElementById('event-picture-preview');
            preview.src = e.target.result;
            preview.style.display = 'block';
          }};
          reader.readAsDataURL(file);
        }}

        document.getElementById('event-picture-file').addEventListener('change', function() {{
          loadEventPictureFile(this.files[0]);
        }});

        document.addEventListener('paste', function(e) {{
          var items = (e.clipboardData || window.clipboardData).items;
          for (var i = 0; i < items.length; i++) {{
            if (items[i].type.indexOf('image') !== -1) {{
              loadEventPictureFile(items[i].getAsFile());
              e.preventDefault();
              break;
            }}
          }}
        }});

        document.getElementById('open-maps-btn').addEventListener('click', function() {{
          var location = document.getElementById('event-location-input').value.trim();
          var title = document.getElementById('event-title-input').value.trim();
          var query = location || title;
          if (!query) {{ alert('Enter a title or location first.'); return; }}
          window.open('https://www.google.com/maps/search/?api=1&query=' + encodeURIComponent(query), '_blank');
        }});
        </script>
        """
        return body

    def handle_event_new_form(self, conn, user):
        self._require_login(user)
        body = self._render_event_form(
            "/events/new", "New trip", "Create trip", self._get_distance_formula(conn), is_new=True,
            catalog_checklist_items=self._get_checklist_items(conn),
        )
        self._send_html(render_page("New trip", body, user))

    def handle_event_new_submit(self, conn, user, form):
        self._require_login(user)
        title = form.get("title", "").strip()
        description = form.get("description", "").strip() or None
        location = form.get("location", "").strip()
        location_label = form.get("location_label", "").strip() or None
        date_start = form.get("date_start", "").replace("T", " ")
        date_end = form.get("date_end", "").replace("T", " ")
        signup_mode = form.get("signup_mode") if form.get("signup_mode") in SIGNUP_MODE_LABELS else "fcfs"
        limit_enabled = form.get("limit_enabled") == "1"
        limit_raw = form.get("participant_limit", "").strip()
        participant_limit = int(limit_raw) if limit_enabled and limit_raw else None
        picture_field = form.get("picture_url", "").strip() or None
        picture_url = None
        if picture_field:
            try:
                picture_url = self._save_data_url_image(picture_field, "events", f"new-{user['id']}")
            except ValueError:
                picture_url = picture_field  # allow a plain external URL too

        formula_enabled = form.get("formula_enabled") == "1"
        distance_formula_raw = form.get("distance_formula", "").strip()
        distance_formula_override = None
        if formula_enabled and distance_formula_raw:
            try:
                formula.validate(distance_formula_raw)
                distance_formula_override = distance_formula_raw
            except formula.FormulaError:
                pass  # fall back to the global default rather than reject event creation

        attending = form.get("attending") == "1"
        checklist_item_ids = self._parse_checklist_form_submission(conn, form)

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO events (host_id, title, description, picture_url, date_start, date_end, location, location_label, signup_mode, participant_limit, distance_formula)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (user["id"], title, description, picture_url, date_start, date_end, location, location_label, signup_mode, participant_limit, distance_formula_override),
            )
            event_id = cur.lastrowid
            if attending:
                cur.execute(
                    "INSERT INTO event_signups (event_id, user_id, status) VALUES (%s, %s, 'approved')",
                    (event_id, user["id"]),
                )
        self._seed_event_gear_rates(conn, event_id)
        self._save_event_checklist(conn, event_id, checklist_item_ids)
        redirect(self, f"/events/{event_id}")

    def handle_event_edit_form(self, conn, user, event_id):
        self._require_login(user)
        event = self._get_event(conn, event_id)
        if not event:
            return self._send_html(render_page("Not found", "<h1>Trip not found</h1>", user), status=404)
        if event["host_id"] != user["id"]:
            return self._send_html(render_page("Forbidden", "<h1>Only the host can edit this trip.</h1>", user), status=403)

        with conn.cursor() as cur:
            cur.execute("SELECT checklist_item_id FROM event_checklist_items WHERE event_id = %s", (event_id,))
            required_checklist_ids = {r["checklist_item_id"] for r in cur.fetchall()}

        body = self._render_event_form(
            f"/events/{event_id}/edit", f"Edit: {event['title']}", "Save changes",
            self._get_distance_formula(conn), event=event, gear_rates=self._resolve_event_gear_rates(conn, event_id),
            catalog_checklist_items=self._get_checklist_items(conn), required_checklist_ids=required_checklist_ids,
        )
        self._send_html(render_page("Edit trip", body, user))

    def handle_event_edit_submit(self, conn, user, event_id, form):
        self._require_login(user)
        event = self._get_event(conn, event_id)
        if not event:
            return redirect(self, "/")
        if event["host_id"] != user["id"]:
            return self._send_html(render_page("Forbidden", "<h1>Only the host can edit this trip.</h1>", user), status=403)

        title = form.get("title", "").strip()
        description = form.get("description", "").strip() or None
        location = form.get("location", "").strip()
        location_label = form.get("location_label", "").strip() or None
        date_start = form.get("date_start", "").replace("T", " ")
        date_end = form.get("date_end", "").replace("T", " ")
        signup_mode = form.get("signup_mode") if form.get("signup_mode") in SIGNUP_MODE_LABELS else "fcfs"
        limit_enabled = form.get("limit_enabled") == "1"
        limit_raw = form.get("participant_limit", "").strip()
        participant_limit = int(limit_raw) if limit_enabled and limit_raw else None

        formula_enabled = form.get("formula_enabled") == "1"
        distance_formula_raw = form.get("distance_formula", "").strip()
        distance_formula_override = None
        if formula_enabled and distance_formula_raw:
            try:
                formula.validate(distance_formula_raw)
                distance_formula_override = distance_formula_raw
            except formula.FormulaError:
                distance_formula_override = event.get("distance_formula")  # keep whatever it was before

        picture_field = form.get("picture_url", "").strip() or None
        picture_url = event.get("picture_url")
        if picture_field and picture_field.startswith("data:image/"):
            try:
                picture_url = self._save_data_url_image(picture_field, "events", f"event-{event_id}")
            except ValueError:
                pass
        elif picture_field:
            picture_url = picture_field  # unchanged existing URL, or a plain external URL
        else:
            picture_url = None  # picture field cleared

        gear_types = self._get_gear_types(conn)
        checklist_item_ids = self._parse_checklist_form_submission(conn, form)
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE events
                SET title = %s, description = %s, picture_url = %s, date_start = %s,
                    date_end = %s, location = %s, location_label = %s, signup_mode = %s, participant_limit = %s,
                    distance_formula = %s
                WHERE id = %s
                """,
                (title, description, picture_url, date_start, date_end, location, location_label, signup_mode, participant_limit, distance_formula_override, event_id),
            )
            for gear_type in gear_types:
                rate_raw = form.get(f"gear_rate_{gear_type['id']}", "").strip()
                if rate_raw:
                    try:
                        rate = Decimal(rate_raw).quantize(Decimal("0.01"))
                    except Exception:
                        continue
                    cur.execute(
                        "UPDATE event_gear_rates SET rate = %s WHERE event_id = %s AND gear_type_id = %s",
                        (str(rate), event_id, gear_type["id"]),
                    )
        self._save_event_checklist(conn, event_id, checklist_item_ids)
        redirect(self, f"/events/{event_id}")

    def _get_event(self, conn, event_id):
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.*, u.name AS host_name, u.profile_picture_url AS host_picture
                FROM events e JOIN users u ON u.id = e.host_id WHERE e.id = %s
                """,
                (event_id,),
            )
            return cur.fetchone()

    def handle_event_map_embed(self, conn, user, event_id):
        """Resolves and redirects to the actual Google Maps embed URL for a
        trip's location. Split out from handle_event_detail and loaded by
        the iframe's own request (lazily, after the page itself has
        rendered) because resolving a maps.app.goo.gl share link's place
        name is a network round-trip that shouldn't block the page load.
        Public: matches the trip detail page it's loaded from."""
        event = self._get_event(conn, event_id)
        if not event:
            return self._send_html("<p>Trip not found.</p>", status=404)
        _, _, maps_embed_url = location_info(event["location"], event.get("location_label"), with_embed=True)
        if maps_embed_url:
            self.send_response(302)
            self.send_header("Location", maps_embed_url)
            self.end_headers()
        else:
            self._send_html('<p style="font-family:sans-serif; color:#65676b; padding:1em;">No map preview available for this location.</p>')

    def handle_event_detail(self, conn, user, event_id):
        event = self._get_event(conn, event_id)
        if not event:
            return self._send_html(render_page("Not found", "<h1>Trip not found</h1>", user), status=404)

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.*, u.name, u.email, u.profile_picture_url, u.membership_expiry, u.password_hash FROM event_signups s
                JOIN users u ON u.id = s.user_id
                WHERE s.event_id = %s ORDER BY s.created_at
                """,
                (event_id,),
            )
            signups = cur.fetchall()

            cur.execute(
                """
                SELECT p.*, u.name, u.profile_picture_url FROM discussion_posts p
                JOIN users u ON u.id = p.user_id
                WHERE p.event_id = %s ORDER BY p.created_at
                """,
                (event_id,),
            )
            posts = cur.fetchall()

            if user:
                cur.execute(
                    "SELECT id, name FROM users WHERE id NOT IN "
                    "(SELECT user_id FROM event_signups WHERE event_id = %s) ORDER BY name",
                    (event_id,),
                )
                addable_users = list(cur.fetchall())
            else:
                addable_users = []

            cur.execute(
                """
                SELECT ci.id, ci.name, ci.kind FROM event_checklist_items eci
                JOIN checklist_items ci ON ci.id = eci.checklist_item_id
                WHERE eci.event_id = %s ORDER BY ci.kind, ci.name
                """,
                (event_id,),
            )
            required_checklist_items = list(cur.fetchall())

        catalog_checklist_items = self._get_checklist_items(conn)

        my_signup = next((s for s in signups if user and s["user_id"] == user["id"]), None)
        approved = [s for s in signups if s["status"] == "approved"]
        pending = [s for s in signups if s["status"] == "pending"]
        is_host = bool(user) and event["host_id"] == user["id"]

        # with_embed=False here: resolving a maps.app.goo.gl share link's
        # place name is a network round-trip (see _resolve_maps_place_name),
        # which would otherwise block this page's response. The iframe below
        # instead points at /events/<id>/map-embed, which the browser loads
        # lazily after the page itself has rendered, so that cost never
        # delays the page.
        location_display, maps_url, _ = location_info(event["location"], event.get("location_label"))

        signup_block = ""
        if not user:
            signup_block = '<a class="btn btn-primary" href="/login">Log in to join</a>'
        elif not my_signup:
            full = event["participant_limit"] and len(approved) >= event["participant_limit"]
            if full:
                signup_block = '<button class="btn" disabled>Trip is full</button>'
            else:
                if is_host:
                    label, btn_class = "Join", "btn-primary"
                elif event["signup_mode"] == "host_picks":
                    label, btn_class = "Request to join", "btn-primary"
                else:
                    label, btn_class = "Not Going", "btn"
                signup_block = f"""<form method="post" action="/events/{event_id}/signup">
                    <button type="submit" class="{btn_class}">{label}</button></form>"""
        else:
            status_label, status_style = {
                "approved": ("Going", "background:var(--fb-blue); color:#fff; border-color:var(--fb-blue);"),
                "pending": ("Pending", "background:#f5c518; color:#3c3000; border-color:#f5c518;"),
                "rejected": ("Not approved", ""),
            }[my_signup["status"]]
            signup_block = f"""<form method="post" action="/events/{event_id}/signup/leave"
                onsubmit="return confirm('Leave this trip?');">
                <button type="submit" class="btn" style="{status_style}">{status_label}</button></form>"""

        pending_rows = ""
        if is_host and event["signup_mode"] == "host_picks" and pending:
            rows = []
            for s in pending:
                rows.append(f"""<div class="guest-row">
                    {avatar(s['name'], s.get('profile_picture_url'))}
                    <span class="name">{html.escape(s['name'])}</span>
                    <form class="inline" method="post" action="/events/{event_id}/signup/{s['user_id']}/approve"><button>Approve</button></form>
                    <form class="inline" method="post" action="/events/{event_id}/signup/{s['user_id']}/reject"><button>Reject</button></form>
                  </div>""")
            pending_rows = f'<div class="card"><h3>Pending requests</h3>{"".join(rows)}</div>'

        guest_rows = "".join(
            f"""<div class="guest-row">
                {avatar(s['name'], s.get('profile_picture_url'))}
                <span class="name">{html.escape(s['name'])}</span>
                {f'<span class="badge" style="background:var(--fb-blue); color:#fff; border-radius:4px; padding:0.1em 0.5em; font-size:0.8em;" title="Member of the National University Caving Club (NUCC)">nucc</span>' if s.get('membership_expiry') else ''}
                <span class="status">{"No login" if not s.get("password_hash") else "Going"}</span>
                {f'''<form class="inline" method="post" action="/events/{event_id}/guests/{s["user_id"]}/remove" onsubmit="return confirm('Remove this guest?');">
                  <button type="submit" class="btn" style="padding:0.2em 0.6em;">Remove</button>
                </form>''' if is_host and not s.get("password_hash") else ''}
              </div>"""
            for s in approved
        ) or '<p class="muted">No one yet &mdash; be the first!</p>'

        required_skills = [c for c in required_checklist_items if c["kind"] == "skill"]
        required_items = [c for c in required_checklist_items if c["kind"] == "item"]
        if not required_checklist_items:
            checklist_html = '<p class="muted">Nothing required yet.</p>'
        else:
            checklist_html = ""
            if required_skills:
                checklist_html += "<p class=\"muted\" style=\"margin-bottom:0.2em;\"><strong>Skills</strong></p><ul style=\"margin-top:0;\">"
                checklist_html += "".join(f"<li>{html.escape(c['name'])}</li>" for c in required_skills)
                checklist_html += "</ul>"
            if required_items:
                checklist_html += "<p class=\"muted\" style=\"margin-bottom:0.2em;\"><strong>Items</strong></p><ul style=\"margin-top:0;\">"
                checklist_html += "".join(f"<li>{html.escape(c['name'])}</li>" for c in required_items)
                checklist_html += "</ul>"

        checklist_dialog_html = ""
        if is_host:
            required_ids = {c["id"] for c in required_checklist_items}
            checklist_dialog_html = f"""
            <dialog id="checklist-dialog" style="border:none; border-radius:8px; padding:0; max-width:380px; width:90%;">
              <div class="card" style="margin:0; box-shadow:none; border:none;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                  <h3 style="margin:0;">Required skills &amp; items</h3>
                  <button type="button" class="btn" onclick="document.getElementById('checklist-dialog').close()">&times;</button>
                </div>
                <form method="post" action="/events/{event_id}/checklist">
                  {self._render_checklist_form_section(catalog_checklist_items, required_ids)}
                  <button type="submit" class="btn-primary">Save</button>
                </form>
              </div>
            </dialog>
            """

        add_guest_dialog_html = ""
        if is_host:
            user_options = "".join(f'<option value="{u["id"]}">{html.escape(u["name"])}</option>' for u in addable_users)
            add_guest_dialog_html = f"""
            <dialog id="add-guest-dialog" style="border:none; border-radius:8px; padding:0; max-width:380px; width:90%;">
              <div class="card" style="margin:0; box-shadow:none; border:none;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                  <h3 style="margin:0;">Add a participant</h3>
                  <button type="button" class="btn" onclick="document.getElementById('add-guest-dialog').close()">&times;</button>
                </div>
                <div id="existing-member-section">
                  <label>Find a member
                    <select id="existing-member-select" {"required" if addable_users else "disabled"}>
                      <option value="" disabled selected>{"Choose a member&hellip;" if addable_users else "No members left to add"}</option>
                      {user_options}
                    </select>
                  </label>
                  <form method="post" id="existing-member-form" action="/events/{event_id}/guests/existing" style="display:flex; gap:0.5em;">
                    <input type="hidden" name="user_id" id="existing-member-id">
                    <button type="submit" class="btn-primary" style="flex:1;" {"disabled" if not addable_users else ""}>Add</button>
                    <button type="submit" name="add_another" value="1" class="btn" style="flex:1;" {"disabled" if not addable_users else ""}>Add &amp; add another</button>
                  </form>
                  <p style="margin-top:0.8em;">
                    <a href="#" onclick="document.getElementById('existing-member-section').style.display='none'; document.getElementById('new-member-section').style.display='block'; return false;">
                      Can't find them? Create a new member
                    </a>
                  </p>
                </div>
                <div id="new-member-section" style="display:none;">
                  <p class="muted">For someone who went on this trip but doesn't have an account here (e.g. importing
                  a past trip's attendance sheet). Creates an account for them with no login -- they count toward the
                  fee split and show up everywhere a regular participant would.</p>
                  <form method="post" action="/events/{event_id}/guests" style="display:flex; flex-direction:column; gap:0.5em;">
                    <input name="name" placeholder="Full name" required style="width:100%;">
                    <input name="email" type="email" placeholder="Email" required style="width:100%;">
                    <div style="display:flex; gap:0.5em;">
                      <button type="submit" class="btn-primary" style="flex:1;">Create</button>
                      <button type="submit" name="add_another" value="1" class="btn" style="flex:1;">Create &amp; add another</button>
                    </div>
                  </form>
                  <p style="margin-top:0.8em;">
                    <a href="#" onclick="document.getElementById('new-member-section').style.display='none'; document.getElementById('existing-member-section').style.display='block'; return false;">
                      &larr; Back to member lookup
                    </a>
                  </p>
                </div>
              </div>
              <script>
                (function() {{
                  var sel = document.getElementById('existing-member-select');
                  var hidden = document.getElementById('existing-member-id');
                  var form = document.getElementById('existing-member-form');
                  if (sel) {{
                    sel.addEventListener('change', function() {{ hidden.value = sel.value; }});
                    form.addEventListener('submit', function(e) {{
                      if (!sel.value) e.preventDefault();
                    }});
                  }}
                }})();
              </script>
            </dialog>
            """

        posts_html = "".join(
            f"""<div style="display:flex; gap:0.7em; padding:0.6em 0; border-bottom:1px solid #eee;">
                {avatar(p['name'], p.get('profile_picture_url'))}
                <div>
                  <strong>{html.escape(p['name'])}</strong> <span class="muted">{p['created_at']:%d %b %Y %H:%M}</span>
                  <p style="margin:0.2em 0 0;">{html.escape(p['message'])}</p>
                </div>
              </div>"""
            for p in posts
        ) or '<p class="muted">No discussion yet.</p>'

        limit_text = f" / {event['participant_limit']}" if event["participant_limit"] else ""
        description_html = event.get("description") or '<span class="muted">No description yet.</span>'

        hero_img = (
            f'<img src="{html.escape(event["picture_url"])}">'
            if event.get("picture_url")
            else '<div style="height:280px;background:#ced0d4;"></div>'
        )

        body = f"""
        <div class="hero">
          <div class="hero-img-wrap">{hero_img}</div>
          <div class="date-badge">
            <div class="mon">{event['date_start']:%b}</div>
            <div class="day">{event['date_start']:%d}</div>
          </div>
        </div>
        <div class="card event-header-card">
          <h1>{html.escape(event['title'])}</h1>
          <div class="muted">{event['date_start']:%a, %d %b %Y, %I:%M %p} &ndash; {event['date_end']:%a, %d %b %Y, %I:%M %p}</div>
          <div class="muted" style="margin-bottom:0.8em;">{html.escape(location_display)}</div>
          <div class="pill-row" style="max-width:100%; justify-content:space-between; flex-wrap:wrap;">
            <div style="display:flex;">{signup_block}</div>
            <div style="display:flex; gap:0.6em; flex-wrap:wrap;">
              <a class="btn" href="/events/{event_id}/contributions" style="white-space:nowrap; flex:0 0 auto;">Contributions and Gear Hire</a>
              {f'<a class="btn" href="/events/{event_id}/edit" style="flex:0 0 auto;">Edit</a>' if is_host else ''}
            </div>
          </div>
        </div>

        <div class="event-layout">
          <div>
            <div class="card">
              <h3>Details</h3>
              <p>{avatar(event['host_name'], event.get('host_picture'))} Trip by <strong>{html.escape(event['host_name'])}</strong></p>
              <p class="muted">Signup mode: {SIGNUP_MODE_LABELS[event['signup_mode']]} &middot; {len(approved)}{limit_text} going</p>
              <div class="description-body">{description_html}</div>
            </div>

            <div class="card">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <h3 style="margin:0;">Required skills &amp; items <a href="/pages/skills" style="font-size:0.7em; font-weight:normal;">(what do these mean?)</a></h3>
                {f'<button type="button" class="btn" title="Edit checklist" onclick="document.getElementById(\'checklist-dialog\').showModal()" style="padding:0.3em 0.7em;">Edit</button>' if is_host else ''}
              </div>
              {checklist_html}
            </div>

            {pending_rows}

            <div class="card">
              <h3>Discussion</h3>
              {posts_html}
              {f'''<form method="post" action="/events/{event_id}/discussion" style="margin-top:0.8em;">
                <textarea name="message" required placeholder="Write something..." rows="2"></textarea>
                <button type="submit" class="btn-primary">Post</button>
              </form>''' if user else '<p class="muted" style="margin-top:0.8em;"><a href="/login">Log in</a> to join the discussion.</p>'}
            </div>
          </div>

          <div>
            <div class="card" style="padding:0;">
              <iframe class="map-embed" src="/events/{event_id}/map-embed" loading="lazy"></iframe>
              <div style="padding:1em;">
                <strong>{html.escape(location_display)}</strong><br>
                <a class="muted" href="{maps_url}" target="_blank">Open in Google Maps</a>
              </div>
            </div>
            <div class="card">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <h3 style="margin:0;">Participants</h3>
                {f'<button type="button" class="btn-primary" title="Add a participant" onclick="document.getElementById(\'add-guest-dialog\').showModal()" style="width:2.2em; height:2.2em; border-radius:50%; padding:0; font-size:1.2em; line-height:1;">+</button>' if is_host else ''}
              </div>
              {guest_rows}
            </div>
          </div>
        </div>
        {add_guest_dialog_html}
        {checklist_dialog_html}
        {"<script>document.getElementById('add-guest-dialog').showModal();</script>" if is_host and parse_qs(urlparse(self.path).query).get("add_participant", [""])[0] == "1" else ""}
        """
        self._send_html(render_page(event["title"], body, user))

    def handle_signup(self, conn, user, event_id):
        self._require_login(user)
        event = self._get_event(conn, event_id)
        if not event:
            return redirect(self, "/")
        is_host = event["host_id"] == user["id"]
        if is_host:
            status = "approved"  # the host never needs their own approval
        else:
            status = "pending" if event["signup_mode"] == "host_picks" else "approved"

        if status == "approved" and event["participant_limit"] and not is_host:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) AS c FROM event_signups WHERE event_id = %s AND status = 'approved'",
                    (event_id,),
                )
                if cur.fetchone()["c"] >= event["participant_limit"]:
                    status = "pending"  # fall back to a waitlist of sorts

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO event_signups (event_id, user_id, status) VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE status = VALUES(status)
                """,
                (event_id, user["id"], status),
            )
        redirect(self, f"/events/{event_id}")

    def handle_signup_leave(self, conn, user, event_id):
        self._require_login(user)
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM event_signups WHERE event_id = %s AND user_id = %s",
                (event_id, user["id"]),
            )
        redirect(self, f"/events/{event_id}")

    def handle_signup_decision(self, conn, user, event_id, target_user_id, decision):
        self._require_login(user)
        event = self._get_event(conn, event_id)
        if not event or event["host_id"] != user["id"]:
            return redirect(self, f"/events/{event_id}")
        new_status = "approved" if decision == "approve" else "rejected"
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE event_signups SET status = %s WHERE event_id = %s AND user_id = %s",
                (new_status, event_id, target_user_id),
            )
        redirect(self, f"/events/{event_id}")

    def handle_discussion_post(self, conn, user, event_id, form):
        self._require_login(user)
        message = form.get("message", "").strip()
        if message:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO discussion_posts (event_id, user_id, message) VALUES (%s, %s, %s)",
                    (event_id, user["id"], message),
                )
        redirect(self, f"/events/{event_id}")

    # -- contributions / accounting ---------------------------------------

    def _compute_event_accounts(self, conn, event_id):
        """Returns accounting.compute_event_accounting()'s result for one
        event: {user_id: {"name", "fee", "paid", "owe", ...}}. Shared by the
        per-trip contributions page and the club-wide balances page.
        Guest accounts (see handle_event_guest_add) are approved signups
        like any other, so they're already covered by the participants
        query below -- no special-casing needed."""
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.user_id AS id, u.name FROM event_signups s
                JOIN users u ON u.id = s.user_id
                WHERE s.event_id = %s AND s.status = 'approved'
                """,
                (event_id,),
            )
            participants = list(cur.fetchall())

            cur.execute(
                """
                SELECT c.*, COALESCE(cu.name, c.contributor_name) AS contributor_display_name
                FROM contributions c
                LEFT JOIN users cu ON cu.id = c.contributor_id
                WHERE c.event_id = %s ORDER BY c.created_at
                """,
                (event_id,),
            )
            contributions = list(cur.fetchall())

            cur.execute(
                """
                SELECT cc.contribution_id, cc.user_id, u.name
                FROM contribution_consumers cc
                JOIN users u ON u.id = cc.user_id
                JOIN contributions c ON c.id = cc.contribution_id
                WHERE c.event_id = %s
                """,
                (event_id,),
            )
            consumers_by_contribution = {}
            for row in cur.fetchall():
                consumers_by_contribution.setdefault(row["contribution_id"], []).append(row)

        accounting_contributions = []
        for c in contributions:
            consumers = consumers_by_contribution.get(c["id"], [])
            c["consumed_by_ids"] = [r["user_id"] for r in consumers]
            c["consumed_by_names"] = [r["name"] for r in consumers]
            accounting_contributions.append(dict(c))

        return accounting.compute_event_accounting(participants, accounting_contributions)

    def _get_event_live_owes(self, conn, event_id):
        """{user_id: owe} for every participant, computed live from the
        trip's current contributions/gear use -- what lodging or amending
        would record right now."""
        accounts = self._compute_event_accounts(conn, event_id)
        return {uid: a["owe"] for uid, a in accounts.items() if isinstance(uid, int)}

    def _get_event_lodgement_totals(self, conn, event_id):
        """{user_id: total} each member's currently-lodged amount for this
        trip -- SUM(amount) of their event_fee_lodgements rows (the initial
        lodge plus any reversal/revision pairs from later amendments)."""
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id, SUM(amount) AS total FROM event_fee_lodgements WHERE event_id = %s GROUP BY user_id",
                (event_id,),
            )
            return {row["user_id"]: row["total"] for row in cur.fetchall()}

    def _get_event_lodgement_diffs(self, conn, event_id):
        """{user_id: (lodged_total, live_owe)} for every member whose live
        owe no longer matches what's lodged -- what an "Amend" would record
        if clicked right now, and whether the button should be enabled."""
        live_owes = self._get_event_live_owes(conn, event_id)
        lodged_totals = self._get_event_lodgement_totals(conn, event_id)
        diffs = {}
        for uid in set(live_owes) | set(lodged_totals):
            lodged = lodged_totals.get(uid, Decimal("0"))
            live = live_owes.get(uid, Decimal("0"))
            if abs(lodged - live) >= Decimal("0.01"):
                diffs[uid] = (lodged, live)
        return diffs

    def handle_contributions_page(self, conn, user, event_id, effective_user=None, event_base=None):
        """effective_user/event_base let this page (and its action forms) be
        rendered for an anonymous visitor holding a valid edit share-link
        (see handle_share_link): effective_user is the trip host, used for
        all permission/ownership checks instead of the (None) logged-in
        user, and event_base replaces "/events/<id>" in every action URL on
        the page with "/share/<token>" so forms submit back through the
        share-link routes rather than requiring a real session."""
        if effective_user is None:
            self._require_login(user)
        viewer = effective_user or user
        base = event_base or f"/events/{event_id}"
        event = self._get_event(conn, event_id)
        if not event:
            return self._send_html(render_page("Not found", "<h1>Trip not found</h1>", user), status=404)
        is_host = event["host_id"] == viewer["id"]

        from_accounting = parse_qs(urlparse(self.path).query).get("from", [""])[0] == "accounting"
        back_link = (
            '<a href="/accounting">&larr; back to accounting</a>' if from_accounting
            else (f'<a href="/events/{event_id}">&larr; back to trip</a>' if effective_user is None else "")
        )

        query = parse_qs(urlparse(self.path).query)
        error_html = (
            '<p class="error">You\'ve already added a contribution with that description for this trip.</p>'
            if query.get("error", [""])[0] == "duplicate" else ""
        )

        with conn.cursor() as cur:
            cur.execute(
                "SELECT s.user_id AS id, u.name FROM event_signups s JOIN users u ON u.id = s.user_id WHERE s.event_id = %s",
                (event_id,),
            )
            all_signed_up = list(cur.fetchall())

            cur.execute(
                """
                SELECT c.*, COALESCE(cu.name, c.contributor_name) AS contributor_display_name
                FROM contributions c
                LEFT JOIN users cu ON cu.id = c.contributor_id
                WHERE c.event_id = %s AND c.gear_type_id IS NULL ORDER BY c.created_at
                """,
                (event_id,),
            )
            contributions = list(cur.fetchall())

            cur.execute(
                """
                SELECT cc.contribution_id, cc.user_id, u.name
                FROM contribution_consumers cc
                JOIN users u ON u.id = cc.user_id
                JOIN contributions c ON c.id = cc.contribution_id
                WHERE c.event_id = %s
                """,
                (event_id,),
            )
            consumers_by_contribution = {}
            for row in cur.fetchall():
                consumers_by_contribution.setdefault(row["contribution_id"], []).append(row)

            cur.execute(
                """
                SELECT c.id, c.amount, gt.name AS gear_name
                FROM contributions c
                JOIN gear_types gt ON gt.id = c.gear_type_id
                WHERE c.event_id = %s ORDER BY c.created_at
                """,
                (event_id,),
            )
            gear_uses = list(cur.fetchall())

        for c in contributions:
            consumers = consumers_by_contribution.get(c["id"], [])
            c["consumed_by_ids"] = [r["user_id"] for r in consumers]
            c["consumed_by_names"] = [r["name"] for r in consumers]

        for g in gear_uses:
            consumers = consumers_by_contribution.get(g["id"], [])
            g["participant_id"] = consumers[0]["user_id"] if consumers else None
            g["participant_name"] = consumers[0]["name"] if consumers else "?"

        accounts = self._compute_event_accounts(conn, event_id)
        gear_rates = self._resolve_event_gear_rates(conn, event_id)

        info_tooltip = self._render_info_tooltip

        bank_details = self._get_bank_details(conn)
        account_rows = "".join(
            f"""<tr>
              <td>{html.escape(a['name'])}</td>
              <td class="owe-negative">{money(a['paid'])} {info_tooltip(a['paid_items'])}</td>
              <td class="muted" style="text-align:center;">&minus;</td>
              <td class="owe-positive">{money(a['fee'])} {info_tooltip(a['fee_items'])}</td>
              <td class="muted" style="text-align:center;">=</td>
              <td class="{'owe-positive' if a['owe'] > 0 else 'owe-negative' if a['owe'] < 0 else ''}">{signed_money(-a['owe'])}</td>
              <td>{self._pay_button(bank_details, f"{a['owe']:.2f}") if a['owe'] > 0 and event['lodged_at'] else ''}</td>
            </tr>"""
            for uid, a in accounts.items()
        )

        contribution_rows = "".join(
            f"""<tr>
              <td>{c['created_at']:%d %b}</td>
              <td>{html.escape(c['description'])}</td>
              <td>{c['type']}{f" ({c['km']} km)" if c['type'] == 'driven_distance' else ''}</td>
              <td>{html.escape(c['contributor_display_name'])}{' <span class="muted">(not a member)</span>' if not c['contributor_id'] else ''}</td>
              <td>{html.escape(', '.join(c['consumed_by_names'])) if c['consumed_by_names'] else '<em>shared</em>'}</td>
              <td>{money(c['amount'])}</td>
              <td>{f'''<div style="display:flex; align-items:center; gap:0.5em;">
                <a class="btn" style="padding:0.2em 0.6em;" href="{base}/contributions/{c["id"]}/edit">Edit</a>
                <form class="inline" method="post" action="{base}/contributions/{c["id"]}/delete" onsubmit="return confirm('Delete this contribution?');">
                  <button type="submit" class="btn" style="padding:0.2em 0.6em;">Delete</button>
                </form>
              </div>''' if c['contributor_id'] == viewer['id'] or event['host_id'] == viewer['id'] else ''}</td>
            </tr>"""
            for c in contributions
        )

        add_form_body = self._render_contribution_form(
            f"{base}/contributions", "Add contribution", all_signed_up, self._resolve_distance_formula(conn, event),
            is_host=is_host, current_user=viewer
        )
        drove_form_body = self._render_drove_form(
            f"{base}/contributions/drove", all_signed_up, self._resolve_distance_formula(conn, event),
            is_host=is_host, current_user=viewer
        )

        gear_use_rows = "".join(
            f"""<tr>
              <td>{html.escape(g['participant_name'])}</td>
              <td>{html.escape(g['gear_name'])}</td>
              <td>{money(g['amount'])}</td>
              <td>{f'''<form class="inline" method="post" action="{base}/gear-use/{g["id"]}/delete" onsubmit="return confirm('Remove this gear use?');">
                <button type="submit" class="btn" style="padding:0.2em 0.6em;">Remove</button>
              </form>''' if is_host or g['participant_id'] == viewer['id'] else ''}</td>
            </tr>"""
            for g in gear_uses
        )

        gear_participant_options = "".join(
            f'<option value="{s["id"]}">{html.escape(s["name"])}</option>'
            for s in ([{"id": viewer["id"], "name": "Myself"}] + [s for s in all_signed_up if s["id"] != viewer["id"]] if is_host
                      else [{"id": viewer["id"], "name": "Myself"}])
        )
        gear_type_options = "".join(
            f'<option value="{g["id"]}" data-description="{html.escape(g["description"] or "")}">{html.escape(g["name"])} (${g["rate"]}/person)</option>'
            for g in gear_rates
        )
        add_gear_use_form = f"""
        <form method="post" action="{base}/gear-use">
          <label>Gear
            <select name="gear_type_id" id="gear-type-select" required onchange="document.getElementById('gear-desc-hint').textContent = this.options[this.selectedIndex].dataset.description || '';">{gear_type_options}</select>
          </label>
          <p class="muted" id="gear-desc-hint" style="margin-top:-0.4em;">{html.escape(gear_rates[0]["description"] or "")}</p>
          {f'<label>For<select name="participant_id">{gear_participant_options}</select></label>' if is_host else ''}
          <button type="submit" class="btn-primary">Add</button>
        </form>
        """ if gear_rates else '<p class="muted">No gear types configured for this trip.</p>'

        lodge_section = ""
        lodge_note = ""
        if is_host:
            from_qs = "?from=accounting" if from_accounting else ""
            if not event["lodged_at"]:
                lodge_section = f"""
                <form method="post" action="{base}/fees/lodge{from_qs}" style="display:inline;">
                  <button type="submit" class="btn-primary">Lodge fees</button>
                </form>"""
                lodge_note = (
                    '<p class="muted">Not yet lodged -- contributions are still being gathered, so amounts '
                    'may still change. Please don\'t pay yet.</p>'
                )
            else:
                live_owes = {uid: a["owe"] for uid, a in accounts.items() if isinstance(uid, int)}
                lodged_totals = self._get_event_lodgement_totals(conn, event_id)
                diffs = {
                    uid for uid in set(live_owes) | set(lodged_totals)
                    if abs(lodged_totals.get(uid, Decimal("0")) - live_owes.get(uid, Decimal("0"))) >= Decimal("0.01")
                }
                lodge_section = f"""
                <form method="post" action="{base}/fees/amend{from_qs}" style="display:inline;">
                  <button type="submit" class="btn{' btn-primary' if diffs else ''}" {'' if diffs else 'disabled'}>Amend fees</button>
                </form>"""
                lodge_note = (
                    f'<p class="muted">Lodged {event["lodged_at"]:%d %b %Y, %I:%M %p}. '
                    + (f"{len(diffs)} member(s) have changed since -- click Amend to record the correction."
                       if diffs else "No changes since lodging.")
                    + "</p>"
                )

        share_section = ""
        if is_host and effective_user is None:
            if not event["share_view_token"] or not event["share_edit_token"]:
                with conn.cursor() as cur:
                    if not event["share_view_token"]:
                        event["share_view_token"] = secrets.token_urlsafe(32)
                        cur.execute("UPDATE events SET share_view_token = %s WHERE id = %s", (event["share_view_token"], event_id))
                    if not event["share_edit_token"]:
                        event["share_edit_token"] = secrets.token_urlsafe(32)
                        cur.execute("UPDATE events SET share_edit_token = %s WHERE id = %s", (event["share_edit_token"], event_id))
            view_url = f"{self._site_base_url()}/share/{event['share_view_token']}"
            edit_url = f"{self._site_base_url()}/share/{event['share_edit_token']}"
            share_section = f"""
            <button type="button" class="btn" onclick="document.getElementById('share-dialog').showModal()">Share</button>
            <dialog id="share-dialog" style="border:none; border-radius:8px; padding:0; max-width:480px; width:90%;">
              <div class="card" style="margin:0; box-shadow:none; border:none;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                  <h3 style="margin:0;">Share this trip's contributions</h3>
                  <button type="button" class="btn" onclick="document.getElementById('share-dialog').close()">&times;</button>
                </div>
                <p class="muted">Anyone with a link below can open it without logging in.</p>

                <p><strong>View only</strong> &mdash; shows just the "who owes what" summary, with a button to log in
                for the full page.</p>
                <button type="button" class="btn" onclick="copyShareLink('{html.escape(view_url, quote=True)}')">Copy view link</button>

                <p style="margin-top:1.2em;"><strong>Edit</strong> &mdash; shows the full page with working
                add/edit/delete, scoped to just this trip (no account or site-wide access needed).</p>
                <button type="button" class="btn" onclick="copyShareLink('{html.escape(edit_url, quote=True)}')">Copy edit link</button>

                <script>
                  function copyShareLink(url) {{
                    navigator.clipboard.writeText(url).then(() => showToast('Link copied to clipboard')).catch(() => showToast('Could not copy link'));
                  }}
                </script>
              </div>
            </dialog>
            """

        body = f"""
        <p>{back_link}</p>
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.6em;">
          <h1 style="margin:0;">{html.escape(event['title'])} &mdash; Contributions and Gear Hire</h1>
          <div style="display:flex; gap:0.5em; align-items:center;">{share_section}{lodge_section}</div>
        </div>
        {self._contributions_intro_note()}
        {lodge_note}
        {error_html}

        <div class="card">
        <h3>Who owes what</h3>
        <table>
          <tr><th>Name</th><th>Contributions</th><th></th><th>Fee</th><th></th><th>{'Owed (-Owe)' if event['lodged_at'] else 'Exp Owed (-Owe)'}</th><th></th></tr>
          {account_rows}
        </table>
        </div>
        {self._render_pay_dialog_and_script(bank_details)}

        <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <h3 style="margin:0;">Gear use</h3>
          <button type="button" class="btn-primary" onclick="document.getElementById('gear-use-dialog').showModal()" style="width:2.2em; height:2.2em; border-radius:50%; padding:0; font-size:1.2em; line-height:1;">+</button>
        </div>
        <p class="muted">A per-person fee for club gear used on this trip -- charged only to whoever used it, on
        top of their share of the trip's other costs.</p>
        <table>
          <tr><th>Participant</th><th>Gear</th><th>Amount</th><th></th></tr>
          {gear_use_rows or '<tr><td colspan="4" class="muted">None yet.</td></tr>'}
        </table>
        </div>

        <dialog id="gear-use-dialog" style="border:none; border-radius:8px; padding:0; max-width:380px; width:90%;">
          <div class="card" style="margin:0; box-shadow:none; border:none;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <h3 style="margin:0;">Add gear use</h3>
              <button type="button" class="btn" onclick="document.getElementById('gear-use-dialog').close()">&times;</button>
            </div>
            {add_gear_use_form}
          </div>
        </dialog>

        <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <h3 style="margin:0;">Contributions {self._maintenance_info_tooltip(self._resolve_distance_formula(conn, event))}</h3>
          <button type="button" class="btn-primary" onclick="document.getElementById('contribution-choice-dialog').showModal()" style="width:2.2em; height:2.2em; border-radius:50%; padding:0; font-size:1.2em; line-height:1;">+</button>
        </div>
        <table>
          <tr><th>Date</th><th>Description</th><th>Type</th><th>Paid by</th><th>Consumed by</th><th>Amount</th><th></th></tr>
          {contribution_rows or '<tr><td colspan="7">None yet</td></tr>'}
        </table>
        </div>

        <dialog id="contribution-choice-dialog" style="border:none; border-radius:8px; padding:0; max-width:360px; width:90%;">
          <div class="card" style="margin:0; box-shadow:none; border:none;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <h3 style="margin:0;">Add a contribution</h3>
              <button type="button" class="btn" onclick="document.getElementById('contribution-choice-dialog').close()">&times;</button>
            </div>
            <p class="muted">What did you contribute?</p>
            <div style="display:flex; flex-direction:column; gap:0.6em;">
              <button type="button" class="btn-primary" style="width:100%;" onclick="document.getElementById('contribution-choice-dialog').close(); document.getElementById('drove-dialog').showModal();">Driving</button>
              <button type="button" class="btn" style="width:100%;" onclick="document.getElementById('contribution-choice-dialog').close(); document.getElementById('add-contribution-dialog').showModal();">Something else</button>
            </div>
          </div>
        </dialog>

        <dialog id="drove-dialog" style="border:none; border-radius:8px; padding:0; max-width:460px; width:90%;">
          <div class="card" style="margin:0; box-shadow:none; border:none;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <h3 style="margin:0;">Driving</h3>
              <button type="button" class="btn" onclick="document.getElementById('drove-dialog').close()">&times;</button>
            </div>
            {drove_form_body}
          </div>
        </dialog>

        <dialog id="add-contribution-dialog" style="border:none; border-radius:8px; padding:0; max-width:460px; width:90%;">
          <div class="card" style="margin:0; box-shadow:none; border:none;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <h3 style="margin:0;">Add a contribution</h3>
              <button type="button" class="btn" onclick="document.getElementById('add-contribution-dialog').close()">&times;</button>
            </div>
            {add_form_body}
          </div>
        </dialog>
        """
        self._send_html(render_page(f"{event['title']} — Contributions and Gear Hire", body, user))

    def _render_paid_by_field(self, is_host, current_user, all_signed_up, current_contributor_id=None):
        """Only the host can log a contribution on behalf of another trip
        participant (picked from a lookup of who's signed up) -- everyone
        else always contributes as themselves."""
        if not is_host:
            return ""
        selected = current_contributor_id or current_user["id"]
        candidates = [{"id": current_user["id"], "name": "Myself"}] + [
            s for s in all_signed_up if s["id"] != current_user["id"]
        ]
        options = "".join(
            f'<option value="{c["id"]}"{" selected" if c["id"] == selected else ""}>{html.escape(c["name"])}</option>'
            for c in candidates
        )
        return f"""
          <label>Paid by
            <select name="contributor_id">{options}</select>
          </label>
        """

    def _render_contribution_form(self, action, submit_label, all_signed_up, distance_formula, contribution=None, is_host=False, current_user=None):
        current_type = contribution["type"] if contribution else "expense"
        amount_val = contribution["amount"] if contribution and current_type == "expense" else ""
        km_val = contribution["km"] if contribution and current_type == "driven_distance" else ""
        description_val = html.escape(contribution["description"]) if contribution else ""
        selected_ids = set(contribution["consumed_by_ids"]) if contribution else set()
        paid_by_field = self._render_paid_by_field(
            is_host, current_user, all_signed_up, contribution["contributor_id"] if contribution else None
        )

        consumer_checkboxes = "".join(
            f"""<label style="display:flex; align-items:center; gap:0.5em; font-weight:normal;">
                <input type="checkbox" name="consumed_by_ids" value="{s['id']}" style="width:auto; margin:0;"{" checked" if s['id'] in selected_ids else ""}>
                {html.escape(s['name'])}
              </label>"""
            for s in all_signed_up
        ) or '<p class="muted">No one has signed up yet.</p>'

        return f"""
        <form method="post" action="{action}" id="contrib-form">
          <label>Type
            <select name="type" onchange="document.getElementById('km-row').style.display = this.value === 'driven_distance' ? 'block' : 'none'; document.getElementById('amount-row').style.display = this.value === 'driven_distance' ? 'none' : 'block';">
              <option value="expense"{" selected" if current_type == "expense" else ""}>Expense (e.g. petrol, cave access fee)</option>
              <option value="driven_distance"{" selected" if current_type == "driven_distance" else ""}>Driven distance (km, formula: {html.escape(distance_formula)})</option>
            </select>
          </label>
          <label>Description<input name="description" value="{description_val}" required autofocus></label>
          <div id="amount-row" style="display:{'none' if current_type == 'driven_distance' else 'block'};">
            <label>Amount ($)<input name="amount" type="number" step="0.01" min="0" value="{amount_val}"></label>
          </div>
          <div id="km-row" style="display:{'block' if current_type == 'driven_distance' else 'none'};">
            <label>Distance (km)<input name="km" type="number" step="0.1" min="0" value="{km_val}"></label>
          </div>
          {paid_by_field}
          <label style="display:flex; justify-content:space-between; align-items:center;">
            Consumed by (optional &mdash; leave all unchecked to split across everyone)
            <span style="display:flex; gap:0.4em;">
              <button type="button" class="btn" style="padding:0.2em 0.6em; font-weight:normal;" onclick="this.closest('form').querySelectorAll('input[name=consumed_by_ids]').forEach(cb => cb.checked = true);">Select all</button>
              <button type="button" class="btn" style="padding:0.2em 0.6em; font-weight:normal;" onclick="this.closest('form').querySelectorAll('input[name=consumed_by_ids]').forEach(cb => cb.checked = false);">Select none</button>
            </span>
          </label>
          <div style="margin-bottom:0.8em;">{consumer_checkboxes}</div>
          <button type="submit" class="btn-primary">{html.escape(submit_label)}</button>
        </form>
        """

    def _render_drove_form(self, action, all_signed_up, distance_formula, is_host=False, current_user=None):
        consumer_checkboxes = "".join(
            f"""<label style="display:flex; align-items:center; gap:0.5em; font-weight:normal;">
                <input type="checkbox" name="consumed_by_ids" value="{s['id']}" style="width:auto; margin:0;">
                {html.escape(s['name'])}
              </label>"""
            for s in all_signed_up
        ) or '<p class="muted">No one has signed up yet.</p>'

        return f"""
        <form method="post" action="{action}" id="drove-form">
          <label>Distance driven return trip (km)
            <input name="km" type="number" step="0.1" min="0" placeholder="e.g. 120" required>
          </label>
          <p class="muted" style="margin-top:-0.4em;">Charged using the distance formula: {html.escape(distance_formula)}</p>
          <label>Petrol cost ($, optional)
            <input name="petrol_amount" type="number" step="0.01" min="0" placeholder="e.g. 40.00">
          </label>
          {self._render_paid_by_field(is_host, current_user, all_signed_up)}
          <label>Consumed by (optional &mdash; leave all unchecked to split across everyone)</label>
          <div style="margin-bottom:0.8em;">{consumer_checkboxes}</div>
          <button type="submit" class="btn-primary">Add</button>
        </form>
        """

    def _is_duplicate_contribution(self, conn, event_id, contributor_id, contributor_name, description):
        """True if this same person already has a contribution with this
        exact description on this trip (case-insensitive)."""
        with conn.cursor() as cur:
            if contributor_id:
                cur.execute(
                    "SELECT 1 FROM contributions WHERE event_id = %s AND contributor_id = %s AND LOWER(description) = LOWER(%s) LIMIT 1",
                    (event_id, contributor_id, description),
                )
            else:
                cur.execute(
                    "SELECT 1 FROM contributions WHERE event_id = %s AND contributor_id IS NULL "
                    "AND LOWER(contributor_name) = LOWER(%s) AND LOWER(description) = LOWER(%s) LIMIT 1",
                    (event_id, contributor_name or "", description),
                )
            return cur.fetchone() is not None

    def _get_event_and_host_by_edit_token(self, conn, token):
        """Resolves a contributions-page edit share-link token to (event,
        host_user) without creating any session -- used so the edit link
        grants full page functionality scoped to just this one event,
        rather than a real site-wide login as the host."""
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM events WHERE share_edit_token = %s", (token,))
            event = cur.fetchone()
            if not event:
                return None, None
            cur.execute("SELECT * FROM users WHERE id = %s", (event["host_id"],))
            host = cur.fetchone()
            return event, host

    def handle_share_link(self, conn, user, token):
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM events WHERE share_view_token = %s", (token,))
            event = cur.fetchone()
            mode = "view"
            if not event:
                cur.execute("SELECT * FROM events WHERE share_edit_token = %s", (token,))
                event = cur.fetchone()
                mode = "edit"
        if not event:
            return self._send_html(render_page("Not found", "<h1>404</h1>", user), status=404)

        if mode == "edit":
            _, host = self._get_event_and_host_by_edit_token(conn, token)
            return self.handle_contributions_page(
                conn, None, event["id"], effective_user=host, event_base=f"/share/{token}"
            )

        accounts = self._compute_event_accounts(conn, event["id"])
        bank_details = self._get_bank_details(conn)
        account_rows = "".join(
            f"""<tr>
              <td>{html.escape(a['name'])}</td>
              <td class="owe-negative">{money(a['paid'])} {self._render_info_tooltip(a['paid_items'])}</td>
              <td class="muted" style="text-align:center;">&minus;</td>
              <td class="owe-positive">{money(a['fee'])} {self._render_info_tooltip(a['fee_items'])}</td>
              <td class="muted" style="text-align:center;">=</td>
              <td class="{'owe-positive' if a['owe'] > 0 else 'owe-negative' if a['owe'] < 0 else ''}">{signed_money(-a['owe'])}</td>
              <td>{self._pay_button(bank_details, f"{a['owe']:.2f}") if a['owe'] > 0 and event['lodged_at'] else ''}</td>
            </tr>"""
            for uid, a in accounts.items()
        )

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.*, COALESCE(cu.name, c.contributor_name) AS contributor_display_name
                FROM contributions c
                LEFT JOIN users cu ON cu.id = c.contributor_id
                WHERE c.event_id = %s AND c.gear_type_id IS NULL ORDER BY c.created_at
                """,
                (event["id"],),
            )
            contributions = list(cur.fetchall())

            cur.execute(
                """
                SELECT cc.contribution_id, cc.user_id, u.name
                FROM contribution_consumers cc
                JOIN users u ON u.id = cc.user_id
                JOIN contributions c ON c.id = cc.contribution_id
                WHERE c.event_id = %s
                """,
                (event["id"],),
            )
            consumers_by_contribution = {}
            for row in cur.fetchall():
                consumers_by_contribution.setdefault(row["contribution_id"], []).append(row)

            cur.execute(
                """
                SELECT c.id, c.amount, gt.name AS gear_name
                FROM contributions c
                JOIN gear_types gt ON gt.id = c.gear_type_id
                WHERE c.event_id = %s ORDER BY c.created_at
                """,
                (event["id"],),
            )
            gear_uses = list(cur.fetchall())

        for g in gear_uses:
            consumers = consumers_by_contribution.get(g["id"], [])
            g["participant_name"] = consumers[0]["name"] if consumers else "?"

        contribution_rows = "".join(
            f"""<tr>
              <td>{c['created_at']:%d %b}</td>
              <td>{html.escape(c['description'])}</td>
              <td>{c['type']}{f" ({c['km']} km)" if c['type'] == 'driven_distance' else ''}</td>
              <td>{html.escape(c['contributor_display_name'])}{' <span class="muted">(not a member)</span>' if not c['contributor_id'] else ''}</td>
              <td>{html.escape(', '.join(r['name'] for r in consumers_by_contribution.get(c['id'], []))) if consumers_by_contribution.get(c['id']) else '<em>shared</em>'}</td>
              <td>{money(c['amount'])}</td>
            </tr>"""
            for c in contributions
        )
        gear_use_rows = "".join(
            f"""<tr>
              <td>{html.escape(g['participant_name'])}</td>
              <td>{html.escape(g['gear_name'])}</td>
              <td>{money(g['amount'])}</td>
            </tr>"""
            for g in gear_uses
        )

        body = f"""
        <h1 style="margin:0;">{html.escape(event['title'])} &mdash; Who owes what</h1>
        <p class="muted">You're viewing a read-only shared summary. <a href="/login?next=/events/{event['id']}/contributions">Log in</a>
        to see the full contributions page.</p>
        {self._contributions_intro_note()}
        <div class="card">
        <table>
          <tr><th>Name</th><th>Contributions</th><th></th><th>Fee</th><th></th><th>{'Owed (-Owe)' if event['lodged_at'] else 'Exp Owed (-Owe)'}</th><th></th></tr>
          {account_rows}
        </table>
        {self._render_pay_dialog_and_script(bank_details)}
        </div>

        <div class="card">
        <h3>Gear use</h3>
        <table>
          <tr><th>Participant</th><th>Gear</th><th>Amount</th></tr>
          {gear_use_rows or '<tr><td colspan="3" class="muted">None yet.</td></tr>'}
        </table>
        </div>

        <div class="card">
        <h3>Contributions {self._maintenance_info_tooltip(self._resolve_distance_formula(conn, event))}</h3>
        <table>
          <tr><th>Date</th><th>Description</th><th>Type</th><th>Paid by</th><th>Consumed by</th><th>Amount</th></tr>
          {contribution_rows or '<tr><td colspan="6">None yet</td></tr>'}
        </table>
        </div>
        """
        self._send_html(render_page(f"{event['title']} -- Who owes what", body, user))

    def handle_contribution_submit(self, conn, user, event_id, form, effective_user=None, event_base=None):
        if effective_user is None:
            self._require_login(user)
        viewer = effective_user or user
        base = event_base or f"/events/{event_id}"
        event = self._get_event(conn, event_id)
        if not event:
            return redirect(self, "/")

        contribution_type = form.get("type") if form.get("type") in ("expense", "driven_distance") else "expense"
        description = form.get("description", "").strip()
        if not description:
            return redirect(self, f"{base}/contributions")
        amount_raw = form.get("amount", "").strip()
        km_raw = form.get("km", "").strip()
        consumed_by_ids = [int(v) for v in form.getlist("consumed_by_ids")]
        contributor_id_raw = form.get("contributor_id", "").strip()
        is_host = event["host_id"] == viewer["id"]
        contributor_id = int(contributor_id_raw) if is_host and contributor_id_raw else viewer["id"]
        contributor_name = None

        km = float(km_raw) if km_raw else None
        amount_input = float(amount_raw) if amount_raw else 0

        if self._is_duplicate_contribution(conn, event_id, contributor_id, contributor_name, description):
            return redirect(self, f"{base}/contributions?error=duplicate")

        distance_formula = self._resolve_distance_formula(conn, event)
        try:
            amount, rate = accounting.compute_contribution_amount(contribution_type, amount_input, km, distance_formula)
        except (ValueError, formula.FormulaError):
            redirect(self, f"{base}/contributions")
            return

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO contributions (event_id, contributor_id, contributor_name, type, description, amount, km, rate_per_km)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (event_id, contributor_id, contributor_name, contribution_type, description, str(amount), km, str(rate) if rate else None),
            )
            contribution_id = cur.lastrowid
            if consumed_by_ids:
                cur.executemany(
                    "INSERT INTO contribution_consumers (contribution_id, user_id) VALUES (%s, %s)",
                    [(contribution_id, uid) for uid in consumed_by_ids],
                )
        redirect(self, f"{base}/contributions")

    def handle_contribution_drove_submit(self, conn, user, event_id, form, effective_user=None, event_base=None):
        """"I drove" shortcut: records a driven_distance contribution (km,
        priced by the event's distance formula) and, if given, a separate
        petrol expense contribution -- both attributed to the same driver
        and split the same way, in one go."""
        if effective_user is None:
            self._require_login(user)
        viewer = effective_user or user
        base = event_base or f"/events/{event_id}"
        event = self._get_event(conn, event_id)
        if not event:
            return redirect(self, "/")

        km_raw = form.get("km", "").strip()
        petrol_raw = form.get("petrol_amount", "").strip()
        consumed_by_ids = [int(v) for v in form.getlist("consumed_by_ids")]
        contributor_id_raw = form.get("contributor_id", "").strip()
        is_host = event["host_id"] == viewer["id"]
        contributor_id = int(contributor_id_raw) if is_host and contributor_id_raw else viewer["id"]
        contributor_name = None

        if not km_raw:
            return redirect(self, f"{base}/contributions")
        km = float(km_raw)
        petrol_amount = float(petrol_raw) if petrol_raw else 0

        maintenance_dup = self._is_duplicate_contribution(conn, event_id, contributor_id, contributor_name, "Maintenance")
        petrol_dup = petrol_amount and self._is_duplicate_contribution(conn, event_id, contributor_id, contributor_name, "Petrol")
        if maintenance_dup and (not petrol_amount or petrol_dup):
            return redirect(self, f"{base}/contributions?error=duplicate")

        distance_formula = self._resolve_distance_formula(conn, event)
        try:
            amount, rate = accounting.compute_contribution_amount("driven_distance", 0, km, distance_formula)
        except (ValueError, formula.FormulaError):
            return redirect(self, f"{base}/contributions")

        with conn.cursor() as cur:
            contribution_ids = []
            if not maintenance_dup:
                cur.execute(
                    """
                    INSERT INTO contributions (event_id, contributor_id, contributor_name, type, description, amount, km, rate_per_km)
                    VALUES (%s, %s, %s, 'driven_distance', 'Maintenance', %s, %s, %s)
                    """,
                    (event_id, contributor_id, contributor_name, str(amount), km, str(rate) if rate else None),
                )
                contribution_ids.append(cur.lastrowid)

            if petrol_amount and not petrol_dup:
                petrol_decimal, _ = accounting.compute_contribution_amount("expense", petrol_amount, None)
                cur.execute(
                    """
                    INSERT INTO contributions (event_id, contributor_id, contributor_name, type, description, amount)
                    VALUES (%s, %s, %s, 'expense', 'Petrol', %s)
                    """,
                    (event_id, contributor_id, contributor_name, str(petrol_decimal)),
                )
                contribution_ids.append(cur.lastrowid)

            if consumed_by_ids:
                cur.executemany(
                    "INSERT INTO contribution_consumers (contribution_id, user_id) VALUES (%s, %s)",
                    [(cid, uid) for cid in contribution_ids for uid in consumed_by_ids],
                )
        redirect(self, f"{base}/contributions")

    def handle_contribution_delete(self, conn, user, event_id, contribution_id, effective_user=None, event_base=None):
        if effective_user is None:
            self._require_login(user)
        viewer = effective_user or user
        base = event_base or f"/events/{event_id}"
        event = self._get_event(conn, event_id)
        contribution = self._get_contribution(conn, contribution_id)
        if not event or not contribution or contribution["event_id"] != event_id:
            return redirect(self, f"{base}/contributions")
        if not self._can_edit_contribution(event, contribution, viewer):
            return self._send_html(render_page("Forbidden", "<h1>You can't delete this contribution.</h1>", user), status=403)

        with conn.cursor() as cur:
            cur.execute("DELETE FROM contributions WHERE id = %s", (contribution_id,))
        redirect(self, f"{base}/contributions")

    def handle_gear_use_submit(self, conn, user, event_id, form, effective_user=None, event_base=None):
        """Records a per-person gear-use fee: stored as a regular
        `contributions` row (gear_type_id set, contributor_id NULL -- nobody
        "paid" the club, it's just a direct charge) with a single
        contribution_consumers row for whoever used it, so it flows into
        the existing fee-splitting machinery (accounting.py) automatically."""
        if effective_user is None:
            self._require_login(user)
        viewer = effective_user or user
        base = event_base or f"/events/{event_id}"
        event = self._get_event(conn, event_id)
        if not event:
            return redirect(self, "/")
        is_host = event["host_id"] == viewer["id"]

        gear_type_id_raw = form.get("gear_type_id", "").strip()
        if not gear_type_id_raw:
            return redirect(self, f"{base}/contributions")
        gear_type_id = int(gear_type_id_raw)

        participant_id_raw = form.get("participant_id", "").strip()
        participant_id = int(participant_id_raw) if is_host and participant_id_raw else viewer["id"]

        with conn.cursor() as cur:
            cur.execute(
                "SELECT gt.name, COALESCE(egr.rate, gt.rate) AS rate FROM gear_types gt "
                "LEFT JOIN event_gear_rates egr ON egr.gear_type_id = gt.id AND egr.event_id = %s "
                "WHERE gt.id = %s",
                (event_id, gear_type_id),
            )
            gear = cur.fetchone()
            if not gear:
                return redirect(self, f"{base}/contributions")
            cur.execute(
                """
                INSERT INTO contributions (event_id, contributor_id, type, description, amount, gear_type_id)
                VALUES (%s, NULL, 'expense', %s, %s, %s)
                """,
                (event_id, gear["name"], str(gear["rate"]), gear_type_id),
            )
            contribution_id = cur.lastrowid
            cur.execute(
                "INSERT INTO contribution_consumers (contribution_id, user_id) VALUES (%s, %s)",
                (contribution_id, participant_id),
            )
        redirect(self, f"{base}/contributions")

    def handle_gear_use_delete(self, conn, user, event_id, contribution_id, effective_user=None, event_base=None):
        if effective_user is None:
            self._require_login(user)
        viewer = effective_user or user
        base = event_base or f"/events/{event_id}"
        event = self._get_event(conn, event_id)
        if not event:
            return redirect(self, f"{base}/contributions")
        is_host = event["host_id"] == viewer["id"]
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT cc.user_id FROM contributions c
                JOIN contribution_consumers cc ON cc.contribution_id = c.id
                WHERE c.id = %s AND c.event_id = %s AND c.gear_type_id IS NOT NULL
                """,
                (contribution_id, event_id),
            )
            row = cur.fetchone()
            if not row:
                return redirect(self, f"{base}/contributions")
            if not is_host and row["user_id"] != viewer["id"]:
                return self._send_html(render_page("Forbidden", "<h1>You can't remove this gear use.</h1>", user), status=403)
            cur.execute("DELETE FROM contributions WHERE id = %s", (contribution_id,))
        redirect(self, f"{base}/contributions")

    def _fees_redirect(self, event_id, event_base=None):
        from_accounting = parse_qs(urlparse(self.path).query).get("from", [""])[0] == "accounting"
        base = event_base or f"/events/{event_id}"
        redirect(self, f"{base}/contributions" + ("?from=accounting" if from_accounting else ""))

    def handle_fees_lodge(self, conn, user, event_id, effective_user=None, event_base=None):
        """First-time lodging: records each participant's current owed
        amount for this trip as a row in event_fee_lodgements, and marks
        the trip lodged -- only from here does it count toward the
        club-wide Member balances (see handle_accounting_page). One-shot:
        once lodged, further changes go through handle_fees_amend instead,
        which leaves a visible correction trail rather than rewriting
        these rows."""
        if effective_user is None:
            self._require_login(user)
        viewer = effective_user or user
        event = self._get_event(conn, event_id)
        if not event:
            return redirect(self, "/")
        if event["host_id"] != viewer["id"]:
            return self._send_html(render_page("Forbidden", "<h1>Only the host can do this.</h1>", user), status=403)
        if event["lodged_at"]:
            return self._fees_redirect(event_id, event_base)  # already lodged -- amend instead

        live_owes = self._get_event_live_owes(conn, event_id)
        with conn.cursor() as cur:
            for uid, owe in live_owes.items():
                if owe != 0:
                    cur.execute(
                        "INSERT INTO event_fee_lodgements (event_id, user_id, description, amount) VALUES (%s, %s, %s, %s)",
                        (event_id, uid, f"Trip: {event['title']}", str(owe)),
                    )
            cur.execute("UPDATE events SET lodged_at = NOW() WHERE id = %s", (event_id,))
        self._fees_redirect(event_id, event_base)

    def handle_fees_amend(self, conn, user, event_id, effective_user=None, event_base=None):
        """For each member whose live owe no longer matches their lodged
        total, records a reversal row (negating the old lodged total) and
        a revision row (the new amount) -- so the member's balance history
        (handle_accounting_user_balance_page) shows the correction as two
        visible entries rather than silently changing a number."""
        if effective_user is None:
            self._require_login(user)
        viewer = effective_user or user
        event = self._get_event(conn, event_id)
        if not event:
            return redirect(self, "/")
        if event["host_id"] != viewer["id"]:
            return self._send_html(render_page("Forbidden", "<h1>Only the host can do this.</h1>", user), status=403)
        if not event["lodged_at"]:
            return self._fees_redirect(event_id, event_base)  # nothing lodged yet -- lodge instead

        diffs = self._get_event_lodgement_diffs(conn, event_id)
        with conn.cursor() as cur:
            for uid, (lodged, live) in diffs.items():
                if lodged != 0:
                    cur.execute(
                        "INSERT INTO event_fee_lodgements (event_id, user_id, description, amount) VALUES (%s, %s, %s, %s)",
                        (event_id, uid, f"Trip: {event['title']} (reverted)", str(-lodged)),
                    )
                if live != 0:
                    cur.execute(
                        "INSERT INTO event_fee_lodgements (event_id, user_id, description, amount) VALUES (%s, %s, %s, %s)",
                        (event_id, uid, f"Trip: {event['title']} (revised)", str(live)),
                    )
        self._fees_redirect(event_id, event_base)

    def handle_event_checklist_submit(self, conn, user, event_id, form):
        """Host picks which club-wide checklist_items this trip requires --
        replaces the trip's whole set of required skills/items with
        whatever's checked in the form."""
        self._require_login(user)
        event = self._get_event(conn, event_id)
        if not event:
            return redirect(self, "/")
        if event["host_id"] != user["id"]:
            return self._send_html(render_page("Forbidden", "<h1>Only the host can edit this trip's checklist.</h1>", user), status=403)
        checklist_item_ids = self._parse_checklist_form_submission(conn, form)
        self._save_event_checklist(conn, event_id, checklist_item_ids)
        redirect(self, f"/events/{event_id}")

    def handle_event_guest_add(self, conn, user, event_id, form):
        """The host adds someone who went on this trip but has no account
        here (e.g. backfilling an old trip's attendance sheet): creates a
        no-login guest account for them (see schema.sql's users.password_hash)
        and signs them up as approved -- from here on they're a full
        participant like anyone else, with no special-casing needed
        elsewhere (contributions, fee-splitting, etc)."""
        self._require_login(user)
        event = self._get_event(conn, event_id)
        if not event:
            return redirect(self, "/")
        if event["host_id"] != user["id"]:
            return self._send_html(render_page("Forbidden", "<h1>Only the host can add guests.</h1>", user), status=403)
        name = form.get("name", "").strip()
        email = form.get("email", "").strip().lower()
        reopen = "?add_participant=1" if form.get("add_another") else ""
        if name and email:
            with conn.cursor() as cur:
                try:
                    cur.execute("INSERT INTO users (name, email) VALUES (%s, %s)", (name, email))
                except pymysql.err.IntegrityError:
                    # Someone with this email already has an account -- don't
                    # create a second, conflicting one for the same person.
                    return redirect(self, f"/events/{event_id}{reopen}")
                guest_id = cur.lastrowid
                cur.execute(
                    "INSERT INTO event_signups (event_id, user_id, status) VALUES (%s, %s, 'approved')",
                    (event_id, guest_id),
                )
        redirect(self, f"/events/{event_id}{reopen}")

    def handle_event_guest_add_existing(self, conn, user, event_id, form):
        """The host picks an existing member from the lookup in the "Add a
        participant" dialog and signs them up directly as approved,
        bypassing the normal request/approve signup flow (e.g. adding
        someone who forgot to sign up themselves)."""
        self._require_login(user)
        event = self._get_event(conn, event_id)
        if not event:
            return redirect(self, "/")
        if event["host_id"] != user["id"]:
            return self._send_html(render_page("Forbidden", "<h1>Only the host can add participants.</h1>", user), status=403)
        user_id_raw = form.get("user_id", "").strip()
        if user_id_raw:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT IGNORE INTO event_signups (event_id, user_id, status) VALUES (%s, %s, 'approved')",
                    (event_id, int(user_id_raw)),
                )
        reopen = "?add_participant=1" if form.get("add_another") else ""
        redirect(self, f"/events/{event_id}{reopen}")

    def handle_event_guest_remove(self, conn, user, event_id, guest_id):
        """Removes a no-login guest account's signup from this trip -- they
        can't log in to leave themselves, so the host does it. The guest
        account itself is left alone (harmless, and may have contributions
        recorded against it worth keeping)."""
        self._require_login(user)
        event = self._get_event(conn, event_id)
        if not event:
            return redirect(self, "/")
        if event["host_id"] != user["id"]:
            return self._send_html(render_page("Forbidden", "<h1>Only the host can remove guests.</h1>", user), status=403)
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM event_signups WHERE event_id = %s AND user_id = %s "
                "AND user_id IN (SELECT id FROM users WHERE password_hash IS NULL)",
                (event_id, guest_id),
            )
        redirect(self, f"/events/{event_id}")

    def _get_contribution(self, conn, contribution_id):
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM contributions WHERE id = %s", (contribution_id,))
            contribution = cur.fetchone()
            if contribution:
                cur.execute(
                    "SELECT user_id FROM contribution_consumers WHERE contribution_id = %s",
                    (contribution_id,),
                )
                contribution["consumed_by_ids"] = [r["user_id"] for r in cur.fetchall()]
            return contribution

    def _can_edit_contribution(self, event, contribution, user):
        return (contribution["contributor_id"] is not None and contribution["contributor_id"] == user["id"]) or event["host_id"] == user["id"]

    def handle_contribution_edit_form(self, conn, user, event_id, contribution_id, effective_user=None, event_base=None):
        if effective_user is None:
            self._require_login(user)
        viewer = effective_user or user
        base = event_base or f"/events/{event_id}"
        event = self._get_event(conn, event_id)
        contribution = self._get_contribution(conn, contribution_id)
        if not event or not contribution or contribution["event_id"] != event_id:
            return self._send_html(render_page("Not found", "<h1>Not found</h1>", user), status=404)
        if not self._can_edit_contribution(event, contribution, viewer):
            return self._send_html(render_page("Forbidden", "<h1>You can't edit this contribution.</h1>", user), status=403)

        with conn.cursor() as cur:
            cur.execute(
                "SELECT s.user_id AS id, u.name FROM event_signups s JOIN users u ON u.id = s.user_id WHERE s.event_id = %s",
                (event_id,),
            )
            all_signed_up = list(cur.fetchall())

        form_body = self._render_contribution_form(
            f"{base}/contributions/{contribution_id}/edit", "Save changes", all_signed_up,
            self._resolve_distance_formula(conn, event), contribution=contribution,
            is_host=(event["host_id"] == viewer["id"]), current_user=viewer
        )
        body = f"""
        <p><a href="{base}/contributions">&larr; back to contributions</a></p>
        <div class="card">
        <h1>Edit contribution</h1>
        {form_body}
        </div>
        """
        self._send_html(render_page("Edit contribution", body, user))

    def handle_contribution_edit_submit(self, conn, user, event_id, contribution_id, form, effective_user=None, event_base=None):
        if effective_user is None:
            self._require_login(user)
        viewer = effective_user or user
        base = event_base or f"/events/{event_id}"
        event = self._get_event(conn, event_id)
        contribution = self._get_contribution(conn, contribution_id)
        if not event or not contribution or contribution["event_id"] != event_id:
            return redirect(self, f"{base}/contributions")
        if not self._can_edit_contribution(event, contribution, viewer):
            return self._send_html(render_page("Forbidden", "<h1>You can't edit this contribution.</h1>", user), status=403)

        contribution_type = form.get("type") if form.get("type") in ("expense", "driven_distance") else "expense"
        description = form.get("description", "").strip()
        if not description:
            return redirect(self, f"{base}/contributions")
        amount_raw = form.get("amount", "").strip()
        km_raw = form.get("km", "").strip()
        consumed_by_ids = [int(v) for v in form.getlist("consumed_by_ids")]
        contributor_id_raw = form.get("contributor_id", "").strip()
        is_host = event["host_id"] == viewer["id"]
        original_contributor_id = contribution["contributor_id"]
        contributor_id = int(contributor_id_raw) if is_host and contributor_id_raw else (original_contributor_id or viewer["id"])
        contributor_name = None

        km = float(km_raw) if km_raw else None
        amount_input = float(amount_raw) if amount_raw else 0
        try:
            amount, rate = accounting.compute_contribution_amount(
                contribution_type, amount_input, km, self._resolve_distance_formula(conn, event)
            )
        except (ValueError, formula.FormulaError):
            return redirect(self, f"{base}/contributions")

        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE contributions
                SET type = %s, description = %s, amount = %s, km = %s, rate_per_km = %s, contributor_id = %s, contributor_name = %s
                WHERE id = %s
                """,
                (contribution_type, description, str(amount), km, str(rate) if rate else None, contributor_id, contributor_name, contribution_id),
            )
            cur.execute("DELETE FROM contribution_consumers WHERE contribution_id = %s", (contribution_id,))
            if consumed_by_ids:
                cur.executemany(
                    "INSERT INTO contribution_consumers (contribution_id, user_id) VALUES (%s, %s)",
                    [(contribution_id, uid) for uid in consumed_by_ids],
                )
        redirect(self, f"{base}/contributions")


class PermissionErrorRedirect(Exception):
    def __init__(self, location):
        super().__init__(location)
        self.location = location


def main():
    server = ThreadingHTTPServer((config.HOST, config.PORT), Handler)
    server._shared_conn = None
    anusport_daemon.start()  # no-op loop until an admin enables it via /admin/anusport-sync (off by default)
    print(f"Serving on http://{config.HOST}:{config.PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
