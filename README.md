# Jeffrey Emanuel's Tweets

A searchable archive of [@doodlestein](https://x.com/doodlestein) (Jeffrey Emanuel)'s tweets. The database is a standard SQLite file, also compatible with [FrankenSQLite](https://github.com/Dicklesworthstone/frankensqlite).

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/ratacat/jeffrey-emanuels-tweets/main/install.sh | bash
```

## Usage

```bash
jet search "claude code agents"       # full-text search
jet search "python GIL" --json -n 5   # JSON output (for agents)
jet top --sort likes -n 10            # most liked tweets
jet recent -n 10                      # latest tweets
jet stats                             # archive overview
jet sql "SELECT * FROM tweets WHERE like_count > 500 ORDER BY like_count DESC"
```

## AGENTS.md snippet

Drop this in your `AGENTS.md` or `CLAUDE.md` to give coding agents access:

```markdown
## Jeffrey Emanuel's Tweets

Search @doodlestein's tweet archive for takes on AI agents, coding workflows, and building in public.

\`\`\`bash
jet search "<query>" --json -n 5      # search tweets (JSON for parsing)
jet top --sort likes --json -n 5      # most liked tweets
jet stats --json                      # archive overview
\`\`\`
```

## Stats

895 tweets | Sep 2025 — Feb 2026 | 76.7 avg likes

## License

MIT
