#!/usr/bin/env python3
"""
build_manifest.py

After fetch_ganjoor.py and mirror_legacy.sh have produced data, this builds:

  snapshot-manifest.json    — counts, fetch timestamp, source URLs, schema version
  CHECKSUMS.sha256 — SHA-256 of every file under data/ and legacy/

These two artifacts make the snapshot independently verifiable and citable.

Data layout this script expects:
  data/<poet>/<cat>/<...>/<num>.json       — one poem per file
  data/<poet>/_progress.json               — per-poet completion sidecar
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

PROGRESS_NAME = "_progress.json"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def walk_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file())


def count_poet(poet_dir: Path) -> tuple[int, list[str]]:
    """Return (poem_count, sorted_relpath_list) for one poet directory."""
    poems: list[Path] = []
    for p in poet_dir.rglob("*.json"):
        if p.name == PROGRESS_NAME:
            continue
        poems.append(p)
    return len(poems), sorted(str(p.relative_to(poet_dir.parent)) for p in poems)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("data"))
    ap.add_argument("--legacy", type=Path, default=Path("legacy"))
    args = ap.parse_args()

    data_files = walk_files(args.root)
    legacy_files = walk_files(args.legacy)

    # Per-poet summary: enumerate immediate child dirs of data/.
    poets: list[dict] = []
    total_poems = 0
    if args.root.exists():
        for poet_dir in sorted(p for p in args.root.iterdir() if p.is_dir()):
            n, _ = count_poet(poet_dir)
            total_poems += n
            entry: dict = {
                "slug": poet_dir.name,
                "dir": str(poet_dir),
                "poems": n,
            }
            progress = poet_dir / PROGRESS_NAME
            if progress.exists():
                try:
                    payload = json.loads(progress.read_text(encoding="utf-8"))
                    entry["poet_id"] = payload.get("poet_id")
                    entry["poet_nickname"] = payload.get("poet_nickname")
                    entry["completed"] = payload.get("completed", False)
                    entry["completed_at"] = payload.get("completed_at")
                except (OSError, json.JSONDecodeError):
                    pass
            poets.append(entry)

    manifest = {
        "schema_version": 1,
        "snapshot_id": os.environ.get(
            "GITHUB_RUN_ID", datetime.now(timezone.utc).strftime("local-%Y%m%dT%H%M%SZ")
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": os.environ.get("GITHUB_REPOSITORY", ""),
        "git_sha": os.environ.get("GITHUB_SHA", ""),
        "source": {
            "api": "https://api.ganjoor.net",
            "site": "https://ganjoor.net",
            "upstream_maintainer": "Hamid Reza Mohammadi (github.com/hrmoh)",
        },
        "license": {
            "code": "MIT",
            "data": "CC-BY-4.0",
            "attribution": (
                "Persian poetry text courtesy of ganjoor.net (Hamid Reza Mohammadi "
                "and contributors), republished under CC-BY-4.0."
            ),
        },
        "layout": {
            "description": "One JSON file per poem, path mirrors ganjoor.net permalink.",
            "example": "data/hafez/ghazal/108.json  <->  ganjoor.net/hafez/ghazal/sh108",
        },
        "counts": {
            "poets": len(poets),
            "poems": total_poems,
            "data_files": len(data_files),
            "legacy_files": len(legacy_files),
        },
        "poets": poets,
    }

    manifest_path = Path("snapshot-manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote {manifest_path} ({len(poets)} poets, {total_poems} poems)")

    checksum_path = Path("CHECKSUMS.sha256")
    with checksum_path.open("w", encoding="utf-8") as f:
        for p in data_files + legacy_files:
            try:
                digest = sha256_file(p)
            except OSError as e:
                print(f"  ! could not hash {p}: {e}")
                continue
            f.write(f"{digest}  {p}\n")
    print(f"Wrote {checksum_path} ({len(data_files) + len(legacy_files)} files)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
