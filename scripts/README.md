# Scripts — Emergency Preservation Snapshot

This directory holds everything the **Emergency Snapshot** GitHub Action needs to mirror ganjoor.net into this repository.

The whole thing is designed to run on a free GitHub-hosted Ubuntu runner, triggered from your phone via the **Actions** tab. Nothing here requires a laptop.

## What gets produced

| Path | Contents |
|---|---|
| `data/<poet-slug>.ndjson` | One full-detail poem per line for that poet. |
| `legacy/sourceforge/` | Mirrored SQLite dumps (2012, 2014) from SourceForge. |
| `legacy/desktop/` | Latest SQLite shipped with the `ganjoor/desktop` Windows app. |
| `legacy/ganjoor-db/ganjoor-db.bundle` | Full git bundle of the archived MySQL-dump repo. |
| `legacy/wayback-jobs.tsv` | Job ids returned by IA's Save Page Now (for later verification). |
| `MANIFEST.json` | Counts, provenance, timestamps, repo metadata. |
| `CHECKSUMS.sha256` | SHA-256 of every file in `data/` and `legacy/`. |

## First run from your phone

1. Open the repo in the GitHub mobile app → **Actions** tab → **Emergency Snapshot**.
2. Tap **Run workflow**. Use these inputs for a first smoke test:
   - `poet_limit`: **5**  (will fetch the 5 lowest-ID poets only — minutes, not hours)
   - `mirror_legacy`: **true**
   - `save_wayback`: **true** *(skip for now if you haven't added the IA keys yet — see below)*
   - `create_release`: **false**
3. Tap **Run**.

Watch the live log from the Actions tab. The job commits results back to `main` on success.

Once the smoke test commits cleanly, re-run with `poet_limit: 0` (= all poets) and `create_release: true` to produce the first proper `v2026.1-emergency` Release.

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

Then a quick smoke test (fetches just one poet, ~2 minutes):

```bash
python scripts/fetch_ganjoor.py --out data --poet-limit 1 --rate 3.0 \
  --user-agent "ganjoor-mirror-dev/0.1"
python scripts/build_manifest.py
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
