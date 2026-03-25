# Phase 05 — YQ Data Collection (Airline Scrapers)

## Goal
Build scrapers that fetch current YQ (fuel surcharge) amounts from airline booking pages, store them in `yq_schedules`, and keep the `carriers` table current. This is what populates the "which airlines have high fuel costs" dimension of the system.

## Deliverables

- [ ] `ingestion/scrapers/base.py` — abstract base scraper with shared logic
- [ ] `ingestion/scrapers/yq/` — one scraper file per airline (see list below)
- [ ] `ingestion/scrapers/yq_dispatcher.py` — runs all configured scrapers in sequence
- [ ] `backend/app/services/yq_service.py` — service layer wrapping scrapers + DB writes
- [ ] Celery task: `app/tasks/yq_tasks.py` — scheduled weekly YQ update
- [ ] Unit tests: `tests/test_ingestion/test_yq_scrapers.py` (mock HTTP)

## Why No API Exists

ATPCO (the authoritative source for YQ data) is a paid GDS service. Amadeus API is shut down for public access. Therefore we must scrape YQ from:
1. **Airline booking pages** — select a route, get to pricing, parse the fare construction
2. **ITA Matrix itself** — for carriers where booking page parsing is hard, run a simple ITA query and read the YQ from the result (reuse Phase 4 automation)

## Priority Carrier List (Build Scrapers in This Order)

| Priority | Carrier | IATA | Why High Priority |
|----------|---------|------|-------------------|
| 1 | Lufthansa | LH | Highest transatlantic YQ, most dump opportunities |
| 2 | British Airways | BA | High YQ, huge route network |
| 3 | Swiss | LX | Same group as LH, often interchangeable |
| 4 | Austrian | OS | Same group as LH |
| 5 | Brussels | SN | Same group as LH |
| 6 | Iberia | IB | Same group as BA |
| 7 | Cathay Pacific | CX | High YQ, Asia routes |
| 8 | Korean Air | KE | High YQ, Asia routes |
| 9 | Asiana | OZ | High YQ, Asia routes |
| 10 | Air France | AF | Moderate YQ, large network |

Low-YQ reference carriers (validate they stay near $0):
- QR (Qatar), EK (Emirates), EY (Etihad), TK (Turkish), SQ (Singapore)

## Base Scraper Interface

```python
class BaseYQScraper(ABC):
    carrier_iata: str
    scrape_url_template: str  # URL with {origin} and {destination} placeholders

    @abstractmethod
    async def scrape_yq(self, origin: str, destination: str) -> YQScrapeResult: ...

@dataclass
class YQScrapeResult:
    carrier_iata: str
    origin: str
    destination: str
    yq_amount_usd: float | None   # None = could not determine
    source_url: str
    scraped_at: datetime
    error: str | None
```

## Scraping Strategy

### Approach A: Airline Booking Page
- Navigate to airline booking flow for a specific route (e.g., LHR-JFK)
- Select a fare, reach the price breakdown page
- Parse the tax/fee breakdown to find YQ line
- Brittle (booking flows change), but gives real-time data

### Approach B: ITA Matrix Baseline (Fallback)
- For carriers where booking page scraping is too fragile: run a standard (non-dumped) ITA Matrix query
- Parse `yq_total_usd` from the result
- This is slower (uses ITA automation) but more reliable long-term
- Use this for carriers 6–10 in the priority list initially

### Approach C: Community-Maintained Reference
- Some FlyerTalk threads maintain up-to-date YQ tables (e.g., "LH YQ chart by route")
- Parse these as a secondary validation against Approach A/B results
- Do NOT use as sole source — too stale

## Scraper Implementation Notes

- All scrapers use `httpx` with async client (not Playwright — only use browser when necessary)
- Add realistic `User-Agent` and `Accept` headers
- Rate limit: 1 request per 3s per domain
- Cache raw responses in Redis for 6h to avoid redundant scrapes within the same day
- If scraping fails 3 times in a row for a carrier, flag it for manual review in the DB

## YQ Service (`yq_service.py`)

```python
async def update_carrier_yq(carrier_iata: str, sample_routes: list[tuple]) -> None:
    """
    Runs YQ scraper for a carrier across sample routes,
    stores results in yq_schedules, updates carriers.typical_yq_usd.
    sample_routes: list of (origin, destination) pairs representative of that carrier's network
    """

async def get_highest_yq_carriers(limit: int = 10) -> list[CarrierYQSummary]:
    """
    Returns carriers sorted by their average typical_yq_usd DESC.
    Used by agents to prioritize route research.
    """

async def get_current_yq(carrier_iata: str, origin: str, destination: str) -> float | None:
    """
    Returns most recent YQ amount for a carrier on a specific route.
    Falls back to carrier-level typical_yq_usd if no route-specific data.
    """
```

## Sample Routes Per Carrier

Define a `data/sample_routes.json` mapping carrier → list of (origin, destination) pairs to sample for YQ data. Include at minimum:
- 3 transatlantic routes per carrier
- 2 transpacific routes per carrier (if applicable)
- 2 intra-regional routes per carrier

## Completion Check

```bash
# Run mock-HTTP unit tests
cd backend && pytest tests/test_ingestion/test_yq_scrapers.py -v

# Run live scrape for LH (requires network)
python -c "
from ingestion.scrapers.yq.lufthansa import LufthansaYQScraper
import asyncio
result = asyncio.run(LufthansaYQScraper().scrape_yq('JFK', 'FRA'))
print(result)
"
```

## Files Changed
- New: `ingestion/scrapers/base.py`
- New: `ingestion/scrapers/yq/` (one file per carrier)
- New: `ingestion/scrapers/yq_dispatcher.py`
- New: `backend/app/services/yq_service.py`
- New: `backend/app/tasks/yq_tasks.py`
- New: `backend/data/sample_routes.json`
- New: `tests/test_ingestion/test_yq_scrapers.py`
