# For AI agents

Before doing anything on this project, read PHASE-1-HANDOFF.md.

- PHASE-1-HANDOFF.md — original state at handoff, fix plan, Phase 2 playbook
- RESEARCH-ARCHIVE.md — strategic blueprints (architecture + preservation)
- PHASE-1-DEBUG-LOG.md — forensics from the two failed snapshot runs
- PRESERVATION-ADDENDUM-free-path.md — the $0 redundancy plan

Phase 1 persistence is fixed and the data layout is per-poem-file. See:
- scripts/fetch_ganjoor.py — writes one JSON per poem at data/<poet>/<cat>/<...>/<N>.json
- scripts/build_manifest.py — counts per-poem files and per-poet completion
- scripts/migrate_ndjson_to_perpoem.py — one-shot helper that explodes any
  legacy data/<slug>.ndjson into the new layout (idempotent)
- .github/workflows/emergency-snapshot.yml — single-job, used for smoke tests
- .github/workflows/emergency-snapshot-matrix.yml — N-bucket parallel job, used for full corpus

Smoke test locally before triggering a full run:
  source .venv/bin/activate
  python scripts/fetch_ganjoor.py --out /tmp/smoke --poet-ids 229 --rate 5.0
  # 229 is آیتی بیرجندی, 12 poems — finishes in ~3s.
  # Verify: ls /tmp/smoke/ayatib/gozide/*.json should show 1.json..12.json.
