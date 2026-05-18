#!/usr/bin/env python3
"""
fetch_ganjoor.py

Walks api.ganjoor.net and produces one NDJSON file per poet at
  <out>/<poet_slug>.ndjson

Each line is one fully-detailed poem object, fetched with verseDetails=true
and the metadata sub-resources we care about for preservation.

Designed for:
- GitHub-hosted Actions runners (6h max per job, 7 GB free disk).
- Resumability: poets already represented with a non-empty .ndjson are skipped.
- Politeness: configurable rate limit, exponential backoff, custom UA.

The walk strategy:
  1. GET /api/ganjoor/poets  -> list of poets, each with root cat id.
  2. For each poet, recursively walk categories starting from root cat:
     GET /api/ganjoor/cat/<cat_id>?poems=true
  3. For every poem id encountered, fetch the full poem:
     GET /api/ganjoor/poem/<poem_id>
        ?verseDetails=true&catInfo=true&rhymes=true
        &recitations=true&images=true&songs=true&navigation=true
     (Comments deferred to a separate, slower job.)
  4. Append the JSON to <poet_slug>.ndjson.

Output schema per line is a faithful pass-through of api.ganjoor.net's poem
object plus a small "_meta" envelope with fetch timestamp and source URL.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
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


def fetch_poet(client: GanjoorClient, poet: dict, out_path: Path) -> int:
    """
    Fetch all poems for one poet, writing one JSON per line to <out_path>.
    Returns the count of poems written.
    """
    root_cat = (
        poet.get("rootCatId")
        or poet.get("rootCat", {}).get("id")
        or poet.get("cat", {}).get("id")
    )
    if not root_cat:
        print(f"  ! no root cat for poet {poet.get('id')}: skipping", flush=True)
        return 0

    written = 0
    seen_poems: set[int] = set()
    tmp_path = out_path.with_suffix(".ndjson.tmp")

    with tmp_path.open("w", encoding="utf-8") as f:
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
            written += 1

            if written % 25 == 0:
                print(f"  - {written} poems written", flush=True)

    tmp_path.replace(out_path)
    return written


# --- main --------------------------------------------------------------------


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
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    cfg = Config(
        out=args.out,
        rate=args.rate,
        user_agent=args.user_agent,
        poet_limit=args.poet_limit,
    )
    client = GanjoorClient(cfg)

    print("Fetching poet index...", flush=True)
    try:
        poets = client.poets()
    except requests.HTTPError as e:
        print(f"FATAL: could not fetch poet index: {e}", file=sys.stderr)
        return 2
    print(f"Found {len(poets)} poets.", flush=True)

    # Stable ordering: by id, smallest first.
    poets.sort(key=lambda p: p.get("id", 1 << 30))

    if cfg.poet_limit > 0:
        poets = poets[: cfg.poet_limit]
        print(f"Limiting this run to first {len(poets)} poets.", flush=True)

    total_poems = 0
    for i, poet in enumerate(poets, 1):
        slug = poet.get("nickname") or poet.get("name") or f"poet-{poet.get('id')}"
        # Filesystem-safe slug: collapse anything weird to "_".
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in slug.lower())
        if not safe:
            safe = f"poet-{poet.get('id')}"
        out_path = args.out / f"{safe}.ndjson"

        if out_path.exists() and out_path.stat().st_size > 0:
            print(f"[{i}/{len(poets)}] {safe}: already exists, skipping", flush=True)
            continue

        print(f"[{i}/{len(poets)}] {safe} (poet id={poet.get('id')}): fetching", flush=True)
        try:
            n = fetch_poet(client, poet, out_path)
            print(f"  done: {n} poems -> {out_path}", flush=True)
            total_poems += n
        except KeyboardInterrupt:
            print("Interrupted by user.", flush=True)
            return 130
        except Exception as e:  # noqa: BLE001  – we want the loop to continue
            print(f"  ! poet {safe} failed: {e}", file=sys.stderr, flush=True)
            # Leave a .err file so the next run knows to retry this one specifically
            (args.out / f"{safe}.err").write_text(str(e), encoding="utf-8")

    print(f"Done. {total_poems} poems written across {len(poets)} poets.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
