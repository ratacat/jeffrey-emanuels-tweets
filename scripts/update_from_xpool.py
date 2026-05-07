#!/usr/bin/env python3
"""Update the Jeffrey Emanuel tweet archive from xpool UserTweets results."""

from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import gzip
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_USER_ID = "29239591"
DEFAULT_TARGET_ITEMS = 800
DEFAULT_MAX_PAGES = 80


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch @doodlestein tweets through xpool and update tweets.db/corpus."
    )
    parser.add_argument("--user-id", default=DEFAULT_USER_ID)
    parser.add_argument("--target-items", type=int, default=DEFAULT_TARGET_ITEMS)
    parser.add_argument("--max-target-items", type=int, default=5000)
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--spare-accounts", type=int, default=None)
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--idempotency-key", default=None)
    parser.add_argument("--xpool-bin", default=os.environ.get("XPOOL_BIN", "xpool"))
    parser.add_argument("--fsfs-bin", default=os.environ.get("FSFS_PATH"))
    parser.add_argument("--skip-fsfs-index", action="store_true")
    parser.add_argument("--skip-tar", action="store_true")
    parser.add_argument("--skip-readme", action="store_true")
    parser.add_argument(
        "--catch-up",
        action="store_true",
        help="Double the xpool fetch window until it reaches an already archived tweet.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--summary-json", action="store_true")
    return parser.parse_args()


def run_json(command: list[str]) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False) as stdout_file:
        stdout_path = Path(stdout_file.name)
        proc = subprocess.run(
            command,
            stdout=stdout_file,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )

    try:
        stdout = stdout_path.read_text(encoding="utf-8", errors="replace")
    finally:
        stdout_path.unlink(missing_ok=True)

    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(command)}\n{proc.stderr.strip()}"
        )

    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line, strict=False)
        except json.JSONDecodeError:
            continue
        if payload.get("ok") is not True:
            raise RuntimeError(f"xpool returned an error: {json.dumps(payload, indent=2)}")
        return payload

    raise RuntimeError(f"No JSON envelope found in command output: {' '.join(command)}")


def submit_job(args: argparse.Namespace, target_items: int) -> str:
    key = args.idempotency_key
    if key is None:
        today = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d")
        key = f"jeffrey-emanuels-tweets-daily-{today}-{target_items}"

    command = [
        args.xpool_bin,
        "--json",
        "--log-level",
        "error",
        "query",
        "--endpoint",
        "UserTweets",
        "--user-id",
        args.user_id,
        "--page-size",
        str(args.page_size),
        "--max-pages",
        str(args.max_pages),
        "--target-items",
        str(target_items),
        "--idempotency-key",
        key,
    ]
    if args.spare_accounts is not None:
        command.extend(["--spare-accounts", str(args.spare_accounts)])

    envelope = run_json(command)
    return str(envelope["data"]["job"]["id"])


def collect_rows(args: argparse.Namespace, target_items: int) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    job_id = submit_job(args, target_items)
    status = wait_for_job(args, job_id)
    rows = normalize_items(fetch_result_items(args, job_id))
    if not rows:
        raise RuntimeError(f"xpool job {job_id} completed but emitted no normalizable tweets")
    return job_id, status, rows


def wait_for_job(args: argparse.Namespace, job_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + args.timeout_seconds
    while True:
        envelope = run_json(
            [
                args.xpool_bin,
                "--json",
                "--log-level",
                "error",
                "query",
                "status",
                "--job-id",
                job_id,
            ]
        )
        job = envelope["data"]["job"]
        state = job.get("state")
        if state == "completed":
            return envelope["data"]
        if state in {"failed", "cancelled", "canceled"}:
            raise RuntimeError(f"xpool job {job_id} ended as {state}: {envelope['data'].get('failure')}")
        if time.monotonic() >= deadline:
            raise TimeoutError(f"xpool job {job_id} did not finish within {args.timeout_seconds}s")
        time.sleep(args.poll_seconds)


def fetch_result_items(args: argparse.Namespace, job_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    after_sequence: int | None = None

    while True:
        command = [
            args.xpool_bin,
            "--json",
            "--log-level",
            "error",
            "query",
            "result",
            "--job-id",
            job_id,
            "--chunk-limit",
            "1",
        ]
        if after_sequence is not None:
            command.extend(["--after-sequence", str(after_sequence)])

        envelope = run_json(command)
        result = envelope["data"]["result"]
        chunks = result.get("chunks", [])
        if not chunks:
            break

        for chunk in chunks:
            items.extend(chunk.get("items", []))
            after_sequence = max(after_sequence or -1, int(chunk.get("sequence", 0)))

        next_sequence = result.get("summary", {}).get("nextSequence")
        if next_sequence is None or after_sequence >= int(next_sequence) - 1:
            break

    return items


def parse_x_time(value: str | None) -> str:
    if not value:
        return ""
    parsed = email.utils.parsedate_to_datetime(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return parsed.astimezone(dt.UTC).isoformat()


def deep_get(data: dict[str, Any], path: list[str]) -> Any:
    cur: Any = data
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def text_for_payload(payload: dict[str, Any], legacy: dict[str, Any]) -> str:
    note_text = deep_get(payload, ["note_tweet", "note_tweet_results", "result", "text"])
    if isinstance(note_text, str) and note_text.strip():
        return note_text.strip()
    return str(legacy.get("full_text") or legacy.get("text") or "").strip()


def normalize_item(item: dict[str, Any]) -> dict[str, Any] | None:
    payload = item.get("payload")
    if not isinstance(payload, dict):
        return None

    legacy = payload.get("legacy")
    if not isinstance(legacy, dict):
        return None

    tweet_id = str(payload.get("rest_id") or legacy.get("id_str") or item.get("id") or "")
    if not tweet_id:
        return None

    text = text_for_payload(payload, legacy)
    is_retweet = bool(legacy.get("retweeted_status_result")) or text.startswith("RT @")
    is_reply = bool(legacy.get("in_reply_to_status_id_str"))
    reply_to_tweet_id = legacy.get("in_reply_to_status_id_str")
    view_count = deep_get(payload, ["views", "count"])

    return {
        "tweet_id": tweet_id,
        "content": text,
        "created_at": parse_x_time(legacy.get("created_at")),
        "like_count": int(legacy.get("favorite_count") or 0),
        "retweet_count": int(legacy.get("retweet_count") or 0),
        "reply_count": int(legacy.get("reply_count") or 0),
        "view_count": int(view_count or 0),
        "is_reply": int(is_reply),
        "is_retweet": int(is_retweet),
        "is_quote": int(bool(legacy.get("is_quote_status"))),
        "reply_to_tweet_id": str(reply_to_tweet_id) if reply_to_tweet_id else None,
    }


def normalize_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for item in items:
        row = normalize_item(item)
        if row is not None:
            by_id[row["tweet_id"]] = row
    return sorted(by_id.values(), key=lambda row: row["created_at"], reverse=True)


def connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(REPO_ROOT / "tweets.db")
    conn.row_factory = sqlite3.Row
    return conn


def existing_latest(conn: sqlite3.Connection) -> str | None:
    return conn.execute("SELECT MAX(created_at) FROM tweets").fetchone()[0]


def existing_tweet_ids(conn: sqlite3.Connection) -> set[str]:
    return {str(row[0]) for row in conn.execute("SELECT tweet_id FROM tweets")}


def rows_to_apply(
    rows: list[dict[str, Any]], current_latest: str | None, current_ids: set[str]
) -> tuple[list[dict[str, Any]], int]:
    apply: list[dict[str, Any]] = []
    skipped_older_unarchived = 0
    for row in rows:
        if row["tweet_id"] in current_ids or current_latest is None or row["created_at"] >= current_latest:
            apply.append(row)
        else:
            skipped_older_unarchived += 1
    return apply, skipped_older_unarchived


def upsert_rows(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> dict[str, int]:
    existing = {
        row["tweet_id"]: dict(row)
        for row in conn.execute(
            "SELECT tweet_id, content, created_at, like_count, retweet_count, reply_count, "
            "view_count, is_reply, is_retweet, is_quote, reply_to_tweet_id FROM tweets"
        )
    }

    inserted = 0
    updated = 0
    unchanged = 0

    for row in rows:
        old = existing.get(row["tweet_id"])
        comparable = {key: row[key] for key in row.keys()}
        if old is None:
            inserted += 1
        elif any(old.get(key) != comparable.get(key) for key in comparable):
            updated += 1
        else:
            unchanged += 1

        conn.execute(
            """
            INSERT INTO tweets (
                tweet_id, content, created_at, like_count, retweet_count, reply_count,
                view_count, is_reply, is_retweet, is_quote, reply_to_tweet_id
            )
            VALUES (
                :tweet_id, :content, :created_at, :like_count, :retweet_count, :reply_count,
                :view_count, :is_reply, :is_retweet, :is_quote, :reply_to_tweet_id
            )
            ON CONFLICT(tweet_id) DO UPDATE SET
                content = excluded.content,
                created_at = excluded.created_at,
                like_count = excluded.like_count,
                retweet_count = excluded.retweet_count,
                reply_count = excluded.reply_count,
                view_count = excluded.view_count,
                is_reply = excluded.is_reply,
                is_retweet = excluded.is_retweet,
                is_quote = excluded.is_quote,
                reply_to_tweet_id = excluded.reply_to_tweet_id
            """,
            row,
        )

    if inserted or updated:
        conn.execute("INSERT INTO tweets_fts(tweets_fts) VALUES ('rebuild')")
    conn.commit()
    return {"inserted": inserted, "updated": updated, "unchanged": unchanged}


def write_file_if_changed(path: Path, content: str) -> bool:
    encoded = content.encode("utf-8")
    if path.exists() and path.read_bytes() == encoded:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)
    return True


def render_corpus_file(row: sqlite3.Row) -> str:
    date = (row["created_at"] or "")[:10]
    likes = int(row["like_count"] or 0)
    content = row["content"] or ""
    return f"{date} | {likes} likes\n\n{content}\n"


def rebuild_corpus(conn: sqlite3.Connection) -> dict[str, int]:
    corpus_dir = REPO_ROOT / "corpus"
    corpus_dir.mkdir(exist_ok=True)

    rows = conn.execute(
        "SELECT tweet_id, created_at, content, like_count FROM tweets "
        "WHERE is_retweet = 0 ORDER BY created_at ASC"
    ).fetchall()
    expected = {f"{row['tweet_id']}.txt" for row in rows}

    written = 0
    for row in rows:
        changed = write_file_if_changed(corpus_dir / f"{row['tweet_id']}.txt", render_corpus_file(row))
        if changed:
            written += 1

    removed = 0
    for path in corpus_dir.glob("*.txt"):
        if path.name not in expected:
            path.unlink()
            removed += 1

    return {"files": len(rows), "written": written, "removed": removed}


def find_fsfs(explicit: str | None) -> str | None:
    candidates = [
        explicit,
        shutil.which("fsfs"),
        str(REPO_ROOT / "frankensearch" / "target" / "release" / "fsfs"),
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def rebuild_fsfs_index(args: argparse.Namespace, corpus_changed: bool) -> bool:
    if args.skip_fsfs_index or not corpus_changed:
        return False

    fsfs = find_fsfs(args.fsfs_bin)
    if fsfs is None:
        raise RuntimeError("corpus changed but fsfs was not found; install fsfs or pass --skip-fsfs-index")

    subprocess.run([fsfs, "index", "corpus"], cwd=REPO_ROOT, check=True)
    return True


def clean_tarinfo(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo:
    tarinfo.uid = 0
    tarinfo.gid = 0
    tarinfo.uname = ""
    tarinfo.gname = ""
    tarinfo.mtime = 0
    return tarinfo


def add_path_to_tar(tar: tarfile.TarFile, path: Path, arcname: str) -> None:
    tar.add(path, arcname=arcname, recursive=False, filter=clean_tarinfo)


def rebuild_corpus_tar() -> bool:
    corpus_dir = REPO_ROOT / "corpus"
    target = REPO_ROOT / "corpus.tar.gz"

    with tempfile.NamedTemporaryFile(dir=REPO_ROOT, delete=False) as raw:
        tmp_path = Path(raw.name)

    try:
        with tmp_path.open("wb") as raw_file:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw_file, mtime=0) as gz:
                with tarfile.open(mode="w", fileobj=gz) as tar:
                    add_path_to_tar(tar, corpus_dir, "corpus")
                    for path in sorted(corpus_dir.rglob("*")):
                        rel = path.relative_to(REPO_ROOT).as_posix()
                        add_path_to_tar(tar, path, rel)

        changed = not target.exists() or target.read_bytes() != tmp_path.read_bytes()
        if changed:
            tmp_path.replace(target)
        else:
            tmp_path.unlink()
        return changed
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def archive_stats(conn: sqlite3.Connection) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN is_retweet = 0 AND is_reply = 0 THEN 1 ELSE 0 END) AS original,
            MIN(created_at) AS earliest,
            MAX(created_at) AS latest,
            ROUND(AVG(CASE WHEN is_retweet = 0 THEN like_count END), 1) AS avg_likes,
            ROUND(AVG(CASE WHEN is_retweet = 0 THEN view_count END), 0) AS avg_views
        FROM tweets
        """
    ).fetchone()
    return dict(row)


def update_readme(conn: sqlite3.Connection) -> bool:
    path = REPO_ROOT / "README.md"
    text = path.read_text(encoding="utf-8")
    stats = archive_stats(conn)
    replacement = (
        f"## Stats\n\n{stats['total']:,} tweets | {stats['original']:,} original | "
        f"{stats['earliest'][:7]} — {stats['latest'][:7]} | "
        f"{stats['avg_likes']} avg likes | {int(stats['avg_views'] or 0):,} avg views"
    )
    new_text = re.sub(r"## Stats\n\n.*?(?=\n\n## License)", replacement, text, flags=re.S)
    if new_text == text:
        return False
    path.write_text(new_text, encoding="utf-8")
    return True


def main() -> int:
    args = parse_args()
    conn = connect_db()
    before_latest = existing_latest(conn)
    before_ids = existing_tweet_ids(conn)

    target_items = args.target_items
    attempts: list[dict[str, Any]] = []

    while True:
        job_id, status, rows = collect_rows(args, target_items)
        saw_existing_boundary = any(row["tweet_id"] in before_ids for row in rows)
        attempts.append(
            {
                "job_id": job_id,
                "target_items": target_items,
                "normalized": len(rows),
                "newest_seen": rows[0]["created_at"],
                "oldest_seen": rows[-1]["created_at"],
                "saw_existing_boundary": saw_existing_boundary,
                "xpool_stop_reason": status["job"].get("stopReason"),
            }
        )

        if not args.catch_up or before_latest is None or saw_existing_boundary:
            break
        if target_items >= args.max_target_items:
            break
        target_items = min(target_items * 2, args.max_target_items)

    applicable_rows, skipped_older_unarchived = rows_to_apply(rows, before_latest, before_ids)
    newest_seen = rows[0]["created_at"]
    oldest_seen = rows[-1]["created_at"]
    saw_existing_boundary = any(row["tweet_id"] in before_ids for row in rows)
    boundary_required = args.catch_up and before_latest is not None

    if boundary_required and not saw_existing_boundary:
        summary = {
            "attempts": attempts,
            "current_latest": before_latest,
            "normalized": len(rows),
            "would_apply": len(applicable_rows),
            "skipped_older_unarchived": skipped_older_unarchived,
            "newest_seen": newest_seen,
            "oldest_seen": oldest_seen,
            "saw_existing_boundary": False,
            "max_target_items": args.max_target_items,
            "error": "catch-up window did not reach an already archived tweet",
        }
        if args.summary_json:
            print(json.dumps(summary, indent=2, sort_keys=True))
        else:
            print(
                "error: catch-up window did not reach an already archived tweet; "
                "increase --max-target-items",
                file=sys.stderr,
            )
        return 2

    if args.dry_run:
        summary = {
            "job_id": job_id,
            "attempts": attempts,
            "xpool_stop_reason": status["job"].get("stopReason"),
            "normalized": len(rows),
            "would_apply": len(applicable_rows),
            "skipped_older_unarchived": skipped_older_unarchived,
            "newest_seen": newest_seen,
            "oldest_seen": oldest_seen,
            "current_latest": before_latest,
            "saw_existing_boundary": saw_existing_boundary,
        }
    else:
        db_changes = upsert_rows(conn, applicable_rows)
        corpus_changes = rebuild_corpus(conn)
        fsfs_rebuilt = rebuild_fsfs_index(args, corpus_changes["written"] > 0 or corpus_changes["removed"] > 0)
        tar_changed = False if args.skip_tar else rebuild_corpus_tar()
        readme_changed = False if args.skip_readme else update_readme(conn)
        summary = {
            "job_id": job_id,
            "attempts": attempts,
            "xpool_stop_reason": status["job"].get("stopReason"),
            "normalized": len(rows),
            "applied": len(applicable_rows),
            "skipped_older_unarchived": skipped_older_unarchived,
            "newest_seen": newest_seen,
            "oldest_seen": oldest_seen,
            "previous_latest": before_latest,
            "saw_existing_boundary": saw_existing_boundary,
            "db": db_changes,
            "corpus": corpus_changes,
            "fsfs_rebuilt": fsfs_rebuilt,
            "corpus_tar_changed": tar_changed,
            "readme_changed": readme_changed,
            "archive": archive_stats(conn),
        }

    if args.summary_json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"xpool job: {summary['job_id']}")
        print(f"normalized tweets: {summary['normalized']}")
        if args.dry_run:
            print(f"would apply: {summary['would_apply']}")
        else:
            print(f"applied tweets: {summary['applied']}")
        print(f"skipped older unarchived tweets: {summary['skipped_older_unarchived']}")
        print(f"seen range: {summary['oldest_seen']} to {summary['newest_seen']}")
        if not summary["saw_existing_boundary"]:
            print(
                "warning: fetched window did not reach the previous archive latest; "
                "increase --target-items for a full catch-up",
                file=sys.stderr,
            )
        if not args.dry_run:
            print(f"db changes: {summary['db']}")
            print(f"corpus changes: {summary['corpus']}")
            print(f"archive stats: {summary['archive']}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
