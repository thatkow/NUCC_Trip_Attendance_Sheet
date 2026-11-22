#!/usr/bin/env bash
# Wipes the local dev DB, reloads schema.sql, seeds a single admin account
# (kow.andrew@gmail.com / password), and reloads the real checklist items
# (skills/items catalog) and content pages from seed_data.sql -- a dump of
# those two tables taken from prod (nucc.anumc.org.au), so a reset doesn't
# lose the actual skills/pages content. Stops+restarts the local dev server
# if it was running.
#
# To refresh seed_data.sql from prod after editing content there:
#   ssh root@172.105.167.40 "mysqldump --no-create-info --complete-insert \
#     -u trip_events -p<password> trip_events checklist_items content_pages" \
#     > seed_data.sql
# (password is in `systemctl cat trip-events`'s TRIP_DB_PASSWORD line).
set -euo pipefail
cd "$(dirname "$0")"

DB_HOST="${TRIP_DB_HOST:-127.0.0.1}"
DB_USER="${TRIP_DB_USER:-root}"
DB_PASSWORD="${TRIP_DB_PASSWORD:-password}"
DB_NAME="${TRIP_DB_NAME:-trip_events}"
PORT="${TRIP_PORT:-8020}"

MYSQL=(mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASSWORD")

was_running=0
if pgrep -f "python3 app.py" > /dev/null; then
    was_running=1
    pkill -f "python3 app.py"
    sleep 1
fi

"${MYSQL[@]}" -e "DROP DATABASE IF EXISTS ${DB_NAME};"
"${MYSQL[@]}" < schema.sql
"${MYSQL[@]}" "$DB_NAME" < seed_data.sql

TRIP_DB_HOST="$DB_HOST" TRIP_DB_USER="$DB_USER" TRIP_DB_PASSWORD="$DB_PASSWORD" TRIP_DB_NAME="$DB_NAME" \
    ./venv/bin/python3 - <<'PYEOF'
import db
import auth

conn = db.get_connection()
user_id = auth.create_user(conn, "kow.andrew@gmail.com", "Andrew Kowalczyk", "password")
with conn.cursor() as cur:
    cur.execute("UPDATE users SET is_admin = 1 WHERE id = %s", (user_id,))
print(f"Seeded admin user id={user_id} (kow.andrew@gmail.com / password)")
PYEOF

if [ "$was_running" = "1" ]; then
    TRIP_DB_HOST="$DB_HOST" TRIP_DB_USER="$DB_USER" TRIP_DB_PASSWORD="$DB_PASSWORD" TRIP_DB_NAME="$DB_NAME" TRIP_PORT="$PORT" \
        nohup ./venv/bin/python3 app.py >> app.log 2>&1 < /dev/null &
    disown
    echo "Dev server restarted on http://localhost:${PORT}"
fi
