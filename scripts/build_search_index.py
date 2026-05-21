#!/usr/bin/env python3
"""
build_search_index.py

For each poet directory under <out>/, walk every per-poem JSON and produce a
compact per-poet search shard at <out>/<poet>/_search.json containing the
normalized plainText of every poem in that poet's subtree.

Shape (compact array-of-arrays, gzipped by GH Pages on the wire):

  [
    ["<url-tail>", "<displayTitle>", "<normalizedPlainText>"],
    ...
  ]

where url-tail is the path under the poet directory with ".json" stripped,
e.g. "ghazal/108", "boostan/sb1/3", "saghiname".

The normalizer is a Python port of toSearch() / toDisplay() in index.html and
MUST stay in sync with the JS — both are applied with the same algorithm so
the prebuilt index matches what the PWA runtime computes on the query.

Atomic per-poet writes (write temp + os.replace). Re-running is idempotent.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

# --- Persian normalizer — keep in sync with index.html toDisplay/toSearch ----

FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
AR_DIGITS = "٠١٢٣٤٥٦٧٨٩"
TO_FA = {"ي": "ی", "ك": "ک", "ى": "ی", "ة": "ه", "ہ": "ه"}
RE_TO_FA = re.compile("[" + "".join(TO_FA.keys()) + "]")
RE_BIDI = re.compile(r"[‎‏‪-‮⁦-⁩]")
RE_DIAC = re.compile(r"[ً-ْٰـٕٔ]")
RE_ALEF_FORMS = re.compile(r"[آأإ]")
RE_HAMZA = re.compile(r"[ؤئء]")
RE_ZWNJ_ZWJ = re.compile(r"[‌‍]")
RE_WS = re.compile(r"\s+")
DIGIT_MAP = str.maketrans(FA_DIGITS + AR_DIGITS, "0123456789" * 2)


def to_display(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFC", s)
    s = RE_TO_FA.sub(lambda m: TO_FA[m.group(0)], s)
    return RE_BIDI.sub("", s)


def to_search(s: str) -> str:
    x = to_display(s)
    x = RE_DIAC.sub("", x)
    x = RE_ALEF_FORMS.sub("ا", x)
    x = RE_HAMZA.sub("", x)
    x = RE_ZWNJ_ZWJ.sub(" ", x)
    x = x.translate(DIGIT_MAP)
    return RE_WS.sub(" ", x.lower()).strip()


# --- Build ------------------------------------------------------------------


def write_atomic(path: Path, payload: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_search_", suffix=".json")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def build_poet_shard(poet_dir: Path) -> tuple[int, int]:
    """Returns (poems_indexed, bytes_written)."""
    entries: list[list] = []
    poet_root = poet_dir.resolve()

    for json_path in sorted(poet_dir.rglob("*.json")):
        name = json_path.name
        # Skip underscore files at any depth (_progress, _index, _search itself)
        if any(part.startswith("_") for part in json_path.relative_to(poet_dir).parts):
            continue
        try:
            with json_path.open("rb") as f:
                doc = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"  skip {json_path}: {e}", file=sys.stderr)
            continue

        poem = doc.get("poem") if isinstance(doc, dict) else None
        if not isinstance(poem, dict):
            continue

        plain = poem.get("plainText") or ""
        title = poem.get("title") or ""
        if not plain.strip():
            continue

        url_tail = str(json_path.relative_to(poet_dir).with_suffix("")).replace(os.sep, "/")
        entries.append([url_tail, to_display(title), to_search(plain)])

    payload = json.dumps(entries, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    out_path = poet_dir / "_search.json"
    write_atomic(out_path, payload)
    return len(entries), len(payload)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data", help="Root data directory (default: data)")
    ap.add_argument("--poets", default="", help="Comma-separated poet slugs (default: all)")
    args = ap.parse_args()

    root = Path(args.out).resolve()
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 1

    if args.poets:
        wanted = set(s.strip() for s in args.poets.split(",") if s.strip())
        poet_dirs = sorted([root / p for p in wanted if (root / p).is_dir()])
    else:
        poet_dirs = sorted([p for p in root.iterdir() if p.is_dir() and not p.name.startswith("_")])

    total_poems = 0
    total_bytes = 0
    t0 = time.monotonic()
    for i, poet in enumerate(poet_dirs, 1):
        t_poet = time.monotonic()
        n, b = build_poet_shard(poet)
        dt = time.monotonic() - t_poet
        total_poems += n
        total_bytes += b
        print(f"  [{i:3}/{len(poet_dirs)}] {poet.name:30} {n:>6} poems  {b/1024:>7.1f} KB  {dt:5.2f}s")

    elapsed = time.monotonic() - t0
    print(
        f"\nDone: {len(poet_dirs)} poets, {total_poems} poems, "
        f"{total_bytes/1024/1024:.1f} MB raw, in {elapsed:.1f}s"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
