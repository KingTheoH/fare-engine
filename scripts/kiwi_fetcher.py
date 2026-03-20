#!/usr/bin/env python3
from __future__ import annotations
import sys
import json
import time
import uuid
import requests
from datetime import datetime

BASE_URL = "https://api.tequila.kiwi.com/v2/search"
HEADERS_TEMPLATE = {"accept": "application/json"}


def make_segment(leg: dict) -> dict:
    dep = leg.get("local_departure", "")
    arr = leg.get("local_arrival", "")

    # duration in minutes
    try:
        dep_dt = datetime.fromisoformat(dep)
        arr_dt = datetime.fromisoformat(arr)
        duration_minutes = int((arr_dt - dep_dt).total_seconds() / 60)
    except Exception:
        duration_minutes = 0

    return {
        "origin": leg.get("flyFrom", ""),
        "destination": leg.get("flyTo", ""),
        "airline": leg.get("airline", ""),
        "airline_name": leg.get("airline", ""),
        "flight_number": f"{leg.get('airline','')}{leg.get('flight_no','')}",
        "departure_time": dep,
        "arrival_time": arr,
        "duration_minutes": duration_minutes,
        "stops": 0,
        "is_throwaway": False,
    }


def fetch_kiwi(params: dict, api_key: str, retries: int = 3) -> list[dict]:
    headers = {**HEADERS_TEMPLATE, "apikey": api_key}
    for attempt in range(retries):
        try:
            resp = requests.get(BASE_URL, params=params, headers=headers, timeout=30)
            if resp.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            return resp.json().get("data", [])
        except Exception as e:
            print(f"[kiwi] attempt {attempt+1} error: {e}", file=sys.stderr)
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    return []


def normalise(item: dict, source_tag: str) -> dict:
    segments = [make_segment(leg) for leg in item.get("route", [])]
    price = float(item.get("price", 0))
    deep_link = item.get("deep_link", "")
    airlines = item.get("airlines", [])

    return {
        "id": f"kiwi_{source_tag}_{uuid.uuid4().hex[:8]}",
        "source": "kiwi",
        "segments": segments,
        "total_price_usd": price,
        "currency": "USD",
        "booking_url": deep_link,
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "airlines": airlines,
    }


def main():
    try:
        inp = json.load(sys.stdin)
    except Exception as e:
        print(f"[kiwi] stdin parse error: {e}", file=sys.stderr)
        print("[]")
        return

    api_key = inp.get("api_key", "")
    if not api_key or api_key == "your_kiwi_api_key_here":
        print("[kiwi] no API key — returning empty", file=sys.stderr)
        print("[]")
        return

    fly_from = inp.get("fly_from", "")
    fly_to   = inp.get("fly_to", "")
    date_from = inp.get("date_from", "")
    date_to   = inp.get("date_to", date_from)  # same day if not given
    flight_type = inp.get("flight_type", "oneway")
    max_stopovers = inp.get("max_stopovers", 2)
    curr = inp.get("curr", "USD")

    results: list[dict] = []

    # ── One-way / return search ────────────────────────────────────────────────
    params: dict = {
        "fly_from": fly_from,
        "fly_to": fly_to,
        "date_from": date_from,
        "date_to": date_to,
        "flight_type": flight_type,
        "max_stopovers": max_stopovers,
        "curr": curr,
        "limit": 40,
        "sort": "price",
        "asc": 1,
    }

    raw = fetch_kiwi(params, api_key)
    for item in raw:
        results.append(normalise(item, "main"))

    # ── Multi-city: append throwaway legs for fuel dump detection ──────────────
    # Try common throwaway destinations from the target city
    throwaway_dests = inp.get("throwaway_dests", [])
    for td in throwaway_dests[:3]:  # max 3 extra queries
        mc_params = {
            "fly_from": fly_from,
            "fly_to": fly_to,
            "date_from": date_from,
            "date_to": date_to,
            "via_city": td,
            "max_stopovers": max_stopovers + 1,
            "curr": curr,
            "limit": 10,
            "sort": "price",
            "asc": 1,
        }
        time.sleep(1)  # rate limit respect
        mc_raw = fetch_kiwi(mc_params, api_key)
        for item in mc_raw:
            results.append(normalise(item, f"mc_{td}"))

    print(json.dumps(results))


if __name__ == "__main__":
    main()
