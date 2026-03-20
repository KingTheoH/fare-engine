#!/usr/bin/env python3
from __future__ import annotations
import sys
import json
import uuid
import requests
from datetime import datetime

BASE_URL = "https://serpapi.com/search.json"


def parse_duration(text: str) -> int:
    """Convert '10 hr 30 min' → minutes."""
    minutes = 0
    h = __import__('re').search(r'(\d+)\s*hr', text)
    m = __import__('re').search(r'(\d+)\s*min', text)
    if h:
        minutes += int(h.group(1)) * 60
    if m:
        minutes += int(m.group(1))
    return minutes


def normalise_time(t: str) -> str:
    """Convert '2026-04-19 07:30' → '2026-04-19T07:30:00' (proper ISO)."""
    if not t:
        return ""
    return t.replace(" ", "T") + ":00" if "T" not in t and len(t) == 16 else t


def make_segment(flight: dict) -> dict:
    dep_airport = flight.get("departure_airport", {})
    arr_airport = flight.get("arrival_airport", {})
    # Airline IATA code: extract from flight_number (e.g. "BA 84" → "BA", "UA 27" → "UA")
    flight_num_raw = flight.get("flight_number", "")
    parts = flight_num_raw.split()
    airline_code = parts[0].upper() if parts and len(parts[0]) == 2 else \
        flight.get("airline_logo", "").split("/")[-1].split(".")[0].upper()[:2]
    # flight_number for display: strip the airline prefix so it's just the number
    # e.g. "B6 604" → "604", then displayed as "B6 604" when combined with airline code
    flight_num_display = parts[1] if len(parts) > 1 else flight_num_raw
    return {
        "origin": dep_airport.get("id", ""),
        "destination": arr_airport.get("id", ""),
        "airline": airline_code,
        "airline_name": flight.get("airline", ""),
        "flight_number": flight_num_display,
        "departure_time": normalise_time(dep_airport.get("time", "")),
        "arrival_time": normalise_time(arr_airport.get("time", "")),
        "duration_minutes": parse_duration(str(flight.get("duration", "0 min"))),
        "stops": 0,
        "is_throwaway": False,
    }


def normalise(itinerary: dict, departure_id: str, arrival_id: str, outbound_date: str) -> dict:
    flights = itinerary.get("flights", [])
    segments = [make_segment(f) for f in flights]
    price = float(itinerary.get("price", 0))

    # Use a real Google Flights search link so users can actually book
    booking_url = (
        f"https://www.google.com/travel/flights?q=flights+from+{departure_id}"
        f"+to+{arrival_id}+on+{outbound_date}&hl=en"
    )

    return {
        "id": f"serpapi_{uuid.uuid4().hex[:8]}",
        "source": "serpapi",
        "segments": segments,
        "total_price_usd": price,
        "currency": "USD",
        "booking_url": booking_url,
        "fetched_at": datetime.utcnow().isoformat() + "Z",
    }


def fetch_serpapi(params: dict, retries: int = 2) -> dict:
    for attempt in range(retries):
        try:
            resp = requests.get(BASE_URL, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"[serpapi] attempt {attempt+1}: {e}", file=sys.stderr)
    return {}


def main():
    try:
        inp = json.load(sys.stdin)
    except Exception as e:
        print(f"[serpapi] stdin parse error: {e}", file=sys.stderr)
        print("[]")
        return

    api_key = inp.get("api_key", "")
    if not api_key or api_key == "your_serpapi_key_here":
        print("[serpapi] no API key — returning empty", file=sys.stderr)
        print("[]")
        return

    departure_id = inp.get("departure_id", "")
    arrival_id   = inp.get("arrival_id", "")
    outbound_date = inp.get("outbound_date", "")
    return_date   = inp.get("return_date", "")
    flight_type   = inp.get("flight_type", 2)  # 1=round, 2=one-way
    currency      = inp.get("currency", "USD")

    params = {
        "engine": "google_flights",
        "departure_id": departure_id,
        "arrival_id": arrival_id,
        "outbound_date": outbound_date,
        "currency": currency,
        "type": flight_type,
        "api_key": api_key,
    }
    if return_date and flight_type == 1:
        params["return_date"] = return_date

    data = fetch_serpapi(params)
    results: list[dict] = []

    for group_key in ("best_flights", "other_flights"):
        for itinerary in data.get(group_key, []):
            results.append(normalise(itinerary, departure_id, arrival_id, outbound_date))

    print(json.dumps(results))


if __name__ == "__main__":
    main()
