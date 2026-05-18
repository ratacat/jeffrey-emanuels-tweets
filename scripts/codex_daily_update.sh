#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
STATE_DIR="${JEFF_UPDATE_STATE_DIR:-$HOME/.local/state/jeffrey-emanuels-tweets}"
LOCK_DIR="${STATE_DIR}/daily.lock"
LOG_DIR="${STATE_DIR}/logs"
TODAY="$(date -u +%Y-%m-%d)"
LOG_FILE="${LOG_DIR}/${TODAY}.log"

export PATH="/Users/jaredsmith/.nvm/versions/node/v22.14.0/bin:/Users/jaredsmith/.bun/bin:/opt/homebrew/bin:/Users/jaredsmith/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

mkdir -p "${LOG_DIR}"

MANAGED_PATHS=(tweets.db corpus corpus.tar.gz README.md)

managed_has_changes() {
  if ! git diff --quiet -- "${MANAGED_PATHS[@]}"; then
    return 0
  fi
  if ! git diff --cached --quiet -- "${MANAGED_PATHS[@]}"; then
    return 0
  fi
  if [ -n "$(git ls-files --others --exclude-standard -- "${MANAGED_PATHS[@]}")" ]; then
    return 0
  fi
  return 1
}

ensure_no_unrelated_changes() {
  local line
  local path
  local found=0

  while IFS= read -r line; do
    path="${line:3}"
    case "${path}" in
      tweets.db|corpus|corpus/*|corpus.tar.gz|README.md)
        ;;
      *)
        echo "unrelated local change blocks archive publish: ${line}"
        found=1
        ;;
    esac
  done < <(git status --short)

  if [ "${found}" -ne 0 ]; then
    exit 1
  fi
}

validate_archive() {
  local integrity

  echo "validating archive"
  integrity="$(sqlite3 tweets.db 'PRAGMA integrity_check;')"
  echo "sqlite integrity: ${integrity}"
  if [ "${integrity}" != "ok" ]; then
    echo "sqlite integrity check failed"
    exit 1
  fi

  ./jeff stats
  ./jeff recent -n 5
}

publish_archive_update() {
  local reason="${1}"

  if ! managed_has_changes; then
    echo "no archive changes to publish after ${reason}"
    return 0
  fi

  ensure_no_unrelated_changes
  validate_archive

  git add -- "${MANAGED_PATHS[@]}"
  if git diff --cached --quiet -- "${MANAGED_PATHS[@]}"; then
    echo "no staged archive changes to commit after ${reason}"
    return 0
  fi

  echo "staged archive changes:"
  git diff --cached --stat -- "${MANAGED_PATHS[@]}"

  git commit -m "Update Jeffrey Emanuel tweet archive ${TODAY}" -- "${MANAGED_PATHS[@]}"
  git pull --rebase
  git push origin main
}

if ! mkdir "${LOCK_DIR}" 2>/dev/null; then
  echo "daily update already running: ${LOCK_DIR}" >> "${LOG_FILE}"
  exit 0
fi
trap 'rmdir "${LOCK_DIR}"' EXIT

{
  echo "==> ${TODAY} jeffrey-emanuels-tweets daily update"
  cd "${REPO_DIR}"

  if managed_has_changes; then
    echo "archive-managed files are already dirty; completing update before publish"
    git status --short -- "${MANAGED_PATHS[@]}"
    ensure_no_unrelated_changes
  else
    git pull --ff-only
  fi

  TARGET_ITEMS="${JEFF_XPOOL_TARGET_ITEMS:-800}"
  MAX_TARGET_ITEMS="${JEFF_XPOOL_MAX_TARGET_ITEMS:-5000}"
  MAX_PAGES="${JEFF_XPOOL_MAX_PAGES:-80}"

  scripts/update_from_xpool.py \
    --catch-up \
    --target-items "${TARGET_ITEMS}" \
    --max-target-items "${MAX_TARGET_ITEMS}" \
    --max-pages "${MAX_PAGES}" \
    --summary-json

  publish_archive_update "daily xpool update"
} >> "${LOG_FILE}" 2>&1
