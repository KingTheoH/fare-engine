"""
pattern_normalizer.py — Converts LLM extraction output to DB-ready format.

Takes raw ExtractedPatternData from the LLM extractor and produces
validated, normalized dicts ready for dump_patterns table insertion.

Key responsibilities:
- HARD-validate IATA codes against known airports/carriers (reject unknowns)
- Map LLM dump_type strings to DumpType enum values
- Generate ITA routing code from extracted carrier/routing data
- Reject patterns with zero/missing YQ savings (no point validating them)
- Reject patterns with deprecation signals (already known dead)
- Set lifecycle_state = discovered (never auto-promote)
- Compute initial confidence_score from LLM confidence + signals
- Set manual_input_bundle = None (populated after first ITA validation)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ingestion.extractors.airport_codes import KNOWN_AIRPORTS
from ingestion.extractors.llm_extractor import ExtractedPatternData

logger = logging.getLogger(__name__)

# ─── Valid values ──────────────────────────────────────────────────────────

VALID_DUMP_TYPES = {"TP_DUMP", "CARRIER_SWITCH", "FARE_BASIS", "ALLIANCE_RULE"}

# Known carrier IATA codes — HARD validation. Unknown carriers are REJECTED.
# If a real carrier gets rejected, add it here AND to seeds/carriers.json.
KNOWN_CARRIERS = {
    "AA", "AC", "AF", "AI", "AM", "AR", "AS", "AT", "AV", "AY",
    "AZ", "BA", "BR", "CA", "CI", "CX", "CZ", "DL", "EI", "EK",
    "ET", "EY", "FJ", "GA", "HA", "HU", "IB", "JL", "KE", "KL",
    "LA", "LH", "LO", "LX", "MH", "MU", "NH", "NZ", "OK", "OS",
    "OZ", "PG", "PR", "QF", "QR", "RJ", "SA", "SK", "SN", "SQ",
    "SU", "SV", "TG", "TK", "TP", "UA", "UL", "UX", "VA", "VN",
    "VS", "WN", "WS",
}

# Minimum YQ savings to justify storing a pattern (USD).
# Patterns below this are Tier 3 noise that waste validation cycles.
MIN_YQ_SAVINGS_USD = 30.0


# ─── Result types ──────────────────────────────────────────────────────────

@dataclass
class RejectionReason:
    """Structured rejection reason for analytics."""
    field: str
    value: str
    reason: str

    def __str__(self) -> str:
        return f"{self.field}={self.value}: {self.reason}"


@dataclass
class NormalizedPattern:
    """A validated, DB-ready pattern dict."""

    data: dict[str, Any]
    warnings: list[str]
    rejections: list[RejectionReason] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return bool(self.data) and len(self.rejections) == 0


@dataclass
class NormalizationResult:
    """Result of normalizing one or more extracted patterns."""

    patterns: list[NormalizedPattern]
    skipped: int = 0
    skip_reasons: list[str] | None = None
    rejection_summary: dict[str, int] = field(default_factory=dict)

    @property
    def valid_count(self) -> int:
        return sum(1 for p in self.patterns if p.is_valid)


# ─── Core normalization ───────────────────────────────────────────────────

def normalize_pattern(
    extracted: ExtractedPatternData,
    source_url: str = "",
    source_post_weight: float = 0.5,
    post_age_days: int | None = None,
) -> NormalizedPattern:
    """
    Normalize a single LLM-extracted pattern to DB-ready format.

    Returns NormalizedPattern with empty data dict if validation fails.
    Hard-rejects patterns with:
    - Unknown carriers (not in KNOWN_CARRIERS)
    - Unknown airports (not in KNOWN_AIRPORTS)
    - Zero or missing YQ savings
    - Active deprecation signals
    - Stale source posts (>365 days without confirmation)
    """
    warnings: list[str] = []
    rejections: list[RejectionReason] = []

    def _reject(field: str, value: str, reason: str) -> NormalizedPattern:
        rejections.append(RejectionReason(field=field, value=value, reason=reason))
        logger.info("Rejected pattern %s→%s: %s=%s (%s)",
                     extracted.origin, extracted.destination, field, value, reason)
        return NormalizedPattern(data={}, warnings=warnings, rejections=rejections)

    # ─── Validate dump_type ─────────────────────────────────────────
    dump_type = extracted.dump_type.upper().strip()
    if dump_type not in VALID_DUMP_TYPES:
        return _reject("dump_type", dump_type, "Invalid dump type")

    # ─── Reject stale posts ─────────────────────────────────────────
    if post_age_days is not None and post_age_days > 365:
        has_recent_confirmation = any(
            _signal_is_recent(sig) for sig in extracted.confirmation_signals
        )
        if not has_recent_confirmation:
            return _reject("post_age", str(post_age_days),
                           "Post >12 months old with no recent confirmation")

    # ─── Reject patterns with deprecation signals ───────────────────
    if extracted.deprecation_signals and len(extracted.deprecation_signals) > 0:
        dep_text = "; ".join(extracted.deprecation_signals[:3])
        return _reject("deprecation", dep_text,
                        "Pattern has active deprecation signals — already known dead")

    # ─── Validate IATA airport codes (HARD) ─────────────────────────
    origin = extracted.origin.upper().strip()
    destination = extracted.destination.upper().strip()

    if not _is_valid_airport(origin):
        return _reject("origin", origin, "Unknown airport code")
    if not _is_valid_airport(destination):
        return _reject("destination", destination, "Unknown airport code")
    if origin == destination:
        return _reject("route", f"{origin}={destination}", "Origin equals destination")

    # ─── Validate carriers (HARD) ───────────────────────────────────
    carriers = [c.upper().strip() for c in extracted.carriers if c]
    if not carriers:
        return _reject("carriers", "[]", "No carriers specified")

    for carrier in carriers:
        if not _is_valid_carrier(carrier):
            return _reject("carrier", carrier, "Unknown carrier code")

    ticketing_carrier = extracted.ticketing_carrier.upper().strip()
    if not _is_valid_carrier(ticketing_carrier):
        return _reject("ticketing_carrier", ticketing_carrier, "Unknown carrier code")

    # ─── Validate routing points (HARD) ──────────────────────────────
    routing_points = [rp.upper().strip() for rp in extracted.routing_points if rp]
    for rp in routing_points:
        if not _is_valid_airport(rp):
            return _reject("routing_point", rp, "Unknown airport code")

    # ─── Validate YQ savings ─────────────────────────────────────────
    savings = extracted.estimated_yq_savings_usd
    if savings is None or savings < MIN_YQ_SAVINGS_USD:
        return _reject("estimated_yq_savings_usd",
                        str(savings),
                        f"Below minimum ${MIN_YQ_SAVINGS_USD} threshold")

    # ─── Validate dump_type-specific requirements ────────────────────
    if dump_type == "TP_DUMP" and not routing_points:
        return _reject("routing_points", "[]",
                        "TP_DUMP requires at least one routing/ticketing point")

    if dump_type == "CARRIER_SWITCH" and len(carriers) < 2:
        return _reject("carriers", str(carriers),
                        "CARRIER_SWITCH requires at least 2 carriers")

    if dump_type == "FARE_BASIS" and not extracted.fare_basis_hint:
        return _reject("fare_basis_hint", "None",
                        "FARE_BASIS requires a fare basis code")

    # ─── Generate ITA routing code ──────────────────────────────────
    routing_code = _build_routing_code(
        dump_type=dump_type,
        origin=origin,
        destination=destination,
        carriers=carriers,
        ticketing_carrier=ticketing_carrier,
        routing_points=routing_points,
        fare_basis_hint=extracted.fare_basis_hint,
    )

    # ─── Demote confidence when LLM cannot cite source text ────────
    effective_confidence = extracted.confidence
    source_quote = extracted.source_quote if hasattr(extracted, "source_quote") else None
    if not source_quote and effective_confidence == "high":
        effective_confidence = "medium"
        warnings.append("No source_quote provided — confidence downgraded from high to medium")

    # ─── Compute initial confidence ────────────────────────────────
    confidence_score = _compute_initial_confidence(
        llm_confidence=effective_confidence,
        source_post_weight=source_post_weight,
        has_confirmation=len(extracted.confirmation_signals) > 0,
        has_deprecation=False,  # Already rejected above if deprecation present
    )

    # ─── Build normalized dict ──────────────────────────────────────
    data: dict[str, Any] = {
        "dump_type": dump_type,
        "lifecycle_state": "discovered",
        "origin_iata": origin,
        "destination_iata": destination,
        "ticketing_carrier_iata": ticketing_carrier,
        "operating_carriers": carriers,
        "routing_points": routing_points,
        "fare_basis_hint": extracted.fare_basis_hint,
        "ita_routing_code": routing_code,
        "manual_input_bundle": None,  # Set after first ITA validation
        "expected_yq_savings_usd": savings,
        "confidence_score": confidence_score,
        "freshness_tier": _assign_freshness_tier(savings),
        "source": "FLYERTALK",
        "source_url": source_url,
        "source_post_weight": source_post_weight,
    }
    # Store grounding quote as part of the manual_input_bundle metadata
    # (source_quote is not a DB column — it travels with the pattern for audit)
    if source_quote:
        data["_source_quote"] = source_quote[:200]  # Truncate if LLM went long

    return NormalizedPattern(data=data, warnings=warnings, rejections=[])


def normalize_all(
    patterns: list[ExtractedPatternData],
    source_url: str = "",
    source_post_weight: float = 0.5,
    post_age_days: int | None = None,
) -> NormalizationResult:
    """
    Normalize a list of extracted patterns.

    Hard-filters invalid patterns. Returns valid ones + rejection stats.
    """
    result = NormalizationResult(patterns=[], skip_reasons=[], rejection_summary={})

    for extracted in patterns:
        normalized = normalize_pattern(
            extracted,
            source_url=source_url,
            source_post_weight=source_post_weight,
            post_age_days=post_age_days,
        )
        if normalized.is_valid:
            result.patterns.append(normalized)
        else:
            result.skipped += 1
            # Track rejection reasons for analytics
            for rej in normalized.rejections:
                key = f"{rej.field}:{rej.reason}"
                result.rejection_summary[key] = result.rejection_summary.get(key, 0) + 1
            if result.skip_reasons is not None and normalized.rejections:
                result.skip_reasons.append(
                    f"{extracted.origin}-{extracted.destination}: {normalized.rejections[0]}"
                )

    if result.rejection_summary:
        logger.info("Normalization rejection summary: %s", result.rejection_summary)

    return result


# ─── Helper functions ──────────────────────────────────────────────────────

def _is_valid_airport(code: str) -> bool:
    """Check if code is a known IATA airport code. HARD validation."""
    if len(code) != 3 or not code.isalpha() or not code.isupper():
        return False
    return code in KNOWN_AIRPORTS


def _is_valid_carrier(code: str) -> bool:
    """Check if code is a known IATA carrier code. HARD validation."""
    if len(code) != 2 or not code.isalpha() or not code.isupper():
        return False
    return code in KNOWN_CARRIERS


def _signal_is_recent(signal_text: str) -> bool:
    """
    Check if a confirmation signal mentions a recent date.

    Looks for year references within the last 2 years or relative recency
    phrases. Dynamically computes the acceptable year range so this never
    needs manual updates.
    """
    import re
    from datetime import datetime
    text_lower = signal_text.lower()
    # Accept any year from (current_year - 1) to (current_year + 1)
    current_year = datetime.now().year
    year_pattern = "|".join(str(y) for y in range(current_year - 1, current_year + 2))
    if re.search(year_pattern, text_lower):
        return True
    # Check for relative recency phrases
    recent_phrases = [
        "this week", "last week", "yesterday", "today",
        "this month", "last month", "just booked", "just flew",
        "still works", "still working", "confirmed",
    ]
    return any(phrase in text_lower for phrase in recent_phrases)


def _build_routing_code(
    dump_type: str,
    origin: str,
    destination: str,
    carriers: list[str],
    ticketing_carrier: str,
    routing_points: list[str],
    fare_basis_hint: str | None,
) -> str:
    """
    Generate an ITA Matrix routing code string from extracted components.

    This is a simplified version — the full query_builder (Phase 03) handles
    more complex routing code generation. This provides an initial best guess
    from LLM-extracted data.
    """
    if dump_type == "TP_DUMP" and routing_points:
        # FORCE carrier:origin-TP / FORCE carrier:TP-destination
        tp = routing_points[0]
        parts = [
            f"FORCE {ticketing_carrier}:{origin}-{tp}",
            f"FORCE {ticketing_carrier}:{tp}-{destination}",
        ]
        return " / ".join(parts)

    elif dump_type == "CARRIER_SWITCH" and len(carriers) >= 2:
        # FORCE carrier1:origin-destination / FORCE carrier2:destination-origin
        parts = []
        if routing_points:
            route = "-".join([origin] + routing_points + [destination])
            parts.append(f"FORCE {carriers[0]}:{route}")
        else:
            parts.append(f"FORCE {carriers[0]}:{origin}-{destination}")

        # Return leg with different carrier
        if len(carriers) >= 2:
            parts.append(f"FORCE {carriers[-1]}:{destination}-{origin}")

        return " / ".join(parts)

    elif dump_type == "FARE_BASIS" and fare_basis_hint:
        route = "-".join([origin] + routing_points + [destination])
        return f"FORCE {ticketing_carrier}:{route} BC={fare_basis_hint}"

    elif dump_type == "ALLIANCE_RULE" and len(carriers) >= 2:
        carrier_str = "/".join(carriers[:2])
        if routing_points:
            route = "-".join([origin] + routing_points + [destination])
        else:
            route = f"{origin}-{destination}"
        return f"FORCE {carrier_str}:{route}"

    else:
        # Fallback: simple FORCE routing
        if routing_points:
            route = "-".join([origin] + routing_points + [destination])
        else:
            route = f"{origin}-{destination}"
        return f"FORCE {ticketing_carrier}:{route}"


def _compute_initial_confidence(
    llm_confidence: str,
    source_post_weight: float,
    has_confirmation: bool,
    has_deprecation: bool,
) -> float:
    """
    Compute initial confidence score for a newly discovered pattern.

    This is a simplified version of the full confidence formula (Phase 07).
    Just uses LLM confidence level + source weight + confirmation/deprecation signals.
    """
    # Base from LLM confidence
    confidence_map = {"high": 0.7, "medium": 0.5, "low": 0.3}
    score = confidence_map.get(llm_confidence.lower(), 0.3)

    # Adjust for source post weight
    score = score * 0.6 + source_post_weight * 0.4

    # Confirmation bonus
    if has_confirmation:
        score += 0.10

    # Deprecation penalty — hard cap
    if has_deprecation:
        score = min(score, 0.2)

    return max(0.0, min(1.0, round(score, 2)))


def _assign_freshness_tier(estimated_savings: float | None) -> int:
    """
    Assign freshness tier based on estimated savings.

    Tier 1: > $200 → daily validation
    Tier 2: $50–200 → weekly
    Tier 3: < $50 → monthly
    """
    if estimated_savings is None or estimated_savings <= 0:
        return 3  # Unknown savings → lowest priority
    if estimated_savings > 200:
        return 1
    if estimated_savings >= 50:
        return 2
    return 3
