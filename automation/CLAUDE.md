# CLAUDE.md — ITA Matrix Automation

## Overview

This module contains all Playwright-based browser automation for querying ITA Matrix (matrix.itasoftware.com).

## Directory Structure

```
automation/
├── CLAUDE.md             ← you are here
├── browser.py            ← Playwright browser/context lifecycle
├── ita_client.py         ← Main ITA Matrix interaction logic
├── query_builder.py      ← Constructs ITA Matrix routing code strings
├── result_parser.py      ← Parses fare breakdown from ITA Matrix results page
├── manual_input.py       ← Generates 1:1 manual input bundles
├── proxy_manager.py      ← Rotating residential proxy pool
└── rate_limiter.py       ← Request throttling with jitter
```

## ITA Matrix Interaction Model

### How ITA Matrix Works (for automation purposes)
1. Navigate to `https://matrix.itasoftware.com`
2. Enter origin/destination airports in the search form
3. Set travel dates
4. In the **Routing Codes** field (advanced options), enter the routing code string
5. Submit search
6. Wait for results page to load (SPA — must wait for specific DOM elements)
7. Click on a specific fare to see the full breakdown including YQ/YR/taxes
8. Parse the fare construction table

### Routing Code Syntax
ITA Matrix uses a proprietary routing code DSL. Key elements:
- `MINCONNECT 0:30` — minimum connection time
- `FORCE LH:JFK-FRA` — force specific carrier on a leg
- `FORCE QR` — force carrier for all legs
- `NONSTOP LH` — nonstop on carrier
- Ticketing Point: specified via the origin booking class or TP routing syntax
- Full syntax reference: maintained in `docs/ita_routing_codes.md` (to be built in Phase 3)

### Human-Like Behavior Requirements
ITA Matrix has bot detection. Every session must:
- Use a realistic viewport (1280x800 or 1440x900)
- Randomize mouse movement paths (not straight lines)
- Add realistic delays between keystrokes (30–120ms per character)
- Wait realistically between page actions (1.5s–4s)
- Use residential proxy rotation (new proxy per session)
- Randomize user agent strings from a pool of real browser UAs

## Rate Limiting

```
MIN_DELAY = 3.5 seconds between requests (from config)
JITTER = random float 0.0–2.0 seconds added on top
DAILY_LIMIT = 200 requests per proxy (rotate before this)
SESSION_LIMIT = 15 requests per browser session (then restart)
```

Never exceed SESSION_LIMIT without restarting the browser context. ITA Matrix tracks session state.

## Manual Input Bundle Format

Every automation run must also generate this structured object:

```json
{
  "routing_code_string": "FORCE LH:JFK-FRA-BKK / NONSTOP AA:BKK-JFK",
  "human_description": "JFK → Frankfurt (LH, nonstop) → Bangkok (LH) // Bangkok → JFK (AA, nonstop). Ticketing point: Frankfurt. Dump mechanism: TP forces YQ carrier switch.",
  "ita_matrix_steps": [
    "1. Go to matrix.itasoftware.com",
    "2. Enter JFK as origin, JFK as destination (roundtrip)",
    "3. Set outbound date to [DATE]",
    "4. Click 'More options' → 'Routing Codes'",
    "5. Paste: FORCE LH:JFK-FRA-BKK / NONSTOP AA:BKK-JFK",
    "6. Click Search",
    "7. Look for fares with YQ = $0 on the AA segment"
  ],
  "expected_yq_savings_usd": 580.00,
  "expected_yq_carrier": "LH",
  "validation_timestamp": "2026-03-24T10:30:00Z",
  "confidence_score": 0.87,
  "backup_routing_code": "FORCE LX:JFK-ZRH-BKK / NONSTOP AA:BKK-JFK",
  "notes": "Works on Y and M fare classes. LH charges ~$580 YQ on transatlantic; this construction bypasses it via TP in FRA."
}
```

The `ita_matrix_steps` array must always have numbered, copy-paste-ready steps. This is the fallback for when automation fails.

## Error Handling

- `TimeoutError` on page load → retry once with fresh proxy, then mark run as `error`
- `ParseError` on fare breakdown → log raw HTML snapshot for debugging, mark run as `error`
- `BotDetectionError` (CAPTCHA or redirect) → rotate proxy immediately, pause 15 minutes, alert
- Never raise exceptions from automation to the service layer — return a structured result object with `success: bool` and `error_message: str | None`

## Proxy Pool

- Stored in config as a list of proxy connection strings
- `proxy_manager.py` tracks usage count per proxy and rotates before daily limit
- On bot detection, immediately retire the proxy for 24h
- Proxy health check runs every 4 hours

## Result Parser

The result parser must extract from ITA Matrix's fare construction display:
- Base fare (USD equivalent)
- YQ amount per direction and total
- YR amount
- All other taxes (breakdown)
- Fare basis code per segment
- Carrier per segment (ticketing vs operating)
- Total price

The fare construction table in ITA Matrix is rendered dynamically. Use `page.wait_for_selector()` with a meaningful timeout before attempting to parse.
