# Phase 1 Debug Log — what actually happened in the snapshot runs

This document preserves the operational details from the two real-world attempts at Phase 1 in the original chat session. It supplements `PROJECT-HANDOFF.md` Part 3 (the bug analysis) with the raw observations that informed the diagnosis. Future agents debugging the snapshot workflow should read this before re-attempting.

## Session timeline

The original chat session covered several phases on May 18, 2026:

1. Initial product discovery: phone-first development model, Persian poetry corpus selection
2. Two deep-research artifacts: the architectural blueprint and the civilizational preservation playbook (preserved in `RESEARCH-ARCHIVE.md`)
3. PWA construction and deployment to GitHub Pages
4. Repository scaffolding: README, licenses, citation file, manifest, icons
5. **Phase 1 implementation:** workflow + scripts written, two runs attempted
6. Phase 1 failure diagnosis (this document)
7. Handoff to Claude Code on the user's Mac

Up to the Phase 1 runs, everything went smoothly. The PWA was installed on the user's home screen, the repo had clean licensing, icons, and a bilingual README. The two failed snapshot runs are the only debugging artifact worth preserving in detail.

## Run #1 — smoke test, manually canceled

**Inputs:** `poet_limit: 5`, `mirror_legacy: true`, `save_wayback: true` (IA secrets were NOT yet added), `create_release: false`.

**Result:** canceled by user after ~32 minutes, during the API walk step.

**Workflow state at that point:** the workflow file did NOT yet have `if: always()` on the commit step.

**Throughput observed:** 3,725 poems written in ~32 minutes at the original `--rate 3.0` setting. The first 5 poets by ID are the canonical big classical poets (Hafez, Saadi, Rumi, Ferdowsi, Khayyam), each with hundreds to thousands of poems. The user's prior estimate of "~50 poems per poet" was wrong; the real average is much higher because the corpus is heavily front-loaded with the biggest poets.

**Why the user canceled:** they assumed the long runtime meant the script was stuck. It wasn't — it was working correctly, just on much larger poets than estimated. The 32-minute log showed continuous progress: lines like `- 25 poems written`, `- 50 poems written`, ... up through `- 3700 poems written`.

**What was lost:** all 3,725 poems. The runner VM was destroyed on cancel and the commit step (without `if: always()`) was skipped.

**Lesson:** the user should have been told to set `poet_limit: 1` for the very first smoke test, not 5. With 5 it spans the largest poets in the corpus, taking ~30 min instead of ~3 min.

## Run #2 — full corpus attempt, hit timeout

**Workflow patches between runs:**
- Bumped `--rate 3.0` → `--rate 5.0` in the workflow (sed-applied locally and pushed)
- Added `if: always()` to the "Commit data back to main" step
- Both changes pushed in commit `98072b6` ("fix(snapshot): bump rate to 5 req/sec and commit on cancel")

**Inputs for run #2:** `poet_limit: 0` (all poets), `mirror_legacy: true`, `save_wayback: false` (still no IA secrets), `create_release: true`.

**Step-by-step result, as observed in the run summary:**

| # | Step | Result | Duration |
|---|---|---|---|
| 1 | Set up job | ✅ | 1s |
| 2 | Checkout | ✅ | 1s |
| 3 | Set up Python | ✅ | 2s |
| 4 | Install Python dependencies | ✅ | 4s |
| 5 | Mirror legacy dumps (SourceForge + ganjoor-db) | ✅ | 1m 48s |
| 6 | Walk api.ganjoor.net into NDJSON | ❌ canceled | **5h 49m 4s** |
| 7 | Build manifest + checksums | ⊘ skipped | — |
| 8 | Trigger Internet Archive Save Page Now | ⊘ skipped (was off anyway) | — |
| 9 | **Commit data back to main** | ✅ **0s** ← the smoking gun | 0s |
| 10 | Bundle release artifacts | ⊘ skipped | — |
| 11 | Publish Release | ⊘ skipped | — |
| 12 | Post Checkout | ✅ | 1s |
| 13 | Complete job | ✅ | 0s |

Total run time: 5h 51m 3s. Canceled by GitHub's `timeout-minutes: 350` setting.

**Walk step details captured from the live log:**

Early in the walk (around log line 18):
```
Fetching poet index...
Found 230 poets.
[1/230] حافظ (poet id=2): fetching
  - 25 poems written
  - 50 poems written
  ...
```

Mid-walk (around log line 3467, approximately 4h elapsed):
```
done: 54 poems -> data/سلطان_باهو.ndjson
[105/230] ابن_یمین (poet id=106): fetching
  - 25 poems written
  - 50 poems written
  ...
```

Late in the walk (around log line 4274, just before cancel):
```
done: 64 poems -> data/عمعق_بخاری.ndjson
[136/230] جهان_ملک_خاتون (poet id=137): fetching
  - 25 poems written
  - 50 poems written
  ...
  - 425 poems written
Error: The operation was canceled.
```

The walk reached **poet 136 of 230** (~59% complete) when the 350-minute hard cap killed the runner. The last poet (Jahan Malek Khatun, poet_id 137) was actively being fetched, with 425 poems already written to its `.ndjson.tmp` file.

**Throughput observed in run #2:** the run wrote into log line ~4274 over 5h 49m. Each `- N poems written` line represents 25 poems (the `% 25 == 0` print interval). So roughly (4274 - 18) ÷ 25 ≈ ~170 batches × 25 = ~4,250 written... but that doesn't match a single counter because the counter resets per poet. The actual cumulative count is harder to derive from the log alone, but extrapolation suggests ~20,000-25,000 poems were fetched before the cancel — none of which made it to the repo.

**The crucial observation: the "Commit data back to main" step shows green ✅ with 0s duration.**

This is the smoking gun for the bug. A real `git add` + `git diff --staged` + `git commit` + `git push` on a populated workspace takes 1-3 seconds minimum even with nothing to commit (the commands themselves execute non-trivially). A 0-second success means **the step ran on a workspace that already had no detectable changes** — `git diff --staged --quiet` exited with status 0, the `else` branch was never entered, and the step exited cleanly with "No changes to commit" or equivalent.

## Diagnostic hypotheses

Three failure mechanisms are possible, in descending probability:

### Hypothesis A: cancellation evaporates the workspace before `if: always()` steps see anything

GitHub Actions cancellation is designed to be quick. When `timeout-minutes` fires, the runner is sent SIGTERM and then SIGKILL shortly after. The `if: always()` next step starts in what is effectively a fresh runner context — depending on exactly how the cancellation is implemented, the prior step's filesystem state may or may not be preserved.

Evidence supporting this: the 0-second commit step duration. If the workspace had even one new file, `git add` alone would take measurable time.

Counter-evidence: GitHub's docs claim `if: always()` steps run "on the same runner", which should mean the filesystem is preserved. So this hypothesis would require GitHub's cleanup to be more aggressive than documented, or some quirk of how `timeout-minutes` differs from a normal cancel.

### Hypothesis B: `.ndjson.tmp` files never become `.ndjson`

Looking at `fetch_ganjoor.py` lines 167-176:

```python
tmp_path = out_path.with_suffix(".ndjson.tmp")
with tmp_path.open("w", encoding="utf-8") as f:
    for poem_id in walk_cat_for_poem_ids(...):
        ...
        f.write(...)
tmp_path.replace(out_path)   # only renames at the END of the poet
```

The script writes each poet's poems to `<poet>.ndjson.tmp` and only renames to `<poet>.ndjson` when the poet completes. The 135 fully-completed poets *should* have been renamed. But — and this is the question — were they renamed before the SIGKILL?

Each `tmp_path.replace(out_path)` is a single atomic rename system call. It would have to happen at the moment a poet completes. If the kill happened mid-rename (extremely unlikely but possible on a busy disk), one poet's file could be in an indeterminate state. But 135 poets all being in indeterminate state at once is implausible.

More likely variant of this hypothesis: the `.ndjson` files DID exist on disk, but `git add data/` didn't pick them up. Possible reasons:
- The `data/` directory was inside `.gitignore` (no — it's not)
- The `git add` was run but a non-fast-forward push silently failed under `|| true` (possible)
- The workspace was checked out from before the data was written — but that doesn't happen between steps

### Hypothesis C: concurrent commit broke the runner's git state

The user made a separate commit to `main` ("feat: rebrand to green-and-gold calligraphy icon set", commit `5036b7c`) at 13:03 local time, while the snapshot was running. That commit landed on origin/main but the runner had a checkout from before it. When the snapshot tried `git push`, the push would have been rejected with non-fast-forward.

But the runner's git logic uses `||true` for failures:
```yaml
git add data legacy MANIFEST.json CHECKSUMS.sha256 || true
if git diff --staged --quiet; then
  echo "No changes to commit."
else
  ...
  git push
fi
```

The `git push` is unguarded. If it failed with non-fast-forward, the step would have exited non-zero. But it shows green with 0s duration, which doesn't match a push failure (which would take time to attempt and error out).

Unless: the workspace was clean and `git diff --staged --quiet` was true, so the `git push` was never reached. This is the case both Hypothesis A and Hypothesis B converge on.

### Most likely combined explanation

Combining the evidence: the runner *probably* still had the workspace files at the moment the commit step ran (`if: always()` worked correctly), BUT the `data/` directory was empty or contained only `.ndjson.tmp` files that were never renamed in time. The 135 "completed" poets' `.tmp → .ndjson` renames may not have all flushed before the kill. So `git status` saw a clean tree (the `.tmp` files might have been there but no `.ndjson` ones), `git diff --staged --quiet` was true, and the step exited cleanly in 0 seconds.

This is consistent with the 0s duration, the green checkmark, and the absence of data on `main`.

## Implications for the fix

The fix sequence in `PROJECT-HANDOFF.md` Part 3.5 follows from this diagnosis:

1. **Fix B first** (append-mode + per-poem progress): write each poem to `<poet>.ndjson` directly as it's fetched, with a `.progress` sidecar. This way, files exist on disk before the next batch is fetched, not just at the end of a poet. Mid-poet kills preserve everything written so far.

2. **Fix C second** (`if: always()` on all post-walk steps + smart push retry): even if the walk dies, manifest, bundle, and release should run on whatever data exists. The smart push retry handles the concurrent-commit case (Hypothesis C) explicitly with `git pull --rebase` on failure.

3. **Fix A third** (matrix workflow): split the 230 poets into 5 parallel jobs of ~46 poets each, ~2 hours per job, well under the 6-hour cap. Each job commits to its own branch; an aggregator merges to `main`. Avoids the timeout problem entirely.

## A small process lesson

The user did not commit to `main` deliberately to break the run; they made the rebrand commit hours earlier and it was just on the timeline. But concurrent commits during long-running workflows are a real risk in solo-developer projects. Phase 2's weekly resync workflow should explicitly use a `concurrency: snapshot` group on the workflow (already done) AND a branch protection rule on `main` that requires PRs from workflow-bot commits.

## Where to find the actual runs

In the user's repo at the time of handoff, the two runs are visible at:
- `https://github.com/sajad2025/ganjoor/actions/workflows/emergency-snapshot.yml`
- Run #1: workflow run #1, manually canceled
- Run #2: workflow run #2, timed out, no data committed

The run pages preserve the full step-by-step logs. The next agent should review these directly rather than trusting only this summary, since GitHub's run-detail pages contain the millisecond-resolution timing that proves or disproves the hypotheses above.

## Recovery action

When the next agent picks this up:

1. Check `git log --oneline -20` on `main` — if there's any commit by `ganjoor-mirror-bot` with `data/` files in it, this analysis is partially wrong and the data may have actually landed somewhere.
2. Check `https://github.com/sajad2025/ganjoor/branches` for any stray branch that might contain the data.
3. Check `https://github.com/sajad2025/ganjoor/actions` runs storage / artifacts tab — there *might* be a workflow artifact from the failed run, though this workflow doesn't use `actions/upload-artifact` so probably not.
4. If none of the above turn up data, accept that run #2's ~5.5 hours of fetching are lost. The script and API both work; only the persistence layer failed. Implement Fix B + C + A as designed and try again.

The good news: the API is reachable, the throttle is correct, the legacy mirror step worked perfectly (took 1m 48s), and the script's BFS walk through the category tree correctly enumerated 136 poets. Only the data persistence layer needs hardening.

---

*End of debug log.*
