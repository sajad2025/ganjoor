#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

data = json.loads(sys.stdin.read())
tool_input = data.get("tool_input", {}) or {}
path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
if not path:
    sys.exit(0)

project_root = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()
data_root = (project_root / "data").resolve()

try:
    rel = Path(path).resolve().relative_to(data_root)
except (ValueError, OSError):
    sys.exit(0)

# Allow underscore-prefixed files at any depth (index, progress, search shards, etc.)
if any(p.startswith("_") for p in rel.parts):
    sys.exit(0)

print(
    f"Blocked: {path}\n\n"
    "Canonical per-poem JSON under data/<poet>/.../<num>.json is a faithful pass-through of "
    "api.ganjoor.net. Per CLAUDE.md \"Things NOT to do\" #1, do not modify these files. "
    "Put enrichment (translations, search index, etc.) in a parallel layer such as "
    "translations/en/ or data/_search/.",
    file=sys.stderr,
)
sys.exit(2)
