#!/usr/bin/env python3
"""
build_indexes.py

Generate the two index files the PWA needs to navigate the corpus:

  data/_poets.json
      Top-level list of every poet that has data on disk. About 50-100 KB.

  data/<poet>/_index.json
      Per-poet category tree with poem listings. Sizes range from ~10 KB
      (obscure poets, a dozen poems) up to a few MB (Saeb, Moulavi).

Both files are derived by walking data/ and reading a single sentinel
poem per directory to extract category title chains from
poem.category.cat.ancestors + poem.category.cat itself, plus reading
every poem to pick up its title and a short content snippet.

Run from the repo root after a snapshot:

  python scripts/build_indexes.py --data data

Idempotent. Safe to rerun.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROGRESS_NAME = "_progress.json"
INDEX_NAME = "_index.json"
POETS_INDEX = "_poets.json"


def first_line(text: str | None) -> str:
    if not text:
        return ""
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line[:120]
    return ""


def safe_int(s: str | None):
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def build_poet_index(poet_dir: Path) -> tuple[dict, dict]:
    """
    Walk a single poet directory and return (index, poet_meta) where:

    index = {
      "categories": [
        {
          "slug": "ghazal",
          "title_fa": "غزلیات",
          "poems_count": 495,
          "categories": [...recursive...],
          "poems": [{"id":..., "n":..., "title":..., "first":..., "couplets":...}, ...]
        }, ...
      ],
      "poems": [...]  # poems at the poet root (rare; e.g. Hafez has 3)
    }

    poet_meta = {
      "name_fa": "حافظ شیرازی",
      "nickname_fa": "حافظ",
      "description": "...",
      "birth_year": ...,
      "death_year": ...,
      "birth_place": "...",
    }

    Strategy: single pass through every poem file. For each unique
    category path, capture the first poem's category.cat (and ancestors)
    so we know each level's Persian title and slug.
    """
    cat_meta: dict[tuple, dict] = {}
    poems_by_cat: dict[tuple, list] = {}
    poet_meta: dict = {}

    for poem_file in sorted(poet_dir.rglob("*.json")):
        if poem_file.name in (PROGRESS_NAME, INDEX_NAME):
            continue
        try:
            env = json.loads(poem_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        poem = env.get("poem") or {}
        category = poem.get("category") or {}
        cat = category.get("cat") or {}

        # Capture poet metadata once from the first poem.
        if not poet_meta:
            p = category.get("poet") or {}
            poet_meta = {
                "id": p.get("id"),
                "name_fa": p.get("name"),
                "nickname_fa": p.get("nickname"),
                "description": p.get("description"),
                "full_url": p.get("fullUrl"),
                "image_url": p.get("imageUrl"),
                "birth_year": p.get("birthYearInLHijri"),
                "death_year": p.get("deathYearInLHijri"),
                "birth_place": p.get("birthPlace"),
                "death_place": p.get("deathPlace"),
            }

        rel = poem_file.relative_to(poet_dir)
        # cat_path is the tuple of directory parts containing this poem,
        # e.g. () for poems at the poet root, ("ghazal",) for hafez/ghazal/108.json,
        # ("golestan", "gbab4") for saadi/golestan/gbab4/6.json.
        cat_path = tuple(rel.parts[:-1])

        # Capture metadata for each level of cat_path the first time we see it.
        # cat.ancestors is [root, intermediate1, ...] excluding the leaf cat itself.
        ancestors = cat.get("ancestors") or []
        # Build a slug-to-title map from the ancestors chain plus the leaf cat.
        all_levels = list(ancestors) + [cat]
        # ancestors[0] is the poet root cat, which we don't represent as a path segment
        # (it's the poet itself, not a subdirectory). Skip it. The remaining levels
        # are the subdirectories.
        sub_levels = all_levels[1:] if all_levels else []

        # Build path prefixes and attach titles.
        for i, lvl in enumerate(sub_levels, 1):
            prefix = tuple(l.get("urlSlug") or "x" for l in sub_levels[:i])
            if prefix not in cat_meta:
                cat_meta[prefix] = {
                    "title_fa": lvl.get("title") or "",
                    "description": lvl.get("description"),
                    "book_name": lvl.get("bookName"),
                }

        # Append this poem to its cat_path bucket.
        entry = {
            "id": poem.get("id"),
            "n": poem_file.stem,
            "title": poem.get("title"),
            "first": first_line(poem.get("plainText") or ""),
            "couplets": poem.get("coupletsCount"),
        }
        poems_by_cat.setdefault(cat_path, []).append(entry)

    # Sort poems within each category by numeric stem when possible, else alpha.
    def sort_key(p):
        n = safe_int(p["n"])
        return (0, n) if n is not None else (1, p["n"])

    for k, v in poems_by_cat.items():
        v.sort(key=sort_key)

    # Build the recursive tree by composing cat_path tuples.
    # Collect every path that appears anywhere (as poems' parent, or as cat_meta key,
    # or as a strict prefix of either).
    all_paths: set[tuple] = set()
    for p in poems_by_cat.keys():
        all_paths.add(p)
        for i in range(len(p)):
            all_paths.add(p[:i])
    for p in cat_meta.keys():
        all_paths.add(p)
        for i in range(len(p)):
            all_paths.add(p[:i])
    all_paths.add(())

    # children index: parent_path -> sorted list of child slugs
    children: dict[tuple, list[str]] = {p: [] for p in all_paths}
    for p in all_paths:
        if p == ():
            continue
        parent = p[:-1]
        children[parent].append(p[-1])
    for parent in children:
        children[parent].sort()

    def render(path: tuple) -> dict:
        node = {}
        if path != ():
            meta = cat_meta.get(path) or {}
            node["slug"] = path[-1]
            node["title_fa"] = meta.get("title_fa", "")
            if meta.get("book_name"):
                node["book_name"] = meta.get("book_name")
            if meta.get("description"):
                node["description"] = meta.get("description")
        subs = []
        for child_slug in children.get(path, []):
            subs.append(render(path + (child_slug,)))
        if subs:
            node["categories"] = subs
        poems_here = poems_by_cat.get(path, [])
        if poems_here:
            node["poems"] = poems_here
        # Aggregate count across this subtree
        node["poems_count"] = len(poems_here) + sum(
            (s.get("poems_count") or 0) for s in subs
        )
        return node

    root = render(())
    # Strip the empty title/slug at the root, keep its children/poems/count.
    root.pop("slug", None)
    root.pop("title_fa", None)

    return root, poet_meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path("data"))
    args = ap.parse_args()

    if not args.data.exists():
        print(f"No data/ at {args.data}", file=sys.stderr)
        return 2

    poet_dirs = sorted(d for d in args.data.iterdir() if d.is_dir())
    print(f"Indexing {len(poet_dirs)} poet directories...")

    poets_summary: list[dict] = []
    written = 0
    for poet_dir in poet_dirs:
        index_path = poet_dir / INDEX_NAME
        progress_path = poet_dir / PROGRESS_NAME

        # Skip poets that have no poems on disk
        if not any(poet_dir.rglob("*.json")):
            continue

        root, poet_meta = build_poet_index(poet_dir)

        # Carry completion status from progress sidecar
        completed = False
        completed_count = root.get("poems_count", 0)
        try:
            if progress_path.exists():
                pg = json.loads(progress_path.read_text(encoding="utf-8"))
                completed = bool(pg.get("completed"))
        except (OSError, json.JSONDecodeError):
            pass

        # Per-poet index file
        index_payload = {
            "poet": poet_meta,
            "tree": root,
            "completed": completed,
        }
        index_path.write_text(
            json.dumps(index_payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

        # Summary entry for _poets.json: just enough for the picker.
        top_cats = []
        for sub in (root.get("categories") or []):
            top_cats.append({
                "slug": sub["slug"],
                "title_fa": sub.get("title_fa", ""),
                "poems_count": sub.get("poems_count", 0),
            })
        poets_summary.append({
            "slug": poet_dir.name,
            "id": poet_meta.get("id"),
            "name_fa": poet_meta.get("name_fa"),
            "nickname_fa": poet_meta.get("nickname_fa"),
            "birth_year": poet_meta.get("birth_year"),
            "death_year": poet_meta.get("death_year"),
            "birth_place": poet_meta.get("birth_place"),
            "poems_count": root.get("poems_count", 0),
            "completed": completed,
            "root_categories": top_cats,
        })
        written += 1
        size = index_path.stat().st_size
        print(
            f"  {poet_dir.name}: {root.get('poems_count', 0)} poems, "
            f"{len(top_cats)} top-level cats, index {size // 1024} KB"
        )

    # Sort poets summary by pin order / by id ascending (smallest classical first)
    poets_summary.sort(key=lambda p: (p.get("id") or 1 << 30))

    poets_payload = {
        "generated_at_count": len(poets_summary),
        "poets": poets_summary,
    }
    (args.data / POETS_INDEX).write_text(
        json.dumps(poets_payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    poets_size = (args.data / POETS_INDEX).stat().st_size
    print(
        f"\nWrote {args.data / POETS_INDEX} "
        f"({poets_size // 1024} KB, {len(poets_summary)} poets) "
        f"and {written} per-poet indexes."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
