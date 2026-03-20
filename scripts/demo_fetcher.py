#!/usr/bin/env python3
"""
Demo fetcher — returns realistic mock flight data so the app works without any API key.
Generates plausible pricing for the requested route using known carrier/price patterns.
"""
from __future__ import annotations
import sys
import json
import uuid
from datetime import datetime, timedelta

# Carriers that impose YQ (European/Middle East majors)
YQ_CARRIERS = [
    ("BA", "British Airways"),
    ("LH", "Lufthansa"),
    ("AF", "Air France"),
    ("KL", "KLM"),
    ("EK", "Emirates"),
    ("QR", "Qatar Airways"),
]
# Carriers that do NOT impose YQ
NO_YQ_CARRIERS = [
    ("UA", "United Airlines"),
    ("AA", "American Airlines"),
    ("DL", "Delta Air Lines"),
    ("AS", "Alaska Airlines"),
]

# Route-based base price estimates (USD)
ROUTE_PRICES: dict[tuple[str, str], int] = {
    ("JFK", "LHR"): 620, ("JFK", "FCO"): 680, ("JFK", "CDG"): 640,
    ("JFK", "FRA"): 660, ("JFK", "AMS"): 610, ("JFK", "NRT"): 900,
    ("JFK", "DXB"): 820, ("JFK", "ORD"): 180,
    ("LAX", "LHR"): 680, ("LAX", "CDG"): 720, ("LAX", "NRT"): 780,
    ("LAX", "SYD"): 950, ("LAX", "ORD"): 220,
    ("LAX", "MNL"): 680, ("LAX", "SIN"): 720, ("LAX", "BKK"): 750,
    ("ORD", "CDG"): 580, ("ORD", "LHR"): 540,
    ("SFO", "LHR"): 700, ("SFO", "AMS"): 710, ("SFO", "NRT"): 760,
    ("BOS", "LHR"): 560, ("MIA", "LHR"): 700,
    # Canadian routes
    ("YVR", "MNL"): 720, ("YVR", "NRT"): 680, ("YVR", "ICN"): 660,
    ("YVR", "HKG"): 710, ("YVR", "SIN"): 780, ("YVR", "BKK"): 800,
    ("YVR", "LHR"): 750, ("YVR", "CDG"): 780, ("YVR", "SYD"): 950,
    ("YYZ", "LHR"): 620, ("YYZ", "CDG"): 650, ("YYZ", "MNL"): 850,
}

THROWAWAY_DESTS: dict[str, list[str]] = {
    "LHR": ["DUB", "CPH", "AMS"], "FCO": ["DUB", "LIS", "AMS"],
    "CDG": ["DUB", "LIS", "VIE"], "FRA": ["DUB", "CPH", "LIS"],
    "AMS": ["DUB", "LIS", "CPH"], "NRT": ["HKG", "BKK", "KUL"],
}


def make_segment(
    origin: str, dest: str, airline: str, airline_name: str,
    dep_time: str, duration_min: int, stops: int = 0, is_throwaway: bool = False
) -> dict:
    dep_dt = datetime.fromisoformat(dep_time)
    arr_dt = dep_dt + timedelta(minutes=duration_min)
    return {
        "origin": origin, "destination": dest,
        "airline": airline, "airline_name": airline_name,
        "flight_number": f"{airline}{100 + abs(hash(origin+dest)) % 900}",
        "departure_time": dep_dt.isoformat(),
        "arrival_time": arr_dt.isoformat(),
        "duration_minutes": duration_min,
        "stops": stops, "is_throwaway": is_throwaway,
    }


def base_price(origin: str, dest: str) -> int:
    return (
        ROUTE_PRICES.get((origin, dest)) or
        ROUTE_PRICES.get((dest, origin)) or
        550
    )


def duration_for(origin: str, dest: str) -> int:
    # rough transatlantic/transpacific/domestic estimates in minutes
    inter = {
        frozenset(["JFK", "LHR"]): 420, frozenset(["JFK", "FCO"]): 510,
        frozenset(["JFK", "CDG"]): 435, frozenset(["JFK", "FRA"]): 480,
        frozenset(["JFK", "AMS"]): 450, frozenset(["JFK", "NRT"]): 820,
        frozenset(["JFK", "DXB"]): 800, frozenset(["LAX", "LHR"]): 660,
        frozenset(["LAX", "NRT"]): 660, frozenset(["LAX", "SYD"]): 960,
        frozenset(["SFO", "LHR"]): 660, frozenset(["SFO", "NRT"]): 660,
        frozenset(["JFK", "ORD"]): 165, frozenset(["LAX", "ORD"]): 235,
        frozenset(["LAX", "MNL"]): 760, frozenset(["YVR", "MNL"]): 690,
        frozenset(["YVR", "NRT"]): 600, frozenset(["YVR", "ICN"]): 620,
        frozenset(["YVR", "HKG"]): 660, frozenset(["YVR", "LHR"]): 570,
        frozenset(["YYZ", "LHR"]): 480, frozenset(["YYZ", "MNL"]): 900,
    }
    return inter.get(frozenset([origin, dest]), 480)


def make_offer(
    origin: str, dest: str, airline: str, airline_name: str,
    price: float, dep_time: str, source: str = "demo",
    extra_leg: tuple[str, str, str, str] | None = None,  # (from, to, airline, airline_name)
) -> dict:
    main_dur = duration_for(origin, dest)
    segments = [make_segment(origin, dest, airline, airline_name, dep_time, main_dur)]

    if extra_leg:
        extra_dep = (datetime.fromisoformat(dep_time) + timedelta(minutes=main_dur + 90)).isoformat()
        o, d, al, aln = extra_leg
        segments.append(make_segment(o, d, al, aln, extra_dep, 90, is_throwaway=True))

    return {
        "id": f"demo_{uuid.uuid4().hex[:8]}",
        "source": source,
        "segments": segments,
        "total_price_usd": round(price, 2),
        "currency": "USD",
        "booking_url": f"https://www.google.com/flights#search;f={origin};t={dest}",
        "fetched_at": datetime.utcnow().isoformat() + "Z",
    }


def generate_offers(origin: str, dest: str, date_out: str, date_back: str | None) -> list[dict]:
    bp = base_price(origin, dest)
    dep = f"{date_out}T09:00:00"
    results = []

    # ── 1. Direct YQ carriers (full price with surcharge baked in) ─────────────
    for airline, name in YQ_CARRIERS[:3]:
        price = bp * (0.95 + (abs(hash(airline)) % 20) / 100)
        results.append(make_offer(origin, dest, airline, name, price, dep))

    # ── 2. YQ-free US carriers (structurally cheaper by ~25%) ─────────────────
    for airline, name in NO_YQ_CARRIERS[:3]:
        price = bp * (0.72 + (abs(hash(airline)) % 12) / 100)
        results.append(make_offer(origin, dest, airline, name, price, dep))

    # ── 3. Fuel dump: YQ carrier + throwaway leg (price ~30% of normal) ───────
    throwaway_list = THROWAWAY_DESTS.get(dest, ["DUB", "LIS"])
    for i, td in enumerate(throwaway_list[:2]):
        yq_airline, yq_name = YQ_CARRIERS[i % len(YQ_CARRIERS)]
        dump_price = bp * 0.28  # YQ surcharge eliminated → ~72% cheaper
        dep_shifted = f"{date_out}T{7 + i:02d}:30:00"
        results.append(make_offer(
            origin, dest, yq_airline, yq_name, dump_price, dep_shifted,
            extra_leg=(dest, td, "FR", "Ryanair"),
        ))

    # ── 4. Round-trip (cheaper than one-way for throwaway detection) ──────────
    if date_back:
        rt_price = bp * 0.85  # round-trip often cheaper than one-way × 2
        results.append(make_offer(origin, dest, "UA", "United Airlines", rt_price, dep))

    # ── 5. Hidden-city: route through dest to further city ────────────────────
    if dest in ("ORD", "LHR", "CDG", "FRA"):
        beyond = {"ORD": "LAX", "LHR": "DUB", "CDG": "LIS", "FRA": "VIE"}.get(dest, "DUB")
        hc_price = bp * 0.62  # routing through dest costs less than flying to it directly
        hc_dep = f"{date_out}T11:00:00"
        # Segment 1: origin → dest (user exits here)
        dur1 = duration_for(origin, dest)
        seg1 = make_segment(origin, dest, "AA", "American Airlines", hc_dep, dur1)
        # Segment 2: dest → beyond (user ignores)
        dep2 = (datetime.fromisoformat(hc_dep) + timedelta(minutes=dur1 + 60)).isoformat()
        seg2 = make_segment(dest, beyond, "AA", "American Airlines", dep2, 90)
        results.append({
            "id": f"demo_hc_{uuid.uuid4().hex[:6]}",
            "source": "demo",
            "segments": [seg1, seg2],
            "total_price_usd": round(hc_price, 2),
            "currency": "USD",
            "booking_url": f"https://www.google.com/flights#search;f={origin};t={beyond}",
            "fetched_at": datetime.utcnow().isoformat() + "Z",
        })

    return results


def main():
    try:
        inp = json.load(sys.stdin)
    except Exception as e:
        print(f"[demo] stdin error: {e}", file=sys.stderr)
        print("[]")
        return

    origin      = inp.get("origin", "JFK")
    destination = inp.get("destination", "LHR")
    date_out    = inp.get("date_out", "2025-06-01")
    date_back   = inp.get("date_back")

    results = generate_offers(origin, destination, date_out, date_back)
    print(json.dumps(results))


if __name__ == "__main__":
    main()
