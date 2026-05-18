#!/usr/bin/env python3
"""
build_manifest.py

After fetch_ganjoor.py and mirror_legacy.sh have produced data, this builds:

  MANIFEST.json    — counts, fetch timestamp, source URLs, schema version
  CHECKSUMS.sha256 — SHA-256 of every file under data/ and legacy/

These two artifacts make the snapshot independently verifiable and citable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


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


def count_lines(p: Path) -> int:
    with p.open("rb") as f:
        return sum(1 for _ in f)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("data"))
    ap.add_argument("--legacy", type=Path, default=Path("legacy"))
    args = ap.parse_args()

    data_files = walk_files(args.root)
    legacy_files = walk_files(args.legacy)

    # Per-poet counts.
    poets = []
    total_poems = 0
    for p in data_files:
        if p.suffix == ".ndjson":
            n = count_lines(p)
            total_poems += n
            poets.append({"slug": p.stem, "file": str(p), "poems": n})

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
        "counts": {
            "poets": len(poets),
            "poems": total_poems,
            "data_files": len(data_files),
            "legacy_files": len(legacy_files),
        },
        "poets": poets,
    }

    manifest_path = Path("MANIFEST.json")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote {manifest_path}")

    # Single checksums file covering both data/ and legacy/
    checksum_path = Path("CHECKSUMS.sha256")
    with checksum_path.open("w", encoding="utf-8") as f:
        for p in data_files + legacy_files:
            try:
                digest = sha256_file(p)
            except OSError as e:
                print(f"  ! could not hash {p}: {e}")
                continue
            # GNU coreutils format: "<hash>  <path>"
            f.write(f"{digest}  {p}\n")
    print(f"Wrote {checksum_path} ({len(data_files) + len(legacy_files)} files)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
