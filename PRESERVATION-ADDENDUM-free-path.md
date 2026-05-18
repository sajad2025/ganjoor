# Free-Tier Preservation Addendum
### Companion to the Ganjoor Preservation Playbook — adjusted for $0 budget

This document overrides Section 9 (Costs and Grants) and adjusts Sections 3 and 5 of the main playbook. Everything else in the playbook stands as written.

**Stance:** the entire preservation strategy — text corpus, audio recitations, manuscript manifests, ongoing weekly syncs — runs on $0 in Year 1, and most of Years 2+. Grants become a "nice to have for paying maintainers later" rather than "required to preserve the corpus." Preservation itself is genuinely free at civilizational scale.

---

## 1. What stays free, forever or near-forever

### Text corpus (~80–150 MB compressed)
Free across six independent platforms, no expiration:

| Platform | Free tier | Role |
|---|---|---|
| **GitHub Releases** | Unlimited assets, 2 GB per file, unlimited bandwidth | Canonical SQLite + JSON dumps |
| **GitHub repo files** | 5 GB total per public repo | Per-poem JSON, schemas |
| **Zenodo** (CERN) | 50 GB per record + 150 GB account allowance | DOI-cited canonical release |
| **Internet Archive** | Unlimited for public-good content | Items + auto-torrent |
| **Software Heritage** | Free, auto-harvests GitHub | ISO/IEC 18670:2025 SWHID |
| **Codeberg** | Free public repos | Non-US-jurisdiction Git mirror |
| **Hugging Face Datasets** | Free up to ~1 TB public | Parquet for ML reuse |

Result: text corpus has **six free persistent identifiers** across three jurisdictions. Genuinely free forever.

### Audio recitations (~80–200 GB estimated)
Two independent free homes:

**Primary: Internet Archive Items.** Free for public-good content, no size cap, auto-generated torrent per item. The realistic v0.1 home. Slower upload than commercial storage but they've hosted petabyte-scale archives since 2001.

**Redundancy: Filecoin Plus DataCap.** Free if approved; cultural heritage projects are explicitly eligible. Precedents: Smithsonian Bell recordings, MIT OpenCourseWare, Flickr Foundation, Starling Lab/USC (22 PB). Apply via `github.com/filecoin-project/filecoin-plus-large-datasets`. Expected approval timeline: 2–6 weeks. Free storage with verifiable replication for deal duration; auto-renew via Lighthouse or Spade (both free tools).

**Tertiary: layered free IPFS pinning.** Filebase (5 GB) + Pinata (1 GB) + Storacha (5 GB) = ~11 GB combined free, enough for a curated audio "highlights" subset.

### Manuscripts and museum scans
Don't mirror pixels (rights belong to Princeton, BL, Bodleian, etc.). Instead mirror **IIIF manifests** (tens of MB of JSON-LD) inside the GitHub repo alongside the text corpus. Free forever.

### Comments and tafsir
Hundreds of MB of text. Fits in GitHub repo files. Free forever. The constraint isn't storage — it's the rights question (each commenter holds copyright). Preserve in repo as a dark archive layer; publish carefully per Section 6 of the main playbook.

### Compute for the initial bulk fetch
**Oracle Cloud Always Free Tier.** 4 ARM Ampere cores + 24 GB RAM + 200 GB block storage. Genuinely free forever (in operation since 2019, no time limit, no credit-card-after-trial gotcha). Register one VM, run a self-hosted GitHub Actions runner on it, kick off the audio mirror job from your phone via the GitHub Actions tab. Total ongoing cost: $0.

**For everything that fits within 6-hour-per-job and 7-GB-disk limits:** GitHub-hosted runners are free for public repos with no monthly minute cap. Use these for the text corpus walk, schema validation, weekly diffs, IA Save Page Now triggers, and Zenodo uploads.

---

## 2. The one place money would otherwise matter — and how to skip it

**Arweave** (the one paid line item in the original playbook) is $5–10 for the text bundle and $1,000–2,000 for full audio. **Skip it entirely for v0.1.** Note it in the README as a planned upgrade. The combination of Zenodo + IA + Software Heritage + Filecoin Plus already gives century-class redundancy across multiple independent jurisdictions; Arweave's marginal contribution is "permanence guarantee independent of any single organization," which is valuable but not required to clear the civilizational-class bar.

Revisit Arweave when (a) the project has any cash, or (b) AR price drops further and the text bundle costs $1, whichever comes first. Either way, it's a Year 2+ decision.

---

## 3. Updated cost forecast

| Time horizon | What stays $0 | What might cost money |
|---|---|---|
| **Year 1** | Everything end-to-end | Nothing |
| **Years 1–5** | Text on six platforms; audio on IA + Filecoin Plus; compute on Oracle Free + GitHub Actions | Nothing structural |
| **Years 5–10** | Same | Nothing structural, assuming IA and Zenodo survive (both have credible 25-year guarantees) |
| **Years 10–25** | Almost certainly still $0 | Optional Arweave one-time payment if you ever want true single-organization-independent permanence |
| **Years 25–100+** | Text via Software Heritage (UNESCO-backed, SWHID is permanent regardless of org survival) | Institutional housing matters more than money |

**Realistic Year 1 total cost: $0.** All-in. Including 200 GB of audio.

---

## 4. Adjusted Week 1 plan

The original Week 1 emergency snapshot from the main playbook is unchanged — every step listed there runs free. Three small adjustments to ordering:

1. **Audio goes to Internet Archive first** (free, day 1) instead of waiting on Filecoin Plus approval. Apply for Filecoin Plus DataCap in parallel as the redundancy layer; it lands ~Week 4.
2. **Skip Arweave entirely for v0.1.** Add a `TODO-PRESERVATION.md` note saying "Arweave deposit deferred to v0.2 budget permitting."
3. **For the bulk audio fetch from i.ganjoor.net** (Week 2–3, requires more than 7 GB of disk), provision an Oracle Cloud Always Free VM and register it as a self-hosted GitHub Actions runner — free for all subsequent runs. One-time setup: ~30 minutes from a phone via Oracle's web console + a single SSH command from an iOS app like Termius (free tier).

---

## 5. Grant pathways become opt-in, not required

Reframed for $0 reality:

- **Roshan Cultural Heritage Institute** — still the best aligned funder, but pursue it for **paying a part-time maintainer** in Year 2+ rather than for storage. Route through Roshan-UMD (Matt Miller) accepting the corpus first; UMD then applies for Roshan funding with the mirror as a named deliverable.
- **CLIR Recordings at Risk** — applicable if/when you want to professionally remaster legacy audio. Not needed for byte-level preservation.
- **NEH DHAG / Mellon / Sloan** — institutional partnerships, Year 2+.
- **Wikimedia Community Fund Rapid Fund** ($500–$5K) — for a Persian Wikisource integration sub-project, Year 1 if energy permits.

None of these is on the critical path for preservation. They become relevant when you want to pay yourself, hire help, or fund formal governance — all Year 2+ decisions.

---

## 6. What this changes about the strategic frame

The original playbook framed grants and institutional partnerships as the path to civilizational durability. The $0 path proves something stronger: **a single individual with a phone and a GitHub account can deliver civilizational-class preservation of the ganjoor corpus before any grant is awarded.** Institutional partnerships still matter for governance, longevity, and scholarly endorsement — but they are no longer prerequisites for the preservation guarantee itself.

The Section 6 governance structure (Preservation Committee, trigger-event protocol, fiscal sponsorship through Code for Science & Society) and Section 10 outreach templates remain exactly as written in the main playbook. They are about institutional credibility and stewardship continuity, not about budget.

---

**Bottom line:** preservation costs $0. Pursue grants when you want to pay maintainers, not to keep bytes alive.
