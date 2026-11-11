#!/usr/bin/env bash
# Authenticated curl against the local dev server, for manual/automated
# testing. Logs in once per email (cookie jar cached in /tmp) and reuses
# the session on subsequent calls.
#
# Usage:
#   dev_scripts/curl_as.sh <email> <curl-args...>
#
# Examples:
#   dev_scripts/curl_as.sh kow.andrew@gmail.com http://localhost:8020/accounting
#   dev_scripts/curl_as.sh kow.andrew@gmail.com -X POST http://localhost:8020/accounting/transactions/bulk-update \
#       --data-urlencode "tag_16=GEAR"
#
# Password is always "password" (matches every seeded dev account).
set -euo pipefail

EMAIL="${1:?usage: curl_as.sh <email> <curl-args...>}"
shift

SAFE_NAME="$(printf '%s' "$EMAIL" | tr -c 'a-zA-Z0-9' '_')"
COOKIE_JAR="/tmp/claude_dev_ck_${SAFE_NAME}.txt"
BASE_URL="${DEV_BASE_URL:-http://localhost:8020}"

if [ ! -s "$COOKIE_JAR" ]; then
  curl -s -c "$COOKIE_JAR" -X POST "${BASE_URL}/login" \
    -d "email=${EMAIL}&password=password" -o /dev/null
fi

curl -s -b "$COOKIE_JAR" -c "$COOKIE_JAR" "$@"
