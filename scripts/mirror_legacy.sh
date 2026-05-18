#!/usr/bin/env bash
# mirror_legacy.sh
#
# Mirrors known third-party preservation copies of the ganjoor corpus that
# already exist outside ganjoor.net itself. These give us a baseline copy
# *even if api.ganjoor.net is unreachable* during a snapshot run.
#
# Items mirrored:
#   1. SourceForge SQLite dumps  (ganjoor-s3db-910612.zip, 930711.zip)
#   2. ganjoor/desktop latest release (contains current ganjoor.s3db)
#   3. ganjoor/ganjoor-db archived repo (full mirror clone + git bundle)
#
# Output lives in ./legacy/ and is committed to the repo.

set -euo pipefail

LEGACY_DIR="legacy"
mkdir -p "${LEGACY_DIR}"

ua="ganjoor-mirror/0.1 (+https://github.com/sajad2025/ganjoor)"

# --- 1. SourceForge dumps ---------------------------------------------------
mkdir -p "${LEGACY_DIR}/sourceforge"
for fname in ganjoor-s3db-910612.zip ganjoor-s3db-930711.zip; do
  dest="${LEGACY_DIR}/sourceforge/${fname}"
  if [[ -f "${dest}" && -s "${dest}" ]]; then
    echo "  - ${fname}: already mirrored"
    continue
  fi
  url="https://sourceforge.net/projects/ganjoor/files/s3db/${fname}/download"
  echo "  - fetching ${fname}"
  if ! curl -fSL --user-agent "${ua}" --retry 3 --retry-delay 5 -o "${dest}.tmp" "${url}"; then
    echo "    ! could not fetch ${fname}, leaving previous copy (if any) in place"
    rm -f "${dest}.tmp"
    continue
  fi
  mv "${dest}.tmp" "${dest}"
done

# --- 2. ganjoor/desktop latest release --------------------------------------
mkdir -p "${LEGACY_DIR}/desktop"
if command -v gh >/dev/null 2>&1; then
  echo "  - fetching ganjoor/desktop latest release via gh"
  # --pattern keeps the SQLite (s3db) and any .zip release artifact; skip large MSIs.
  gh release download --repo ganjoor/desktop --dir "${LEGACY_DIR}/desktop" \
      --pattern '*.s3db' --pattern '*.zip' --pattern '*.tar.gz' \
      --skip-existing || echo "    ! gh release download failed; continuing"
else
  echo "  - gh not available; skipping ganjoor/desktop release mirror"
fi

# --- 3. ganjoor/ganjoor-db (archived MySQL dump repo) -----------------------
mkdir -p "${LEGACY_DIR}/ganjoor-db"
if [[ ! -d "${LEGACY_DIR}/ganjoor-db/.git" && ! -f "${LEGACY_DIR}/ganjoor-db/ganjoor-db.bundle" ]]; then
  echo "  - cloning ganjoor/ganjoor-db (full mirror)"
  if git clone --mirror https://github.com/ganjoor/ganjoor-db.git \
       "${LEGACY_DIR}/ganjoor-db/ganjoor-db.git"; then
    (
      cd "${LEGACY_DIR}/ganjoor-db/ganjoor-db.git"
      git bundle create ../ganjoor-db.bundle --all
    )
    # Keep the bundle, drop the bare repo to save space.
    rm -rf "${LEGACY_DIR}/ganjoor-db/ganjoor-db.git"
  else
    echo "    ! clone failed; continuing"
  fi
else
  echo "  - ganjoor-db already mirrored"
fi

echo "Legacy mirror complete."
ls -la "${LEGACY_DIR}"/* 2>/dev/null || true
