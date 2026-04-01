"""
strike_routes.py — Curated library of known strike segments.

A "strike segment" is a throwaway leg appended to the end of a routing
that zeroes YQ across the entire ticket. The segment is rarely flown —
its purpose is to trigger no-YQ fare construction rules.

Used for:
1. Grounding the LLM extraction prompt (real examples to recognise)
2. Soft-validating extracted strike_segment IATA codes in the normalizer
3. Reference for agents building manual searches
"""

from typing import TypedDict


class StrikeRoute(TypedDict):
    origin: str          # 3-letter IATA origin
    destination: str     # 3-letter IATA destination
    carrier: str         # 2-letter IATA carrier
    why: str             # Mechanism explanation
    active: bool         # Still being reported as working?
    notes: str           # Historical context / caveats


# ─── Known strike segments ─────────────────────────────────────────────────

KNOWN_STRIKE_ROUTES: list[StrikeRoute] = [
    {
        "origin": "SKD",
        "destination": "TAS",
        "carrier": "HY",
        "why": (
            "Uzbekistan Airways domestic segment. HY does not levy YQ, and their "
            "interline fare construction rules cause YQ to be zeroed on all through-ticketed "
            "sectors when HY is the final operating carrier on the itinerary."
        ),
        "active": False,
        "notes": (
            "The canonical strike segment — widely used 2022–2024 on LHR/CDG→BKK/SIN routes "
            "ticketed on BA, SQ, TG. Most major carriers patched their fare rules by late 2024. "
            "Still reported occasionally on less-watched routes."
        ),
    },
    {
        "origin": "TAS",
        "destination": "SKD",
        "carrier": "HY",
        "why": "Reverse direction of SKD→TAS — same mechanism, same carrier.",
        "active": False,
        "notes": "Less common than SKD→TAS but same effect when applicable.",
    },
    {
        "origin": "FRU",
        "destination": "OSS",
        "carrier": "QH",
        "why": (
            "Air Bishkek (QH) Kyrgyzstan domestic. No YQ charged. Used similarly to "
            "the HY trick on certain routings via Central Asia."
        ),
        "active": False,
        "notes": "Reported occasionally in 2023. Less documented than SKD→TAS.",
    },
    {
        "origin": "DXB",
        "destination": "AUH",
        "carrier": "FZ",
        "why": (
            "flydubai (FZ) domestic UAE segment. FZ does not charge YQ on short-haul. "
            "Used to break YQ chain on some Gulf carrier through-tickets."
        ),
        "active": False,
        "notes": "Patched quickly — only seen in 2022 reports.",
    },
]

# ─── Carriers with known strike-segment history ────────────────────────────

STRIKE_ROUTE_CARRIERS: set[str] = {
    route["carrier"] for route in KNOWN_STRIKE_ROUTES
}

# ─── Airport pairs with known strike-segment history ──────────────────────

STRIKE_ROUTE_PAIRS: set[tuple[str, str]] = {
    (route["origin"], route["destination"]) for route in KNOWN_STRIKE_ROUTES
}


# ─── Helpers ───────────────────────────────────────────────────────────────

def get_strike_route(origin: str, destination: str, carrier: str) -> StrikeRoute | None:
    """Look up a known strike route by its three identifiers."""
    for route in KNOWN_STRIKE_ROUTES:
        if (
            route["origin"] == origin.upper()
            and route["destination"] == destination.upper()
            and route["carrier"] == carrier.upper()
        ):
            return route
    return None


def is_known_strike_carrier(carrier: str) -> bool:
    """True if this carrier has ever been used as a strike-segment carrier."""
    return carrier.upper() in STRIKE_ROUTE_CARRIERS


def prompt_context() -> str:
    """
    Return a compact string suitable for inclusion in the LLM extraction prompt.
    Gives the model grounding context on what strike segments look like.
    """
    lines = ["Known historical strike segments (throwaway legs that zero YQ):"]
    for r in KNOWN_STRIKE_ROUTES:
        status = "active" if r["active"] else "mostly patched"
        lines.append(
            f"  - {r['origin']}→{r['destination']} on {r['carrier']} "
            f"({status}): {r['notes'].split('.')[0]}."
        )
    return "\n".join(lines)
