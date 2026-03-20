#!/usr/bin/env python3
from __future__ import annotations
import sys
import json
import uuid
import requests
from datetime import datetime

AUTH_URL = "https://test.api.amadeus.com/v1/security/oauth2/token"
SEARCH_URL = "https://test.api.amadeus.com/v2/shopping/flight-offers"


def get_token(api_key: str, api_secret: str) -> str | None:
    try:
        resp = requests.post(AUTH_URL, data={
            "grant_type": "client_credentials",
            "client_id": api_key,
            "client_secret": api_secret,
        }, timeout=15)
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as e:
        print(f"[amadeus] auth error: {e}", file=sys.stderr)
        return None


def parse_duration(iso_dur: str) -> int:
    """PT10H30M → 630 minutes"""
    import re
    hours = re.search(r"(\d+)H", iso_dur)
    mins  = re.search(r"(\d+)M", iso_dur)
    return (int(hours.group(1)) * 60 if hours else 0) + (int(mins.group(1)) if mins else 0)


def normalise(offer: dict) -> dict:
    segments = []
    for itin in offer.get("itineraries", []):
        for seg in itin.get("segments", []):
            dep = seg.get("departure", {})
            arr = seg.get("arrival", {})
            segments.append({
                "origin":           dep.get("iataCode", ""),
                "destination":      arr.get("iataCode", ""),
                "airline":          seg.get("carrierCode", ""),
                "airline_name":     seg.get("carrierCode", ""),
                "flight_number":    f"{seg.get('carrierCode','')}{seg.get('number','')}",
                "departure_time":   dep.get("at", ""),
                "arrival_time":     arr.get("at", ""),
                "duration_minutes": parse_duration(seg.get("duration", "PT0M")),
                "stops":            seg.get("numberOfStops", 0),
                "is_throwaway":     False,
            })

    price = float(offer.get("price", {}).get("grandTotal", 0))

    return {
        "id":             f"amadeus_{uuid.uuid4().hex[:8]}",
        "source":         "amadeus",
        "segments":       segments,
        "total_price_usd": price,
        "currency":       offer.get("price", {}).get("currency", "USD"),
        "booking_url":    "https://www.google.com/flights",  # Amadeus test env has no deep link
        "fetched_at":     datetime.utcnow().isoformat() + "Z",
    }


def fetch_offers(token: str, params: dict) -> list[dict]:
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(SEARCH_URL, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json().get("data", [])
    except Exception as e:
        print(f"[amadeus] search error: {e}", file=sys.stderr)
        if hasattr(e, 'response') and e.response is not None:
            print(f"[amadeus] response: {e.response.text[:300]}", file=sys.stderr)
        return []


def main():
    try:
        inp = json.load(sys.stdin)
    except Exception as e:
        print(f"[amadeus] stdin parse error: {e}", file=sys.stderr)
        print("[]")
        return

    api_key    = inp.get("api_key", "")
    api_secret = inp.get("api_secret", "")

    if not api_key or not api_secret:
        print("[amadeus] no API credentials — returning empty", file=sys.stderr)
        print("[]")
        return

    token = get_token(api_key, api_secret)
    if not token:
        print("[]")
        return

    origin      = inp.get("origin", "")
    destination = inp.get("destination", "")
    date_out    = inp.get("date_out", "")
    date_back   = inp.get("date_back", "")
    passengers  = inp.get("passengers", 1)
    max_stops   = inp.get("max_stops", 2)
    currency    = inp.get("currency", "USD")

    results: list[dict] = []

    # ── One-way search ─────────────────────────────────────────────────────────
    params: dict = {
        "originLocationCode":      origin,
        "destinationLocationCode": destination,
        "departureDate":           date_out,
        "adults":                  passengers,
        "max":                     25,
        "currencyCode":            currency,
    }
    if max_stops == 0:
        params["nonStop"] = "true"

    raw = fetch_offers(token, params)
    for offer in raw:
        results.append(normalise(offer))

    # ── Round-trip (for throwaway detection) ──────────────────────────────────
    if date_back:
        rt_params = {**params, "returnDate": date_back}
        rt_raw = fetch_offers(token, rt_params)
        for offer in rt_raw:
            n = normalise(offer)
            n["id"] = f"amadeus_rt_{uuid.uuid4().hex[:8]}"
            results.append(n)

    print(json.dumps(results))


if __name__ == "__main__":
    main()
