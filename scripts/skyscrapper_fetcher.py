#!/usr/bin/env python3
from __future__ import annotations
import sys
import json
import uuid
import requests
from datetime import datetime

BASE   = "https://sky-scrapper.p.rapidapi.com"
HEADERS_TEMPLATE = {
    "x-rapidapi-host": "sky-scrapper.p.rapidapi.com",
}


def get_headers(api_key: str) -> dict:
    return {**HEADERS_TEMPLATE, "x-rapidapi-key": api_key}


def search_airport(query: str, api_key: str) -> str | None:
    """Resolve IATA/city name → Sky Scrapper entityId."""
    try:
        resp = requests.get(
            f"{BASE}/api/v1/flights/searchAirport",
            params={"query": query, "locale": "en-US"},
            headers=get_headers(api_key),
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        if data:
            return data[0].get("entityId", "")
    except Exception as e:
        print(f"[skyscrapper] airport lookup error for '{query}': {e}", file=sys.stderr)
    return None


def parse_duration(minutes: int | None) -> int:
    return int(minutes) if minutes else 0


def normalise_leg(leg: dict) -> dict:
    origin = leg.get("origin", {})
    dest   = leg.get("destination", {})
    return {
        "origin":           origin.get("displayCode", ""),
        "destination":      dest.get("displayCode", ""),
        "airline":          leg.get("carriers", {}).get("marketing", [{}])[0].get("alternateId", ""),
        "airline_name":     leg.get("carriers", {}).get("marketing", [{}])[0].get("name", ""),
        "flight_number":    "",
        "departure_time":   leg.get("departure", ""),
        "arrival_time":     leg.get("arrival", ""),
        "duration_minutes": parse_duration(leg.get("durationInMinutes")),
        "stops":            leg.get("stopCount", 0),
        "is_throwaway":     False,
    }


def normalise_itinerary(itin: dict) -> dict:
    legs     = itin.get("legs", [])
    segments = [normalise_leg(l) for l in legs]
    price    = float(itin.get("price", {}).get("raw", 0))
    url      = itin.get("deeplink", "")

    return {
        "id":              f"sky_{uuid.uuid4().hex[:8]}",
        "source":          "skyscrapper",
        "segments":        segments,
        "total_price_usd": price,
        "currency":        "USD",
        "booking_url":     url,
        "fetched_at":      datetime.utcnow().isoformat() + "Z",
    }


def search_flights(
    origin_id: str,
    dest_id: str,
    date_out: str,
    passengers: int,
    cabin: str,
    api_key: str,
    date_back: str | None = None,
) -> list[dict]:
    params: dict = {
        "originSkyId":        origin_id,
        "destinationSkyId":   dest_id,
        "originEntityId":     origin_id,
        "destinationEntityId": dest_id,
        "date":               date_out,
        "adults":             passengers,
        "cabinClass":         cabin,
        "currency":           "USD",
        "countryCode":        "US",
        "market":             "en-US",
    }
    if date_back:
        params["returnDate"] = date_back

    try:
        resp = requests.get(
            f"{BASE}/api/v2/flights/searchFlights",
            params=params,
            headers=get_headers(api_key),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        itins = (
            data.get("data", {})
                .get("itineraries", [])
        )
        return itins
    except Exception as e:
        print(f"[skyscrapper] search error: {e}", file=sys.stderr)
        if hasattr(e, 'response') and e.response is not None:
            print(f"[skyscrapper] body: {e.response.text[:300]}", file=sys.stderr)
        return []


def main():
    try:
        inp = json.load(sys.stdin)
    except Exception as e:
        print(f"[skyscrapper] stdin error: {e}", file=sys.stderr)
        print("[]")
        return

    api_key  = inp.get("api_key", "")
    if not api_key:
        print("[skyscrapper] no API key", file=sys.stderr)
        print("[]")
        return

    origin      = inp.get("origin", "")
    destination = inp.get("destination", "")
    date_out    = inp.get("date_out", "")
    date_back   = inp.get("date_back")
    passengers  = inp.get("passengers", 1)
    cabin       = inp.get("cabin", "economy")

    # Resolve entity IDs (Sky Scrapper accepts IATA codes directly as entityId too)
    origin_id = search_airport(origin, api_key) or origin
    dest_id   = search_airport(destination, api_key) or destination

    raw = search_flights(origin_id, dest_id, date_out, passengers, cabin, api_key, date_back)

    results = [normalise_itinerary(i) for i in raw]
    print(json.dumps(results))


if __name__ == "__main__":
    main()
