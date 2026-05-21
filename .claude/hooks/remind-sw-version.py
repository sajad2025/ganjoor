#!/usr/bin/env python3
import json
import os
import re
import sys
from pathlib import Path

data = json.loads(sys.stdin.read())
tool_input = data.get("tool_input", {}) or {}
path = tool_input.get("file_path") or ""
if not path.endswith("/index.html") and Path(path).name != "index.html":
    sys.exit(0)

project_root = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path(path).parent)).resolve()
sw = project_root / "sw.js"
if not sw.exists():
    sys.exit(0)

text = sw.read_text(errors="ignore")
m = re.search(r"ganjoor-shell-v(\d+)", text)
ver = m.group(1) if m else "?"

out = {
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": (
            f"You edited index.html. Per CLAUDE.md (PWA gotcha): if this is a substantive "
            f"change, bump the version constants in sw.js — currently "
            f"SHELL_CACHE='ganjoor-shell-v{ver}' and DATA_CACHE='ganjoor-data-v{ver}'. "
            f"Otherwise users get stuck on the old cached shell."
        ),
    }
}
print(json.dumps(out))
sys.exit(0)
