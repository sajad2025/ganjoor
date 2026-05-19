<div align="center">

# گنجور · Ganjoor

**An open, citable archive of classical Persian poetry**
**آرشیوی متن‌باز و قابل‌ارجاع از شعر کلاسیک پارسی**

[![License: MIT](https://img.shields.io/badge/Code-MIT-blue.svg)](LICENSE)
[![Data: CC BY 4.0](https://img.shields.io/badge/Data-CC%20BY%204.0-lightgrey.svg)](LICENSE-DATA)
[![Source: ganjoor.net](https://img.shields.io/badge/Source-ganjoor.net-green.svg)](https://ganjoor.net)
[![Live PWA](https://img.shields.io/badge/Live-PWA-orange.svg)](https://sajad2025.github.io/ganjoor/)

[**Open the app →**](https://sajad2025.github.io/ganjoor/)

</div>

---

## What this is

Persian classical poetry is one of the great literatures of the world, and [ganjoor.net](https://ganjoor.net) — built and maintained by **Hamid Reza Mohammadi** ([github.com/hrmoh](https://github.com/hrmoh)) and contributors since 2007 — is its most complete free corpus. This project mirrors ganjoor's data into a stable, schema-documented, citable form, and ships a small reference reader (Progressive Web App) on top.

**The reader is the demo. The data is the product.** Our goal is the most useful piece of infrastructure for anyone — readers, app developers, scholars — who wants to build with Persian poetry.

> **این چیست؟**
> این پروژه دادهٔ گنجور را در قالبی پایدار، مستند و قابل‌ارجاع منتشر می‌کند، با یک نرم‌افزار خواندنی کوچک به‌عنوان نمونه. هدف، فراهم‌آوردن زیرساختی برای پروژه‌های آیندهٔ شعر پارسی است.

---

## Who is this for?

| You are a… | Start here |
|---|---|
| 📖 **Reader** | [Open the app](https://sajad2025.github.io/ganjoor/), tap Share → Add to Home Screen |
| 💻 **Developer** | [`/data`](./data) — per-poem JSON; [`schema/`](./schema) — JSON Schema |
| 🎓 **Researcher** | [Releases](../../releases) ship versioned SQLite + Parquet dumps with DOI |
| ✍️ **Contributor** | Open a [data-correction issue](../../issues/new?template=data-correction.yml) or PR |

---

## What's in v0.1

- **One poet, fully:** Hafez (~495 ghazals + qasidas, qet'at, rubaiyat, masnavi)
- **Per-poem JSON** with stable identifiers (URN + canonical_id + ganjoor_id)
- **Persian-aware search** with two-layer normalization (ي→ی, ك→ک, ZWNJ, digits, diacritics)
- **PWA reader** with RTL typography, sepia/light/dark themes, Vazirmatn/Estedad fonts, faal (تفأل)
- **MIT** code, **CC-BY-4.0** data, **frozen schema v1**

Out of v0.1 (planned for v1.0): audio recitations, translations, other poets, manuscript variants.

---

## Permalink design — the long-term contract

Every poem has **three identifiers**, all first-class, all forever stable:

```
Path:           /poet/hafez/divan/ghazal/108
URN:            urn:ganjoor:hafez:divan:ghazal:108
Ganjoor ID:     2237
```

Once minted, a canonical_id **is never reused or repointed**. Deprecated entries keep their slot with a `deprecated_at` timestamp. Use these identifiers in citations, apps, databases — they will resolve in 2040.

---

## Data shape

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

Full schema: [`schema/v1.json`](./schema/v1.json). Frozen — breaking changes require schema v2.

**On-disk layout.** Every poem is one file, path mirrors the ganjoor.net permalink:

```
data/hafez/ghazal/108.json       ↔  ganjoor.net/hafez/ghazal/sh108
data/hafez/robaee2/12.json       ↔  ganjoor.net/hafez/robaee2/sh12
data/saadi/boostan/sb1/3.json    ↔  ganjoor.net/saadi/boostan/sb1/sh3
```

This means downstream apps can fetch any single poem with a single HTTP call against `raw.githubusercontent.com` — no NDJSON parsing, no index, no API. The repo is itself a per-poem CDN.

---

## Versioning

- **Code** — [SemVer](https://semver.org) (`1.4.2`)
- **Corpus** — CalVer with ordinal (`2026.1`, `2026.2`)
- **Schema** — SemVer (`v1`, `v2`) — frozen between majors

Each corpus release ships SQLite + JSON + Parquet + checksums on [Releases](../../releases) with a Zenodo DOI.

---

## Licensing

| Layer | License |
|---|---|
| App code, scripts | [MIT](./LICENSE) |
| Schemas, dictionaries | CC0-1.0 |
| Curated text corpus | [CC-BY-4.0](./LICENSE-DATA) |
| Audio (when added) | Per-file; default: do not redistribute |

**Required attribution string for derived works:**

> Persian poetry text courtesy of [گنجور — ganjoor.net](https://ganjoor.net) (Hamid Reza Mohammadi and contributors), republished under CC-BY-4.0 via [sajad2025/ganjoor](https://github.com/sajad2025/ganjoor).

---

## How to cite

See [`CITATION.cff`](./CITATION.cff) — GitHub renders a "Cite this repository" button at the top of this page with BibTeX export.

---

## Acknowledgements

- **[ganjoor.net](https://ganjoor.net)** — Hamid Reza Mohammadi and the ganjoor community, who built and have maintained the source corpus since 2007. This project would not exist without their two decades of editorial work.
- **Vazirmatn** — Saber Rastikerdar (OFL).
- **Hazm**, **DadmaTools**, **persian-tools** — for Persian NLP groundwork.

---

## Status

🌱 **Pre-alpha (v0.1).** Hafez only. Schema frozen. APIs may change. PRs and issues welcome.

— Started May 2026 from a phone, no laptop, no PC.
