#!/usr/bin/env python3
"""
One-shot migration: explode each existing data/<slug>.ndjson into the
new per-poem layout under data/<poet>/<cat>/<...>/<num>.json.

For each NDJSON file in data/:
  1. Read each line as a poem envelope.
  2. Derive the destination path from poem.fullUrl (or the cat URL +
     poem.urlSlug) using the same logic as fetch_ganjoor.derive_poem_path.
  3. Write the envelope to the per-poem file atomically.
  4. Reconstruct a new <poet>/_progress.json from the per-poet
     .progress.json sidecar that accompanied the NDJSON.
  5. Delete the old NDJSON and old .progress.json once migration is verified.

Run from the repo root after `git pull`:

    python scripts/migrate_ndjson_to_perpoem.py --data data
    # then inspect, commit, push.

Idempotent: re-running on an already-migrated tree is a no-op.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Import the helpers we already use in fetch_ganjoor — avoid duplicating logic.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_ganjoor as fg  # noqa: E402


def migrate_ndjson(ndjson_path: Path, data_root: Path) -> tuple[int, str]:
    """Explode one NDJSON file. Returns (poems_written, poet_slug)."""
    poems_written = 0
    poet_slug: str | None = None

    with ndjson_path.open("r", encoding="utf-8") as f:
        for line_no, raw in enumerate(f, 1):
            line = raw.strip()
            if not line:
                continue
            try:
                envelope = json.loads(line)
            except json.JSONDecodeError as e:
                print(
                    f"  ! {ndjson_path.name}:{line_no} JSON decode error: {e}; "
                    "skipping",
                    file=sys.stderr,
                )
                continue

            poem = envelope.get("poem") or {}
            poem_id = poem.get("id")
            if not isinstance(poem_id, int):
                continue

            poem_full_url = poem.get("fullUrl")
            poem_url_slug = poem.get("urlSlug")
            cat_full_url = (poem.get("category") or {}).get("fullUrl")

            # Track the poet slug — derived from the first poem's path.
            if poet_slug is None and poem_full_url:
                parts = poem_full_url.strip("/").split("/")
                if parts:
                    poet_slug = parts[0]

            out_path = fg.derive_poem_path(
                data_root,
                cat_full_url=cat_full_url,
                poem_full_url=poem_full_url,
                poem_url_slug=poem_url_slug,
                poem_id=poem_id,
            )
            if out_path.exists():
                # Idempotency: already migrated this poem.
                continue
            fg.write_poem_atomically(out_path, envelope)
            poems_written += 1

    return poems_written, poet_slug or "unknown"


def find_old_progress_for(ndjson_path: Path) -> Path | None:
    """Locate the legacy progress sidecar that paired with this NDJSON."""
    # Old layout: data/<slug>.ndjson + data/<slug>.progress.json
    candidate = ndjson_path.with_suffix(".progress.json")
    return candidate if candidate.exists() else None


def write_new_progress(
    data_root: Path,
    poet_slug: str,
    poems_written: int,
    old_progress: Path | None,
) -> Path:
    """
    Build the new <poet>/_progress.json. Carry over poet metadata from the
    old sidecar if available.
    """
    payload: dict = {
        "completed": True,
        "completed_count": poems_written,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "migrated_from": "ndjson",
    }
    if old_progress and old_progress.exists():
        try:
            old = json.loads(old_progress.read_text(encoding="utf-8"))
            payload["poet_id"] = old.get("poet_id")
            payload["poet_nickname"] = old.get("poet_nickname")
            payload["root_cat_id"] = old.get("root_cat_id")
        except (OSError, json.JSONDecodeError):
            pass

    progress_path = data_root / poet_slug / fg.PROGRESS_NAME
    fg.save_progress(progress_path, payload)
    return progress_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path("data"))
    ap.add_argument(
        "--keep-old",
        action="store_true",
        help="Don't delete the source NDJSON + .progress.json after migration.",
    )
    args = ap.parse_args()

    if not args.data.exists():
        print(f"No data/ directory at {args.data}; nothing to migrate.")
        return 0

    ndjson_files = sorted(args.data.glob("*.ndjson"))
    if not ndjson_files:
        print("No *.ndjson files at the top of data/; nothing to migrate.")
        return 0

    print(f"Found {len(ndjson_files)} NDJSON file(s) to migrate.")
    total_poems = 0
    for nd in ndjson_files:
        print(f"\n→ {nd.name}")
        old_progress = find_old_progress_for(nd)
        n, poet_slug = migrate_ndjson(nd, args.data)
        print(f"  wrote {n} poem files into data/{poet_slug}/")

        # If the NDJSON contained zero usable poems, leave everything alone.
        if n == 0 and not (args.data / poet_slug).exists():
            print(f"  ! no poems migrated; leaving {nd.name} in place")
            continue

        new_progress = write_new_progress(args.data, poet_slug, n, old_progress)
        print(f"  wrote {new_progress.relative_to(args.data.parent)}")

        if not args.keep_old:
            nd.unlink()
            print(f"  removed {nd.name}")
            if old_progress and old_progress.exists():
                old_progress.unlink()
                print(f"  removed {old_progress.name}")

        total_poems += n

    print(f"\nMigration done. {total_poems} poems migrated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
