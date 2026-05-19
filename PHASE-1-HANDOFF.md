# Ganjoor Preservation — Phase 1 Handoff

**Reader: this document is written for Claude Code (or any AI agent) picking up work on the `sajad2025/ganjoor` repository. Read it end-to-end before touching anything.**

## TL;DR — where we are

The repo `sajad2025/ganjoor` is an open-source preservation mirror + reference PWA for the Persian classical poetry corpus hosted at **ganjoor.net** (maintained solely by **Hamid Reza Mohammadi** / `github.com/hrmoh`, Tehran). We are building this because ganjoor has bus factor 1, runs partly on Iran-hosted infrastructure currently affected by the long 2026 Iranian internet shutdown, and has no complete third-party mirror.

**Phase 1 goal:** an emergency snapshot of the entire text corpus, committed to the repo and published as a tagged Release, with `MANIFEST.json` + `CHECKSUMS.sha256`. From there, we plan to mirror to Zenodo (DOI), Internet Archive, Software Heritage, Filecoin Plus, and ideally an academic institutional home (UMD Roshan/OpenITI being the strongest target).

**Phase 1 status: blocked.** The GitHub Actions workflow `Emergency Snapshot` runs end-to-end and walks `api.ganjoor.net` correctly, **but**:

1. The full corpus takes ~10–12 hours to fetch at the current throttle (5 req/sec), while GitHub-hosted free runners cap at 6 hours per job.
2. Run #2 (the first real attempt) timed out at 5h 49m on poet 136 of 230.
3. The `if: always()` safety net we added on the commit step **ran but committed nothing** — `data/` does not exist on `main`. The 5h+ of fetched data was lost when the runner was destroyed.

**The work you are picking up: fix the persistence/resumability problem so a single run, or a chain of resumable runs, can fetch and commit the full corpus.**

---

## Project framing — what we are building and why

The umbrella project is **a phone-buildable, GitHub-only, MIT/CC-BY infrastructure-class republication of ganjoor.net**, with a reference PWA reader on top. The PWA is the demo. **The data layer is the product.** The corpus is the thing scholars and downstream apps should be able to cite and depend on for the next 25+ years even if ganjoor.net itself disappears.

Three foundational decisions that are locked in and should not be revisited:

1. **Permalink contract.** Every poem has three first-class identifiers, all permanent: a `canonical_id` (e.g. `hafez/divan/ghazal/108`), a `urn:ganjoor:...` URN, and the upstream numeric `ganjoor_id`. Once minted, never reused or repointed. This is what turns the repo from a scraper into infrastructure.
2. **Layered licensing.** Code is **MIT** (`LICENSE`). Curated text corpus is **CC-BY-4.0** (`LICENSE-DATA`). Schemas are CC0. Audio defaults to no-redistribute. Attribution to "گنجور — ganjoor.net (Hamid Reza Mohammadi and contributors)" is required.
3. **Hosting is GitHub-only for v0.1.** GitHub Releases, GitHub Pages, GitHub Actions, with `raw.githubusercontent.com` as a Range-request-capable CDN. Cloudflare is a documented Phase-2 option only if/when we hit specific limits (per-PR previews, custom headers, >100 GB/mo bandwidth, or want Workers). The cost forecast is **$0 for Year 1**, including all preservation; grants are about paying maintainers later, not keeping bytes alive.

For the longer architectural context see in the repo:

- `README.md` — bilingual, audience-segmented (reader / developer / researcher / contributor)
- `LICENSE-DATA` — CC-BY-4.0 + attribution template
- `CITATION.cff` — academic citation, will be tied to a Zenodo concept DOI once we deposit
- `PRESERVATION-ADDENDUM-free-path.md` — the $0 path

The strategic preservation playbook (the long one) lives in the chat I had with the human; this handoff document is the operational summary. You don't need that playbook to do Phase 1, but if you want context on Phase 2+ (institutional outreach, Filecoin Plus, Software Heritage, Zenodo, the audio rights problem, governance), ask the user to share it.

---

## Repository layout (as of this handoff)

```
ganjoor/
├── index.html                          # PWA reader, single file, deployed to GitHub Pages
├── manifest.json                       # PWA manifest
├── icon-{192,512,maskable}.png         # PWA icons (calligraphic گ on parchment)
├── apple-touch-icon.png
├── favicon.png
├── README.md                           # bilingual, infrastructure framing
├── LICENSE                             # MIT (code)
├── LICENSE-DATA                        # CC-BY-4.0 (corpus)
├── CITATION.cff
├── PRESERVATION-ADDENDUM-free-path.md
├── .gitignore                          # Node template + Python additions (.venv, __pycache__)
├── .github/
│   └── workflows/
│       └── emergency-snapshot.yml      # Phase 1 workflow — THE THING TO FIX
└── scripts/
    ├── README.md                       # phone-triggerable run instructions
    ├── requirements.txt                # requests, tenacity
    ├── fetch_ganjoor.py                # walks api.ganjoor.net into NDJSON per poet
    ├── mirror_legacy.sh                # SourceForge + ganjoor-db + ganjoor/desktop release
    ├── save_to_wayback.py              # IA Save Page Now caller
    ├── wayback_urls.txt                # starter URL list
    ├── build_manifest.py               # MANIFEST.json + CHECKSUMS.sha256
    └── setup_venv.sh                   # local-dev venv with macOS DYLD workaround
```

The PWA is already live at <https://sajad2025.github.io/ganjoor/> and installable as a home-screen app on iOS via Safari → Add to Home Screen. The PWA currently ships two seed Hafez ghazals (#81, #108) hardcoded; once `data/` exists in the repo, the PWA will eventually be wired to read from it. That wiring is a later phase — do not do it in Phase 1.

---

## How the snapshot workflow is supposed to work

`.github/workflows/emergency-snapshot.yml` is triggered manually (`workflow_dispatch`) from the GitHub Actions UI on a phone or browser. It takes four inputs:

- `poet_limit` (string, default `"5"`) — how many poets to fetch, 0 means all
- `mirror_legacy` (boolean, default true) — also mirror SourceForge + ganjoor-db
- `save_wayback` (boolean, default true) — call IA Save Page Now (requires `IA_S3_*` secrets)
- `create_release` (boolean, default false) — tag + publish a Release with bundle artifacts

Step sequence inside the single `snapshot` job:

1. Checkout
2. Set up Python 3.12
3. `pip install -r scripts/requirements.txt`
4. (if `mirror_legacy`) `bash scripts/mirror_legacy.sh` — mirrors `legacy/sourceforge/*.zip`, `legacy/desktop/*`, `legacy/ganjoor-db/ganjoor-db.bundle`
5. `python scripts/fetch_ganjoor.py --out data --poet-limit ${poet_limit} --rate 5.0 --user-agent ...` — writes `data/<poet-slug>.ndjson` per poet
6. `python scripts/build_manifest.py --root data --legacy legacy` — writes `MANIFEST.json` and `CHECKSUMS.sha256`
7. (if `save_wayback`) `python scripts/save_to_wayback.py --urls scripts/wayback_urls.txt`
8. **Commit `data/`, `legacy/`, `MANIFEST.json`, `CHECKSUMS.sha256` back to `main`** — currently has `if: always()` so it runs on cancel
9. (if `create_release`) bundle into `release/*.tar.zst` using zstd
10. (if `create_release`) `softprops/action-gh-release@v2` publishes a tagged Release

`fetch_ganjoor.py` is the meat of step 5. Key behaviors:

- Hits `GET /api/ganjoor/poets`, returns 230 poets (smaller than the 700+ public-facing browseable count — the API list is the canonical one).
- For each poet, recursively walks the category tree starting from `rootCatId`, BFS-style, yielding every poem id encountered.
- For each poem id, fetches `/api/ganjoor/poem/{id}?verseDetails=true&catInfo=true&rhymes=true&recitations=true&images=true&songs=true&navigation=true`.
- Writes an envelope `{"_meta": {...}, "poem": {...}}` as one JSON line per poem.
- **Critical detail:** writes to `<poet>.ndjson.tmp` first and only `.replace()`s to `<poet>.ndjson` when the poet is *fully complete*. **This is one of the persistence problems** — see below.
- Resumability is by poet only: if `<poet>.ndjson` exists and is non-empty at the start of a run, the poet is skipped.
- Throttle: `Throttle(rate)` enforces ≤ `rate` requests/sec via a leaky-bucket sleep. Currently `--rate 5.0`.
- Retries via `tenacity`: exponential backoff on `ConnectionError`, `Timeout`, `HTTPError` (which includes 5xx and 429), 5 attempts, 2–60s wait.

---

## What we actually learned from the two real runs

**Run #1 (smoke test): `poet_limit: 5`, `mirror_legacy: true`, `save_wayback: false`, `create_release: false`**
- Walked the first 5 poets in ~32 minutes at the original 3 req/sec.
- 3,725 poems fetched across those 5 poets — the big classical poets (Hafez, Saadi, Rumi, Ferdowsi, Khayyam) have **hundreds to thousands of poems each**, not the ~50 I'd initially estimated.
- Canceled manually before it could complete the smoke test.
- **Nothing committed** because the commit step at that point did not have `if: always()`.

**Run #2 (real attempt): `poet_limit: 0`, `mirror_legacy: true`, `save_wayback: false`, `create_release: true`**
- We then patched the workflow to bump `--rate 3.0 → 5.0` and added `if: always()` to the commit step only.
- Run #2 reached poet 136 of 230 (~59%) at 5h 49m, where the GitHub job's 350-minute `timeout-minutes` killed it.
- The "Commit data back to main" step shows **green check, 0s duration**, but **`data/` does not exist on `main`** and there is no `ganjoor-mirror-bot` commit. **All ~135 completed poets of fetched data were lost.**
- The subsequent `if: always()`-less steps (manifest, bundle, release) all skipped, as expected.

**Throughput numbers from the real runs:**
- At 3 req/sec: ~117 poems/minute, ~3,725 poems in 32 min on the first 5 (big) poets.
- At 5 req/sec: ~136 poets in ~5h 49m. Implies ~10–12 hours for full 230 poets. **Will not fit in a single 6-hour job.**
- ~230 poets total, dominated by a few very-large ones at the top (canonical classical poets).
- Estimated full-corpus poem count: ~35,000–50,000. (Academic papers cite 1.47M verses across the corpus, but verses ≠ poems; each ghazal has multiple beyts.)

---

## The actual bug — Phase 1 blocker

When run #2 was force-canceled by GitHub's 350-minute timeout, the "Commit data back to main" step ran (good — `if: always()` worked) but committed nothing (bad). Two failure mechanisms are possible, both probably contributing:

### Mechanism A: `.ndjson.tmp` files aren't ever renamed mid-poet
`fetch_ganjoor.py` opens `<poet>.ndjson.tmp`, writes all the poet's poems, then `tmp_path.replace(out_path)`. If the runner is killed mid-poet, the temp file is left as-is and `git add data/` doesn't pick it up because we add by directory — but `*.tmp` would be picked up. **However**, GitHub's job cancellation typically kills the entire runner VM, not just the Python process, so the in-flight write may not even be flushed to disk before the disk is gone.

### Mechanism B: cancellation evaporates the workspace before `if: always()` steps run
Looking at the step durations from run #2:
- Walk step: 5h 49m, then ❌
- Build manifest: skipped (no `if: always()`) ✅ expected
- Commit: 0s, ✅ — **0s strongly suggests the workspace was already gone, no files to add, `git diff --staged --quiet` was true, exited cleanly with "No changes to commit"**
- All later steps: skipped, expected

The `0s` is the smoking gun. A real commit with even one file would take 1–2 seconds for `git add` + `git diff` + `git commit` + `git push`. A 0-second success means **`git status` saw a clean tree at the moment the step ran.**

### What this implies for the fix
Whatever the precise mechanism, the lesson is: **we cannot rely on a single 6-hour job to fetch the full corpus and commit at the end.** The data must persist incrementally so that a runner kill cannot erase progress.

---

## Recommended fix for Phase 1

Three layered changes, do them in order:

### Fix A — make `fetch_ganjoor.py` commit progress after every N poets
Change the script so that after each completed poet (or every 5 poets), it does a `git add` / `git commit` / `git push` of whatever it has so far. This way the runner getting killed at minute 348 still preserves the previous ~135 poets' files because they're already in the remote.

This requires the script to know about git, which is a layering violation, but for Phase 1 the simplest fix is honest. Alternative: have the workflow run the python script with `& tail -F` and the workflow itself runs a parallel `while true; do sleep 600; git add -A && git commit -m "...checkpoint..." && git push; done`. Uglier but keeps git logic out of the Python.

**I'd go with a third option: matrix strategy by poet bucket.** Split the 230 poets into ~5 parallel jobs of ~46 poets each. Each job runs ≤2 hours and commits at the end. They commit to a shared branch (`snapshot-buckets`) and a final aggregator job merges to `main`. The matrix gives parallelism + smaller per-job blast radius. Concrete implementation:

```yaml
strategy:
  fail-fast: false
  matrix:
    bucket: [0, 1, 2, 3, 4]   # 5 buckets of ~46 poets each
```

And in `fetch_ganjoor.py` add `--bucket N --num-buckets M` flags that select poets by `poet_id % M == N` (or by sorted-index modulo, more even). Each job commits its bucket's files to a unique branch like `snapshot-bucket-${N}`, then a final job (`needs: [bucket]`) merges all bucket branches into a single PR or directly into `main`.

### Fix B — checkpoint within long poets
For the 4–5 biggest poets (Rumi, Ferdowsi, Hafez, Saadi, Nezami), even one poet exceeds the bucket budget. Change `fetch_ganjoor.py` to write each poem to the `.ndjson` directly (append mode) as it's fetched, rather than buffering the whole poet in a `.tmp` and only renaming at the end. Then a mid-poet kill at least preserves all completed poems.

The trade-off: appending means we can't trivially detect a partially-completed poet on the next run. Two options:

1. Use a **sidecar `.ndjson.progress`** file with a JSON record like `{"last_poem_id": 12345, "completed": false}` updated atomically after each write. On startup, if `<poet>.ndjson.progress` exists and `completed: false`, read it and skip poem ids ≤ `last_poem_id`.
2. Or, simpler: rely on poem id ordering and at startup tail the existing `.ndjson` to find the highest poem id already written, then resume from the next one in the BFS walk.

Option 2 is fewer files and matches the "data is the canonical form" principle. Option 1 is more robust to BFS order changes. **I lean option 1.**

### Fix C — add `if: always()` to all the post-walk steps
Currently only the commit step has it. Manifest, bundle, and release should also have it, so that even on cancel we get an annotated release with whatever data made it. Acceptable to have a `partial: true` flag in `MANIFEST.json` when run on a canceled walk.

```yaml
- name: Build manifest + checksums
  if: always()
  run: python scripts/build_manifest.py --root data --legacy legacy

- name: Bundle release artifacts
  if: always() && inputs.create_release
  run: |
    mkdir -p release
    tar --use-compress-program="zstd -19" -cf release/ganjoor-data.tar.zst data
    ...

- name: Publish Release
  if: always() && inputs.create_release
  uses: softprops/action-gh-release@v2
```

---

## Concrete proposed plan for Claude Code

Phase 1 closeout sequence:

1. **Read this document, the existing workflow at `.github/workflows/emergency-snapshot.yml`, and `scripts/fetch_ganjoor.py` carefully** before changing anything.
2. **Implement Fix B first** (append-mode + resumable-mid-poet). Lowest risk, highest leverage. Unit-test locally with a small `--poet-limit 1` against a known-big poet (Rumi has poet_id 5, Ferdowsi has poet_id 3).
3. **Implement Fix C** (`if: always()` on all post-walk steps). Pure YAML edit.
4. **Implement Fix A as the matrix strategy** (Fix-A-third-option above). This is the bigger change. Add a separate workflow file `emergency-snapshot-matrix.yml` rather than replacing the existing one — easier to fall back.
5. **Run a small matrix test** (`poet_limit: 3` per bucket, 2 buckets) to validate the merge logic works.
6. **Run the real matrix snapshot** with all buckets, `create_release: true`.
7. **Confirm `data/` lands on `main`** with ~230 NDJSON files, `legacy/` has the SQLite mirrors, a tagged release exists with `.tar.zst` artifacts, and `MANIFEST.json` reports the correct counts.

Once Phase 1 closes (full corpus committed and released), Phase 2 is:

8. Mirror the release to **Zenodo** via REST API → mint a DOI. Update `CITATION.cff`.
9. Upload to **Internet Archive** Items via `ia upload`.
10. Trigger **Software Heritage** harvest (auto via GitHub but also `archive.softwareheritage.org/save/`).
11. Send the **Hamid email** (Persian + English bilingual template in the preservation playbook — ask the user for it).
12. Send the **institutional outreach** emails (UMD Roshan / Matt Miller first).

But none of that is your job today. Today is just: **fix Phase 1 so the snapshot actually lands.**

---

## Things to know about working in this repo

- **Solo dev, public repo, no other contributors.** PRs are not required, direct commits to `main` are fine, but at least include a meaningful commit message.
- **GitHub Actions for public repos is free-tier unlimited minutes.** Spend them generously.
- **Free-tier runner specs:** Ubuntu 24.04, 4 vCPU, 16 GB RAM, 14 GB SSD free space, 6-hour wall clock per job. Brew/apt/pip work normally.
- **The runner has full network egress.** No tunneling needed for `api.ganjoor.net` or `archive.org`. The Iran-located parts of ganjoor (audio at `i.ganjoor.net`, blog, dg) may be unreachable depending on the day of the Iranian shutdown.
- **`api.ganjoor.net` itself is reachable** from GitHub runners (confirmed by run #2's 5h 49m of successful walks). The throttle of 5 req/sec yielded zero 429s in our logs.
- **Schema is intentionally a faithful pass-through** of api.ganjoor.net's poem object plus a `_meta` envelope. Do not "normalize" the data layer in Phase 1 — fidelity to upstream is the whole point. Persian text normalization happens later, at a separate enriched data layer.
- **The PWA already has a Persian text normalizer** (`toDisplay` and `toSearch` JS functions in `index.html`). That's the reference for any future normalization layer.

## Things NOT to do

- **Don't touch `index.html`**. That's the PWA. Phase 1 is data-only.
- **Don't change the schema** of the poem envelope in `fetch_ganjoor.py` beyond the bug fixes. Downstream tools may already be parsing this.
- **Don't add new dependencies** to `scripts/requirements.txt` unless required by the fix. We want the install step to stay fast.
- **Don't rehost audio** under any circumstance. The audio rights model is unresolved and is a Phase 3 problem. Only mirror the audio *index* (URL + sync XML pointer + checksum) if you touch audio at all in Phase 1, which you probably shouldn't.
- **Don't change the licensing** files (`LICENSE`, `LICENSE-DATA`) without explicit user confirmation.
- **Don't push to `main` while a workflow is running on `main`.** That's how we lost run #2's data (probably) — concurrent commits caused git-side weirdness on the runner's checkout. Use branches for any concurrent work.

## User context

The human you're handing off to has been doing this from a phone for most of the project but has now switched to a Mac. They're a developer (comfortable with git, terminal, Python). They are not an expert in Persian poetry or digital-humanities preservation; the strategic framing came from research. They care a lot about cultural preservation and the project has clear emotional weight for them — be respectful of that when surfacing trade-offs.

They specifically asked for this handoff because debugging via screenshots through the web Claude interface had become slow. The Mac has Claude Code installed (or about to be). Work directly in the repo from there.

---

## Quick-start commands for Claude Code

```bash
cd ~/wherever/ganjoor   # the local clone

# Check repo state
git pull
git log --oneline -10
ls data/ 2>/dev/null || echo "no data/ yet (expected)"
ls legacy/ 2>/dev/null || echo "no legacy/ yet (expected)"

# Activate local venv (uses the setup_venv.sh that handles macOS RTI DYLD)
source .venv/bin/activate 2>/dev/null || bash scripts/setup_venv.sh && source .venv/bin/activate

# Local smoke test of fetch (one poet, fast)
python scripts/fetch_ganjoor.py --out data --poet-limit 1 --rate 3.0 \
    --user-agent "ganjoor-mirror-dev/0.1"

# Inspect what landed
ls -la data/
head -1 data/*.ndjson | python -m json.tool | head -50
```

The `setup_venv.sh` script in `scripts/` documents a Mac-specific RTI Connext DDS / DYLD interaction that breaks naïve `python3 -m venv` on this developer's machine. Worth reading if you hit `ssl` import errors locally.

---

## Open questions for the user (not for you to resolve, just to flag)

- **`api.ganjoor.net` rate limit headroom.** We've only tested 5 req/sec. The API has no documented limit. A polite stretch goal would be testing 10 req/sec briefly to see if it cuts full-corpus time without 429s. If it does, full corpus fits in a single non-matrix job at ~5h.
- **Mid-snapshot upstream changes.** If Hamid is editing ganjoor during our walk, different buckets might see slightly different states. For Phase 1 this is acceptable — the `_meta.fetched_at` timestamp per poem is the audit trail. For Phase 2+, the weekly resync handles drift.
- **Should we attempt audio at all in Phase 1?** Strong recommendation: no. Audio is ~80–200 GB, doesn't fit on free runners' disk, has rights complications, and is its own dedicated Phase. Phase 1 = text only.

---

**End of handoff. Good luck. The corpus is worth this.**
