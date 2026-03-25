# CLAUDE.md — Agent Dashboard (Frontend)

## Overview

A Next.js 14 application for travel agents. The UI is **utility-first** — it prioritizes speed of use and information density over visual polish. Agents need to see working dump patterns quickly and extract manual inputs in seconds.

## Directory Structure

```
frontend/
├── CLAUDE.md              ← you are here
├── package.json
├── app/                   ← Next.js App Router
│   ├── layout.tsx
│   ├── page.tsx           ← redirects to /patterns
│   ├── patterns/
│   │   ├── page.tsx       ← pattern leaderboard (main view)
│   │   └── [id]/
│   │       └── page.tsx   ← pattern detail + manual input
│   ├── carriers/
│   │   └── page.tsx       ← YQ tracker / carrier list
│   └── validations/
│       └── page.tsx       ← validation run history
├── components/
│   ├── PatternCard.tsx
│   ├── ManualInputBundle.tsx   ← KEY COMPONENT (see below)
│   ├── ValidationBadge.tsx
│   ├── LifecycleBadge.tsx
│   └── ConfidenceBar.tsx
└── lib/
    └── api.ts             ← typed API client
```

## Key Views

### Pattern Leaderboard (`/patterns`)
The main agent view. Shows all `active` patterns sorted by `expected_yq_savings_usd DESC`.

Columns:
- Route (JFK → BKK)
- Dump Type badge
- Carriers involved
- YQ Savings (large, bold)
- Confidence bar
- Freshness (how recently validated)
- Lifecycle state badge
- Quick-action: "Get Manual Input" button

Filters:
- By origin/destination (freetext airport code)
- By dump type
- By carrier
- Min confidence slider
- Min savings threshold

### Pattern Detail (`/patterns/[id]`)
Full details + manual input bundle.

Left panel: pattern metadata, validation history chart, confidence trend.

Right panel: **Manual Input Bundle** (the most important thing on this page).

### ManualInputBundle Component — CRITICAL

This component is the most important in the entire frontend. It must:
1. Display the `routing_code_string` in a monospace code block with a one-click copy button
2. Display `human_description` in plain English
3. Show numbered `ita_matrix_steps` as a checklist (agents can check them off as they go)
4. Show `expected_yq_savings_usd` prominently
5. Show validation timestamp and confidence
6. Show `backup_routing_code` in a collapsible "If this fails..." section
7. Show `notes` field
8. Have a "Download as PDF" option (single-page cheat sheet for agent use)
9. Have a "Print" option

The manual input bundle should be usable with zero context — a new agent who has never seen the system should be able to use it to replicate the fare construction manually.

### YQ Tracker (`/carriers`)
Table of carriers with YQ data:
- Carrier name + IATA code
- Alliance
- Current typical YQ (USD)
- Last updated
- "charges YQ" boolean badge

Sorted by YQ amount descending by default. Agents use this to prioritize which routes to hunt.

## State Management

- No Redux / Zustand in MVP — use React Query for server state, `useState` for local UI state
- React Query key conventions: `['patterns', filters]`, `['pattern', id]`, `['validations', patternId]`

## API Client (`lib/api.ts`)

Typed wrapper around `fetch`. All calls go to `/api/v1/*` (proxied to FastAPI backend in Next.js config).

Always include `X-API-Key` header from environment variable `NEXT_PUBLIC_API_KEY` (for MVP; replace with proper auth in production).

## Styling

- Tailwind CSS utility classes only
- Color conventions:
  - `active` lifecycle: green
  - `degrading`: amber/yellow
  - `deprecated`: red
  - `archived`: gray
  - High confidence (>0.75): green
  - Medium confidence (0.4–0.75): amber
  - Low confidence (<0.4): red

## What NOT to Do

- Do not show `deprecated` or `archived` patterns on the leaderboard — filter them out in the API call
- Do not auto-refresh the page — agents are often mid-copy when the page updates; use a manual refresh button
- Do not require login in MVP — API key in env var is sufficient for a small agent team
- Do not build a mobile-responsive layout in MVP — agents use desktop
