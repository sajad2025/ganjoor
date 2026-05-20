# For AI agents

This document is the entry point for any Claude (or other) agent picking up this repo. Read it end-to-end, then skim the referenced docs as needed.

## TL;DR — where we are (as of 2026-05-19)

**Phase 1 is complete.** The full Persian corpus is on `main` and citable:
- 230 / 230 poets, 129,465 poems, zero incomplete (per `snapshot-manifest.json`)
- Per-poem JSON files at `data/<poet>/<cat>/<...>/<num>.json` — path mirrors `ganjoor.net/<poet>/<cat>/sh<num>`
- Release `v2026.1` tagged with `.tar.zst` bundles (data + legacy mirrors + manifest + checksums)
- PWA live at https://sajad2025.github.io/ganjoor/ — all 230 poets browsable, deep links, favorites, faal, share/copy, offline cache

**Phase 2 (distribute the archival copy) and the translation track are both open work.**

## Reference docs

| Doc | Purpose |
|---|---|
| `PHASE-1-HANDOFF.md` | Original Phase 1 fix plan + Phase 2 playbook. Most of Phase 2 below is the punch list from this doc. |
| `RESEARCH-ARCHIVE.md` | Strategic blueprints — architecture, preservation, governance. The "why" behind the project. Long but worth skimming for context. |
| `PHASE-1-DEBUG-LOG.md` | Forensics from the two failed snapshot runs. Useful only if you hit similar persistence bugs. |
| `PRESERVATION-ADDENDUM-free-path.md` | The $0 preservation path. Year-1 budget reality. |

## Open work — in priority order

### Phase 2 — preservation distribution

Each step is independent; some can be parallelized.

1. **Zenodo DOI** (~30 min, free, blocks 4 and 5)
   - Mints a citable DOI for the corpus.
   - User needs a Zenodo account + API token (`deposit:write`, `deposit:actions`).
   - Plan: write `scripts/zenodo_deposit.py` that takes a token + release tag, pulls assets from the GitHub Release URL, creates a deposition, publishes it. Then update `CITATION.cff` with the concept DOI.
   - Alternative: workflow `zenodo-deposit.yml` triggered on each release tag.

2. **Internet Archive** (~1h upload, free)
   - `ia upload ganjoor-2026-1 ./bundle/` with metadata. See `RESEARCH-ARCHIVE.md` § Tier 1 for the metadata template.
   - Mediatype is permanent on first upload — choose `texts` for the corpus, separate item for `audio` if/when audio is ever included.

3. **Software Heritage** (~5 min, free, no account)
   - `archive.softwareheritage.org/save/origin/save/git/url/...` against the repo URL. SWH also auto-harvests GitHub.
   - Mints a SWHID independent of GitHub's survival.

4. **Hamid email** (the most important step culturally — your voice)
   - Maintainer: **Hamid Reza Mohammadi** (`github.com/hrmoh`, Tehran, hamireza.ir).
   - Bilingual Persian + English. Tone: respectful, deferential, informing not asking. The mirror exists; here is the Zenodo DOI; we are not competing.
   - User should send personally. AI agents can draft, but the user reviews and edits before sending.

5. **UMD Roshan / Matt Miller** (`mtmiller@umd.edu`)
   - Wait until Zenodo DOI exists. Ask for inclusion in OpenITI / EOMPDL pipeline.
   - Pair with a draft PR to `github.com/OpenITI/RELEASE`.

### Translation enrichment (separate track)

The user wants English translations beneath each Persian beyt. Design constraints:

- **Translations are a derived layer**, NOT folded into canonical `data/<poet>/.../<num>.json`. They live in a parallel tree:
  ```
  translations/en/<poet>/<cat>/.../<num>.json
  ```
  Each file: `{_meta: {model, model_version, generated_at, license, kind: "machine-translation"}, beyts: [{vOrder, fa, en}]}`
- **Mechanism**: Anthropic Batch API (50% cost discount, 24h SLA). Resumable.
- **Pilot**: top 10 canonical poets (Hafez, Saadi, Rumi, Khayyam, Ferdowsi, Nezami, Attar, Sanaee, Jami, Bidel) ≈ 25,000 poems, est. $30-60, ~3 days
- **Full corpus**: 129,465 poems, est. $150-300, weeks
- **Quality framing**: every output labels as machine-translated, "not a substitute for scholarly translations by Davis / Avery / Mojaddedi / etc." Honest disclosure.
- **PWA integration**: per-beyt show/hide toggle in the Reader. Fetch `translations/en/...` alongside the canonical poem.
- **System prompt** should be tuned per form (ghazal = lyric + Sufi ambiguity; masnavi = narrative; rubaiyat = FitzGerald-style quatrain).

To implement: `scripts/translate.py` — iterate `data/`, prepare batched prompts, submit to Batch API, poll, write per-poem files to `translations/en/`. User provides `ANTHROPIC_API_KEY`.

## What's already in place — quick reference

**Scripts**:
- `fetch_ganjoor.py` — per-poem file writer; supports `--bucket / --num-buckets / --poet-ids`. Crash-safe (atomic per-poem writes), resumable (poet `_progress.json` + scan of existing files).
- `build_indexes.py` — generates `data/_poets.json` + per-poet `_index.json` for PWA navigation. Cat title chain comes from `poem.category.cat.ancestors`.
- `build_manifest.py` — generates `snapshot-manifest.json` + `CHECKSUMS.sha256`.
- `migrate_ndjson_to_perpoem.py` — one-shot (no longer needed, kept for history).
- `mirror_legacy.sh` — SourceForge + ganjoor-db legacy mirrors.

**Workflows**:
- `emergency-snapshot.yml` — single-job fetch, used for smoke tests via `poet_limit`.
- `emergency-snapshot-matrix.yml` — N-bucket parallel fetch (default 5) for full-corpus runs. Includes 10-min checkpoint commits, rebase-retry on push, salvage-on-cancel.
- `cut-release.yml` — fetch-free; bundles current `data/` + `legacy/` into a tagged GitHub Release with SHA256SUMS.

**PWA** (`index.html` + `sw.js`):
- Single file. React + Tailwind via CDN. Babel standalone for JSX.
- Hash routing: `#/`, `#/poets`, `#/poet/<slug>`, `#/poet/<slug>/<cat>/<...>`, `#/read/<slug>/<cat>/<...>/<num>`, `#/search`, `#/settings`.
- Settings persist in localStorage: theme (sepia/light/dark), font (Vazirmatn/Estedad), font size (root font-size scaling), favorites (browsable on home), recents.
- Service worker: stale-while-revalidate for data files, cache-first for shell.
- **When changing `index.html` substantively, bump the version constant in `sw.js`** (currently `v7`) — otherwise old cached shell can persist on user devices indefinitely.

## Smoke test (run before triggering anything substantive)

```bash
source .venv/bin/activate
# Quick end-to-end of fetch + per-poem write + progress + resume:
python scripts/fetch_ganjoor.py --out /tmp/smoke --poet-ids 229 --rate 5.0
# Expected: data/ayatib/gozide/{1..12}.json + _progress.json with completed:true
ls /tmp/smoke/ayatib/gozide/  # should list 12 JSON files
```

## Gotchas — non-obvious things discovered the hard way

1. **GitHub Pages runs Jekyll by default** → drops any file/dir starting with `_`. Required `.nojekyll` at repo root. Our index files (`_poets.json`, `_index.json`, `_progress.json`) all use underscore prefix.

2. **macOS APFS is case-insensitive by default** → `manifest.json` (PWA) and `MANIFEST.json` (snapshot) collapse to the same inode locally, silently overwriting each other. We renamed the snapshot output to `snapshot-manifest.json`. Don't introduce other case-only file-name conflicts.

3. **`git add` with multiple pathspecs is atomic** — if ANY pathspec is missing, the entire add aborts with exit 128, and `|| true` silently swallows it. Always loop:
   ```bash
   for p in data legacy snapshot-manifest.json; do
     [ -e "$p" ] && git add "$p" || true
   done
   ```
   This was the silent Run-#2 bug.

4. **API quirks**:
   - `poet.fullUrl`, `cat.fullUrl`, `poem.fullUrl` — all present.
   - **BUT** `poem.previous` / `poem.next` only carry `id` + `urlSlug` (no `fullUrl`). To navigate siblings, resolve `id` against the flattened poet `_index.json` (see Reader's `goSibling` in `index.html`). Reusing the current catPath fails at category boundaries (linear order across the whole poet, not per-category).
   - `poem.category.cat.ancestors[]` carries the full title chain root→leaf-parent. No extra API calls needed for nested categories like `saadi/golestan/gbab4`.

5. **`fetch()` with `cache: 'force-cache'` is dangerous during deploys** — pinned 404 HTML responses across the `.nojekyll` fix until users cleared cache. Use default cache mode; let the SW handle persistence.

6. **The Persian text normalizer (`toDisplay`, `toSearch` in `index.html`) is the reference**. If any future enrichment layer needs to normalize Persian text, copy the JS logic (or port to Python) — don't re-invent.

## Things NOT to do (still relevant)

- **Don't modify canonical `data/<poet>/.../<num>.json`** — the schema is intentionally a faithful pass-through of `api.ganjoor.net`. All enrichment (translations, normalized search index, FTS) belongs in parallel layers.
- **Don't rehost `ganjoor.net` audio** — rights are unresolved. Phase 3 problem. Only mirror the audio *index* (URL + sync XML pointer + SHA-256) if you touch audio at all.
- **Don't change `LICENSE` or `LICENSE-DATA`** without explicit user confirmation.
- **Don't push to `main` while a long-running workflow is fetching** — the matrix workflow's rebase-retry handles brief concurrent commits, but multi-hour overlap is risky. Use branches for any parallel work.

## Maintainer attribution — locked in

The corpus is mirrored from **Hamid Reza Mohammadi** (`github.com/hrmoh`, Tehran). Any doc, citation, manifest, or release body must credit him. The README previously said "Habib Hadianfard" — that was wrong, now fixed. If you see that name anywhere new, it's a regression.

CC-BY-4.0 attribution string for derived works:

> Persian poetry text courtesy of [گنجور — ganjoor.net](https://ganjoor.net) (Hamid Reza Mohammadi and contributors), republished under CC-BY-4.0 via [sajad2025/ganjoor](https://github.com/sajad2025/ganjoor).
