"""
manual_input.py — Generates complete ManualInputBundle from pattern data.

The ManualInputBundle is the most important output of the system.
It must be completely self-contained: an agent with zero context
should be able to follow the steps and replicate the fare construction.

This module is pure Python — no DB or browser dependencies.
"""

from datetime import datetime, timezone

from automation.query_builder import (
    CARRIER_HUBS,
    PatternInput,
    build_routing_code,
    generate_backup_routing_code,
)

# Human-readable dump type descriptions for notes
_DUMP_DESCRIPTIONS = {
    "TP_DUMP": (
        "Ticketing Point manipulation — the routing breaks the YQ assessment "
        "into separate pricing units at the TP city, preventing the carrier's "
        "fuel surcharge from being applied to the full itinerary."
    ),
    "CARRIER_SWITCH": (
        "Carrier Switch — the long-haul sector uses a carrier that does not "
        "charge YQ (fuel surcharge), bypassing the high-YQ carrier entirely "
        "on the surcharge-bearing segment."
    ),
    "FARE_BASIS": (
        "Fare Basis exclusion — the specific fare basis code triggers a pricing "
        "rule that structurally excludes YQ from the fare construction."
    ),
    "ALLIANCE_RULE": (
        "Alliance interline rule — the joint carrier designation between alliance "
        "partners triggers an interline pricing agreement that waives YQ under "
        "the codeshare/interline terms."
    ),
}

# City name lookup for human-readable descriptions
_CITY_NAMES: dict[str, str] = {
    "JFK": "New York (JFK)",
    "EWR": "Newark (EWR)",
    "LAX": "Los Angeles (LAX)",
    "SFO": "San Francisco (SFO)",
    "ORD": "Chicago (ORD)",
    "DFW": "Dallas (DFW)",
    "MIA": "Miami (MIA)",
    "IAD": "Washington (IAD)",
    "BOS": "Boston (BOS)",
    "SEA": "Seattle (SEA)",
    "ATL": "Atlanta (ATL)",
    "FRA": "Frankfurt (FRA)",
    "MUC": "Munich (MUC)",
    "LHR": "London Heathrow (LHR)",
    "LGW": "London Gatwick (LGW)",
    "CDG": "Paris (CDG)",
    "AMS": "Amsterdam (AMS)",
    "ZRH": "Zurich (ZRH)",
    "VIE": "Vienna (VIE)",
    "BRU": "Brussels (BRU)",
    "MAD": "Madrid (MAD)",
    "FCO": "Rome (FCO)",
    "CPH": "Copenhagen (CPH)",
    "HEL": "Helsinki (HEL)",
    "WAW": "Warsaw (WAW)",
    "LIS": "Lisbon (LIS)",
    "IST": "Istanbul (IST)",
    "DOH": "Doha (DOH)",
    "DXB": "Dubai (DXB)",
    "AUH": "Abu Dhabi (AUH)",
    "BKK": "Bangkok (BKK)",
    "SIN": "Singapore (SIN)",
    "HKG": "Hong Kong (HKG)",
    "NRT": "Tokyo Narita (NRT)",
    "HND": "Tokyo Haneda (HND)",
    "ICN": "Seoul (ICN)",
    "SYD": "Sydney (SYD)",
    "MEL": "Melbourne (MEL)",
    "ADD": "Addis Ababa (ADD)",
    "AMM": "Amman (AMM)",
    "CAI": "Cairo (CAI)",
    "SCL": "Santiago (SCL)",
    "GRU": "São Paulo (GRU)",
}

# Carrier name lookup
_CARRIER_NAMES: dict[str, str] = {
    "LH": "Lufthansa",
    "LX": "SWISS",
    "OS": "Austrian",
    "SN": "Brussels Airlines",
    "BA": "British Airways",
    "AA": "American Airlines",
    "UA": "United Airlines",
    "DL": "Delta",
    "IB": "Iberia",
    "AF": "Air France",
    "KL": "KLM",
    "QR": "Qatar Airways",
    "EK": "Emirates",
    "EY": "Etihad",
    "TK": "Turkish Airlines",
    "CX": "Cathay Pacific",
    "SQ": "Singapore Airlines",
    "NH": "ANA",
    "JL": "Japan Airlines",
    "KE": "Korean Air",
    "OZ": "Asiana",
    "QF": "Qantas",
    "SK": "SAS",
    "AY": "Finnair",
    "LO": "LOT Polish",
    "TP": "TAP Portugal",
    "AZ": "ITA Airways",
    "ET": "Ethiopian Airlines",
    "RJ": "Royal Jordanian",
    "MS": "EgyptAir",
    "LA": "LATAM",
    "VS": "Virgin Atlantic",
}


def _city_name(iata: str) -> str:
    """Get human-readable city name, falling back to raw IATA code."""
    return _CITY_NAMES.get(iata, iata)


def _carrier_name(iata: str) -> str:
    """Get human-readable carrier name, falling back to raw IATA code."""
    return _CARRIER_NAMES.get(iata, iata)


def build_human_description(pattern: PatternInput) -> str:
    """
    Build a plain-English route description.

    Example: "JFK → Frankfurt (LH) → Bangkok (LH) // Bangkok → JFK (AA)"
    """
    # Outbound segments
    cities = [pattern.origin_iata] + pattern.routing_points + [pattern.destination_iata]
    outbound_parts = []
    for i, city in enumerate(cities):
        if i == 0:
            outbound_parts.append(_city_name(city))
        else:
            carrier = (
                pattern.operating_carriers[i - 1]
                if i - 1 < len(pattern.operating_carriers)
                else pattern.ticketing_carrier_iata
            )
            outbound_parts.append(f"{_city_name(city)} ({carrier})")

    outbound = " → ".join(outbound_parts)

    # Return segment (if there's a dedicated return carrier)
    if len(pattern.operating_carriers) > len(cities) - 1:
        return_carrier = pattern.operating_carriers[-1]
        return_segment = (
            f"{_city_name(pattern.destination_iata)} → "
            f"{_city_name(pattern.origin_iata)} ({return_carrier})"
        )
        return f"{outbound} // {return_segment}"

    return outbound


def build_ita_matrix_steps(
    pattern: PatternInput,
    routing_code: str,
    backup_code: str | None = None,
) -> list[str]:
    """
    Build numbered, self-contained step-by-step instructions for an agent.

    These steps must be usable with zero prior context.
    """
    steps = [
        "1. Open matrix.itasoftware.com in your browser",
        f"2. Set origin: {pattern.origin_iata}, destination: {pattern.origin_iata} (roundtrip to same city)",
        "3. Set outbound date to a date 3–6 weeks from now for best availability",
        "4. Set return date 7–14 days after outbound",
        "5. Click 'More options' below the search form",
        "6. Find the 'Routing codes' text field",
        f"7. Paste exactly: {routing_code}",
        "8. Click 'Search flights'",
        "9. Wait for results to load (may take 15–30 seconds)",
        (
            f"10. In results, look for fares from {_carrier_name(pattern.ticketing_carrier_iata)} "
            f"({pattern.ticketing_carrier_iata}) — these should show reduced or zero YQ"
        ),
        "11. Click on a fare to expand the full price breakdown",
        (
            f"12. Verify: the YQ column should show $0.00 (or near-$0) on the "
            f"{pattern.ticketing_carrier_iata} sectors"
        ),
    ]

    if backup_code:
        steps.append(
            f"13. If YQ still shows a charge, try the backup routing code instead: {backup_code}"
        )

    return steps


def build_notes(pattern: PatternInput) -> str:
    """Build informational notes about the dump mechanism."""
    dump_desc = _DUMP_DESCRIPTIONS.get(pattern.dump_type, "")
    carrier_name = _carrier_name(pattern.ticketing_carrier_iata)
    hub = CARRIER_HUBS.get(pattern.ticketing_carrier_iata, "")

    parts = [f"Dump mechanism: {dump_desc}"]

    if pattern.dump_type == "TP_DUMP" and pattern.routing_points:
        tp_city = _city_name(pattern.routing_points[0])
        parts.append(f"Ticketing point: {tp_city}.")

    if pattern.fare_basis_hint:
        parts.append(f"Fare basis: {pattern.fare_basis_hint}.")

    parts.append(
        f"{carrier_name} ({pattern.ticketing_carrier_iata}) "
        f"typically charges high YQ on intercontinental routes"
        + (f" via {_city_name(hub)}" if hub else "")
        + "."
    )

    return " ".join(parts)


def generate_manual_input_bundle(
    pattern: PatternInput,
    expected_yq_savings_usd: float = 0.0,
    confidence_score: float = 0.0,
    validation_timestamp: datetime | None = None,
) -> dict:
    """
    Generate a complete ManualInputBundle dict from a pattern.

    Returns a dict matching the ManualInputBundle Pydantic schema shape.
    Can be validated with ManualInputBundle.model_validate(result).

    Args:
        pattern: The pattern input data.
        expected_yq_savings_usd: Expected savings from dumping YQ.
        confidence_score: Current confidence score (0.0–1.0).
        validation_timestamp: When this was last validated. Defaults to now.
    """
    routing_code = build_routing_code(pattern)
    backup_code = generate_backup_routing_code(pattern)

    if validation_timestamp is None:
        validation_timestamp = datetime.now(timezone.utc)

    steps = build_ita_matrix_steps(pattern, routing_code, backup_code)
    description = build_human_description(pattern)
    notes = build_notes(pattern)

    return {
        "routing_code_string": routing_code,
        "human_description": description,
        "ita_matrix_steps": steps,
        "expected_yq_savings_usd": expected_yq_savings_usd,
        "expected_yq_carrier": pattern.ticketing_carrier_iata,
        "validation_timestamp": validation_timestamp.isoformat(),
        "confidence_score": confidence_score,
        "backup_routing_code": backup_code,
        "notes": notes,
    }
