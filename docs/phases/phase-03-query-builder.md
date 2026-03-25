# Phase 03 — ITA Matrix Query Builder

## Goal
Build the module that translates a `DumpPattern` record into an ITA Matrix routing code string, and also generates the complete `ManualInputBundle`. This phase has zero external dependencies — it's pure Python logic that can be fully unit tested without a browser or database.

## Deliverables

- [ ] `automation/query_builder.py` — builds ITA routing code strings from pattern data
- [ ] `automation/manual_input.py` — generates complete `ManualInputBundle` from pattern + validation result
- [ ] `docs/ita_routing_codes.md` — reference doc for ITA Matrix routing code syntax
- [ ] Comprehensive unit tests in `tests/test_automation/test_query_builder.py`
- [ ] At least 10 real-world example patterns as test fixtures (cover all 4 dump types)

## Query Builder Logic

### Input
A `DumpPattern` record with:
- `origin_iata`, `destination_iata`
- `ticketing_carrier_iata`
- `operating_carriers` (ordered list)
- `routing_points` (via/TP points)
- `dump_type`
- `fare_basis_hint` (optional)

### Output
A string ready to paste into ITA Matrix's routing codes field.

### Rules by Dump Type

**TP_DUMP**
```
# Ticketing Point dump: routing via a specific city to break YQ chain
# Example: JFK-FRA-BKK (LH throughout, but TP in FRA prevents transatlantic YQ)
FORCE LH:JFK-FRA / FORCE LH:FRA-BKK / FORCE AA:BKK-JFK
```

**CARRIER_SWITCH**
```
# Use a no-YQ carrier on the long haul sector
# Example: JFK-DOH (QR, no YQ) then QR metal to final destination
FORCE QR:JFK-DOH-BKK / FORCE AA:BKK-JFK
```

**FARE_BASIS**
```
# Specific fare basis codes that structurally exclude YQ
# Must include fare basis hint in the routing code
FORCE LH:JFK-FRA-BKK BC=YLOWUS / FORCE AA:BKK-JFK
```

**ALLIANCE_RULE**
```
# Alliance interline agreement waives YQ between specific partner pairs
# Typically requires specific ticketing carrier designation
FORCE BA/AA:JFK-LHR-SYD / FORCE BA/AA:SYD-LHR-JFK
```

### Backup Routing Generation
If a primary routing uses carrier X, attempt to generate a backup using:
- Same alliance partners of X
- Same routing points but substitute sister carrier (LH → LX, LX → OS, etc.)
- Store as `backup_routing_code` in the bundle

## Manual Input Bundle Generation

`manual_input.py` must generate fully human-readable step-by-step instructions. The steps must never reference internal IDs or database fields. Example output for a TP dump:

```
1. Open matrix.itasoftware.com in your browser
2. Set origin: JFK, destination: JFK (roundtrip to yourself)
   OR set origin: JFK, destination: BKK if searching one-way fares
3. Set outbound date: [use a date 3–6 weeks out for best availability]
4. Click "More options" below the search form
5. Find the "Routing codes" text field
6. Paste exactly: FORCE LH:JFK-FRA / FORCE LH:FRA-BKK / FORCE AA:BKK-JFK
7. Click "Search flights"
8. In results, look for fares priced around $[base_fare_estimate] — these are the ones without YQ
9. Click a fare to expand the construction table
10. Verify: YQ column should show $0.00 on the AA/LH sectors
11. If YQ still shows: try the backup routing code instead (see below)
```

## ITA Routing Code Reference (`docs/ita_routing_codes.md`)

This doc must cover:
- Basic syntax: `FORCE carrier:routing`
- Ticketing point syntax
- Fare class/basis code forcing: `BC=CODE`
- Connection time constraints: `MINCONNECT H:MM`
- Nonstop forcing: `NONSTOP carrier`
- Combining multiple segments with `/`
- Common pitfalls (case sensitivity, spaces, carrier code format)

Build this from existing knowledge of ITA Matrix advanced features. This doc is used by agents as a reference and by future Opus sessions implementing the automation.

## Test Fixtures

Create `tests/fixtures/dump_patterns.json` with 10+ example patterns:
- At least 2 TP_DUMPs (different carrier groups)
- At least 2 CARRIER_SWITCHes
- At least 1 FARE_BASIS
- At least 1 ALLIANCE_RULE
- At least 1 with a backup routing
- At least 1 with a fare basis hint

## Completion Check

```bash
cd backend && pytest tests/test_automation/test_query_builder.py -v
# All tests should pass, including round-trip: pattern → routing code → manual bundle
```

## Files Changed
- New: `automation/query_builder.py`
- New: `automation/manual_input.py`
- New: `docs/ita_routing_codes.md`
- New: `tests/test_automation/test_query_builder.py`
- New: `tests/fixtures/dump_patterns.json`
