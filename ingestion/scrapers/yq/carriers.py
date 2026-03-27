"""
carriers.py — Carrier-specific YQ scraper instances.

Each carrier gets an ITABasedYQScraper with its own sample routes.
Routes are chosen to represent the carrier's primary YQ-bearing markets.

Factory function create_all_scrapers() returns all scrapers ready to use.
"""

from ingestion.scrapers.yq.ita_based import ITABasedYQScraper

# ─── Sample routes per carrier ──────────────────────────────────────────────
# Format: (origin, destination) — representative intercontinental routes
# At least 3 transatlantic, 2 transpacific or intra-regional per carrier

_CARRIER_CONFIGS: list[dict] = [
    # Priority 1: Lufthansa — highest transatlantic YQ
    {
        "carrier_iata": "LH",
        "carrier_name": "Lufthansa",
        "sample_routes": [
            ("JFK", "FRA"), ("LAX", "MUC"), ("ORD", "FRA"),
            ("JFK", "BKK"), ("SFO", "SIN"),
        ],
    },
    # Priority 2: British Airways — high YQ, huge network
    {
        "carrier_iata": "BA",
        "carrier_name": "British Airways",
        "sample_routes": [
            ("JFK", "LHR"), ("LAX", "LHR"), ("MIA", "LHR"),
            ("LHR", "HKG"), ("LHR", "SYD"),
        ],
    },
    # Priority 3: Swiss — same group as LH
    {
        "carrier_iata": "LX",
        "carrier_name": "SWISS",
        "sample_routes": [
            ("JFK", "ZRH"), ("LAX", "ZRH"), ("ORD", "ZRH"),
            ("ZRH", "BKK"), ("ZRH", "SIN"),
        ],
    },
    # Priority 4: Austrian
    {
        "carrier_iata": "OS",
        "carrier_name": "Austrian",
        "sample_routes": [
            ("JFK", "VIE"), ("ORD", "VIE"), ("IAD", "VIE"),
            ("VIE", "BKK"), ("VIE", "NRT"),
        ],
    },
    # Priority 5: Brussels Airlines
    {
        "carrier_iata": "SN",
        "carrier_name": "Brussels Airlines",
        "sample_routes": [
            ("JFK", "BRU"), ("IAD", "BRU"), ("ORD", "BRU"),
            ("BRU", "ADD"), ("BRU", "NRT"),
        ],
    },
    # Priority 6: Iberia
    {
        "carrier_iata": "IB",
        "carrier_name": "Iberia",
        "sample_routes": [
            ("JFK", "MAD"), ("MIA", "MAD"), ("ORD", "MAD"),
            ("MAD", "NRT"), ("MAD", "GRU"),
        ],
    },
    # Priority 7: Cathay Pacific
    {
        "carrier_iata": "CX",
        "carrier_name": "Cathay Pacific",
        "sample_routes": [
            ("JFK", "HKG"), ("LAX", "HKG"), ("SFO", "HKG"),
            ("HKG", "LHR"), ("HKG", "SYD"),
        ],
    },
    # Priority 8: Korean Air
    {
        "carrier_iata": "KE",
        "carrier_name": "Korean Air",
        "sample_routes": [
            ("JFK", "ICN"), ("LAX", "ICN"), ("SFO", "ICN"),
            ("ICN", "FRA"), ("ICN", "CDG"),
        ],
    },
    # Priority 9: Asiana
    {
        "carrier_iata": "OZ",
        "carrier_name": "Asiana",
        "sample_routes": [
            ("JFK", "ICN"), ("LAX", "ICN"), ("SFO", "ICN"),
            ("ICN", "FRA"), ("ICN", "LHR"),
        ],
    },
    # Priority 10: Air France
    {
        "carrier_iata": "AF",
        "carrier_name": "Air France",
        "sample_routes": [
            ("JFK", "CDG"), ("LAX", "CDG"), ("MIA", "CDG"),
            ("CDG", "NRT"), ("CDG", "SIN"),
        ],
    },
    # ─── Low-YQ reference carriers (validate they stay near $0) ─────────
    {
        "carrier_iata": "QR",
        "carrier_name": "Qatar Airways",
        "sample_routes": [("JFK", "DOH"), ("LAX", "DOH"), ("DOH", "BKK")],
    },
    {
        "carrier_iata": "EK",
        "carrier_name": "Emirates",
        "sample_routes": [("JFK", "DXB"), ("LAX", "DXB"), ("DXB", "BKK")],
    },
    {
        "carrier_iata": "EY",
        "carrier_name": "Etihad",
        "sample_routes": [("JFK", "AUH"), ("LAX", "AUH"), ("AUH", "BKK")],
    },
    {
        "carrier_iata": "TK",
        "carrier_name": "Turkish Airlines",
        "sample_routes": [("JFK", "IST"), ("LAX", "IST"), ("IST", "BKK")],
    },
    {
        "carrier_iata": "SQ",
        "carrier_name": "Singapore Airlines",
        "sample_routes": [("JFK", "SIN"), ("LAX", "SIN"), ("SIN", "LHR")],
    },
]


def create_all_scrapers(ita_client: object | None = None) -> list[ITABasedYQScraper]:
    """
    Create scraper instances for all configured carriers.

    Args:
        ita_client: ITAClient instance for running ITA Matrix queries.
                    Pass None for unit testing (scrapers will return errors).
    """
    return [
        ITABasedYQScraper(
            carrier_iata=cfg["carrier_iata"],
            carrier_name=cfg["carrier_name"],
            sample_routes=cfg["sample_routes"],
            ita_client=ita_client,
        )
        for cfg in _CARRIER_CONFIGS
    ]


def create_scraper(carrier_iata: str, ita_client: object | None = None) -> ITABasedYQScraper | None:
    """Create a scraper for a specific carrier. Returns None if carrier not configured."""
    for cfg in _CARRIER_CONFIGS:
        if cfg["carrier_iata"] == carrier_iata:
            return ITABasedYQScraper(
                carrier_iata=cfg["carrier_iata"],
                carrier_name=cfg["carrier_name"],
                sample_routes=cfg["sample_routes"],
                ita_client=ita_client,
            )
    return None


def get_carrier_configs() -> list[dict]:
    """Return all carrier configs (for reference/testing)."""
    return list(_CARRIER_CONFIGS)
