# CLAUDE.md — Seed Data

## Overview

Seed data populates the database with the initial carrier records needed for the system to function. All seed files are JSON so they can be version-controlled and reviewed without running Python.

## Files

```
seeds/
├── CLAUDE.md          ← you are here
└── carriers.json      ← 30+ airline records (created in Phase 01)
```

## `carriers.json` Format

```json
[
  {
    "iata_code": "LH",
    "name": "Lufthansa",
    "alliance": "STAR",
    "charges_yq": true,
    "typical_yq_usd": 580.0,
    "yq_scrape_url": "https://www.lufthansa.com/..."
  }
]
```

## Required Carriers

At minimum, `carriers.json` must include:

### High-YQ carriers (primary dump targets)
| IATA | Carrier | Alliance | Notes |
|------|---------|---------|-------|
| LH | Lufthansa | STAR | Highest transatlantic YQ (~$580), most dump opportunities |
| BA | British Airways | ONEWORLD | High YQ, huge network |
| LX | Swiss | STAR | Same Lufthansa Group, often interchangeable with LH |
| OS | Austrian | STAR | Lufthansa Group |
| SN | Brussels Airlines | STAR | Lufthansa Group |
| IB | Iberia | ONEWORLD | Same IAG group as BA |
| CX | Cathay Pacific | ONEWORLD | High YQ on Asia routes |
| KE | Korean Air | SKYTEAM | High YQ on transpacific |
| OZ | Asiana | STAR | High YQ on Asia routes |
| AF | Air France | SKYTEAM | Moderate YQ, large network |
| KL | KLM | SKYTEAM | Air France-KLM group |

### Low/No-YQ carriers (useful as dump vehicles)
| IATA | Carrier | Alliance | Notes |
|------|---------|---------|-------|
| QR | Qatar Airways | ONEWORLD | Charges no YQ — common dump vehicle |
| EK | Emirates | NONE | No YQ on most routes |
| EY | Etihad | NONE | No YQ on most routes |
| TK | Turkish Airlines | STAR | Low YQ |
| SQ | Singapore Airlines | STAR | Low YQ |

### US carriers (operating carriers in dump constructions)
| IATA | Carrier | Alliance | Notes |
|------|---------|---------|-------|
| AA | American Airlines | ONEWORLD | Common operating carrier in TP dumps |
| UA | United Airlines | STAR | Common operating carrier in TP dumps |
| DL | Delta Air Lines | SKYTEAM | Common operating carrier |

### Additional carriers (complete the list to 30+)
AY (Finnair/ONEWORLD), AZ (ITA Airways/SKYTEAM), MS (EgyptAir/STAR), ET (Ethiopian/STAR),
NH (ANA/STAR), JL (Japan Airlines/ONEWORLD), OA (Olympic/STAR), SK (SAS/STAR),
LO (LOT/STAR), TP (TAP/STAR), RJ (Royal Jordanian/ONEWORLD), LA (LATAM/ONEWORLD)

## Seed Script (`scripts/seed_carriers.py`)

The script must:
1. Load `seeds/carriers.json`
2. For each carrier: `INSERT ... ON CONFLICT (iata_code) DO UPDATE` (idempotent)
3. Print a summary: "Seeded 32 carriers (5 updated, 27 inserted)"
4. Exit 0 on success, 1 on error

Run via:
```bash
cd backend && python scripts/seed_carriers.py
```

Or via Makefile:
```bash
make db-seed
```

## Notes

- `typical_yq_usd` is an estimate for initialization. The YQ scraper (Phase 05) will update these values with accurate scraped data.
- `yq_scrape_url` can be `null` for carriers where the booking page is too fragile — Phase 05 will use ITA Matrix as fallback for those.
- Carriers added during community ingestion (Phase 06) are created as stubs — `charges_yq: null`, `typical_yq_usd: null` — and enriched later by Phase 05.
