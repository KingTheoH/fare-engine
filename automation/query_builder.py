"""
query_builder.py — Constructs ITA Matrix routing code strings from pattern data.

This is pure Python logic with zero external dependencies.
Given a pattern's dump type, carriers, and routing points, it generates
the exact string to paste into ITA Matrix's "Routing codes" field.

Routing code DSL rules:
- Segments separated by " / "
- Each segment: "FORCE <carrier>:<origin>-<via1>-<via2>-<destination>"
- Fare basis forcing: append " BC=<code>" to segment
- Alliance interline: "FORCE <carrier1>/<carrier2>:<routing>"
- Case-sensitive carrier codes (2-letter IATA)
- Airport codes (3-letter IATA)
"""

from dataclasses import dataclass

# Sister carrier substitution map for backup routing generation.
# When primary carrier X fails, try these alliance partners.
SISTER_CARRIERS: dict[str, list[str]] = {
    # Star Alliance
    "LH": ["LX", "OS", "SN"],
    "LX": ["LH", "OS", "SN"],
    "OS": ["LH", "LX", "SN"],
    "SN": ["LH", "LX", "OS"],
    "NH": ["LH", "LX"],
    "SK": ["LH", "LX"],
    "AY": ["LH", "LX"],
    "LO": ["LH", "LX"],
    "TP": ["LH", "LX"],
    # oneworld
    "BA": ["AA", "IB", "QF"],
    "AA": ["BA", "IB", "QF"],
    "IB": ["BA", "AA"],
    "QF": ["BA", "AA", "CX"],
    "CX": ["BA", "AA", "QF"],
    "JL": ["BA", "AA"],
    # SkyTeam
    "AF": ["KL", "AZ"],
    "KL": ["AF", "AZ"],
    "AZ": ["AF", "KL"],
    "KE": ["AF", "KL"],
    "OZ": ["KE", "AF"],
    # Middle East (no traditional alliance but low/no YQ)
    "QR": ["EK", "EY"],
    "EK": ["QR", "EY"],
    "EY": ["QR", "EK"],
    "TK": ["LH"],  # Star Alliance member
    "ET": ["LH"],  # Star Alliance member
}

# Hub airports for sister carriers — used in backup routing generation
CARRIER_HUBS: dict[str, str] = {
    "LH": "FRA",
    "LX": "ZRH",
    "OS": "VIE",
    "SN": "BRU",
    "BA": "LHR",
    "AA": "DFW",
    "IB": "MAD",
    "AF": "CDG",
    "KL": "AMS",
    "QR": "DOH",
    "EK": "DXB",
    "EY": "AUH",
    "TK": "IST",
    "CX": "HKG",
    "SQ": "SIN",
    "NH": "NRT",
    "JL": "NRT",
    "KE": "ICN",
    "OZ": "ICN",
    "QF": "SYD",
    "SK": "CPH",
    "AY": "HEL",
    "LO": "WAW",
    "TP": "LIS",
    "AZ": "FCO",
    "ET": "ADD",
    "RJ": "AMM",
    "MS": "CAI",
    "LA": "SCL",
}


@dataclass
class PatternInput:
    """
    Minimal input needed to build a routing code.
    Decoupled from the ORM model so this module has zero DB dependencies.
    """

    dump_type: str  # TP_DUMP, CARRIER_SWITCH, FARE_BASIS, ALLIANCE_RULE
    origin_iata: str
    destination_iata: str
    ticketing_carrier_iata: str
    operating_carriers: list[str]
    routing_points: list[str]
    fare_basis_hint: str | None = None


def build_routing_code(pattern: PatternInput) -> str:
    """
    Build an ITA Matrix routing code string from a pattern.

    Returns the exact string to paste into the ITA Matrix "Routing codes" field.

    Raises ValueError if the pattern has insufficient data for its dump type.
    """
    builder = _BUILDERS.get(pattern.dump_type)
    if builder is None:
        raise ValueError(f"Unknown dump type: {pattern.dump_type}")
    return builder(pattern)


def generate_backup_routing_code(pattern: PatternInput) -> str | None:
    """
    Generate an alternate routing code by substituting the ticketing carrier
    with a sister carrier from the same alliance.

    Returns None if no suitable sister carrier exists.
    """
    sisters = SISTER_CARRIERS.get(pattern.ticketing_carrier_iata, [])
    if not sisters:
        return None

    sister = sisters[0]  # Primary sister carrier
    sister_hub = CARRIER_HUBS.get(sister)

    # Build a new pattern with the sister carrier substituted
    new_routing_points = list(pattern.routing_points)

    # If the sister has a different hub, substitute the first routing point
    if sister_hub and new_routing_points:
        original_hub = CARRIER_HUBS.get(pattern.ticketing_carrier_iata)
        if original_hub and original_hub in new_routing_points:
            new_routing_points = [
                sister_hub if rp == original_hub else rp for rp in new_routing_points
            ]
    elif sister_hub and not new_routing_points and pattern.dump_type == "TP_DUMP":
        # TP dump needs a routing point — use sister's hub
        new_routing_points = [sister_hub]

    # Replace ticketing carrier in operating carriers
    new_operating = [
        sister if oc == pattern.ticketing_carrier_iata else oc
        for oc in pattern.operating_carriers
    ]

    backup_pattern = PatternInput(
        dump_type=pattern.dump_type,
        origin_iata=pattern.origin_iata,
        destination_iata=pattern.destination_iata,
        ticketing_carrier_iata=sister,
        operating_carriers=new_operating,
        routing_points=new_routing_points,
        fare_basis_hint=pattern.fare_basis_hint,
    )

    try:
        return build_routing_code(backup_pattern)
    except ValueError:
        return None


# ─── Private builders per dump type ────────────────────────────────────────


def _build_tp_dump(pattern: PatternInput) -> str:
    """
    Ticketing Point dump: route via a specific city to break the YQ chain.

    Structure: FORCE <carrier>:<origin>-<tp> / FORCE <carrier>:<tp>-<dest> / FORCE <return_carrier>:<dest>-<origin>
    The TP point breaks the YQ assessment — the surcharge is per-segment,
    and the TP point creates separate pricing units.
    """
    segments = []
    cities = [pattern.origin_iata] + pattern.routing_points + [pattern.destination_iata]

    for i in range(len(cities) - 1):
        carrier = (
            pattern.operating_carriers[i]
            if i < len(pattern.operating_carriers)
            else pattern.ticketing_carrier_iata
        )
        segments.append(f"FORCE {carrier}:{cities[i]}-{cities[i + 1]}")

    # Add return segment if last operating carrier differs (roundtrip construction)
    if len(pattern.operating_carriers) > len(cities) - 1:
        return_carrier = pattern.operating_carriers[-1]
        segments.append(
            f"FORCE {return_carrier}:{pattern.destination_iata}-{pattern.origin_iata}"
        )

    return " / ".join(segments)


def _build_carrier_switch(pattern: PatternInput) -> str:
    """
    Carrier Switch dump: use a no-YQ carrier on the surcharge-bearing sector.

    Structure: FORCE <no_yq_carrier>:<origin>-<via1>-...-<dest> / FORCE <return_carrier>:<dest>-<origin>
    The long-haul sector uses a carrier that doesn't charge YQ.
    """
    segments = []

    # Build outbound: carrier with routing through any connection points
    outbound_carrier = pattern.ticketing_carrier_iata
    outbound_cities = [pattern.origin_iata] + pattern.routing_points + [pattern.destination_iata]
    outbound_route = "-".join(outbound_cities)
    segments.append(f"FORCE {outbound_carrier}:{outbound_route}")

    # Return segment if there's a different return carrier
    if len(pattern.operating_carriers) > 1:
        return_carrier = pattern.operating_carriers[-1]
        if return_carrier != outbound_carrier:
            segments.append(
                f"FORCE {return_carrier}:{pattern.destination_iata}-{pattern.origin_iata}"
            )

    return " / ".join(segments)


def _build_fare_basis(pattern: PatternInput) -> str:
    """
    Fare Basis dump: specific fare basis codes structurally exclude YQ.

    Structure: FORCE <carrier>:<origin>-<via>-<dest> BC=<fare_basis> / FORCE <return_carrier>:<dest>-<origin>
    The fare basis code triggers a pricing rule that excludes YQ.
    """
    if not pattern.fare_basis_hint:
        raise ValueError("FARE_BASIS dump requires fare_basis_hint to be set")

    segments = []

    # Outbound with fare basis
    outbound_cities = [pattern.origin_iata] + pattern.routing_points + [pattern.destination_iata]
    outbound_route = "-".join(outbound_cities)
    outbound_carrier = pattern.ticketing_carrier_iata
    segments.append(f"FORCE {outbound_carrier}:{outbound_route} BC={pattern.fare_basis_hint}")

    # Return segment
    if len(pattern.operating_carriers) > 1:
        return_carrier = pattern.operating_carriers[-1]
        segments.append(
            f"FORCE {return_carrier}:{pattern.destination_iata}-{pattern.origin_iata}"
        )

    return " / ".join(segments)


def _build_alliance_rule(pattern: PatternInput) -> str:
    """
    Alliance Rule dump: interline agreement between carrier pairs waives YQ.

    Structure: FORCE <carrier1>/<carrier2>:<origin>-<via>-<dest> / FORCE <carrier1>/<carrier2>:<dest>-<via>-<origin>
    The joint carrier designation triggers an interline pricing rule.
    """
    if len(pattern.operating_carriers) < 2:
        raise ValueError("ALLIANCE_RULE dump requires at least 2 operating carriers")

    # Use the first two unique carriers for the alliance pair
    unique_carriers = []
    for c in pattern.operating_carriers:
        if c not in unique_carriers:
            unique_carriers.append(c)
        if len(unique_carriers) == 2:
            break

    if len(unique_carriers) < 2:
        raise ValueError("ALLIANCE_RULE dump requires 2 distinct operating carriers")

    carrier_pair = f"{unique_carriers[0]}/{unique_carriers[1]}"

    # Outbound
    outbound_cities = [pattern.origin_iata] + pattern.routing_points + [pattern.destination_iata]
    outbound_route = "-".join(outbound_cities)

    # Return (reverse routing points)
    return_cities = (
        [pattern.destination_iata]
        + list(reversed(pattern.routing_points))
        + [pattern.origin_iata]
    )
    return_route = "-".join(return_cities)

    return f"FORCE {carrier_pair}:{outbound_route} / FORCE {carrier_pair}:{return_route}"


# Builder dispatch table
_BUILDERS = {
    "TP_DUMP": _build_tp_dump,
    "CARRIER_SWITCH": _build_carrier_switch,
    "FARE_BASIS": _build_fare_basis,
    "ALLIANCE_RULE": _build_alliance_rule,
}
