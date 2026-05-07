# jeff — Jeffrey Emanuel's Tweets

Jeffrey Emanuel ([@doodlestein](https://x.com/doodlestein)) is one of the most cutting-edge agentic programmers working today. He routinely orchestrates fleets of 30+ AI coding agents across a dozen projects simultaneously — Claude Code, Codex, Gemini CLI — all coordinating through tools he built himself. He's overhauling massive systems with a precision and velocity that shouldn't be possible for a single person.

His open-source "Franken" ecosystem is a good example: [FrankenSearch](https://github.com/Dicklesworthstone/frankensearch) (hybrid BM25 + semantic vector search, 11 Rust crates), [FrankenSQLite](https://github.com/Dicklesworthstone/frankensqlite) (an 11k-line spec for a next-gen SQLite layer), [FrankenTUI](https://github.com/Dicklesworthstone/frankentui) (a monstrously fast terminal UI framework replacing ratatui), plus tools like [beads](https://github.com/Dicklesworthstone/beads) for git-backed task management and [MCP Agent Mail](https://github.com/Dicklesworthstone/mcp_agent_mail) for inter-agent communication. All built in public, all open source.

His 900+ tweets are probably the richest public corpus of practical AI-agent wisdom on the internet — covering prompting techniques, multi-agent orchestration, tool use patterns, coding workflows, and hard-won lessons from actually shipping with these tools every day.

`jeff` is a dead-simple way to let your AI query that corpus. Use it directly for research, to synthesize his approaches into your own workflows, or tell your AI to "be Jeffrey Emanuel" and answer your questions drawing on everything he's written.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/ratacat/jeffrey-emanuels-tweets/main/install.sh | bash
```

## Usage

```bash
jeff search "best prompting techniques"   # hybrid search (semantic + keyword)
jeff search "multi-agent" --json -n 5     # JSON output (for agents)
jeff top --sort likes -n 10               # most liked tweets
jeff recent -n 10                         # latest tweets
jeff stats                                # archive overview
jeff sql "SELECT * FROM tweets WHERE like_count > 500 ORDER BY like_count DESC"
```

## For AI agents

Drop this in your `AGENTS.md` or `CLAUDE.md`:

```markdown
## Jeffrey Emanuel's Tweets

@doodlestein's tweet archive — the richest public corpus of practical AI-agent wisdom.
900+ tweets on prompting, multi-agent workflows, tool use, and building in public.
Use `jeff` to search it, synthesize approaches, or role-play as Jeffrey Emanuel.

\`\`\`bash
jeff search "<query>" --json -n 5      # search tweets (JSON for parsing)
jeff top --sort likes --json -n 5      # most liked tweets
jeff stats --json                      # archive overview
\`\`\`
```

## FrankenSearch (optional)

`jeff search` uses SQLite FTS5 by default. Install [FrankenSearch](https://github.com/Dicklesworthstone/frankensearch) (`fsfs`) for hybrid BM25 + semantic vector search — significantly better results for natural language queries.

When `fsfs` is available, `jeff` uses it automatically and enriches results with tweet metadata (dates, likes, views) from the database. If `fsfs` is not found or fails, it falls back silently to FTS5.

`fsfs` is discovered via: `FSFS_PATH` env var > `PATH` > sibling `frankensearch/target/release/fsfs`.

## Daily Updates

The repo includes an `xpool`-based updater and a Codex CLI cron wrapper:

```bash
scripts/update_from_xpool.py --summary-json
scripts/codex_daily_update.sh
scripts/cron/install.sh
```

The updater fetches `@doodlestein` through `xpool`, updates `tweets.db`, rebuilds `corpus/`, refreshes `corpus.tar.gz`, and rebuilds the FrankenSearch index when `fsfs` is available. The cron wrapper runs Codex CLI with medium reasoning once per day so Codex can run the updater, verify the archive, commit changes, and push them.

Cron uses `--catch-up`, so it expands the latest-tweets window until it reaches an already archived tweet. That catches up the backlog since the last archived tweet, not just tweets from the current day.

## Stats

895 tweets | 472 original | Sep 2025 — Feb 2026 | 76.7 avg likes | 12,553 avg views

## License

MIT
