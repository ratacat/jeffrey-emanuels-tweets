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

if ! mkdir "${LOCK_DIR}" 2>/dev/null; then
  echo "daily update already running: ${LOCK_DIR}" >> "${LOG_FILE}"
  exit 0
fi
trap 'rmdir "${LOCK_DIR}"' EXIT

{
  echo "==> ${TODAY} jeffrey-emanuels-tweets daily update"
  cd "${REPO_DIR}"

  MANAGED_PATHS=(tweets.db corpus corpus.tar.gz README.md)
  if ! git diff --quiet -- "${MANAGED_PATHS[@]}" || ! git diff --cached --quiet -- "${MANAGED_PATHS[@]}"; then
    echo "archive-managed files are already dirty; skipping daily update"
    git status --short -- "${MANAGED_PATHS[@]}"
    exit 0
  fi

  git pull --ff-only

  CODEX_BIN="${CODEX_BIN:-codex}"
  CODEX_MODEL_ARG=()
  if [ -n "${CODEX_MODEL:-}" ]; then
    CODEX_MODEL_ARG=(-m "${CODEX_MODEL}")
  fi

  TARGET_ITEMS="${JEFF_XPOOL_TARGET_ITEMS:-800}"
  MAX_TARGET_ITEMS="${JEFF_XPOOL_MAX_TARGET_ITEMS:-5000}"
  MAX_PAGES="${JEFF_XPOOL_MAX_PAGES:-80}"

  PROMPT="Run the daily Jeffrey Emanuel tweet archive update.

Use xpool only for collection. Do not use Apify or web scraping.

Steps:
1. Run: scripts/update_from_xpool.py --catch-up --target-items ${TARGET_ITEMS} --max-target-items ${MAX_TARGET_ITEMS} --max-pages ${MAX_PAGES} --summary-json
2. If the script exits non-zero because the catch-up window did not reach an already archived tweet, stop and report the failure. Do not commit a partial update.
3. Validate with: sqlite3 tweets.db 'PRAGMA integrity_check;' and ./jeff stats and ./jeff recent -n 5.
4. If there are no git changes, report that and stop.
5. If archive files changed, commit only the relevant archive/update files and push origin main. Use commit message: Update Jeffrey Emanuel tweet archive ${TODAY}.

Keep changes scoped. Do not modify AGENTS.md, CLAUDE.md, docs/, or days/. Do not commit unrelated pre-existing local edits such as changes to jeff."

  "${CODEX_BIN}" -a never exec \
    -C "${REPO_DIR}" \
    -s workspace-write \
    -c model_reasoning_effort=\"medium\" \
    "${CODEX_MODEL_ARG[@]}" \
    "${PROMPT}" < /dev/null
} >> "${LOG_FILE}" 2>&1
