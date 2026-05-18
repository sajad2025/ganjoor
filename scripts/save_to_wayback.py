#!/usr/bin/env python3
"""
save_to_wayback.py

Submit URLs to the Internet Archive Wayback Machine via the "Save Page Now 2"
(SPN2) API, so they are independently archived even if api.ganjoor.net or
ganjoor.net itself goes offline.

Reads one URL per line from --urls (default: scripts/wayback_urls.txt).

Authentication: if IA_S3_ACCESS_KEY and IA_S3_SECRET_KEY env vars are present
(grab them from https://archive.org/account/s3.php and add as repo secrets),
the API runs as an authenticated user with a 15-URL-per-minute quota.
Without credentials the script falls back to unauthenticated submissions,
which are heavily rate-limited and may be rejected during high IA load.

Note: this script does not wait for the captures to complete. SPN2 returns
a job_id; the archive happens asynchronously on IA's side, usually within
a few minutes. We log the job_ids for later verification.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import requests

SPN2_ENDPOINT = "https://web.archive.org/save"


def submit(url: str, session: requests.Session, auth_header: str | None) -> dict:
    headers = {"Accept": "application/json"}
    if auth_header:
        headers["Authorization"] = auth_header
    data = {
        "url": url,
        # Save outlinks too? Off by default — it's per-domain expensive and
        # would inflate IA's queue. We submit specific URLs deliberately.
        "capture_outlinks": "0",
        "capture_screenshot": "0",
        "skip_first_archive": "0",
        # Capture even if the URL was archived recently. Override if you want
        # less duplication.
        "if_not_archived_within": "30d",
    }
    resp = session.post(SPN2_ENDPOINT, headers=headers, data=data, timeout=30)
    try:
        body = resp.json()
    except ValueError:
        body = {"raw": resp.text}
    body["_status"] = resp.status_code
    return body


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--urls",
        type=Path,
        default=Path("scripts/wayback_urls.txt"),
        help="file with one URL per line",
    )
    ap.add_argument(
        "--rate-seconds",
        type=float,
        default=4.5,
        help="sleep between submissions (sec). 4.5s ≈ 13/min, under the 15/min cap.",
    )
    args = ap.parse_args()

    if not args.urls.exists():
        print(f"No URL file at {args.urls}; nothing to do.", flush=True)
        return 0

    access = os.environ.get("IA_S3_ACCESS_KEY")
    secret = os.environ.get("IA_S3_SECRET_KEY")
    auth_header = f"LOW {access}:{secret}" if access and secret else None
    if not auth_header:
        print(
            "  WARNING: no IA_S3_ACCESS_KEY/SECRET in env. Submissions will be "
            "unauthenticated and may be rate-limited or rejected.",
            flush=True,
        )

    urls = [
        line.strip()
        for line in args.urls.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    print(f"Submitting {len(urls)} URLs to the Wayback Machine.", flush=True)

    session = requests.Session()
    session.headers["User-Agent"] = (
        "ganjoor-mirror/0.1 (+https://github.com/sajad2025/ganjoor)"
    )

    successes = 0
    failures = 0
    job_log = []
    for i, url in enumerate(urls, 1):
        try:
            result = submit(url, session, auth_header)
            job_id = result.get("job_id")
            status = result.get("_status")
            if job_id:
                successes += 1
                job_log.append(f"{url}\t{job_id}\t{status}")
                print(f"  [{i}/{len(urls)}] OK {status} job={job_id} {url}", flush=True)
            else:
                failures += 1
                print(
                    f"  [{i}/{len(urls)}] FAIL {status} {url} -> {result}",
                    flush=True,
                )
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"  [{i}/{len(urls)}] EXC {url}: {e}", flush=True)

        time.sleep(args.rate_seconds)

    # Persist a log of submitted job ids for later verification.
    log_path = Path("legacy/wayback-jobs.tsv")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        for line in job_log:
            f.write(line + "\n")

    print(f"\nDone. {successes} submitted, {failures} failed.", flush=True)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
