# Scripts — Emergency Preservation Snapshot

This directory holds everything the **Emergency Snapshot** GitHub Actions need to mirror ganjoor.net into this repository.

The whole thing is designed to run on free GitHub-hosted Ubuntu runners, triggered from your phone via the **Actions** tab. Nothing here requires a laptop.

## Two workflows

| Workflow | When to use |
|---|---|
| **Emergency Snapshot** ([emergency-snapshot.yml](../.github/workflows/emergency-snapshot.yml)) | Smoke tests, small slices via `poet_limit`. Single job, ≤6h budget. |
| **Emergency Snapshot (Matrix)** ([emergency-snapshot-matrix.yml](../.github/workflows/emergency-snapshot-matrix.yml)) | Full-corpus runs. N parallel buckets (default 5), each ~2h. |

Both share `fetch_ganjoor.py` and both are crash-safe: writes append after every poem and flush, a `.progress.json` sidecar marks per-poet completion, and a runner kill at any moment loses at most the in-flight poem. The matrix workflow additionally checkpoints to `main` every 10 minutes (configurable).

## What gets produced

| Path | Contents |
|---|---|
| `data/<poet-slug>.ndjson` | One full-detail poem per line for that poet. |
| `data/<poet-slug>.progress.json` | Per-poet completion marker (`completed: true/false`, counts, timestamps). Used for resume. |
| `legacy/sourceforge/` | Mirrored SQLite dumps (2012, 2014) from SourceForge. |
| `legacy/desktop/` | Latest SQLite shipped with the `ganjoor/desktop` Windows app. |
| `legacy/ganjoor-db/ganjoor-db.bundle` | Full git bundle of the archived MySQL-dump repo. |
| `legacy/wayback-jobs.tsv` | Job ids returned by IA's Save Page Now (for later verification). |
| `MANIFEST.json` | Counts, provenance, timestamps, repo metadata (produced by the finalize step). |
| `CHECKSUMS.sha256` | SHA-256 of every file in `data/` and `legacy/`. |

## First run from your phone

**Smoke test first.** Open the repo in the GitHub mobile app → **Actions** tab → **Emergency Snapshot** → **Run workflow** with:
- `poet_limit`: **1**  (one small poet — finishes in seconds)
- `mirror_legacy`: **false** (skip for the smoke test; it takes ~2 minutes)
- `save_wayback`: **false** (skip until you have IA keys — see below)
- `create_release`: **false**

Verify the commit lands on `main` with one `.ndjson` and one `.progress.json` under `data/`.

**Then the real run.** Switch to **Emergency Snapshot (Matrix)** → **Run workflow** with:
- `num_buckets`: **5** (default)
- `mirror_legacy`: **true**
- `save_wayback`: **true** (or false if no IA keys yet)
- `create_release`: **true**
- `checkpoint_seconds`: **600** (default)

This launches 5 parallel jobs of ~46 poets each. Watch the live logs — each bucket commits its data to `main` every 10 minutes and on completion. A final `finalize` job builds `MANIFEST.json` + `CHECKSUMS.sha256`, then tags and publishes the release.

## fetch_ganjoor.py flags

```
--out PATH                output directory (required)
--rate FLOAT              max req/sec to api.ganjoor.net (default 3.0; workflows use 5.0)
--user-agent STR          custom UA string
--poet-limit N            stop after N poets (0 = all)
--bucket N                0-indexed bucket id, used with --num-buckets
--num-buckets M           split poets into M buckets; only this --bucket runs
--poet-ids "1,2,3"        explicit poet ids to fetch (overrides bucket selection)
```

The script is **resumable at two layers**: completed poets (via `.progress.json`) are skipped; partially-completed poets (no/false progress marker) read their NDJSON to learn which poems are already on disk and resume from there.

## Adding the Internet Archive credentials

Save Page Now works without auth but is heavily rate-limited under load. To get the full 15-URL-per-minute quota:

1. Make a free archive.org account.
2. Visit <https://archive.org/account/s3.php>. Copy the access key and secret.
3. In this repo: **Settings → Secrets and variables → Actions → New repository secret**.
4. Add two secrets:
   - `IA_S3_ACCESS_KEY` = the access key
   - `IA_S3_SECRET_KEY` = the secret
5. Re-run the workflow with `save_wayback: true`.

## Local development (optional)

You don't need this for normal operation — the GitHub Action is the supported path. But if you want to run the scripts on your Mac for debugging, use a virtual environment so packages don't pollute your system Python.

### One-time setup

From the repo root:

```bash
./scripts/setup_venv.sh
```

The script picks a Python with a working `ssl` module (Homebrew's `python3.12` on macOS, `python3.12` on Linux), builds `.venv/` from it, and installs `scripts/requirements.txt`. See the comments at the top of `scripts/setup_venv.sh` for the gory details of why plain `python3 -m venv .venv` can produce a venv whose pip can't reach PyPI.

### Every subsequent shell

```bash
cd /path/to/ganjoor
source .venv/bin/activate
```

You'll see `(.venv)` prefix in your prompt when it's active. To leave: `deactivate`.

Then a quick smoke test (fetches one tiny obscure poet, ~3 seconds):

```bash
python scripts/fetch_ganjoor.py --out /tmp/smoke --poet-ids 229 --rate 5.0 \
  --user-agent "ganjoor-mirror-dev/0.1"
# 229 = آیتی بیرجندی, 12 poems. The first poets by id are Hafez/Saadi/Rumi —
# huge. Use --poet-ids with a tail poet for fast smoke tests.

# Verify append-mode + sidecar:
ls -la /tmp/smoke/
cat /tmp/smoke/*.progress.json
wc -l /tmp/smoke/*.ndjson   # should equal completed_count in the progress file

# Verify resume: kill mid-fetch, re-run, confirm completion with zero duplicates.
```

The `.venv/` directory is git-ignored (already covered by the Node `.gitignore` template you chose at repo creation — Python `__pycache__` and friends too).

## What runs but is intentionally deferred to v0.2

- **Per-poem comments.** Each poem has its own comments endpoint; comments multiply request count by ~10–100× and have unresolved per-comment copyright. They will land in a separate `fetch_comments.py` with a much slower rate limit.
- **Audio bytes.** Audio MP3s live on `i.ganjoor.net` and aren't suitable for free-tier runners (200 GB > 7 GB disk). Plan: register a free Oracle Cloud Always Free VM as a self-hosted runner for the bulk audio job. Index only (URL + sync XML pointer + SHA-256) lands in `data/` from this v0.1 run.
- **WARC of ganjoor.net itself.** Captured via Internet Archive Save Page Now for now; a `browsertrix-crawler` job in v0.2 produces self-hosted WARC.

## Why this design

- **Phone-triggerable** — `workflow_dispatch` with simple inputs.
- **Resumable** — poets already mirrored are skipped on re-run.
- **Polite** — 3 req/sec by default, exponential backoff on errors, custom User-Agent that links back to this repo.
- **Auditable** — every snapshot ends with `MANIFEST.json` + `CHECKSUMS.sha256`. The Action commit message includes a UTC timestamp.
- **Independent** — three legacy mirrors plus IA Save Page Now mean we have a copy of the corpus even if `api.ganjoor.net` is unreachable during a run.
