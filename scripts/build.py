#!/usr/bin/env python3
"""Build the production PWA artifact.

Source `index.html` carries a single inline `<script type="text/babel">`
block (~1500 lines of JSX) plus a Babel Standalone <script> tag that
compiles it at runtime. That CDN bundle is ~3 MB and parsing it before
the app can mount costs 2-3 s of cold-start latency on iOS — even when
fully cached offline.

This script reads `index.html`, transpiles the JSX once via esbuild, and
emits a production `_site/index.html` that ships plain pre-compiled JS
with no Babel runtime. Other deployable assets (data/, sw.js, icons,
manifest.json, legacy/) get staged into the same `_site/` tree so the
GitHub Actions deploy workflow can upload it as a single Pages artifact.

Source `index.html` stays unchanged. Local dev keeps working without a
build step: `python -m http.server` in the repo root and the Babel
runtime handles JSX in-browser (slow but zero-setup).

Usage:
    python scripts/build.py                  # full deploy build into _site/
    python scripts/build.py --html-only      # just emit _site/index.html
    python scripts/build.py --out path.html  # custom output path
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "index.html"
DEFAULT_OUT_DIR = ROOT / "_site"

# Top-level paths that must be served by GitHub Pages alongside index.html.
# Mirrors what the previous "Deploy from a branch" mode picked up from the
# repo root, minus docs and tooling.
DEPLOY_PATHS = [
    "data",
    "legacy",
    "manifest.json",
    "sw.js",
    "favicon.png",
    "apple-touch-icon.png",
    "icon-192.png",
    "icon-512.png",
    "icon-maskable.png",
    ".nojekyll",
    "CITATION.cff",
    "snapshot-manifest.json",
    "CHECKSUMS.sha256",
]

BABEL_SCRIPT_RE = re.compile(
    r'\s*<script src="https://unpkg\.com/@babel/standalone[^"]+"></script>'
)
JSX_BLOCK_RE = re.compile(
    r'<script type="text/babel"[^>]*>(.*?)</script>',
    re.DOTALL,
)


def find_esbuild() -> list[str]:
    """Return the command prefix to invoke esbuild.

    Prefers a globally installed `esbuild` binary (fast — no npm download
    per invocation). Falls back to `npx --yes esbuild` which pulls esbuild
    on demand. The CI workflow installs esbuild globally so it never has
    to take the npx fallback path.
    """
    exe = shutil.which("esbuild")
    if exe:
        return [exe]
    if shutil.which("npx"):
        return ["npx", "--yes", "esbuild"]
    raise SystemExit(
        "esbuild is not installed and npx is not available. Install with:\n"
        "    npm install -g esbuild\n"
        "or ensure Node/npx is on PATH so the fallback can fetch it."
    )


def transpile(jsx: str) -> str:
    """Run esbuild over a JSX string and return minified JS."""
    cmd = find_esbuild() + [
        "--loader=jsx",
        "--target=es2018",
        "--minify",
        "--charset=utf8",
        "--log-level=warning",
    ]
    proc = subprocess.run(
        cmd, input=jsx, capture_output=True, text=True, encoding="utf-8"
    )
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    if proc.returncode != 0:
        raise SystemExit(f"esbuild failed (exit {proc.returncode})")
    return proc.stdout


def build_html() -> tuple[str, dict[str, int]]:
    """Read source index.html and return (production HTML, stats dict)."""
    html = SRC.read_text(encoding="utf-8")

    m = JSX_BLOCK_RE.search(html)
    if not m:
        raise SystemExit(
            'No <script type="text/babel"> block found in index.html'
        )
    jsx = m.group(1)
    js = transpile(jsx)

    # Replace JSX block with built JS — drop the type="text/babel" so the
    # browser executes it as plain JavaScript.
    built = html[: m.start()] + f"<script>{js}</script>" + html[m.end():]

    # Drop the Babel Standalone <script src=...> tag entirely. If it slips
    # through, fall back loud rather than silent — the file still works
    # but ships an unused 3 MB CDN bundle, which would be a regression.
    new_built, n = BABEL_SCRIPT_RE.subn("", built, count=1)
    if n == 0:
        print(
            "  warning: Babel Standalone <script> tag not found; built file "
            "may still reference the CDN",
            file=sys.stderr,
        )
    built = new_built

    stats = {
        "src_html_bytes": len(html),
        "src_jsx_bytes": len(jsx),
        "built_js_bytes": len(js),
        "built_html_bytes": len(built),
    }
    return built, stats


def _link_or_copy(src: Path, dst: Path) -> None:
    """Hardlink if possible (~free), otherwise copy.

    Hardlinks make the 130K-file data/ tree stage in ~1 s on Linux/macOS
    instead of the ~30 s a real copy would take. Falls back to copy when
    src and dst are on different filesystems or hardlinks are disallowed.
    """
    try:
        os.link(src, dst)
    except (OSError, NotImplementedError):
        shutil.copy2(src, dst)


def copy_deployables(dest_dir: Path) -> None:
    """Stage all DEPLOY_PATHS into dest_dir, preserving structure."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    staged = 0
    for name in DEPLOY_PATHS:
        src = ROOT / name
        if not src.exists():
            continue
        dst = dest_dir / name
        if dst.exists():
            if dst.is_dir() and not dst.is_symlink():
                shutil.rmtree(dst)
            else:
                dst.unlink()
        if src.is_dir():
            shutil.copytree(src, dst, copy_function=_link_or_copy)
        else:
            _link_or_copy(src, dst)
        staged += 1
    print(
        f"  staged {staged}/{len(DEPLOY_PATHS)} top-level paths "
        f"into {dest_dir.relative_to(ROOT)}/",
        file=sys.stderr,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--out",
        default=None,
        help="Output path for built index.html "
        "(default: _site/index.html for full builds, "
        "or this exact path for --html-only)",
    )
    ap.add_argument(
        "--html-only",
        action="store_true",
        help="Only emit the built HTML — skip copying data/, sw.js etc. "
        "Fast iteration during local testing.",
    )
    args = ap.parse_args()

    print(f"Building from {SRC.relative_to(ROOT)}", file=sys.stderr)
    built, stats = build_html()
    print(
        f"  source: {stats['src_html_bytes']:,} B HTML "
        f"({stats['src_jsx_bytes']:,} B inline JSX)",
        file=sys.stderr,
    )
    print(
        f"  built : {stats['built_html_bytes']:,} B HTML "
        f"({stats['built_js_bytes']:,} B compiled JS, "
        f"{100 * stats['built_js_bytes'] / max(1, stats['src_jsx_bytes']):.0f}% "
        f"of JSX source)",
        file=sys.stderr,
    )

    if args.html_only:
        out = Path(args.out) if args.out else ROOT / "_site" / "index.html"
        out = out.resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(built, encoding="utf-8")
        print(f"  wrote {out}", file=sys.stderr)
        return

    out_dir = (
        Path(args.out).resolve().parent if args.out else DEFAULT_OUT_DIR
    )
    out_html = (
        Path(args.out).resolve() if args.out else out_dir / "index.html"
    )
    copy_deployables(out_dir)
    out_html.write_text(built, encoding="utf-8")
    print(f"  wrote {out_html.relative_to(ROOT)}", file=sys.stderr)


if __name__ == "__main__":
    main()
