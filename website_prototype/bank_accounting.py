"""
Parsing and member-matching for the club bank account's transaction history
(see the Accounting module in app.py).

Reconciliation works per-member, not per-trip/tag: a transaction is matched
to whichever member's bank_name_aliases covers its description, and that's
the only linkage this module is concerned with.
"""

import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation


class CsvParseError(ValueError):
    pass


def _parse_money(raw):
    raw = raw.strip().replace(",", "")
    if not raw:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        raise CsvParseError(f"couldn't parse amount '{raw}'")


def match_user(description, users):
    """Guesses which user a bank transaction's description is from/to, by
    looking for one of their bank_name_aliases (comma-separated) as a
    case-insensitive substring of the description -- the bank's own export
    always puts the other party's name right after "From "/"To " at the
    start of the free-text part, e.g. "Fast Transfer From ALICE KELLY Wee j
    double pay" or "Transfer To A ROBERTS PayID Phone from NetBank ...".

    `users`: list of dicts with 'id' and 'bank_name_aliases' (str or None).
    Returns the matching user's id, or None. If more than one user's alias
    matches, prefers the longest alias (most specific) to avoid e.g. a bare
    first name shadowing a fuller match.
    """
    desc_lower = description.lower()
    best_id, best_len = None, 0
    for u in users:
        aliases = (u.get("bank_name_aliases") or "").split(",")
        for alias in aliases:
            alias = alias.strip()
            if alias and alias.lower() in desc_lower and len(alias) > best_len:
                best_id, best_len = u["id"], len(alias)
    return best_id


def parse_combank_csv(text):
    """The bank's own export: date (DD/MM/YYYY), amount ("+12.34"/"-12.34"),
    description -- no header row. Any extra columns are ignored."""
    reader = csv.reader(io.StringIO(text))
    rows = []
    for line_no, row in enumerate(reader, start=1):
        if not row or not any(cell.strip() for cell in row):
            continue
        if len(row) < 3:
            raise CsvParseError(f"line {line_no}: expected at least 3 columns, got {len(row)}")
        date_raw, amount_raw, description = row[0].strip(), row[1], row[2].strip()
        try:
            txn_date = datetime.strptime(date_raw, "%d/%m/%Y").date()
        except ValueError:
            raise CsvParseError(f"line {line_no}: couldn't parse date '{date_raw}' (expected DD/MM/YYYY)")
        amount = _parse_money(amount_raw)
        if amount is None:
            raise CsvParseError(f"line {line_no}: missing amount")
        rows.append({"date": txn_date, "amount": amount, "description": description})
    return rows


def to_csv(transactions):
    """transactions: list of dicts with 'date', 'amount', 'description'.
    Returns CSV text: date (DD/MM/YYYY), amount, description."""
    out = io.StringIO()
    writer = csv.writer(out)
    for t in transactions:
        writer.writerow([
            t["date"].strftime("%d/%m/%Y") if hasattr(t["date"], "strftime") else t["date"],
            str(t["amount"]),
            t["description"],
        ])
    return out.getvalue()
