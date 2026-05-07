#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
WRAPPER="${REPO_DIR}/scripts/codex_daily_update.sh"
DRY_RUN=0

if [ "${1:-}" = "--dry-run" ]; then
  DRY_RUN=1
fi

MINUTE="${JEFF_CRON_MINUTE:-17}"
HOUR="${JEFF_CRON_HOUR:-7}"
TARGET_ITEMS="${JEFF_XPOOL_TARGET_ITEMS:-800}"
MAX_TARGET_ITEMS="${JEFF_XPOOL_MAX_TARGET_ITEMS:-5000}"
MAX_PAGES="${JEFF_XPOOL_MAX_PAGES:-80}"

BEGIN_MARKER="# BEGIN jeffrey-emanuels-tweets daily codex update"
END_MARKER="# END jeffrey-emanuels-tweets daily codex update"
CRON_LINE="${MINUTE} ${HOUR} * * * JEFF_XPOOL_TARGET_ITEMS=${TARGET_ITEMS} JEFF_XPOOL_MAX_TARGET_ITEMS=${MAX_TARGET_ITEMS} JEFF_XPOOL_MAX_PAGES=${MAX_PAGES} ${WRAPPER}"

if [ ! -x "${WRAPPER}" ]; then
  chmod +x "${WRAPPER}"
fi

tmp="$(mktemp)"
trap 'rm -f "${tmp}" "${tmp}.new"' EXIT

if crontab -l > "${tmp}" 2>/dev/null; then
  :
else
  : > "${tmp}"
fi

awk -v begin="${BEGIN_MARKER}" -v end="${END_MARKER}" '
  $0 == begin { skip = 1; next }
  $0 == end { skip = 0; next }
  skip != 1 { print }
' "${tmp}" > "${tmp}.new"

{
  cat "${tmp}.new"
  echo "${BEGIN_MARKER}"
  echo "${CRON_LINE}"
  echo "${END_MARKER}"
} > "${tmp}"

if [ "${DRY_RUN}" -eq 1 ]; then
  echo "Would install daily cron job:"
  echo "${CRON_LINE}"
  exit 0
fi

crontab "${tmp}"

echo "Installed daily cron job:"
echo "${CRON_LINE}"
