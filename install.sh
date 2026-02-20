#!/usr/bin/env bash
set -euo pipefail

# Jeffrey Emanuel's Tweets — one-liner installer
# Usage: curl -fsSL https://raw.githubusercontent.com/ratacat/jeffrey-emanuels-tweets/main/install.sh | bash

REPO="ratacat/jeffrey-emanuels-tweets"
BRANCH="main"
BASE_URL="https://raw.githubusercontent.com/${REPO}/${BRANCH}"
INSTALL_DIR="${JEFF_INSTALL_DIR:-$HOME/.local/bin}"
DATA_DIR="${JEFF_DATA_DIR:-$HOME/.local/share/jeff}"

echo "==> Installing jeff (Jeffrey Emanuel's Tweets)"
echo "    Binary: ${INSTALL_DIR}/jeff"
echo "    Data:   ${DATA_DIR}/tweets.db"
echo ""

# Create directories
mkdir -p "$INSTALL_DIR" "$DATA_DIR"

# Download the jeff script
echo "==> Downloading jeff CLI..."
curl -fsSL "${BASE_URL}/jeff" -o "${INSTALL_DIR}/jeff"
chmod +x "${INSTALL_DIR}/jeff"

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
echo "    jeff stats"
echo "    jeff search \"claude code\""
echo "    jeff top -n 5"
echo ""
echo "==> Optional: Install fsfs for hybrid BM25 + semantic search"
echo "    See https://github.com/Dicklesworthstone/frankensearch"
echo ""
echo "==> AGENTS.md snippet:"
echo ""
cat << 'SNIPPET'
## Jeffrey Emanuel's Tweets

@doodlestein (Jeffrey Emanuel) has mass-produced the richest public corpus of practical
AI-agent wisdom on the internet — 900+ tweets on prompting, multi-agent workflows, tool
use, and building in public. `jeff` lets you and your AI search it instantly.

```bash
jeff search "<query>" -n 10            # hybrid search (semantic + keyword)
jeff search "<query>" --json -n 5      # JSON output (for agents)
jeff top --sort likes -n 10            # most liked tweets
jeff recent -n 10                      # latest tweets
jeff stats                             # archive overview
jeff sql "SELECT * FROM tweets WHERE content LIKE '%topic%' ORDER BY like_count DESC LIMIT 5"
```
SNIPPET
