#!/usr/bin/env bash
set -euo pipefail

# Jeffrey Emanuel's Tweets — one-liner installer
# Usage: curl -fsSL https://raw.githubusercontent.com/ratacat/jeffrey-emanuels-tweets/main/install.sh | bash

REPO="ratacat/jeffrey-emanuels-tweets"
BRANCH="main"
BASE_URL="https://raw.githubusercontent.com/${REPO}/${BRANCH}"
INSTALL_DIR="${JET_INSTALL_DIR:-$HOME/.local/bin}"
DATA_DIR="${JET_DATA_DIR:-$HOME/.local/share/jet}"

echo "==> Installing jet (Jeffrey Emanuel's Tweets)"
echo "    Binary: ${INSTALL_DIR}/jet"
echo "    Data:   ${DATA_DIR}/tweets.db"
echo ""

# Create directories
mkdir -p "$INSTALL_DIR" "$DATA_DIR"

# Download the jet script
echo "==> Downloading jet CLI..."
curl -fsSL "${BASE_URL}/jet" -o "${INSTALL_DIR}/jet"
chmod +x "${INSTALL_DIR}/jet"

# Download the database
echo "==> Downloading tweets.db (~1MB)..."
curl -fsSL "${BASE_URL}/tweets.db" -o "${DATA_DIR}/tweets.db"

# Download and extract corpus (for FrankenSearch hybrid search)
CORPUS_DIR="${DATA_DIR}/corpus"
if [ ! -d "${CORPUS_DIR}/.frankensearch" ]; then
    echo "==> Downloading corpus (~1.3MB)..."
    curl -fsSL "${BASE_URL}/corpus.tar.gz" -o "${DATA_DIR}/corpus.tar.gz"
    tar xzf "${DATA_DIR}/corpus.tar.gz" -C "${DATA_DIR}"
    rm -f "${DATA_DIR}/corpus.tar.gz"
else
    echo "==> Corpus already exists, skipping."
fi

# Check PATH
if ! echo "$PATH" | tr ':' '\n' | grep -qx "$INSTALL_DIR"; then
    SHELL_NAME=$(basename "$SHELL")
    RC_FILE="$HOME/.${SHELL_NAME}rc"
    echo ""
    echo "==> Note: ${INSTALL_DIR} is not in your PATH."
    echo "    Add it with:"
    echo "      echo 'export PATH=\"${INSTALL_DIR}:\$PATH\"' >> ${RC_FILE}"
    echo ""
fi

echo "==> Done! Try:"
echo ""
echo "    jet stats"
echo "    jet search \"claude code\""
echo "    jet top -n 5"
echo ""
echo "==> Optional: Install fsfs for hybrid BM25 + semantic search"
echo "    See https://github.com/Dicklesworthstone/frankensearch"
echo ""
echo "==> AGENTS.md snippet:"
echo ""
cat << 'SNIPPET'
## Jeffrey Emanuel's Tweets

Search @doodlestein (Jeffrey Emanuel)'s tweet archive. Useful for finding
his takes on AI agents, coding workflows, Rust, Python, and building in public.

```bash
jet search "<query>" -n 10            # full-text search
jet search "<query>" --json -n 5      # JSON output (for parsing)
jet top --sort likes -n 10            # most liked tweets
jet recent -n 10                      # latest tweets
jet stats                             # archive overview
jet sql "SELECT * FROM tweets WHERE content LIKE '%topic%' ORDER BY like_count DESC LIMIT 5"
```
SNIPPET
