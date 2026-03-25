# Phase 04 — ITA Matrix Automation Engine

## Goal
Build the Playwright-based browser automation that executes ITA Matrix queries and parses fare breakdowns. By the end of this phase, the system can take a routing code string, run it against ITA Matrix, and return a structured fare result.

## Deliverables

- [ ] `automation/browser.py` — browser/context lifecycle manager
- [ ] `automation/proxy_manager.py` — rotating proxy pool
- [ ] `automation/rate_limiter.py` — request throttling with jitter
- [ ] `automation/ita_client.py` — main ITA Matrix interaction
- [ ] `automation/result_parser.py` — fare breakdown parser
- [ ] Integration test: `tests/test_automation/test_ita_client.py` (runs against real ITA Matrix — flag as slow/integration)
- [ ] `automation/screenshots/` directory for failure debugging (gitignored, created at runtime)

## Browser Manager (`browser.py`)

```python
class BrowserManager:
    """
    Manages a single Playwright browser instance with session limits.
    After SESSION_LIMIT (15) requests, the browser context is recycled.
    Each new context gets a fresh proxy from the pool.
    """
    async def get_page(self) -> Page: ...
    async def close(self) -> None: ...
    async def _rotate_context(self) -> None: ...
```

- Uses Playwright async API
- Headless by default, but `HEADLESS=false` env var for debugging
- Viewport: randomize between `[1280, 800]`, `[1440, 900]`, `[1366, 768]`
- User agent: rotate from a pool of 10 real Chrome UAs (stored in `automation/data/user_agents.json`)

## ITA Matrix Client (`ita_client.py`)

### `run_query(routing_code: str, origin: str, destination: str, date: date) -> ITAResult`

Steps:
1. Navigate to `https://matrix.itasoftware.com`
2. Wait for search form (`#flight-search` or equivalent selector — verify on first implementation)
3. Fill in origin airport code
4. Fill in destination airport code
5. Set date (click date field → type date in MM/DD/YYYY format)
6. Open "More options" panel
7. Find and fill "Routing codes" field with routing_code string
8. Click "Search"
9. Wait for results (up to 30s, poll for results container)
10. If no results returned: return `ITAResult(success=False, error="no_results")`
11. Click first matching fare to open fare construction
12. Wait for fare construction panel
13. Call `result_parser.parse_fare_construction(page)`
14. Return structured result

### Human-Like Behavior Requirements (see `automation/CLAUDE.md`)
- Use `page.type()` with `delay` parameter (not `fill()`) for all text inputs
- Between major actions: `await asyncio.sleep(random.uniform(1.5, 3.5))`
- After navigation: wait for network idle before proceeding
- On CAPTCHA detection: take screenshot, raise `BotDetectionError`

## Result Parser (`result_parser.py`)

### `parse_fare_construction(page: Page) -> FareBreakdown`

Parses the ITA Matrix fare construction display. Must extract:

```python
@dataclass
class FareBreakdown:
    base_fare_usd: float
    yq_total_usd: float          # KEY: this is what we're checking for dumps
    yr_total_usd: float
    other_taxes_usd: float
    total_price_usd: float
    fare_basis_per_segment: list[str]
    carrier_per_segment: list[str]
    ticketing_carrier: str
    raw_tax_lines: list[dict]    # full breakdown for audit trail
```

ITA Matrix renders fare breakdowns in a table. The YQ line is labeled "Carrier-imposed fees" or "YQ" depending on version. Always check for both labels.

**IMPORTANT**: ITA Matrix's DOM structure changes occasionally. Build the parser with multiple fallback selectors. If parsing fails, take a screenshot of the fare panel to `automation/screenshots/parse_failure_[timestamp].png` for debugging.

## `ITAResult` Schema

```python
@dataclass
class ITAResult:
    success: bool
    fare_breakdown: FareBreakdown | None
    error: str | None          # "no_results", "parse_failure", "bot_detection", "timeout"
    screenshot_path: str | None  # path to failure screenshot if applicable
    raw_page_title: str | None   # for debugging
    duration_seconds: float
```

## Proxy Manager (`proxy_manager.py`)

- Load proxy list from `ITA_PROXY_LIST` config (list of `user:pass@host:port` strings)
- Track usage count per proxy (in Redis)
- Rotate before `DAILY_LIMIT` (200) requests per proxy
- On `BotDetectionError`: immediately retire proxy for 24h (store retirement timestamp in Redis)
- Health check: `async def check_proxy_health(proxy: str) -> bool` — simple HTTP GET via the proxy

## Rate Limiter (`rate_limiter.py`)

Simple async rate limiter using Redis:
```python
async def wait_for_rate_limit() -> None:
    """
    Waits until enough time has passed since the last ITA Matrix request.
    MIN_DELAY + random jitter (both from config).
    """
```

## Error Handling Contract

- **Never** raise exceptions from `run_query()`. Always return `ITAResult` with `success=False`.
- The service layer that calls this decides whether to retry, alert, or mark as error.
- Log all errors with `pattern_id` and `routing_code` for debugging.

## Completion Check

```bash
# Integration test (requires real network + proxies configured)
cd backend && pytest tests/test_automation/test_ita_client.py -v -m integration

# For a quick smoke test with a known-working route:
python -c "
from automation.ita_client import run_query
import asyncio
result = asyncio.run(run_query('FORCE AA:JFK-LHR-JFK', 'JFK', 'JFK', date(2026, 5, 15)))
print(result)
"
```

## Files Changed
- New: all files in `automation/` listed above
- New: `automation/data/user_agents.json`
- New: `tests/test_automation/test_ita_client.py`
- New: `.gitignore` entry for `automation/screenshots/`
