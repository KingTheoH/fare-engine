"""
llm_extractor.py — Two-pass Claude API extraction of dump patterns from forum text.

Pass 1 (Filter): claude-haiku — "Does this post describe a fuel dump?" (~$0.001/post)
Pass 2 (Extract): claude-sonnet — Full structured JSON extraction (~$0.01/post)

Only posts flagged as likely containing dump patterns in Pass 1 are sent to Pass 2.
This keeps LLM costs low while maintaining high extraction quality.

Key functions:
- filter_post: Pass 1 — cheap relevance check
- extract_patterns: Pass 2 — full structured extraction
- process_post: Combined two-pass pipeline
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ─── Model constants ──────────────────────────────────────────────────────

FILTER_MODEL = "claude-haiku-4-5"
EXTRACT_MODEL = "claude-sonnet-4-6"

MAX_POST_LENGTH = 10000  # Truncate very long posts
MAX_RETRIES = 3

# ─── Prompts ───────────────────────────────────────────────────────────────

FILTER_PROMPT = """\
You are analyzing a forum post from FlyerTalk (a frequent flyer community).

Determine if this post describes a SPECIFIC, ACTIONABLE fuel dump fare construction.

A fuel dump (YQ dump) is a specific routing trick that eliminates or reduces
airline-imposed fuel surcharges (YQ) on air tickets. It involves specific:
- Origin and destination airports
- Carrier sequences (which airlines to ticket on)
- Routing points or ticketing points
- Sometimes specific fare basis codes

Answer ONLY with a JSON object:
{
  "contains_dump_pattern": true/false,
  "reason": "brief explanation"
}

If the post merely DISCUSSES fuel dumps in general, mentions YQ without a specific
construction, or asks a question without providing a working pattern, answer false.

Only answer true if the post contains enough detail to reconstruct the actual
routing/ticketing sequence.

POST TEXT:
"""

EXTRACT_PROMPT = """\
You are extracting structured fuel dump pattern data from a FlyerTalk forum post.

A fuel dump (YQ dump) eliminates airline-imposed fuel surcharges via specific routing tricks.

Extract ALL distinct dump patterns described in this post. For each pattern, identify:

1. **dump_type** — classify as one of:
   - "TP_DUMP": Ticketing Point manipulation (a routing via a specific city causes YQ to drop)
   - "CARRIER_SWITCH": Using a no-YQ carrier on a surcharge-bearing sector
   - "FARE_BASIS": A specific fare basis code structurally excludes YQ
   - "ALLIANCE_RULE": Interline agreement between specific carrier pairs waives YQ
   - "STRIKE_SEGMENT": A throwaway leg appended to the END of the routing on a no-YQ carrier zeroes surcharges for the whole ticket (e.g. adding SKD→TAS on Uzbekistan Airways as a final segment)

2. **origin** — 3-letter IATA origin airport code (must appear explicitly in the post)
3. **destination** — 3-letter IATA destination airport code (must appear explicitly in the post)
4. **carriers** — list of 2-letter IATA carrier codes in the routing sequence
5. **ticketing_carrier** — the carrier the ticket is issued on (2-letter IATA)
6. **ticketing_point** — the city/airport used as ticketing point (if TP_DUMP)
7. **routing_points** — list of via/connection points (3-letter IATA codes)
8. **fare_basis_hint** — fare basis code if mentioned (e.g., "YLOWUS")
9. **estimated_yq_savings_usd** — dollar savings if explicitly mentioned, else null
10. **confidence** — "high" if the post explicitly states the route/carrier sequence;
    "medium" if inferable but not stated outright; "low" if you are guessing
11. **confirmation_signals** — copy EXACT phrases from the post that confirm this works
    (e.g., "just booked this last week", "confirmed working March 2026")
12. **deprecation_signals** — copy EXACT phrases from the post indicating it no longer works
13. **source_quote** — a SHORT direct quote (≤40 words) from the post that most clearly
    establishes the core routing or carrier construction. If you cannot find a specific
    quote that establishes the route, set confidence to "low".
14. **strike_segment** — ONLY if dump_type is "STRIKE_SEGMENT" (or any pattern that explicitly
    appends a throwaway final leg): extract as {"origin": "SKD", "destination": "TAS",
    "carrier": "HY", "note": "brief reason this leg zeroes YQ"}. Set to null for all other
    dump types unless the post specifically describes appending a throwaway segment.

STRIKE SEGMENT RECOGNITION:
Look for language like: "add a [city] leg at the end", "throwaway segment", "append [carrier]
flight to complete the routing", "tack on a [route] flight", "book [route] as the last segment".
Known historical strike segments: SKD→TAS on HY (Uzbekistan domestic, ~2022–2024, mostly patched),
TAS→SKD on HY, FRU→OSS on QH (Air Bishkek). If you see references to these or similar
Central Asian / no-YQ carrier domestic legs appended to intercontinental routings, classify
as STRIKE_SEGMENT and extract the strike_segment field.

IMPORTANT RULES:
- Only extract IATA codes you can see written in the post. Do NOT infer or guess codes
  from city names unless the post explicitly gives the code.
- If the post mentions a city like "Frankfurt" but no IATA code, use "FRA" ONLY if
  FRA is unambiguous for that city in context.
- If you are uncertain about any IATA code, set confidence to "low".
- Do NOT extract patterns from hypothetical examples or questions — only from
  descriptions of actual bookings or confirmed constructions.

Respond ONLY with a JSON object:
{
  "patterns": [
    {
      "dump_type": "TP_DUMP",
      "origin": "JFK",
      "destination": "BKK",
      "carriers": ["LH", "AA"],
      "ticketing_carrier": "LH",
      "ticketing_point": "FRA",
      "routing_points": ["FRA"],
      "fare_basis_hint": null,
      "estimated_yq_savings_usd": 580.00,
      "confidence": "high",
      "confirmation_signals": ["just booked this last week"],
      "deprecation_signals": [],
      "source_quote": "ticketed on LH via FRA, zero YQ on the BKK sector",
      "strike_segment": null
    }
  ],
  "extraction_notes": "any relevant notes about ambiguity or assumptions"
}

If the post contains no extractable patterns despite being flagged, return:
{"patterns": [], "extraction_notes": "reason"}

POST TEXT:
"""


# ─── Result types ──────────────────────────────────────────────────────────

@dataclass
class FilterResult:
    """Result of Pass 1 (haiku filter)."""

    contains_dump_pattern: bool = False
    reason: str = ""
    error: str | None = None
    model_used: str = FILTER_MODEL
    tokens_used: int = 0


@dataclass
class ExtractedPatternData:
    """A single pattern extracted by the LLM in Pass 2."""

    dump_type: str = ""
    origin: str = ""
    destination: str = ""
    carriers: list[str] = field(default_factory=list)
    ticketing_carrier: str = ""
    ticketing_point: str | None = None
    routing_points: list[str] = field(default_factory=list)
    fare_basis_hint: str | None = None
    estimated_yq_savings_usd: float | None = None
    confidence: str = "low"
    confirmation_signals: list[str] = field(default_factory=list)
    deprecation_signals: list[str] = field(default_factory=list)
    source_quote: str | None = None  # Grounding quote from the post
    strike_segment: dict | None = None  # {origin, destination, carrier, note} — STRIKE_SEGMENT type only


@dataclass
class ExtractionResult:
    """Result of Pass 2 (sonnet extraction)."""

    patterns: list[ExtractedPatternData] = field(default_factory=list)
    extraction_notes: str = ""
    error: str | None = None
    model_used: str = EXTRACT_MODEL
    tokens_used: int = 0


@dataclass
class ProcessResult:
    """Combined result of the full two-pass pipeline."""

    filter_result: FilterResult = field(default_factory=FilterResult)
    extraction_result: ExtractionResult | None = None
    passed_filter: bool = False
    total_patterns: int = 0
    error: str | None = None


# ─── Core extractor class ─────────────────────────────────────────────────

@dataclass
class LLMExtractor:
    """
    Two-pass LLM extraction pipeline for dump patterns.

    Usage:
        extractor = LLMExtractor(api_key="sk-ant-...")
        result = await extractor.process_post("Forum post text here...")
    """

    api_key: str = ""
    filter_model: str = FILTER_MODEL
    extract_model: str = EXTRACT_MODEL
    _client: Any = field(default=None, init=False)

    def _get_client(self) -> Any:
        """Get or create an Anthropic client."""
        if self._client is None:
            import anthropic

            self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
        return self._client

    async def filter_post(self, post_text: str) -> FilterResult:
        """
        Pass 1: Cheap relevance check with claude-haiku.

        Returns FilterResult with contains_dump_pattern = True/False.
        Never raises — returns error in result on failure.
        """
        truncated = post_text[:MAX_POST_LENGTH]

        for attempt in range(MAX_RETRIES):
            try:
                client = self._get_client()
                response = await client.messages.create(
                    model=self.filter_model,
                    max_tokens=200,
                    messages=[
                        {"role": "user", "content": FILTER_PROMPT + truncated}
                    ],
                )

                text = response.content[0].text.strip()
                tokens = response.usage.input_tokens + response.usage.output_tokens

                parsed = _parse_json_response(text)
                if parsed is None:
                    return FilterResult(
                        error=f"Failed to parse filter response: {text[:200]}",
                        tokens_used=tokens,
                    )

                return FilterResult(
                    contains_dump_pattern=bool(parsed.get("contains_dump_pattern", False)),
                    reason=str(parsed.get("reason", "")),
                    tokens_used=tokens,
                )

            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    logger.error("Filter failed after %d attempts: %s", MAX_RETRIES, e)
                    return FilterResult(error=f"API error: {str(e)}")
                logger.warning("Filter attempt %d failed: %s", attempt + 1, e)

        return FilterResult(error="Max retries exceeded")

    async def extract_patterns(self, post_text: str) -> ExtractionResult:
        """
        Pass 2: Full structured extraction with claude-sonnet.

        Returns ExtractionResult with list of extracted patterns.
        Never raises — returns error in result on failure.
        """
        truncated = post_text[:MAX_POST_LENGTH]

        for attempt in range(MAX_RETRIES):
            try:
                client = self._get_client()
                response = await client.messages.create(
                    model=self.extract_model,
                    max_tokens=2000,
                    messages=[
                        {"role": "user", "content": EXTRACT_PROMPT + truncated}
                    ],
                )

                text = response.content[0].text.strip()
                tokens = response.usage.input_tokens + response.usage.output_tokens

                parsed = _parse_json_response(text)
                if parsed is None:
                    return ExtractionResult(
                        error=f"Failed to parse extraction response: {text[:200]}",
                        tokens_used=tokens,
                    )

                patterns = []
                for raw_pattern in parsed.get("patterns", []):
                    patterns.append(
                        ExtractedPatternData(
                            dump_type=raw_pattern.get("dump_type", ""),
                            origin=raw_pattern.get("origin", ""),
                            destination=raw_pattern.get("destination", ""),
                            carriers=raw_pattern.get("carriers", []),
                            ticketing_carrier=raw_pattern.get("ticketing_carrier", ""),
                            ticketing_point=raw_pattern.get("ticketing_point"),
                            routing_points=raw_pattern.get("routing_points", []),
                            fare_basis_hint=raw_pattern.get("fare_basis_hint"),
                            estimated_yq_savings_usd=raw_pattern.get("estimated_yq_savings_usd"),
                            confidence=raw_pattern.get("confidence", "low"),
                            confirmation_signals=raw_pattern.get("confirmation_signals", []),
                            deprecation_signals=raw_pattern.get("deprecation_signals", []),
                            source_quote=raw_pattern.get("source_quote"),
                            strike_segment=raw_pattern.get("strike_segment"),
                        )
                    )

                return ExtractionResult(
                    patterns=patterns,
                    extraction_notes=parsed.get("extraction_notes", ""),
                    tokens_used=tokens,
                )

            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    logger.error("Extraction failed after %d attempts: %s", MAX_RETRIES, e)
                    return ExtractionResult(error=f"API error: {str(e)}")
                logger.warning("Extraction attempt %d failed: %s", attempt + 1, e)

        return ExtractionResult(error="Max retries exceeded")

    async def process_post(self, post_text: str) -> ProcessResult:
        """
        Full two-pass pipeline: filter → extract.

        Runs Pass 1 (haiku) first. Only runs Pass 2 (sonnet) if Pass 1
        indicates the post contains a dump pattern.
        """
        result = ProcessResult()

        # Pass 1: Filter
        filter_result = await self.filter_post(post_text)
        result.filter_result = filter_result

        if filter_result.error:
            result.error = f"Filter error: {filter_result.error}"
            return result

        if not filter_result.contains_dump_pattern:
            result.passed_filter = False
            return result

        # Pass 2: Extract
        result.passed_filter = True
        extraction_result = await self.extract_patterns(post_text)
        result.extraction_result = extraction_result

        if extraction_result.error:
            result.error = f"Extraction error: {extraction_result.error}"
            return result

        result.total_patterns = len(extraction_result.patterns)
        return result


# ─── Utility functions ─────────────────────────────────────────────────────

def _parse_json_response(text: str) -> dict[str, Any] | None:
    """
    Parse JSON from LLM response text.

    Handles cases where the LLM wraps JSON in markdown code blocks.
    """
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code block
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding first { ... } block
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    return None
