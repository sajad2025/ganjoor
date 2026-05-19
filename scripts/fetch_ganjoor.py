#!/usr/bin/env python3
"""
fetch_ganjoor.py

Walks api.ganjoor.net and produces one JSON file per poem at
  <out>/<poet>/<cat>/<...>/<num>.json

mirroring ganjoor.net's permalink hierarchy. Each file is a single poem
envelope:

  {
    "_meta": { "fetched_at": ..., "source": ..., "source_flags": ... },
    "poem":  { ... full api.ganjoor.net poem object ... }
  }

Per-poet completion is tracked at
  <out>/<poet>/_progress.json

Each poet directory at <out>/<poet>/ corresponds to ganjoor.net's
/<poet> URL space. Subdirectories mirror the category tree:

  /hafez/ghazal/sh108        ↔ data/hafez/ghazal/108.json
  /saadi/boostan/sb1/sh3     ↔ data/saadi/boostan/sb1/3.json

Filename rule: the poem's urlSlug is normally "sh<N>" (ganjoor's poem
URL convention). We strip the "sh" prefix so the file is "<N>.json",
matching the canonical_id form documented in README. Non-standard
slugs are preserved verbatim (with non-filesystem-safe characters
sanitized).

Designed for:
- GitHub-hosted Actions runners (6h max per job, 7 GB free disk).
- **Crash-safe persistence:** each poem is written atomically (write a
  temp file, then rename). A runner kill at any moment loses at most
  the in-flight poem, never a previously-completed one.
- **Resumability:** existing .json files in a poet directory are
  treated as done. A poet with a completed _progress.json sidecar is
  skipped entirely.
- **No file-size cliff:** every file is one poem (tens of KB at most),
  so we never hit GitHub's 100 MB-per-file hard limit even for Rumi
  or Ferdowsi.
- **Sharding:** --bucket N --num-buckets M selects only poets whose
  stable-sorted index satisfies index % M == N.
- **Targeted re-runs:** --poet-ids 1,2,3 overrides selection.
"""

from __future__ import annotations

import argparse
import json
import re
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
PROGRESS_NAME = "_progress.json"


@dataclass
class Config:
    out: Path
    rate: float
    user_agent: str
    poet_limit: int
    bucket: int
    num_buckets: int
    poet_ids: set[int] = field(default_factory=set)
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
            {"User-Agent": cfg.user_agent, "Accept": "application/json"}
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
        if resp.status_code >= 500 or resp.status_code == 429:
            resp.raise_for_status()
        resp.raise_for_status()
        return resp.json()

    def poets(self) -> list[dict]:
        data = self._get("/api/ganjoor/poets")
        if isinstance(data, dict) and "poets" in data:
            data = data["poets"]
        return data or []

    def cat(self, cat_id: int, with_poems: bool = True) -> dict | None:
        suffix = "?poems=true" if with_poems else ""
        return self._get(f"/api/ganjoor/cat/{cat_id}{suffix}")

    def poem(self, poem_id: int) -> dict | None:
        return self._get(f"/api/ganjoor/poem/{poem_id}?{POEM_FLAGS}")


# --- walking -----------------------------------------------------------------


def walk_cat_for_poems(
    client: GanjoorClient, cat_id: int
) -> Iterable[tuple[int, str | None, str | None]]:
    """
    BFS the category tree. Yield (poem_id, poem_url_slug, cat_full_url).
    cat_full_url is the absolute permalink path of the cat containing
    this poem, e.g. '/hafez/ghazal'.
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

        cat_obj = cat.get("cat") or {}
        cat_full_url = cat_obj.get("fullUrl") or ""

        poems = cat.get("poems") or cat_obj.get("poems") or []
        for p in poems:
            pid = p.get("id")
            if isinstance(pid, int):
                yield pid, p.get("urlSlug"), cat_full_url

        children = cat.get("children") or cat_obj.get("children") or []
        for ch in children:
            cid_child = ch.get("id")
            if isinstance(cid_child, int):
                queue.append(cid_child)


# --- path derivation ---------------------------------------------------------


_SH_NUM_RE = re.compile(r"sh(\d+)")
_PATH_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_segment(s: str) -> str:
    """Filesystem-safe path segment. Collapse runs of unsafe chars to '_'."""
    safe = _PATH_SAFE_RE.sub("_", s).strip("._-")
    return safe or "x"


def derive_poem_filename(url_slug: str | None, poem_id: int) -> str:
    """
    Build a clean filename for a poem.
      sh108  -> 108.json   (the common ganjoor case)
      sh1    -> 1.json
      m1     -> m1.json    (preserved when it's not the sh<N> form)
      None   -> p<id>.json
    """
    if url_slug:
        m = _SH_NUM_RE.fullmatch(url_slug)
        if m:
            return f"{m.group(1)}.json"
        safe = _sanitize_segment(url_slug)
        return f"{safe}.json"
    return f"p{poem_id}.json"


def derive_poem_path(
    out_root: Path,
    cat_full_url: str | None,
    poem_full_url: str | None,
    poem_url_slug: str | None,
    poem_id: int,
) -> Path:
    """
    Compute the on-disk path for a poem. Prefer poem_full_url (authoritative,
    only available after fetching). Fall back to cat_full_url + filename.
    """
    if poem_full_url:
        parts = [_sanitize_segment(p) for p in poem_full_url.strip("/").split("/") if p]
        if parts:
            # Last segment is the poem slug; strip the sh-prefix for the file.
            last = parts[-1]
            m = _SH_NUM_RE.fullmatch(last)
            filename = f"{m.group(1)}.json" if m else f"{_sanitize_segment(last)}.json"
            return out_root.joinpath(*parts[:-1], filename)

    # Fallback: synthesise from cat_full_url + poem's urlSlug
    cat_parts = [
        _sanitize_segment(p)
        for p in (cat_full_url or "").strip("/").split("/")
        if p
    ]
    if not cat_parts:
        cat_parts = ["uncategorized"]
    filename = derive_poem_filename(poem_url_slug, poem_id)
    return out_root.joinpath(*cat_parts, filename)


def poet_slug_of(poet: dict) -> str:
    """ASCII slug for a poet, used as the top-level dir under data/."""
    full = (poet.get("fullUrl") or "").strip("/")
    if full:
        # poet.fullUrl is like '/hafez' — single segment expected.
        return _sanitize_segment(full.split("/")[0])
    # Fallbacks: try nickname/name (likely Persian — sanitize to Latin-friendly)
    nick = poet.get("nickname") or poet.get("name") or f"poet-{poet.get('id')}"
    return _sanitize_segment(nick)


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
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = progress_path.with_suffix(progress_path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(progress_path)


def scan_done_poem_ids(poet_dir: Path) -> set[int]:
    """
    Walk an existing poet directory and collect every poem.id present.
    Used for mid-poet resume: skip ids we've already fetched.
    """
    ids: set[int] = set()
    if not poet_dir.exists():
        return ids
    for p in poet_dir.rglob("*.json"):
        if p.name == PROGRESS_NAME:
            continue
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        poem = payload.get("poem") or {}
        pid = poem.get("id")
        if isinstance(pid, int):
            ids.add(pid)
    return ids


def write_poem_atomically(out_path: Path, envelope: dict) -> None:
    """Write JSON to disk via temp + rename so a kill mid-write is harmless."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    tmp.replace(out_path)


# --- fetch -------------------------------------------------------------------


def fetch_poet(
    client: GanjoorClient,
    poet: dict,
    poet_dir: Path,
    progress_path: Path,
    out_root: Path,
) -> tuple[int, int]:
    """
    Fetch all poems for one poet, writing one JSON file per poem.
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

    poet_dir.mkdir(parents=True, exist_ok=True)
    already_done = scan_done_poem_ids(poet_dir)
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

    for poem_id, poem_url_slug, cat_full_url in walk_cat_for_poems(client, int(root_cat)):
        if poem_id in seen_poems:
            continue
        seen_poems.add(poem_id)

        poem = client.poem(poem_id)
        if not poem:
            continue

        out_path = derive_poem_path(
            out_root,
            cat_full_url=cat_full_url,
            poem_full_url=poem.get("fullUrl"),
            poem_url_slug=poem_url_slug,
            poem_id=poem_id,
        )

        envelope = {
            "_meta": {
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "source": f"{BASE}/api/ganjoor/poem/{poem_id}",
                "source_flags": POEM_FLAGS,
            },
            "poem": poem,
        }
        write_poem_atomically(out_path, envelope)
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True, help="output directory")
    ap.add_argument("--rate", type=float, default=3.0, help="max req/sec")
    ap.add_argument(
        "--user-agent",
        default="ganjoor-mirror/0.1 (+https://github.com/sajad2025/ganjoor)",
    )
    ap.add_argument("--poet-limit", type=int, default=0)
    ap.add_argument("--bucket", type=int, default=0)
    ap.add_argument("--num-buckets", type=int, default=0)
    ap.add_argument("--poet-ids", type=str, default=None)
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
        slug = poet_slug_of(poet)
        poet_dir = args.out / slug
        progress_path = poet_dir / PROGRESS_NAME

        progress = load_progress(progress_path)
        if (
            progress
            and progress.get("completed")
            and poet_dir.exists()
            and any(poet_dir.rglob("*.json"))
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
            new, on_disk = fetch_poet(client, poet, poet_dir, progress_path, args.out)
            print(
                f"  done: {new} new this run, {on_disk} total -> {poet_dir}",
                flush=True,
            )
            total_new += new
            total_known += on_disk
        except KeyboardInterrupt:
            print("Interrupted by user. Partial progress preserved on disk.", flush=True)
            return 130
        except Exception as e:  # noqa: BLE001
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
