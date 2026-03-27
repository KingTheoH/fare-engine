"""
airport_codes.py — Known IATA airport codes for hard validation.

~600 major airports worldwide. Used by pattern_normalizer to reject
LLM-hallucinated airport codes that look valid (3 uppercase letters)
but don't correspond to real airports.

This is NOT exhaustive — it covers major international airports, hubs,
and common routing/ticketing points relevant to fuel dump constructions.
Niche regional airports may not be listed. If a real airport gets
rejected, add it here.
"""

# fmt: off
KNOWN_AIRPORTS: frozenset[str] = frozenset({
    # ─── North America ───────────────────────────────────────────────
    # US major hubs
    "ATL", "BOS", "BWI", "CLT", "DCA", "DEN", "DFW", "DTW", "EWR",
    "FLL", "HNL", "IAD", "IAH", "JFK", "LAS", "LAX", "LGA", "MCO",
    "MDW", "MIA", "MSP", "OAK", "ORD", "PBI", "PDX", "PHL", "PHX",
    "PIT", "RDU", "SAN", "SEA", "SFO", "SJC", "SLC", "SMF", "SNA",
    "STL", "TPA", "AUS", "BNA", "CLE", "CMH", "CVG", "DAL", "HOU",
    "IND", "JAX", "MCI", "MEM", "MKE", "MSY", "OGG", "ONT", "RSW",
    "SAT", "SJU", "BDL", "ABQ", "ANC", "BHM", "BUF", "BUR", "CHS",
    "DSM", "ELP", "GRR", "GSP", "ICT", "LIT", "OKC", "OMA", "PVD",
    "RIC", "RNO", "ROC", "SAV", "SDF", "SYR", "TUL", "TUS",
    # Canada
    "YYZ", "YVR", "YUL", "YOW", "YYC", "YEG", "YWG", "YHZ", "YQB",
    # Mexico & Caribbean
    "MEX", "CUN", "GDL", "SJD", "PVR", "MTY", "TIJ",
    "NAS", "MBJ", "KIN", "PUJ", "SDQ", "SXM", "AUA", "CUR", "BGI",
    "POS", "GCM", "HAV", "STT", "STX",

    # ─── Europe ──────────────────────────────────────────────────────
    # UK & Ireland
    "LHR", "LGW", "STN", "LTN", "MAN", "BHX", "EDI", "GLA", "BRS",
    "NCL", "BFS", "DUB", "SNN", "ORK",
    # Germany
    "FRA", "MUC", "TXL", "BER", "DUS", "HAM", "CGN", "STR", "HAJ",
    "NUE", "LEJ",
    # France
    "CDG", "ORY", "LYS", "NCE", "MRS", "TLS", "BOD", "NTE",
    # Benelux
    "AMS", "BRU", "LUX", "RTM", "EIN",
    # Scandinavia
    "CPH", "ARN", "OSL", "HEL", "GOT", "BGO", "TRD",
    # Iberia
    "MAD", "BCN", "LIS", "OPO", "AGP", "PMI", "ALC", "VLC", "FAO",
    "SVQ", "BIO",
    # Italy
    "FCO", "MXP", "LIN", "VCE", "NAP", "BLQ", "PSA", "FLR", "CTA",
    "BGY",
    # Switzerland & Austria
    "ZRH", "GVA", "BSL", "VIE", "SZG", "INN",
    # Eastern Europe
    "PRG", "WAW", "BUD", "OTP", "SOF", "ZAG", "BEG", "LJU", "KRK",
    "GDN",
    # Greece & Cyprus
    "ATH", "SKG", "HER", "LCA", "PFO",
    # Turkey
    "IST", "SAW", "ESB", "AYT", "ADB", "DLM",
    # Nordic/Baltic
    "KEF", "TLL", "RIX", "VNO",
    # Russia (major)
    "SVO", "DME", "LED", "VKO",

    # ─── Middle East ─────────────────────────────────────────────────
    "DXB", "AUH", "DOH", "AMM", "BAH", "KWI", "MCT", "RUH", "JED",
    "TLV", "BEY", "CAI", "HRG", "SSH", "MED",

    # ─── Asia-Pacific ────────────────────────────────────────────────
    # East Asia
    "NRT", "HND", "KIX", "NGO", "FUK", "CTS",
    "ICN", "GMP",
    "PEK", "PKX", "PVG", "SHA", "CAN", "SZX", "CTU", "CKG", "WUH",
    "HGH", "XIY", "NKG", "TSN", "KMG", "XMN", "TAO", "DLC",
    "HKG",
    "TPE", "KHH",
    "MNL", "CEB",
    # Southeast Asia
    "SIN", "BKK", "DMK", "HKT", "CNX", "KUL", "PEN", "SGN", "HAN",
    "CGK", "DPS", "SUB", "RGN", "PNH", "REP", "VTE", "DAD",
    # South Asia
    "DEL", "BOM", "MAA", "BLR", "CCU", "HYD", "COK", "AMD", "GOI",
    "CMB", "DAC", "KTM", "ISB", "LHE", "KHI",
    # Oceania
    "SYD", "MEL", "BNE", "PER", "ADL", "CBR", "OOL",
    "AKL", "WLG", "CHC", "ZQN",
    "NAN", "PPT",

    # ─── Africa ──────────────────────────────────────────────────────
    "JNB", "CPT", "DUR",
    "NBO", "MBA", "DAR", "EBB", "KGL",
    "ADD", "ACC", "LOS", "ABV",
    "CMN", "RAK", "TUN", "ALG",
    "MPM", "WDH", "MRU", "SEZ",

    # ─── South America ───────────────────────────────────────────────
    "GRU", "GIG", "BSB", "CNF", "SSA", "REC", "POA", "CWB", "FOR",
    "EZE", "AEP", "SCL",
    "BOG", "MDE", "CTG",
    "LIM", "UIO", "GYE",
    "CCS", "MVD", "ASU", "LPB", "VVI",
    "PTY", "SJO", "SAL", "GUA", "TGU",
})
# fmt: on
