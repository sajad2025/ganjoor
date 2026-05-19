#!/usr/bin/env python3
"""
fetch_ganjoor.py

Walks api.ganjoor.net and produces one NDJSON file per poet at
  <out>/<poet_slug>.ndjson

with a per-poet progress sidecar at
  <out>/<poet_slug>.progress.json

Each NDJSON line is one fully-detailed poem object, fetched with verseDetails=true
and the metadata sub-resources we care about for preservation.

Designed for:
- GitHub-hosted Actions runners (6h max per job, 7 GB free disk).
- **Crash-safe persistence:** each poem is appended to the poet's NDJSON
  and flushed before the next request is issued. A runner kill loses at
  most the in-flight poem, not the whole poet.
- **Resumability at two layers:**
    (1) Whole poets: a completed `.progress.json` marker means skip.
    (2) Mid-poet: existing `<slug>.ndjson` is scanned at start-of-poet
        to derive the set of already-written poem ids; the walk skips them
        and appends only new poems. A truncated trailing line from a
        prior SIGKILL is detected and trimmed.
- **Sharding for parallel matrix runs:** `--bucket N --num-buckets M`
  selects only poets whose stable-sorted index satisfies `index % M == N`.
- **Targeted re-runs:** `--poet-ids A,B,C` overrides selection to fetch
  exactly the given poet ids (useful for filling gaps).
- **Politeness:** configurable rate limit, exponential backoff, custom UA.

Walk strategy (unchanged from v0.1):
  1. GET /api/ganjoor/poets  -> list of poets, each with root cat id.
  2. For each poet, recursively walk categories starting from root cat:
     GET /api/ganjoor/cat/<cat_id>?poems=true
  3. For every poem id encountered, fetch the full poem:
     GET /api/ganjoor/poem/<poem_id>
        ?verseDetails=true&catInfo=true&rhymes=true
        &recitations=true&images=true&songs=true&navigation=true
     (Comments deferred to a separate, slower job.)
  4. Append the JSON to <poet_slug>.ndjson and flush.

Output schema per line is a faithful pass-through of api.ganjoor.net's poem
object plus a small "_meta" envelope with fetch timestamp and source URL.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

BASE = "https://api.ganjoor.net"
POEM_FLAGS = (
    "verseDetails=true&catInfo=true&rhymes=true"
    "&recitations=true&images=true&songs=true&navigation=true"
)


@dataclass
class Config:
    out: Path
    rate: float            # max requests per second
    user_agent: str
    poet_limit: int        # 0 = all
    bucket: int            # 0-indexed bucket selector (ignored if num_buckets == 0)
    num_buckets: int       # 0 = no bucketing
    poet_ids: set[int] = field(default_factory=set)   # explicit override
    request_timeout: int = 30


class Throttle:
    """Simple leaky bucket. Sleep so we never exceed `rate` requests/sec."""

    def __init__(self, rate: float):
        self.min_interval = 1.0 / rate if rate > 0 else 0.0
        self._last = 0.0

    def wait(self) -> None:
        if self.min_interval == 0:
            return
        now = time.monotonic()
        gap = now - self._last
        if gap < self.min_interval:
            time.sleep(self.min_interval - gap)
        self._last = time.monotonic()


class GanjoorClient:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": cfg.user_agent,
                "Accept": "application/json",
            }
        )
        self.throttle = Throttle(cfg.rate)

    @retry(
        retry=retry_if_exception_type(
            (requests.ConnectionError, requests.Timeout, requests.HTTPError)
        ),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def _get(self, path: str) -> Any:
        self.throttle.wait()
        url = f"{BASE}{path}"
        resp = self.session.get(url, timeout=self.cfg.request_timeout)
        if resp.status_code == 404:
            return None
        # Treat 429/5xx as retryable
        if resp.status_code >= 500 or resp.status_code == 429:
            resp.raise_for_status()
        resp.raise_for_status()
        return resp.json()

    # --- typed endpoints ---------------------------------------------------

    def poets(self) -> list[dict]:
        data = self._get("/api/ganjoor/poets")
        # Endpoint historically returned a list, but defensively unwrap.
        if isinstance(data, dict) and "poets" in data:
            data = data["poets"]
        return data or []

    def cat(self, cat_id: int, with_poems: bool = True) -> dict | None:
        suffix = "?poems=true" if with_poems else ""
        return self._get(f"/api/ganjoor/cat/{cat_id}{suffix}")

    def poem(self, poem_id: int) -> dict | None:
        return self._get(f"/api/ganjoor/poem/{poem_id}?{POEM_FLAGS}")


# --- walking -----------------------------------------------------------------


def walk_cat_for_poem_ids(client: GanjoorClient, cat_id: int) -> Iterable[int]:
    """
    Recursively walk a category tree, yielding every poem id we encounter.

    The api.ganjoor.net cat response shape (observed):
      {
        "cat": { "id": ..., "title": ..., "urlSlug": ..., ... },
        "poems":    [ { "id": ..., "title": ..., ... }, ... ],
        "children": [ { "id": ..., ... }, ... ]
      }
    Some categories nest poems only on their leaves; some have both.
    """
    queue: list[int] = [cat_id]
    seen_cats: set[int] = set()

    while queue:
        cid = queue.pop()
        if cid in seen_cats:
            continue
        seen_cats.add(cid)

        cat = client.cat(cid, with_poems=True)
        if not cat:
            continue

        # poems may be top-level or nested inside "cat" depending on schema rev
        poems = cat.get("poems") or cat.get("cat", {}).get("poems") or []
        for p in poems:
            pid = p.get("id")
            if isinstance(pid, int):
                yield pid

        children = cat.get("children") or cat.get("cat", {}).get("children") or []
        for ch in children:
            cid_child = ch.get("id")
            if isinstance(cid_child, int):
                queue.append(cid_child)


# --- persistence -------------------------------------------------------------


def load_progress(progress_path: Path) -> dict | None:
    if not progress_path.exists():
        return None
    try:
        return json.loads(progress_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_progress(progress_path: Path, payload: dict) -> None:
    """Atomic write: temp + rename."""
    tmp = progress_path.with_suffix(progress_path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(progress_path)


def read_done_poem_ids(ndjson_path: Path) -> tuple[set[int], bool]:
    """
    Return (set of poem ids already written, was_trailing_line_truncated).
    Tolerates a truncated final line from a SIGKILL mid-write.
    """
    ids: set[int] = set()
    truncated = False
    if not ndjson_path.exists():
        return ids, truncated
    with ndjson_path.open("r", encoding="utf-8") as f:
        lines = f.readlines()
    for i, raw in enumerate(lines):
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        try:
            envelope = json.loads(line)
        except json.JSONDecodeError:
            if i == len(lines) - 1:
                # Likely a kill mid-write. We'll trim it before appending.
                truncated = True
                continue
            # Mid-file corruption — preserve, surface via warning.
            print(
                f"  ! warning: malformed mid-file line {i} in {ndjson_path}, kept",
                file=sys.stderr,
                flush=True,
            )
            continue
        poem = envelope.get("poem") or {}
        pid = poem.get("id")
        if isinstance(pid, int):
            ids.add(pid)
    return ids, truncated


def trim_truncated_trailing_line(ndjson_path: Path) -> None:
    """Drop the last line if it doesn't parse as JSON (kill-mid-write recovery)."""
    if not ndjson_path.exists():
        return
    raw = ndjson_path.read_bytes()
    if not raw:
        return
    has_trailing_newline = raw.endswith(b"\n")
    lines = raw.split(b"\n")
    if has_trailing_newline and lines and lines[-1] == b"":
        lines.pop()
    if not lines:
        return
    last = lines[-1]
    if not last.strip():
        return
    try:
        json.loads(last.decode("utf-8"))
        return  # last line parses; nothing to trim
    except (json.JSONDecodeError, UnicodeDecodeError):
        lines.pop()
        new_bytes = b"\n".join(lines)
        if new_bytes:
            new_bytes += b"\n"
        ndjson_path.write_bytes(new_bytes)
        print(
            f"  recovered: trimmed truncated trailing line from {ndjson_path.name}",
            flush=True,
        )


# --- fetch -------------------------------------------------------------------


def fetch_poet(
    client: GanjoorClient,
    poet: dict,
    out_path: Path,
    progress_path: Path,
) -> tuple[int, int]:
    """
    Fetch all poems for one poet using crash-safe append-mode writes.
    Returns (newly_written, total_on_disk).
    """
    root_cat = (
        poet.get("rootCatId")
        or (poet.get("rootCat") or {}).get("id")
        or (poet.get("cat") or {}).get("id")
    )
    if not root_cat:
        print(f"  ! no root cat for poet {poet.get('id')}: skipping", flush=True)
        return 0, 0

    # Recover from any prior kill-mid-write before we read the file.
    trim_truncated_trailing_line(out_path)

    already_done, _ = read_done_poem_ids(out_path)
    if already_done:
        print(f"  resume: {len(already_done)} poems already on disk", flush=True)

    save_progress(progress_path, {
        "poet_id": poet.get("id"),
        "poet_nickname": poet.get("nickname"),
        "root_cat_id": int(root_cat),
        "completed": False,
        "completed_count": len(already_done),
        "started_at": datetime.now(timezone.utc).isoformat(),
    })

    newly_written = 0
    seen_poems: set[int] = set(already_done)

    with out_path.open("a", encoding="utf-8") as f:
        for poem_id in walk_cat_for_poem_ids(client, int(root_cat)):
            if poem_id in seen_poems:
                continue
            seen_poems.add(poem_id)

            poem = client.poem(poem_id)
            if not poem:
                continue

            envelope = {
                "_meta": {
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "source": f"{BASE}/api/ganjoor/poem/{poem_id}",
                    "source_flags": POEM_FLAGS,
                },
                "poem": poem,
            }
            f.write(json.dumps(envelope, ensure_ascii=False) + "\n")
            f.flush()  # push to OS pagecache so SIGKILL doesn't lose this line
            newly_written += 1

            if newly_written % 25 == 0:
                print(
                    f"  - {newly_written} new poems written "
                    f"(total on disk: {len(seen_poems)})",
                    flush=True,
                )

    save_progress(progress_path, {
        "poet_id": poet.get("id"),
        "poet_nickname": poet.get("nickname"),
        "root_cat_id": int(root_cat),
        "completed": True,
        "completed_count": len(seen_poems),
        "newly_written_this_run": newly_written,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    })

    return newly_written, len(seen_poems)


# --- main --------------------------------------------------------------------


def parse_poet_ids(spec: str | None) -> set[int]:
    if not spec:
        return set()
    out: set[int] = set()
    for tok in spec.split(","):
        tok = tok.strip()
        if not tok:
            continue
        out.add(int(tok))
    return out


def slugify(poet: dict) -> str:
    raw = poet.get("nickname") or poet.get("name") or f"poet-{poet.get('id')}"
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in raw.lower())
    return safe or f"poet-{poet.get('id')}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True, help="output directory")
    ap.add_argument("--rate", type=float, default=3.0, help="max req/sec")
    ap.add_argument(
        "--user-agent",
        default="ganjoor-mirror/0.1 (+https://github.com/sajad2025/ganjoor)",
    )
    ap.add_argument(
        "--poet-limit",
        type=int,
        default=0,
        help="stop after N poets (0 = all). Useful for first-run smoke tests.",
    )
    ap.add_argument(
        "--bucket",
        type=int,
        default=0,
        help="0-indexed bucket id (used with --num-buckets > 0 for matrix runs)",
    )
    ap.add_argument(
        "--num-buckets",
        type=int,
        default=0,
        help="how many buckets to split poets into. 0 = no bucketing.",
    )
    ap.add_argument(
        "--poet-ids",
        type=str,
        default=None,
        help="comma-separated explicit poet ids to fetch (overrides selection).",
    )
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    cfg = Config(
        out=args.out,
        rate=args.rate,
        user_agent=args.user_agent,
        poet_limit=args.poet_limit,
        bucket=args.bucket,
        num_buckets=args.num_buckets,
        poet_ids=parse_poet_ids(args.poet_ids),
    )

    if cfg.num_buckets and not (0 <= cfg.bucket < cfg.num_buckets):
        print(
            f"FATAL: --bucket must be in [0, {cfg.num_buckets}), got {cfg.bucket}",
            file=sys.stderr,
        )
        return 2

    client = GanjoorClient(cfg)

    print("Fetching poet index...", flush=True)
    try:
        poets = client.poets()
    except requests.HTTPError as e:
        print(f"FATAL: could not fetch poet index: {e}", file=sys.stderr)
        return 2
    print(f"Found {len(poets)} poets.", flush=True)

    # Stable ordering: by id, smallest first. Bucket selection depends on this.
    poets.sort(key=lambda p: p.get("id", 1 << 30))

    if cfg.poet_ids:
        wanted = cfg.poet_ids
        poets = [p for p in poets if p.get("id") in wanted]
        missing = wanted - {p.get("id") for p in poets}
        if missing:
            print(f"  ! poet ids not in index: {sorted(missing)}", flush=True)
        print(f"Selection: {len(poets)} poets by --poet-ids.", flush=True)
    elif cfg.num_buckets > 0:
        poets = [p for i, p in enumerate(poets) if i % cfg.num_buckets == cfg.bucket]
        print(
            f"Selection: bucket {cfg.bucket}/{cfg.num_buckets} -> {len(poets)} poets.",
            flush=True,
        )

    if cfg.poet_limit > 0:
        poets = poets[: cfg.poet_limit]
        print(f"Limiting this run to first {len(poets)} of the selection.", flush=True)

    total_new = 0
    total_known = 0
    skipped = 0
    for i, poet in enumerate(poets, 1):
        slug = slugify(poet)
        out_path = args.out / f"{slug}.ndjson"
        progress_path = args.out / f"{slug}.progress.json"

        progress = load_progress(progress_path)
        if (
            progress
            and progress.get("completed")
            and out_path.exists()
            and out_path.stat().st_size > 0
        ):
            print(
                f"[{i}/{len(poets)}] {slug}: previously completed "
                f"({progress.get('completed_count')} poems), skipping",
                flush=True,
            )
            skipped += 1
            total_known += int(progress.get("completed_count") or 0)
            continue

        print(
            f"[{i}/{len(poets)}] {slug} (poet id={poet.get('id')}): fetching",
            flush=True,
        )
        try:
            new, on_disk = fetch_poet(client, poet, out_path, progress_path)
            print(f"  done: {new} new this run, {on_disk} total -> {out_path}", flush=True)
            total_new += new
            total_known += on_disk
        except KeyboardInterrupt:
            print("Interrupted by user. Partial progress preserved on disk.", flush=True)
            return 130
        except Exception as e:  # noqa: BLE001  – we want the loop to continue
            print(f"  ! poet {slug} failed: {e}", file=sys.stderr, flush=True)
            (args.out / f"{slug}.err").write_text(str(e), encoding="utf-8")

    print(
        f"Done. {total_new} new poems written across this run; "
        f"{total_known} poems known on disk across {len(poets)} selected poets "
        f"({skipped} skipped as previously completed).",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
