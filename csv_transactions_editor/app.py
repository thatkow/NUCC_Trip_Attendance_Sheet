#!/usr/bin/env python3
"""
Small standalone tool for building a bank-transactions CSV by hand: add,
edit and delete rows in a table, then download the result as CSV.

Output format matches the club bank export used by the main site's
accounting import (see website_prototype/bank_accounting.py
parse_combank_csv): one row per transaction, no header, columns

    date (DD/MM/YYYY), amount, description

State lives in memory only (this is a scratch tool, not a database) --
restarting the server clears the table. Use Download CSV to save your work.
"""

import csv
import html
import io
import os
import socketserver
from datetime import date
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, quote

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8030"))

transactions = []  # list of {"id": int, "date": str, "amount": str, "description": str}
next_id = 1


def _parse_form(body):
    return {k: v[0] for k, v in parse_qs(body, keep_blank_values=True).items()}


def _parse_multipart_file(body, content_type):
    """Pulls the first file part's raw bytes out of a multipart/form-data
    body (stdlib has no multipart parser since cgi was removed). Returns
    None if there's no boundary or no file part with content."""
    marker = "boundary="
    idx = content_type.find(marker)
    if idx == -1:
        return None
    boundary = content_type[idx + len(marker):].strip().strip('"').encode()
    parts = body.split(b"--" + boundary)
    for part in parts:
        part = part.strip(b"\r\n")
        if not part or part == b"--":
            continue
        if b"\r\n\r\n" not in part:
            continue
        headers, _, content = part.partition(b"\r\n\r\n")
        if b"filename=" not in headers:
            continue
        content = content.rstrip(b"\r\n")
        if content:
            return content
    return None


def _parse_imported_csv(text):
    """Parses an uploaded transactions CSV: date (DD/MM/YYYY), amount,
    description, no header -- same shape this tool exports. Extra columns
    are ignored; blank lines are skipped. Returns (rows, errors)."""
    rows, errors = [], []
    reader = csv.reader(io.StringIO(text))
    for line_no, row in enumerate(reader, start=1):
        if not row or not any(cell.strip() for cell in row):
            continue
        if len(row) < 3:
            errors.append(f"line {line_no}: expected at least 3 columns, got {len(row)}")
            continue
        raw_date, amount, description = row[0].strip(), row[1].strip(), row[2].strip()
        d, m, y = (raw_date.split("/") + ["", "", ""])[:3]
        if not (d.isdigit() and m.isdigit() and y.isdigit() and len(y) == 4):
            errors.append(f"line {line_no}: couldn't parse date '{raw_date}' (expected DD/MM/YYYY)")
            continue
        try:
            float(amount)
        except ValueError:
            errors.append(f"line {line_no}: couldn't parse amount '{amount}'")
            continue
        rows.append({"date": raw_date, "amount": amount, "description": description})
    return rows, errors


def _row_html(t):
    return f"""
    <tr>
      <td>{html.escape(t['date'])}</td>
      <td class="amount">{html.escape(t['amount'])}</td>
      <td>{html.escape(t['description'])}</td>
      <td class="actions">
        <a class="btn" href="/transactions/{t['id']}/edit">Edit</a>
        <form class="inline" method="post" action="/transactions/{t['id']}/delete" onsubmit="return confirm('Delete this transaction?');">
          <button type="submit" class="btn btn-danger">Delete</button>
        </form>
      </td>
    </tr>"""


PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Transactions CSV builder</title>
<style>
  :root {{
    --border: #d9dde3; --muted: #65676b; --blue: #1877f2; --blue-dark: #166fe0;
    --red: #e41e3f; --bg: #f0f2f5; --card: #fff; --text: #1c1e21;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: var(--bg); color: var(--text); margin: 0; padding: 2em 1em;
  }}
  .wrap {{ max-width: 920px; margin: 0 auto; }}
  h1 {{ font-size: 1.5em; margin: 0 0 0.2em; }}
  p.muted {{ color: var(--muted); margin-top: 0; }}
  .card {{
    background: var(--card); border: 1px solid var(--border); border-radius: 8px;
    padding: 1.2em; margin-bottom: 1.2em; box-shadow: 0 1px 2px rgba(0,0,0,0.06);
  }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border-bottom: 1px solid #eee; padding: 0.5em 0.6em; text-align: left; vertical-align: top; }}
  th {{ color: var(--muted); font-weight: 600; font-size: 0.85em; text-transform: uppercase; letter-spacing: 0.02em; }}
  td.amount {{ font-variant-numeric: tabular-nums; white-space: nowrap; }}
  td.actions {{ white-space: nowrap; display: flex; gap: 0.4em; }}
  form.inline {{ display: inline; }}
  label {{ display: block; font-weight: 600; font-size: 0.9em; margin-bottom: 0.3em; }}
  input {{
    width: 100%; padding: 0.5em 0.6em; border: 1px solid var(--border); border-radius: 6px;
    font-size: 0.95em; margin-bottom: 0.9em;
  }}
  .add-row {{ display: grid; grid-template-columns: 9em 8em 1fr auto; gap: 0.8em; align-items: end; }}
  .add-row label {{ margin-bottom: 0.3em; }}
  .add-row input {{ margin-bottom: 0; }}
  @media (max-width: 640px) {{ .add-row {{ grid-template-columns: 1fr; }} }}
  button, .btn {{
    padding: 0.5em 1em; cursor: pointer; border-radius: 6px; border: 1px solid var(--border);
    background: #e4e6eb; font-weight: 600; font-size: 0.9em; color: var(--text);
    text-decoration: none; display: inline-block;
  }}
  button[type="submit"].btn-primary, .btn-primary {{ background: var(--blue); color: #fff; border-color: var(--blue); }}
  button[type="submit"].btn-primary:hover, .btn-primary:hover {{ background: var(--blue-dark); }}
  .btn-danger {{ background: #fff; color: var(--red); border-color: var(--red); }}
  .btn-danger:hover {{ background: #fdeced; }}
  .top-row {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 1em; flex-wrap: wrap; }}
  .empty {{ color: var(--muted); padding: 1em 0; }}
  .message {{ padding: 0.8em 1em; border-radius: 6px; margin-bottom: 1.2em; font-size: 0.92em; }}
  .message.success {{ background: #e3f3df; color: #2a7a1f; border: 1px solid #c3e6c0; }}
  .message.error {{ background: #fdeced; color: #b3261e; border: 1px solid #f5c2bf; white-space: pre-line; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="top-row">
    <div>
      <h1>Transactions CSV builder</h1>
      <p class="muted">Build a transactions CSV by hand: date (DD/MM/YYYY), amount, description &mdash; no header row, matching the bank export format.</p>
    </div>
    <div style="display:flex; gap:0.6em; align-items:center;">
      <form method="post" action="/import" enctype="multipart/form-data" style="display:flex; gap:0.5em; align-items:center;">
        <input type="file" name="file" accept=".csv" required style="width:auto; margin:0;">
        <button type="submit" class="btn">Import CSV</button>
      </form>
      <a class="btn btn-primary" href="/download">&#8681; Download CSV</a>
    </div>
  </div>

  {message}

  <div class="card">
    <h3 style="margin-top:0;">Add a transaction</h3>
    <form class="add-row" method="post" action="/transactions">
      <div><label>Date<input type="date" name="date" value="{today}" required></label></div>
      <div><label>Amount<input type="number" step="0.01" name="amount" placeholder="-22.16" required></label></div>
      <div><label>Description<input type="text" name="description" placeholder="e.g. Fast Transfer From Andrew Dart Yagby trip fee" required autofocus></label></div>
      <div><button type="submit" class="btn-primary">Add</button></div>
    </form>
  </div>

  <div class="card">
    <table>
      <tr><th>Date</th><th>Amount</th><th>Description</th><th></th></tr>
      {rows}
    </table>
    {empty}
  </div>
</div>
</body>
</html>"""

EDIT_PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Edit transaction</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #f0f2f5; margin: 0; padding: 2em 1em; }}
  .wrap {{ max-width: 480px; margin: 0 auto; }}
  .card {{ background: #fff; border: 1px solid #d9dde3; border-radius: 8px; padding: 1.2em; box-shadow: 0 1px 2px rgba(0,0,0,0.06); }}
  label {{ display: block; font-weight: 600; font-size: 0.9em; margin-bottom: 0.3em; }}
  input {{ width: 100%; padding: 0.5em 0.6em; border: 1px solid #d9dde3; border-radius: 6px; font-size: 0.95em; margin-bottom: 0.9em; box-sizing: border-box; }}
  button {{ padding: 0.5em 1.1em; cursor: pointer; border-radius: 6px; border: 1px solid #1877f2; background: #1877f2; color: #fff; font-weight: 600; font-size: 0.95em; }}
  a {{ color: #1877f2; text-decoration: none; font-size: 0.9em; }}
</style>
</head>
<body>
<div class="wrap">
  <p><a href="/">&larr; back</a></p>
  <div class="card">
    <h1 style="margin-top:0; font-size:1.3em;">Edit transaction</h1>
    <form method="post" action="/transactions/{id}/edit">
      <label>Date<input type="date" name="date" value="{date}" required></label>
      <label>Amount<input type="number" step="0.01" name="amount" value="{amount}" required></label>
      <label>Description<input type="text" name="description" value="{description}" required autofocus></label>
      <button type="submit">Save changes</button>
    </form>
  </div>
</div>
</body>
</html>"""


def _to_display_date(iso_date):
    """<input type=date> gives YYYY-MM-DD; the CSV/export format is DD/MM/YYYY."""
    try:
        y, m, d = iso_date.split("-")
        return f"{d}/{m}/{y}"
    except ValueError:
        return iso_date


def _to_iso_date(display_date):
    """DD/MM/YYYY -> YYYY-MM-DD, for prefilling the <input type=date> on edit."""
    try:
        d, m, y = display_date.split("/")
        return f"{y}-{m}-{d}"
    except ValueError:
        return display_date


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send_html(self, body, status=200):
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def _read_form(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length else ""
        return _parse_form(body)

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            query = parse_qs(self.path.partition("?")[2])
            imported = query.get("imported", [None])[0]
            errors = query.get("errors", [None])[0]
            if errors:
                message = f'<div class="message error">Import had problems:\n{html.escape(errors)}</div>'
            elif imported:
                message = f'<div class="message success">Imported {html.escape(imported)} transaction(s).</div>'
            else:
                message = ""
            rows = "".join(_row_html(t) for t in transactions)
            empty = '<p class="empty">No transactions yet &mdash; add one above.</p>' if not transactions else ""
            self._send_html(PAGE.format(today=date.today().isoformat(), rows=rows, empty=empty, message=message))
            return

        if self.path == "/download":
            out = io.StringIO()
            writer = csv.writer(out)
            for t in transactions:
                writer.writerow([t["date"], t["amount"], t["description"]])
            encoded = out.getvalue().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="transactions.csv"')
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return

        if self.path.startswith("/transactions/") and self.path.endswith("/edit"):
            try:
                tid = int(self.path.split("/")[2])
            except (IndexError, ValueError):
                return self._redirect("/")
            t = next((x for x in transactions if x["id"] == tid), None)
            if not t:
                return self._redirect("/")
            self._send_html(EDIT_PAGE.format(
                id=t["id"], date=_to_iso_date(t["date"]),
                amount=html.escape(t["amount"]), description=html.escape(t["description"]),
            ))
            return

        self._redirect("/")

    def do_POST(self):
        global next_id

        if self.path == "/import":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b""
            content_type = self.headers.get("Content-Type", "")
            file_bytes = _parse_multipart_file(body, content_type)
            if not file_bytes:
                return self._redirect("/?errors=" + quote("no file uploaded"))
            try:
                text = file_bytes.decode("utf-8-sig")
            except UnicodeDecodeError:
                return self._redirect("/?errors=" + quote("file isn't valid UTF-8 text"))
            rows, errors = _parse_imported_csv(text)
            for row in rows:
                row["id"] = next_id
                next_id += 1
                transactions.append(row)
            if errors:
                return self._redirect("/?imported=" + str(len(rows)) + "&errors=" + quote("\n".join(errors)))
            return self._redirect("/?imported=" + str(len(rows)))

        if self.path == "/transactions":
            form = self._read_form()
            iso_date = form.get("date", "").strip()
            amount = form.get("amount", "").strip()
            description = form.get("description", "").strip()
            if iso_date and amount and description:
                transactions.append({
                    "id": next_id,
                    "date": _to_display_date(iso_date),
                    "amount": amount,
                    "description": description,
                })
                next_id += 1
            return self._redirect("/")

        if self.path.startswith("/transactions/") and self.path.endswith("/edit"):
            try:
                tid = int(self.path.split("/")[2])
            except (IndexError, ValueError):
                return self._redirect("/")
            form = self._read_form()
            t = next((x for x in transactions if x["id"] == tid), None)
            if t:
                iso_date = form.get("date", "").strip()
                amount = form.get("amount", "").strip()
                description = form.get("description", "").strip()
                if iso_date and amount and description:
                    t["date"] = _to_display_date(iso_date)
                    t["amount"] = amount
                    t["description"] = description
            return self._redirect("/")

        if self.path.startswith("/transactions/") and self.path.endswith("/delete"):
            try:
                tid = int(self.path.split("/")[2])
            except (IndexError, ValueError):
                return self._redirect("/")
            transactions[:] = [x for x in transactions if x["id"] != tid]
            return self._redirect("/")

        self._redirect("/")


def main():
    with socketserver.ThreadingTCPServer((HOST, PORT), Handler) as server:
        print(f"Serving on http://{HOST}:{PORT}")
        server.serve_forever()


if __name__ == "__main__":
    main()
