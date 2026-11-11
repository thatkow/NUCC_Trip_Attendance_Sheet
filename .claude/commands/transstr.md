---
description: Fetch the Accounting Member balances page and output a transactions CSV string that would settle every non-settled member.
---

Fetch `http://localhost:8020/accounting` using `website_prototype/dev_scripts/curl_as.sh kow.andrew@gmail.com http://localhost:8020/accounting` (the dev server must be running on port 8020).

From the "Member balances" table in the response HTML, take every row whose Net is not $0.00 (skip "Settled" rows) and emit one CSV line per member in the bank-transactions format used by `/accounting/transactions` import (no header row): `date,amount,description`.

- `date`: today's date as DD/MM/YYYY.
- `amount`: the member's Net value as shown (not the absolute value) — positive for "Owes club" (money coming in from them), negative for "Owed by club" (money going out to them) — formatted to 2 decimal places, no `$`.
- `description`: `Transfer From {name}` if the amount is positive, `Transfer To {name}` if negative.

Output just the CSV lines, one per non-settled member, nothing else — ready to paste into the "Import (Paste)" dialog on `/accounting/transactions`.
