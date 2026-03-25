# Phase 10 — Agent Dashboard (UI)

## Goal
Build the Next.js agent dashboard. Agents use this to browse working dump patterns, get manual input bundles, and monitor validation health.

## Deliverables

- [ ] `frontend/package.json` with all dependencies
- [ ] `frontend/app/layout.tsx` — root layout with nav
- [ ] `frontend/app/patterns/page.tsx` — pattern leaderboard
- [ ] `frontend/app/patterns/[id]/page.tsx` — pattern detail
- [ ] `frontend/app/carriers/page.tsx` — YQ tracker
- [ ] `frontend/app/validations/page.tsx` — validation history
- [ ] `frontend/components/ManualInputBundle.tsx` — CRITICAL (see below)
- [ ] `frontend/components/PatternCard.tsx`
- [ ] `frontend/components/ValidationBadge.tsx`
- [ ] `frontend/components/LifecycleBadge.tsx`
- [ ] `frontend/components/ConfidenceBar.tsx`
- [ ] `frontend/lib/api.ts` — typed API client
- [ ] `frontend/next.config.js` — API proxy to backend

## Dependencies

```json
{
  "dependencies": {
    "next": "14.x",
    "react": "18.x",
    "react-dom": "18.x",
    "@tanstack/react-query": "5.x",
    "tailwindcss": "3.x"
  },
  "devDependencies": {
    "typescript": "5.x",
    "@types/react": "18.x",
    "eslint": "8.x"
  }
}
```

## ManualInputBundle Component (Most Important)

This is the most important component. It must be:
- **Self-contained**: An agent with no prior context can use it
- **Copy-friendly**: Every code/string has a one-click copy button
- **Print-friendly**: Renders cleanly when printed (agents print cheat sheets)

```tsx
interface ManualInputBundleProps {
  bundle: ManualInputBundle;
  showValidationMeta?: boolean; // show confidence/timestamp (default true)
}
```

Layout:
```
┌─────────────────────────────────────────────────────────┐
│  ROUTING CODE                              [Copy]        │
│  ┌─────────────────────────────────────────────────┐   │
│  │  FORCE LH:JFK-FRA / FORCE LH:FRA-BKK / ...     │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
│  ROUTE                                                   │
│  JFK → Frankfurt (LH, nonstop) → Bangkok (LH)           │
│  Bangkok → JFK (AA, nonstop)                             │
│  Dump mechanism: Ticketing Point in FRA                  │
│                                                          │
│  STEP-BY-STEP INSTRUCTIONS                               │
│  ☐ 1. Go to matrix.itasoftware.com                      │
│  ☐ 2. Enter JFK as origin, JFK as destination ...       │
│  ☐ 3. Set outbound date 3–6 weeks out                   │
│  ☐ 4. Click "More options" → "Routing Codes"             │
│  ☐ 5. Paste the routing code above                       │
│  ☐ 6. Click Search                                       │
│  ☐ 7. Look for fares with YQ = $0.00                    │
│                                                          │
│  EXPECTED SAVINGS     VALIDATED           CONFIDENCE     │
│  $580 YQ avoided      2 days ago         ████████░░ 87% │
│                                                          │
│  NOTES                                                   │
│  Works on Y and M fare classes. LH charges ~$580 YQ...  │
│                                                          │
│  ▼ If this fails — try backup routing              [+]  │
│  ┌─────────────────────────────────────────────────┐   │
│  │  FORCE LX:JFK-ZRH-BKK / FORCE AA:BKK-JFK       │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
│  [Download PDF]  [Print]                                 │
└─────────────────────────────────────────────────────────┘
```

The checklist items should be interactive (checkboxes that agents can tick as they go). State is local to the session (no persistence needed).

## Pattern Leaderboard Page

Sort order: `expected_yq_savings_usd DESC` (default). Agents care most about maximum savings.

Columns:
- Route (origin → destination)
- Dump Type badge (color-coded)
- Carriers (ticketing carrier prominently, operating carriers smaller)
- **YQ Savings** (large, bold green)
- Confidence (colored bar)
- Last Validated (relative time: "2 days ago")
- State badge

Filter panel (collapsible, left side):
- Origin / Destination (freetext IATA code inputs)
- Dump Type checkboxes
- Min Confidence slider (0–100%)
- Min Savings ($0–$1000 slider)
- Carrier select (searchable dropdown from carriers API)

**"Get Manual Input" button** on each row opens a modal with the `ManualInputBundle` component. Agents shouldn't need to navigate away just to get the routing code.

## Carriers Page (YQ Tracker)

Table sorted by `typical_yq_usd DESC`. Columns:
- Carrier name + code
- Alliance badge
- YQ Amount (USD) — in big text
- Last Updated (relative time)
- "Charges YQ" yes/no badge

Purpose: agents use this to identify which airlines to target for dump hunting.

## Validation History Page

Shows recent validation runs across all patterns. Useful for monitoring system health.
Columns: Pattern route, run time, success/fail, YQ result, duration.
Filter: last 24h / 7d / 30d.

## API Proxy (`next.config.js`)

```js
rewrites: async () => [
  {
    source: "/api/v1/:path*",
    destination: `${process.env.BACKEND_URL}/api/v1/:path*`,
  },
],
```

This keeps the API key server-side (set in Next.js server env, never exposed to browser).

## Color Reference (Tailwind)

```
lifecycle active: text-green-700 bg-green-100
lifecycle degrading: text-amber-700 bg-amber-100
lifecycle deprecated: text-red-700 bg-red-100
lifecycle archived: text-gray-500 bg-gray-100

confidence high (>0.75): text-green-600
confidence medium (0.4–0.75): text-amber-600
confidence low (<0.4): text-red-600

dump type TP_DUMP: bg-blue-100 text-blue-800
dump type CARRIER_SWITCH: bg-purple-100 text-purple-800
dump type FARE_BASIS: bg-teal-100 text-teal-800
dump type ALLIANCE_RULE: bg-orange-100 text-orange-800
```

## Completion Check

```bash
cd frontend && npm install && npm run dev

# Check leaderboard loads
open http://localhost:3000/patterns

# Check manual input modal works on first pattern
# Click "Get Manual Input" → verify routing code is copyable
# Verify backup routing is in collapsible section
# Verify steps are checkboxable
# Click "Print" → verify clean print layout
```

## Files Changed
- New: all files in `frontend/`
- Modified: `docker-compose.yml` (add frontend service)
