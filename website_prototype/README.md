# Trip Events prototype

Plain Python stdlib webserver (`http.server`) + MySQL backend. No framework.

## Setup

```bash
pip install -r requirements.txt
mysql -u root -p < schema.sql
export TRIP_DB_USER=root
export TRIP_DB_PASSWORD=yourpassword
python3 app.py
```

Then open http://localhost:8000

## What's here

- **Auth**: email + password registration/login, PBKDF2-SHA256 hashed
  passwords, DB-backed session tokens in an HttpOnly cookie.
- **Events**: title, picture, start/end date, location (linked out to Google
  Maps), host, signup mode (`fcfs` or `host_picks`), optional participant
  limit.
- **Signups**: first-come-first-served auto-approves; host_picks puts
  signups into `pending` until the host approves/rejects them from the
  event page.
- **Discussion**: a flat comment thread per event.
- **Contributions & accounting** (`/events/<id>/contributions`):
  - Contribution types: `expense` (enter a dollar amount) or
    `driven_distance` (enter km, dollar amount derived from
    `DEPRECIATION_RATE_PER_KM` in `config.py`).
  - Every contribution has an optional "consumed by" person. If set, the
    full cost is charged to that one person. If left blank, the cost is
    pooled and split evenly across all approved participants (this is how
    a driver's `driven_distance` entry becomes a per-person fee while the
    driver's own payment still offsets their share -- the same mechanic as
    the Petrol/Distance/Maintenance-Credit columns on the club's paper trip
    sheets).
  - The "who owes what" table recomputes live from the contributions table
    on every page load -- there's no separate step to "finalise" a trip.

## Known prototype limitations (deliberately out of scope for now)

- No file upload for event pictures -- `picture_url` is just a string.
- No password reset / email verification flow.
- One shared DB connection per server process (fine for a prototype, not
  for concurrent production load).
- No CSRF protection on forms.
- Google Maps is a plain link-out (`?q=<location>`), not an embedded map or
  geocoded pin.
