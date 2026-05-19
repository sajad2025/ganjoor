# Research Archive — Persian Poetry Preservation Project

This document preserves the two deep-research reports that were generated during the original chat session and that exist only as artifacts in that chat (not on the public web, not generated from any single source). They are the strategic foundation for the project. Future agents working on `sajad2025/ganjoor` should read both before making non-trivial decisions about scope, architecture, or governance.

The reports are reproduced verbatim from the original session. They are dated mid-May 2026.

---

# Report 1 — Persian Poetry Archive PWA Blueprint

*The strategic and architectural foundation. This is what defined the project as infrastructure rather than another reader app.*

## What this is

This is the technical blueprint for an open-source republication of the ganjoor.net Persian classical poetry corpus, with a reference Progressive Web App (PWA) reader. The animating insight is that the Persian-poetry software ecosystem has had twenty years of apps but zero authoritative, citable, schema-documented forks of the underlying data. **The data layer is the product. The reader is the demo.**

## The corpus: what we are working with

Ganjoor.net is the most complete digital corpus of classical Persian poetry on the web. Academic papers as of September 2025 cite **approximately 1.47 million verses (beyts) across approximately 700+ poets**, including the canonical classical figures: Hafez (~495 ghazals plus qasidas, qet'at, rubaiyat, masnavi), Saadi (Bustan, Golestan, ghazals, qasidas, qet'at), Rumi (Masnavi-ye Ma'navi ~25,000 couplets, Divan-e Shams, Fihi Ma Fihi), Ferdowsi (Shahnameh, ~50,000 couplets), Khayyam (Rubaiyat), Nezami (Khamseh), Hatef, Bahar, Iraj Mirza, and roughly seven hundred others ranging from major canonical to minor regional.

The API endpoint `api.ganjoor.net` returns a smaller curated list of 230 poets — these are the API-authoritative entries with full metadata; the public-facing browse shows ~700 because of poet aliases, sub-categories, and parent-of-collection entries that don't appear in the API list.

The poems carry rich metadata: meter (in the Persian aruz system, with extensive vocabulary like "فعلاتن فعلاتن فعلاتن فعلن (رمل مثمن مخبون محذوف)"), rhyme (with both rhyme word and rhyme letter analyses), sections/categories (divan → ghazaliat → ghazal 108), and a "similar poems" graph computed from rhyme + meter signatures.

User-contributed audio recitations (~tens of thousands of MP3s) include verse-level XML sync data for highlighting verses during playback. Museum scans link out to printed editions (Qazvini-Ghani, Khanlari for Hafez), manuscript photographs, and lithographs. Comments (حاشیه‌ها) on each poem provide tafsir, scholarly variants, and corrections.

## The maintainer reality

The site is maintained by **one person**: Hamid Reza Mohammadi (`github.com/hrmoh`, Tehran, personal site `hamireza.ir`). It has been a personal hobby for over fifteen years, with no organizational affiliation and no public revenue model. He explicitly states on `ganjoor.net/about` that "Ganjoor has been a personal hobby" and is "affiliated with no organization." All meaningful commits on `ganjoor/GanjoorService` (the ASP.NET Core backend, GPL-3.0) are by `hrmoh`.

The architecture has three failure surfaces:

1. A Windows server **outside Iran** hosts ganjoor.net, api.ganjoor.net, museum.ganjoor.net, abjad.ganjoor.net, epub.ganjoor.net, tj.ganjoor.net, ava.ganjoor.net, gaudiopanel.ganjoor.net. This stays reachable during Iranian shutdowns but cannot be administered from Iran when networks are cut.

2. A file-hosting service **inside Iran** holds all audio (`i.ganjoor.net/a/*.mp3`), museum images, ePub library, and desktop binaries. **When Iran is offline, the rest of the world cannot reach this content.**

3. `blog.ganjoor.net` and `dg.ganjoor.net` live on a Linux server **inside Iran** — globally unreachable during shutdowns.

As of mid-May 2026 Iran is in day 130+ of its longest-ever national internet shutdown, which began January 8, 2026. Ganjoor's audio and image servers (Iran-hosted) have been globally unreachable since.

## API surface

Base: `https://api.ganjoor.net` (also `https://ganjgah.ir`). Swagger UI at `/index.html`, OpenAPI JSON at `/swagger/v1/swagger.json`. All read endpoints are anonymous GET; OAuth is required only for write/moderation.

Read endpoints we care about:

| Resource | Path |
|---|---|
| Poets index | `/api/ganjoor/poets` |
| Poet by id | `/api/ganjoor/poet/{id}` |
| Poet by slug | `/api/ganjoor/poet?url={slug}` |
| Category | `/api/ganjoor/cat/{id}?poems=true` (recursive walk target) |
| Poem (full) | `/api/ganjoor/poem/{id}?verseDetails=true&catInfo=true&rhymes=true&recitations=true&images=true&songs=true&navigation=true` |
| Recitations | `/api/audio/{id}`, `/api/audio/published`, `/api/ganjoor/audio?id={poemId}` |
| Search | `/api/ganjoor/poems/search?term=...&poetId=...` |
| Random | `/api/ganjoor/poem/random` |
| Faal (Hafez divination) | `/api/ganjoor/hafez/faal` |
| Similar poems | `/api/ganjoor/poem/probablysamepoems/{id}` |

Every poem carries a `FullUrl` like `/hafez/ghazal/sh1` mirroring the ganjoor.net path structure. Preserve these as canonical surface forms.

No documented rate limit. Confirmed empirically: 5 req/sec returns zero 429s. 3 req/sec is even safer. Don't push past 5 without a brief test.

## The permalink contract — locked in

This is the single most important long-term design decision. Every poem has three first-class identifiers, all permanent, never reused, never repointed:

```
Path:           /poet/hafez/divan/ghazal/108
URN:            urn:ganjoor:hafez:divan:ghazal:108
Ganjoor ID:     2237
```

Verse sub-references use CTS-style colon extension in URNs (`urn:ganjoor:hafez:divan:ghazal:108:b2.m1`) and `#`-fragments in URLs (`/poet/hafez/divan/ghazal/108#b2`). When alternate editions get added (Qazvini-Ghani, Khanlari for Hafez), use an `@edition` suffix rather than overloading the number.

**Written stability commitment**: once minted, a `canonical_id` is never reused or repointed. Deprecated poems keep their entry with a `deprecated_at` timestamp.

This is what turns the repository from a scraper into infrastructure. Anyone citing `urn:ganjoor:hafez:divan:ghazal:108` in 2040 must be able to resolve it.

## Licensing — layered, locked in

| Layer | License | Rationale |
|---|---|---|
| App code, scripts | MIT | Maximally permissive; commercial downstream OK |
| Schemas, data dictionary | CC0-1.0 | Schemas are facts; zero friction |
| Curated text corpus | **CC-BY-4.0** | Public-domain sources + editorial compilation; matches Sefaria/Tanzil precedent; avoids CC-BY-SA which would force copyleft on downstream apps and kill the infrastructure thesis |
| Audio | Per-file metadata | Default: do not redistribute (see audio rights below) |

The choice of CC-BY (not CC-BY-SA) for the data layer is deliberate and load-bearing. CC-BY-SA infects downstream apps with copyleft obligations. The infrastructure thesis requires that a commercial app developer can build on the corpus without re-licensing their own code. CC-BY gives that freedom while preserving attribution.

Mandatory attribution string for derived works:

> Persian poetry text courtesy of گنجور — ganjoor.net (Hamid Reza Mohammadi and contributors), republished under CC-BY-4.0 via sajad2025/ganjoor.

## Data schema — frozen v1

The per-poem JSON shape:

```json
{
  "id": 2237,
  "canonical_id": "hafez/divan/ghazal/108",
  "urn": "urn:ganjoor:hafez:divan:ghazal:108",
  "ganjoor_url": "/hafez/ghazal/sh108",
  "poet": "hafez",
  "book_fa": "دیوان اشعار",
  "category_fa": "غزلیات",
  "form": "ghazal",
  "number": 108,
  "title": "غزل شمارهٔ ۱۰۸",
  "meter_fa": "فعلاتن فعلاتن فعلاتن فعلن (رمل مثمن مخبون محذوف)",
  "rhyme": "ان تو باد",
  "verses": [
    { "vorder": 1, "position": "right", "text": "خسروا گویِ فلک در خَمِ چوگان تو باد" },
    { "vorder": 2, "position": "left",  "text": "ساحتِ کون و مکان عرصهٔ میدانِ تو باد" }
  ],
  "source": "ganjoor.net",
  "fetched_at": "2026-05-18T..."
}
```

For Phase 1, the actual NDJSON files use an envelope (`{"_meta": {...}, "poem": {...}}`) and pass through ganjoor's poem object verbatim. **Fidelity to upstream is the whole point.** Persian normalization happens later, in a separate enriched-data layer.

## Persian text normalization — two layers

Persian text has multiple equivalent encodings that breakk naïve search. The normalizer has two outputs:

**Display layer** (preserves typographic quality):
- Arabic ي (U+064A) → Persian ی (U+06CC)
- Arabic ك (U+0643) → Persian ک (U+06A9)
- Preserve ZWNJ (U+200C) where typographically correct
- Preserve diacritics if present in source

**Search layer** (collapses everything for matching):
- All `Display` transformations
- Strip diacritics (fatha, kasra, damma, tashdid, sukun, etc.)
- Strip ZWNJ entirely
- Fold final ه (heh) and ة (teh marbuta)
- Fold hamza variants (أ، إ، ؤ، ئ، ء → ا or strip)
- Persian/Arabic digits → ASCII (۰-۹ and ٠-٩ → 0-9)
- Lowercase Latin-script transliterations
- Collapse whitespace

The current PWA implements both in JS (`toDisplay` and `toSearch` functions in `index.html`). That is the reference for any future server-side normalizer.

## RTL typography choices

- **Vazirmatn** variable font from Google Fonts as default. Estedad as alternate. Both are OFL-licensed, designed by Saber Rastikerdar, and handle Persian typography correctly (proper kashida, ZWNJ, kerning).
- Hemistich-pair grid: each beyt is two mesras on one line on desktop (with the second hemistich flowed to the left), collapsing to two stacked lines on mobile.
- Three themes: sepia (`#faf6ef`/`#2b2620`) as default, light, dark (`#1a1814`/`#e9e2d4`).
- Body text 18px / 1.9 line-height minimum; ghazals and qasidas benefit from 20px+ and 2.0 line-height.
- Justified text **off** by default; Persian poetry uses center alignment or hemistich-aligned grid.

## Versioning

- **Code:** SemVer (`1.4.2`)
- **Corpus:** CalVer with ordinal (`2026.1`, `2026.2`) — matches OpenITI's pattern
- **Schema:** SemVer (`v1`, `v2`) — frozen between majors

Release artifacts per corpus version: `corpus-2026.N.sqlite.gz`, `.json.tar.gz`, `.jsonl.gz`, `.parquet`, `schema-2026.N.json`, `checksums.txt`. Zenodo DOI per release; concept DOI resolves to latest.

## Hosting — GitHub only for v0.1

Source, data, builds, releases, hosting — all GitHub. One platform, one account, one mental model. The PWA is on GitHub Pages. Release artifacts go to GitHub Releases. Heavy compute runs on GitHub Actions (free unlimited minutes for public repos).

Cloudflare is a Phase-2 option if and only if one of these becomes a real problem:
1. Per-PR preview deployments (multi-reviewer workflow)
2. Per-path `_headers` for COOP/COEP (to enable OPFS)
3. >100 GB/month bandwidth
4. Workers/D1/R2 for server-side features

Until one of those four hits, GitHub-only is cleaner. The migration cost is roughly zero: Cloudflare Pages connects to the same GitHub repo without touching code, data, or schemas.

## What v0.1 ships, what it doesn't

**In scope for v0.1:**

- One poet, fully: Hafez (~495 ghazals + qasidas, qet'at, rubaiyat, masnavi)
- Per-poem JSON with stable identifiers
- Persian-aware search with two-layer normalization
- PWA reader with RTL typography, sepia/light/dark themes, Vazirmatn font, faal (تفأل)
- MIT code, CC-BY-4.0 data, frozen schema v1

**Deferred to v1.0:**

- Audio recitations
- Translations (Persian → English, transliteration)
- Other poets
- Manuscript variants
- Comments / tafsir layer

## Stretch goals beyond v0.2

In rough priority order:

- **Bilingual reading mode** for diaspora — Persian + curated English translation + optional transliteration (UniPers or DMG/IJMES) + tap-word-for-gloss. High value, low data cost. Nobody does both well.
- **Meter detection** via Theodore Beers' `persian-meter` and ganjoor's `sangin` (already exists, just wire it in).
- **Audio integration** streaming from ganjoor's CDN with verse-level highlighting from sync XML (rights-clean if you stream not rehost).
- **Manuscript variants** from Naskban.
- **Semantic search** via sqlite-vec inside the FTS5 DB.
- **OpenITI coordination** — their Persian holdings already originate from ganjoor; a schema-clean parallel mirror could be a high-leverage partnership.

## Closing principle

The durability test for this project is not the PWA. It is the canonical-id allocation table, the JSON Schema, and the CC-BY corpus release with Zenodo DOI. Framework, search library, CSS, host — all replaceable. The two day-one decisions that aren't replaceable: the permalink contract (URN + canonical_id + ganjoor_id, never reassigned) and the license layering (MIT code, CC-BY data, never CC-BY-SA on the corpus).

Build the data layer like it will outlive the app, because it will.

---

# Report 2 — Civilizational Preservation Playbook

*A century-class preservation strategy. Generated after the user explicitly framed this as a civilizational obligation.*

## The clock is already running

As of May 2026, Iran is in day 130+ of its longest national internet shutdown ever — ganjoor.net's audio and image servers (hosted on Iranian datacenters) have been globally unreachable since January 8, 2026, even though the main site stays partially up from its Windows server abroad. Hamid Reza Mohammadi — the project's sole maintainer, working alone from Tehran as a full-time-elsewhere hobbyist — has explicitly written that *"Ganjoor has been a personal hobby"* and is *"affiliated with no organization."* The bus factor is exactly 1. **The emergency snapshot should ship this week.**

This playbook gives you a one-week emergency-snapshot procedure that runs entirely from GitHub Actions on a phone, a layered redundancy stack across EU, US, and decentralized storage, named contacts at every institution worth approaching from NYC, defensible answers on the audio/manuscript rights gray zone, and a respectful coordination script for Hamid himself.

## The threat model is real, current, and named

Ganjoor's architecture has three independent failure surfaces (see Report 1 above). The realistic disappearance scenarios, in descending probability:

**Maintainer attrition.** Hamid is a single full-time-employed volunteer in Tehran. No co-administrators are visible in the GitHub org's permission settings; all GanjoorService commits since inception are by `hrmoh`. A career change, family event, health issue, or emigration could pause development indefinitely. There is no published successor.

**Iranian connectivity collapse.** Iran has had nationwide shutdowns in November 2019, September 2022, the June 2025 Twelve-Day War, and is currently in a 50+ day national shutdown that began January 8, 2026 — the longest ever recorded, with Iran moving toward whitelist-based national-intranet connectivity. Each event takes ganjoor's audio offline globally.

**Hosting/payment failure.** Sanctions affect Iran-issued payment cards reaching foreign hosting providers; if Hamid's foreign-hosting payment method breaks, the outside-Iran server lapses. Ganjoor disclaims commercial activity, so there is no revenue cushion.

**Domain expiration.** ganjoor.net is the only official domain; Hamid has publicly warned about lookalikes. If the renewal fails for any reason, the lookalikes inherit the audience.

**Political pressure on the maintainer.** Persian classical poetry is broadly culturally sanctioned in Iran, but a single individual hosting commentary, user comments, and book scans is exposed to pressure that an institution would not be.

**Hardware failure.** The site runs on what Hamid describes as *"a pretty old version of WordPress"* with idiosyncratic dependencies; recovery from a disk loss depends on his backups, of which we have no public documentation.

## What is already preserved by third parties — and why it is not enough

| Mirror | Coverage | Last refresh | Verdict |
|---|---|---|---|
| `mabidan/ganjoor` (Hugging Face) | 119,061 poems, 203 poets, CSV from `ganjoor/desktop v2.96` | stale, ~2024 | Text only, no metadata graph, no audio |
| OpenITI RELEASE (GitHub + Zenodo 10007820) | Partial Persian texts, derived from Ganjoor circa 2015–2016 | last full release 2023 | Snapshot, not synced; mARkdown incompatibility flagged in their README |
| SourceForge `ganjoor/s3db/` | SQLite dumps dated 2012 and 2014 (`ganjoor-s3db-910612.zip` ≈34 MB; `930711.zip` ≈42 MB) | 2014 | Decade-stale |
| GitLab `prp-e/database-ganjoor`, gists, ad-hoc forks | Point-in-time SQLite copies | varied | Not maintained |
| Internet Archive Wayback | ganjoor.net landing + popular poet pages, sparse coverage of api.ganjoor.net | continuous | Reading not archiving the data graph |
| Persian Wikisource | Overlapping classical canon, sourced independently from print | active | Parallel corpus, not a ganjoor mirror |

**No complete mirror of ganjoor exists.** No third party has the comment archive, the verse-level sync XML for audio, the meter/rhyme metadata graph, the "similar poems" relationships, the museum scans, or the api.ganjoor.net JSON shape. Persian Wikisource is a parallel literary corpus, not a backup. **The preservation gap we are filling is real.**

## What we are actually preserving, by category and size

The corpus naturally separates into seven layers, with very different size and rights profiles.

**Text corpus** is the crown jewel and the smallest object. Uncompressed JSON of all text plus metadata is on the order of 300–500 MB; gzipped, roughly 80–150 MB. The current SQLite `ganjoor.s3db` published with `ganjoor/desktop v2.96` is ~80 MB compressed. **This entire layer fits on a single GitHub Release asset and is trivially preserved everywhere.**

**Audio recitations** are the largest and most fragile layer. Hamid imposes a 10-recitation cap per poem (set August 2022); the corpus likely holds tens of thousands to ~100k MP3s. Working size estimate: 80–200 GB. Critically, `ava.ganjoor.net/about` documents a strong, explicit reciter consent regime: *"by submitting your recitation to Ganjoor you accept that your work may be reused without restriction and freely, in both free and commercial works. The only condition is attribution of the reciter's name and original source."* This is effectively a CC-BY-equivalent license granted to ganjoor and downstream users, with a separate prohibition on submitting commercial third-party recordings. In practice this means audio submitted through `gaudiopanel.ganjoor.net` is safe to re-distribute under CC-BY; the audit problem is identifying any pre-panel legacy uploads where consent is unclear.

**Manuscript scans** under `museum.ganjoor.net` and `naskban.ir` are a hybrid. The blog announcement (Esfand 1402 / March 2024) confirms naskban hosts >30,000 PDF books obtained from the Soha online library — these are not ganjoor's originals but rehosted scans, several hundred GB to TB-scale. External manuscript links to Princeton, Bodleian, British Library, HathiTrust, Smithsonian are not redistributable but **their IIIF manifests are.**

**Comments (حاشیه‌ها)** carry significant literary value — scholarly tafsir, variant readings, corrections collected over a decade. Popular Hafez ghazals have dozens to hundreds of comments; aggregated across the corpus, hundreds of thousands to ~1M total. Each comment is the copyright of its author. Mirror with attribution but do not republish at scale until governance is in place.

**AI-generated paraphrases and "برگردان به زبان ساده"** are editorial-class content under ganjoor's control — preserve verbatim with provenance metadata flagging them as machine-assisted.

**The rendered website** (HTML + CSS + JS + images + navigation) is the user-experience layer; WARC capture is the answer.

**The codebase** — `ganjoor/GanjoorService` (ASP.NET Core, GPL-3.0), `ganjoor/desktop` (MIT), `ganjoor/NaskbanService` (AGPL-3.0), and 50 other repos in the `ganjoor` org — is already preserved by GitHub's normal infrastructure and harvested continuously by Software Heritage. Mirror to Codeberg or a non-US Git forge as sanctions insurance.

## The redundancy stack ranked by durability and political diversity

Treat preservation as a portfolio problem: independent jurisdictions, independent failure modes, independent identifier systems. Four tiers.

### Tier 1 — Trusted decade+ archives

**Zenodo (CERN, Switzerland)** is the primary canonical home. Only target combining DataCite DOI minting per version, CERN-grade tape backup, EU jurisdiction (insulating Iran-origin content from US legal pressure), and 20-year minimum retention commitment. Default record limit 50 GB / 100 files, plus 150 GB account allowance, with one-time 200 GB single-record quota available for cultural-heritage datasets. Upload via REST API at `developers.zenodo.org` using a bearer token from account settings; files frozen 30 days after publish, after which a new version mints a fresh DOI while the concept DOI always resolves to latest. Use Zenodo for the text-corpus canonical release and a curated audio subset (~50 GB highlights).

**Internet Archive** is the largest-reach mirror, with caveats. Items get permanent `archive.org/details/...` URLs, ARK identifiers, automatic torrent generation, replication across Richmond CA, Sacramento CA, Vancouver BC, Amsterdam. The Bibliotheca Alexandrina mirror reportedly stopped working in 2022 — do not count it. The Hachette v. IA ruling (2d Cir., September 4, 2024; SCOTUS petition declined December 2024) cost IA its CDL program; the pending UMG/Sony Great 78 Project recordings lawsuit carries potential damages reportedly exceeding $400M and is a genuine institutional-solvency risk. The October 2024 DDoS + credential-breach incidents did not compromise stored archive data but illustrate elevated risk. **Conclusion: still use IA aggressively — its reach and free tier are unmatched — but never as the sole copy.** Upload with the `ia` CLI: `ia upload ganjoor-2026-1 ./bundle/ --metadata="mediatype:texts" --metadata="language:per" --metadata="licenseurl:https://creativecommons.org/licenses/by/4.0/" --metadata="subject:Persian poetry"`. Mediatype is permanent on first upload — choose carefully (`texts` for the corpus, separate item with `audio` for recitations).

**Software Heritage (Inria/UNESCO, France)** is the text corpus's most durable home. SWHIDs became ISO/IEC 18670:2025 in April 2025, decoupling identifier permanence from the SWH organization itself; the corpus's cryptographic identifier can be recomputed locally from any future copy. Five mirrors operate as of 2026 (ENEA Bologna, GRNET Greece, FossID, UNIDUE Germany, new Spanish mirror announced at Symposium 2026), with renewed five-year UNESCO Digital Public Goods partnership announced January 2026. Push the text repo to GitHub; SWH harvests automatically. For belt-and-braces, trigger a deposit at `archive.softwareheritage.org/save/`. **Do not deposit audio here** — SWH is for source code and text-as-source, not media.

**GitHub itself** provides the working surface. The Arctic Code Vault is a one-shot February 2020 snapshot that has not been refreshed, despite community requests; treat it as a historical curiosity, not active service. Normal GitHub redundancy (Azure multi-region) plus continuous Software Heritage harvesting is the real protection. **Mirror everything to Codeberg.org as well** — non-US jurisdiction, in case OFAC-related restrictions on Iranian collaborators tighten.

**Hugging Face Datasets** is a redistribution hub, not preservation. Free public datasets up to ~1 TB, no SLA, no formal retention commitment, backed by AWS S3 us-east. Excellent for ML reuse (`mabidan/ganjoor` already shows precedent) but it's a commercial company — never count as an archive.

### Tier 2 — Academic and cultural institutions

The single highest-value institutional contact is **Matthew Thomas Miller at UMD Roshan** (`mtmiller@umd.edu`). Co-PI of OpenITI, director of PersDig@UMD, director of the newly endowed **Elahé Omidyar Mir-Djalali Persian Digital Library (EOMPDL)** — explicitly funded in 2025 with $1.5M endowment plus $310K startup to build *"the first open-access Persian digital library to feature texts professionally edited and vetted by scholars."* OpenITI's own corpus documentation already names ganjoor as an upstream source. **A clean CC-BY-4.0 ganjoor mirror is exactly what they have been waiting for.** Pair the email with a draft pull request to `github.com/OpenITI/RELEASE`.

The other institutions worth approaching, ranked by NYC accessibility and mandate fit:

**Library of Congress's Hirad Dinavari** (Reference Specialist for Iranian World Collections, AMED Near East Section, (202) 707-4188, via `ask.loc.gov/africa-middle-east/`) curated *A Thousand Years of the Persian Book* and oversaw the 2019 digitization of 150 rare Persian manuscripts — the symbolic North American national archive, three hours by Amtrak from NYC.

**Columbia's Peter Magierski** (`pm2650@columbia.edu`, Middle East and Islamic Studies Librarian) and **Kaoukab Chebaro** (`kc3287@columbia.edu`, Head of Global Studies) are the right operational contacts since the Encyclopaedia Iranica editorial office moved to UC Irvine under Touraj Daryaee in 2024–2025 (Marie McCrone / Elton Daniel pages on Columbia's site are stale).

**NYU's Ali Mirsepassi** (`am128@nyu.edu`, Iranian Studies Initiative) and **Fidele Harfouche** (`fh38@nyu.edu`, Kevorkian Center programs) are the easiest in-person targets — same city, walkable.

**Princeton's Deborah Schlein** (Near Eastern Studies Librarian, via `library.princeton.edu/about/staff-directory`) and **Mireille Djenno** (Global Special Collections) cover the largest Islamic manuscript holdings in North America (16,000 titles), one hour by NJ Transit.

**UCLA's Domenico Ingenito** (`ingenito@humnet.ucla.edu`) is the most relevant Persian-poetry computational-scholarship peer; he co-edits volumes with Matt Miller — getting both on side establishes the corpus's scholarly endorsement.

**British Library's Ursula Sims-Williams** (Lead Curator Persian, `apac-enquiries@bl.uk`) leads BL's 12,000-manuscript Persian digitization; their Endangered Archives Programme (`endangeredarchives@bl.uk`) does not fit ganjoor itself — EAP requires the material be located outside Western Europe/North America and pre-mid-20th century — but EAP-funded digitization of physical manuscripts in Iran/Tajikistan could complement ganjoor.

Two notes on prior confusions: **OpenITI is not based at the University of Chicago** — its three lead institutions are Aga Khan University–ISMC London (Savant), University of Vienna (Romanov), and UMD Roshan (Miller). And **Encyclopaedia Iranica editorial leadership transitioned in 2024–2025**; Touraj Daryaee at UC Irvine is Editor-in-Chief.

For non-Iran Persian-language nations, only **Tajikistan is currently viable**. The Firdausi National Library of Tajikistan (named for Ferdowsi) and the Institute of Oriental Studies (Tajik Academy of Sciences, Dushanbe) hold the relevant collections; route via the Tajik Embassy cultural section in Washington DC. **Afghanistan should be avoided under current Taliban governance.** Uzbekistan's Al-Biruni Institute holds 26,000 manuscripts but has no published digital-deposit program.

**Bibliotheca Alexandrina** accepts digital donations (`infobib@bibalex.org`, "Gift Donations" subject line). IA-mirror status uncertain, but cultural mandate covers Persian heritage and they have published donation procedures.

Wikimedia-side: the Knowledge Equity Fund has wound down its open application cycle (final round announced October 2024). The actionable Wikimedia path is the **Community Fund Rapid Fund** ($500–$5K, 2-month turnaround) for a Persian-Wikisource integration project, and contributing canonical ganjoor texts to fa.wikisource.org under CC-BY-SA dual-license to create a genuine Wikimedia institutional copy.

### Tier 3 — Decentralized and permaweb

**Filecoin Plus is the single most attractive option for the full audio corpus.** Cultural-heritage projects are explicitly eligible for DataCap allocation — recent recipients include Smithsonian's Bell sound recordings, MIT OpenCourseWare, Flickr Foundation, and Starling Lab at USC (22 PB). Apply via `github.com/filecoin-project/filecoin-plus-large-datasets` or through an Allocator at `allocator.tech`. The Filecoin Foundation's January 2025 announcement crossed 500K cultural artifacts preserved; the new Proof of Data Possession primitive (May 2025) gives verifiable hot-storage replication. If DataCap is granted, the full 50–200 GB ganjoor audio is **free, replicated, and provably stored** for the duration of the deal — which must be renewed (use Lighthouse or Spade to automate renewals).

**Arweave is the strongest paid permanence guarantee.** AR price is depressed (~$2.10–$2.40 in May 2026, down ~95% from November 2021 ATH of $89.24), which means USD storage cost is **cheap right now** — roughly $5–10 per GB one-time. The Persian text corpus at 500 MB costs ~$2.50–5. A 50 GB curated audio subset costs ~$250–500. The full 200 GB audio costs ~$1,000–2,000. The endowment math (one-time fee covering 200 years at current cost, betting on Kryder's law) has not required endowment drawdown since 2018 mainnet launch and the Arweave Foundation reports the endowment ratio is growing. Upload via ArDrive Turbo (credit-card USD payment, no AR token handling required) or Irys SDK. **Each upload yields a permanent TXID** at `arweave.net/<txid>` — third independent persistent identifier alongside DOI (Zenodo) and SWHID (Software Heritage).

**IPFS pinning has consolidated in 2026.** Use **Filebase** for audio (5 GB free, $20/month Starter, 1 TB per-file cap, S3-compatible, unlimited-bandwidth plan added December 2025 — best fit for large media). Use **Pinata** for the text/manifests (1 GB free is plenty, dedicated gateway included). **Storacha** (web3.storage's UCAN-based successor) is third. **Avoid Fleek** (IPFS hosting discontinued January 31, 2026), **Estuary** (shut down April 2024), and **nft.storage Ltd** (wound down 2024–2025).

Storj DCS and Sia are recurring-payment hot storage, not preservation — useful as a working mirror, never as an archive.

### Tier 4 — Physical and offline (LOCKSS principle)

A WARC bundle on two USB SSDs hand-carried to two NYC-area academics (Mirsepassi at NYU, Magierski at Columbia) plus one mailed to Matt Miller at UMD costs under $200 total and provides the cleanest disaster-recovery story. Each IA item gets an automatic torrent at `archive.org/download/<id>/<id>_archive.torrent`; publish that magnet URI in the GitHub README. Submit the same bundle to **academictorrents.com**, which is the appropriate tracker for research data. If the project catches on, the magnet link gets hundreds of seeders without further intervention.

## Format strategy: what survives centuries

The Library of Congress's annually-updated **Recommended Formats Statement** (`loc.gov/preservation/resources/rfs/`) gives unambiguous guidance for each category, and SQLite has been a Preferred dataset format since the famous 2018 endorsement (LoC FDD `fdd000461`). Build the canonical release bundle around five formats:

For the **text corpus**, ship three redundant representations:
- **SQLite** (`ganjoor.s3db`, LoC-Preferred, public-domain format, byte-identical across architectures, validated by `PRAGMA integrity_check`)
- **Newline-delimited JSON** per poet (`hafez.ndjson` etc., zstd-compressed; trivially diff-able and machine-parseable in any language)
- **TEI XML** export for the scholarly community (the OpenITI/Persian-DH lingua franca)

All three serialize the same canonical data model. Publish a JSON Schema alongside, versioned semantically.

For **web content**, capture WARC files (ISO 28500:2017, LoC FDD `fdd000236` updated April 2024). Use **browsertrix-crawler** in a Docker container (v1.12.0 as of March 2026, actively maintained, the de facto leading tool) for the modern JS-heavy ganjoor.net pages; fall back to `wget --warc` for simple static targets. Outputs WACZ bundles that replay in any browser via ReplayWeb.page. **Do not build new workflows on Conifer** — Rhizome announced its "twilight" for June 2026.

For **audio**, the question of FLAC versus original MP3 has a clear answer: **preserve the original MP3 bytes verbatim.** Transcoding lossy to lossless produces a larger file with the original quantization artifacts baked in — pointless. The LoC stance is that MP3 is Acceptable (not Preferred), but for born-digital MP3 with no higher-quality master available, the original bytes are the canonical preservation object. Generate SHA-256 at ingest, validate annually, wrap with BagIt manifests.

For **manuscript images**, preserve the **IIIF manifests** (the JSON-LD documents) — not the pixels — for third-party-hosted scans. Manifests are typically licensed CC-BY or CC0 (Penn's OPenn rights statement is explicit: *"all materials on OPenn are in the public domain or released under Creative Commons licenses as Free Cultural Works"*), are a few KB to MB each, and preserve full bibliographic provenance plus the citation graph to reconstruct from source. For ganjoor's own museum.ganjoor.net scans, use TIFF or JPEG2000-lossless as the LoC-Preferred master if you re-derive from originals, otherwise preserve the original JPEG/WebP bytes.

For documentation, **PDF/A** (ISO 19005); for narrative content, plain Markdown / UTF-8 text.

The canonical release bundle for `v2026.1`:

```
ganjoor-v2026.1/
  ganjoor.s3db                       # SQLite, LoC-Preferred
  ganjoor.s3db.sha256
  json/
    poets.ndjson.zst
    poems-{poet}.ndjson.zst          # one file per poet
    metadata-graph.ndjson.zst        # meters, rhymes, similar-poems
  tei/                               # TEI XML per poet
  schemas/
    poem.schema.json
    poet.schema.json
  warc/
    ganjoor-net-{date}.wacz          # browsertrix capture
    api-ganjoor-net-{date}.warc.gz   # wget --warc of API
  manifests/
    iiif/                            # third-party manuscript manifests
    audio-index.csv                  # reciter, poem_id, url, sha256, sync_xml_url
  CHECKSUMS.sha256
  README.md
  LICENSE                            # CC-BY-4.0
  PROVENANCE.md                      # ganjoor.net as source, dates, methodology
  RIGHTS.md                          # per-category rights statement
```

## Audio rights — the safest practical path

Iran is **not a signatory to the Berne Convention nor the WIPO Copyright Treaty** and is a WTO observer (not member), so unbound by TRIPS substantive copyright obligations. Domestic Iranian law (1970 Act, amended August 2010) gives 50 years post mortem auctoris protection. Outside Iran, enforcement of Iranian copyrights is historically uncertain — but this is not legal cover, it is jurisdictional drift, and any rights-holder can sue in your local jurisdiction regardless.

The defensible position rests on `ava.ganjoor.net/about`'s explicit consent text: reciters who submitted via gaudiopanel granted ganjoor (and downstream users) a free-and-commercial-reuse license requiring only attribution. That is functionally a **CC-BY 4.0-equivalent license**. For audio uploaded through this channel, mirroring with full attribution (reciter name + ganjoor.net as original source) is on solid contractual ground.

The unresolved risk is legacy audio uploaded before the panel formalized, or any case where a reciter denies having submitted via panel. The pragmatic mitigation is a **two-archive structure** modeled on CLOCKSS:

- A **public CC-BY mirror** of the audio with full attribution, hosted at IA + Filecoin Plus + Hugging Face. Honor takedown requests within 7 days. Maintain a public takedown log.
- A **dark archive** copy on Arweave + offline encrypted USB SSDs held by 2–3 academic preservation contacts, with a written **trigger-event protocol** modeled on CLOCKSS: release to the world under CC-BY only on (a) ganjoor.net unreachable >90 consecutive days with no maintainer announcement, (b) documented maintainer incapacity, (c) public statement of project termination, or (d) 365 days of no maintainer response. A 3-of-5 majority of a designated **Preservation Committee** (e.g., Miller, Magierski, Mirsepassi, Ingenito, Dinavari) votes to release.

CLOCKSS has done this for academic journals (first real trigger: SAGE's *Graft*); the model is well-established. The Hachette v. IA ruling (September 4, 2024) explicitly killed Controlled Digital Lending of in-copyright books — **do not attempt CDL-style "one copy out at a time" for ganjoor audio**; the same fair-use reasoning maps cleanly. Dark archive with trigger events is the safer path.

A defensible middle option for week-1 launch: **mirror the audio bytes to private storage (Filecoin Plus, Arweave private bundles, encrypted SSDs)** but publish only the **audio-index manifest** (reciter, poem ID, original ganjoor URL, SHA-256, sync XML URL) under CC-BY. Streaming playback continues to come from ganjoor's CDN until trigger. This preserves the bytes you need without re-distributing audio you cannot cleanly license — and the index alone is itself a substantial preservation artifact.

## Manuscript scans — IIIF as the lightweight insurance layer

Almost all the manuscript images linked from museum.ganjoor.net to outside institutions belong to those institutions, not ganjoor. Princeton's Manuscripts of the Islamic World (16,000 titles, largest in North America), the Bodleian, the British Library's 12,000-manuscript Persian digitization, HathiTrust, and the Smithsonian each carry their own licenses. **Do not bulk-mirror pixels** without per-institution permission.

What you **can** do, with high legal confidence, is **mirror the IIIF manifests** themselves. The Penn/Columbia/Free Library of Philadelphia consortium's **OPenn** (host of Manuscripts of the Muslim World) publishes an explicit policy: *"All materials on OPenn are in the public domain or released under Creative Commons licenses as Free Cultural Works"* — pixels included for that collection. Princeton's digitized Islamic Manuscripts are similarly permissive on a per-manuscript basis. Bodleian, BnF, and Vatican typically license the manifests themselves under CC-BY or CC0, restricting pixels to non-commercial/scholarly use.

Practical workflow: for each external manuscript link on ganjoor.net, identify the institution's IIIF manifest URL, fetch the manifest JSON, store under `manifests/iiif/<institution>/<id>.json`, record the manifest's `rendering` and `service` URLs (which point to the pixels), and capture the manifest's own SHA-256. Total size for thousands of manifests is on the order of tens of MB. If a manuscript later goes dark at its institution, the manifest preserves the citation graph and bibliographic provenance — enough for a future researcher to find the object or a derivative. For ganjoor's own museum.ganjoor.net scans, those are user-contributed under ganjoor's site terms and can likely be mirrored fully — confirm with Hamid.

Naskban is a special case: the 30,000+ PDFs were rehosted from the Soha library, not originally ganjoor's. The cleanest preservation move is to mirror the catalog (titles, page mappings to ganjoor poems, ISBNs/identifiers) rather than the PDFs themselves, and coordinate any bulk PDF preservation directly with the Soha team if reachable.

## Governance — from one person to a multi-maintainer trust

The best-documented analog is **Project Gutenberg**: Michael Hart founded it in 1971, established **PGLAF (501(c)(3))** in 2000 — eleven years before his September 2011 death — and publicly designated **Gregory Newby** as continuator. **Distributed Proofreaders** ran as a separate 501(c)(3) with a flat volunteer governance and produced the content. When Hart died, nothing broke. The structural lessons are unambiguous: **set up the legal shell before you need it, designate successors publicly and in writing, decouple infrastructure from content production**.

**Sefaria** is the closer modern peer (founded 2011, 501(c)(3) since 2013, ~30–50 staff in 2025, $3.6M → $10M budget trajectory through 2026, open-source codebase, open API, ~80 downstream third-party apps). Sefaria took 2 years from launch to incorporate, 4 years to multi-person staff. **That trajectory is realistic for ganjoor-mirror.** Tanzil is the cautionary case: opaque governance, no published successor, high downstream dependency.

**Recommended sequence for ganjoor-mirror:**

1. **Months 1–6**: Stay informal. Use **Code for Science & Society fiscal sponsorship** (`codeforsociety.org`) to receive tax-deductible donations and apply for grants without yet having your own 501(c)(3). CS&S is international-project-friendly and was built for exactly this transition.
2. **Months 6–18**: If Roshan-UMD/OpenITI accepts the corpus as part of EOMPDL, **defer institutional housing to them** — they have HR, legal, fiscal, and IT infrastructure that a solo developer cannot replicate. Your project becomes a technical mirror feeding their authoritative corpus.
3. **Months 12–24**: Designate a **3–5 person Preservation Committee** in writing, with the trigger-event authority described in §audio-rights. Reasonable initial members: Matt Miller (UMD), Domenico Ingenito (UCLA), Peter Magierski (Columbia), Ali Mirsepassi (NYU), and Hamid Reza Mohammadi himself (if willing). Document committee bylaws in the GitHub repo's `GOVERNANCE.md`.
4. **Year 2+**: If institutional housing doesn't materialize, incorporate a lightweight **501(c)(3) "Persian Digital Heritage Trust"** with the Preservation Committee as the founding board, and apply for direct Mellon/NEH/Roshan grants. Do not incorporate prematurely.

A **dead-man's-switch repository** (encrypted releases auto-published if the maintainer doesn't sign in for X months) is overengineering for the corpus itself (which is already public) but is **the right pattern for the dark-archive audio** — encrypted at rest, decryption key held in a 3-of-5 Shamir split among the Preservation Committee members.

**Persian Wikisource partnership** is the right Wikimedia move. Dual-license the canonical text dump as CC-BY-4.0 **plus** CC-BY-SA-4.0 specifically for fa.wikisource.org integration; engage their Village Pump (ویکی‌گفتگو) and the Wikimedia Iran user group; apply for a **Wikimedia Community Fund Rapid Fund** ($500–$5K, 2-month turnaround) to fund a 6-month Wikidata integration project that gives every ganjoor poem a Wikidata Q-item linking all institutional copies. This creates a genuine Wikimedia institutional copy and a permanent identifier graph.

## Realistic costs and grant pathways

The text corpus preservation is **genuinely free at civilizational scale**. Zenodo, Internet Archive, Software Heritage, GitHub, Hugging Face, and IPFS pinning free tiers cover it indefinitely. GitHub Actions for public repos is free with generous monthly minutes. The only one-time cost is **Arweave for the text bundle (~$5–10) and optionally for a curated audio subset (~$250–500 for 50 GB)**.

The full audio mirror is the only place where money matters. Three tractable paths:

- **Filecoin Plus DataCap (free if approved).** Cultural-heritage projects explicitly eligible. Application via `github.com/filecoin-project/filecoin-plus-large-datasets`. Realistic odds: moderate-to-high with a clean CC-BY corpus and a Roshan-UMD letter of support.
- **Arweave one-time payment (~$1,000–2,000 for 200 GB at current AR price).** Genuinely permanent in the endowment sense. Single largest expense in the whole playbook.
- **A small VPS for one-time bulk fetch + seeding ($10–30 for a month on Hetzner, OVH, or DigitalOcean).** Or use **Oracle Cloud Always Free Tier** (4 ARM cores, 24 GB RAM, 200 GB disk, free since 2019).

A reasonable solo budget for Year 1: **$0 if Filecoin Plus is approved; $1,500–2,500 if not.** Both within an individual's capacity. Beyond that, ongoing costs are essentially zero.

**Grant pathways**, in descending probability of first-application success:

The **Roshan Cultural Heritage Institute** is the single best-aligned funder on the planet — Dr. Elahé Omidyar Mir-Djalali (the founder's mother and primary donor) has explicitly committed $1.5M endowment + $310K to UMD's EOMPDL in 2025, plus $2.5M to UArizona Persian Studies in 2024. Award sizes range $300K–$2.5M. Letters of inquiry from 501(c)(3) public charities only. Path: get the corpus accepted by Roshan-UMD as part of EOMPDL → UMD itself applies for Roshan Institute funding with the ganjoor mirror as a named deliverable. **Realistic odds via this path: very high.**

**CLIR Recordings at Risk** ($10K–$50K, Mellon-funded, open application, multi-cycle per year, 501(c)(3) host required) is the natural funder for the audio-preservation tranche.

**NEH Digital Humanities Advancement Grants** ($50K Level I planning, $350K Level II development, $500K+ Level III; US-501(c)(3)-only, no individuals) needs a university PI. With a Roshan-UMD or UCLA partnership, a Level I planning grant is a realistic ask. The 2026 cycle has January and May deadlines.

**Mellon Public Knowledge Program** is invitation-only; route via CLIR's regranting programs for an open-application path. **Sloan Foundation** is highly relationship-driven and US-institution-only.

**Open Technology Fund** has $15M authorized for Iran internet freedom for both FY2025 and FY2026 per the Iran Internet Freedom Act (NDAA Section 5124, signed December 2024). Mandate is circumvention and access tools, not cultural preservation, but a framing around resilience of Iranian cultural heritage against state-sponsored disruption is plausible.

**Wikimedia Knowledge Equity Fund is winding down**; pivot to the **Wikimedia Community Fund Rapid Fund** for the Persian Wikisource integration sub-project.

**Iran Heritage Foundation (London)** caps grants at £3K and requires UK academic affiliation — useful for a UK conference or partnership but not core funding.

## What to do tomorrow morning

The single most consequential action this week is to **send the Hamid email**, then trigger the emergency-snapshot workflow before the end of the day. The risk profile justifies it: the maintainer is one person, his audio infrastructure is currently unreachable globally due to an Iranian shutdown now entering its fifth month, and no third-party mirror is complete. Every other action in this playbook — the institutional deposits, the Filecoin Plus application, the Preservation Committee — flows naturally from a clean v2026.1 release sitting on Zenodo with a DOI by end of Week 3.

The honest forecast is that ganjoor.net will probably outlive its current outage and continue for many more years — but a 5% annual probability of permanent loss compounds to roughly 40% over a decade, and the cost of preserving an 80 MB compressed corpus is one weekend of work and zero dollars. The text corpus is in your hands by next Sunday. The audio is a six-month project. The institutional housing is a one-to-two-year project. The civilizational guarantee — DOI plus SWHID plus Arweave TXID across four jurisdictions, with a written trigger-event protocol held by five academics — is achievable by the end of 2026 by a single person working evenings.

The thing worth remembering is that this is not a technically hard problem; it is a coordination problem. Ganjoor has been a one-person hobby for fifteen years, which means the institutional energy to preserve it has never been organized. **You are the coordination.**

---

*End of research archive. The detailed action templates (Hamid email in EN+FA, institutional outreach template, etc.) are in `PROJECT-HANDOFF.md` Part 6.3. The week-by-week sequenced playbook is in `PROJECT-HANDOFF.md` Part 6.8.*
