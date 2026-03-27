"""
result_parser.py — Parses fare breakdown from ITA Matrix results page.

Extracts structured fare data from ITA Matrix's dynamically rendered
fare construction table. Designed to work with Playwright page objects.

The parser handles the two-step process:
1. Parse the results list to find matching fares
2. Parse the expanded fare breakdown (after clicking a fare)

All parsing functions return structured dicts — never raise exceptions.
On parse failure, return a result with success=False and an error message.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TaxLine:
    """A single line item from the tax breakdown."""

    code: str  # e.g., "YQ", "YR", "US", "XF"
    description: str
    amount_usd: float


@dataclass
class SegmentInfo:
    """Information about a single flight segment."""

    origin: str
    destination: str
    operating_carrier: str
    ticketing_carrier: str
    fare_basis: str
    fare_class: str = ""


@dataclass
class FareBreakdown:
    """Complete parsed fare breakdown from ITA Matrix."""

    success: bool = True
    error_message: str | None = None

    base_fare_usd: float = 0.0
    yq_total_usd: float = 0.0
    yr_total_usd: float = 0.0
    other_taxes_usd: float = 0.0
    total_price_usd: float = 0.0

    tax_lines: list[TaxLine] = field(default_factory=list)
    segments: list[SegmentInfo] = field(default_factory=list)
    ticketing_carrier: str = ""
    raw_text: str = ""

    @property
    def yq_savings(self) -> float:
        """How much YQ was avoided (0 means full dump success)."""
        return self.yq_total_usd

    @property
    def is_dump_success(self) -> bool:
        """Whether YQ was effectively eliminated."""
        return self.success and self.yq_total_usd < 1.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for storage as JSONB."""
        return {
            "success": self.success,
            "error_message": self.error_message,
            "base_fare_usd": self.base_fare_usd,
            "yq_total_usd": self.yq_total_usd,
            "yr_total_usd": self.yr_total_usd,
            "other_taxes_usd": self.other_taxes_usd,
            "total_price_usd": self.total_price_usd,
            "tax_lines": [
                {"code": t.code, "description": t.description, "amount_usd": t.amount_usd}
                for t in self.tax_lines
            ],
            "segments": [
                {
                    "origin": s.origin,
                    "destination": s.destination,
                    "operating_carrier": s.operating_carrier,
                    "ticketing_carrier": s.ticketing_carrier,
                    "fare_basis": s.fare_basis,
                    "fare_class": s.fare_class,
                }
                for s in self.segments
            ],
            "ticketing_carrier": self.ticketing_carrier,
        }


async def parse_fare_results(page: Any) -> list[dict[str, Any]]:
    """
    Parse the ITA Matrix results list page.

    Returns a list of fare result dicts with basic info (carrier, price, etc.).
    Each dict has an 'index' field for clicking to expand.

    Returns empty list on parse failure.
    """
    results = []
    try:
        # Wait for results to render
        await page.wait_for_selector(
            "[class*='result'], [class*='fare'], [id*='result']",
            timeout=30000,
        )

        # Try to find fare result rows
        rows = await page.query_selector_all(
            "[class*='result-row'], [class*='fareRow'], tr[class*='fare']"
        )

        for i, row in enumerate(rows):
            text = await row.inner_text()
            results.append({
                "index": i,
                "raw_text": text.strip(),
                "element": row,
            })

    except Exception as e:
        logger.warning("Failed to parse results list: %s", e)

    return results


async def parse_fare_breakdown(page: Any) -> FareBreakdown:
    """
    Parse the expanded fare construction table after clicking a fare.

    Extracts base fare, YQ, YR, other taxes, segments, and total price.
    Never raises — returns FareBreakdown(success=False) on failure.
    """
    try:
        # Wait for the fare detail/breakdown to render
        await page.wait_for_selector(
            "[class*='detail'], [class*='breakdown'], [class*='construction']",
            timeout=15000,
        )

        # Get full text of the breakdown area
        detail_el = await page.query_selector(
            "[class*='detail'], [class*='breakdown'], [class*='construction']"
        )
        if not detail_el:
            return FareBreakdown(success=False, error_message="Fare detail element not found")

        raw_text = await detail_el.inner_text()

        return parse_fare_text(raw_text)

    except Exception as e:
        logger.error("Failed to parse fare breakdown: %s", e)
        return FareBreakdown(success=False, error_message=f"Parse error: {str(e)}")


def parse_fare_text(raw_text: str) -> FareBreakdown:
    """
    Parse fare breakdown from raw text.

    This is separated from the async page interaction so it can be
    unit-tested with sample text without Playwright.
    """
    breakdown = FareBreakdown(raw_text=raw_text)
    tax_lines: list[TaxLine] = []

    try:
        # Extract base fare: look for "Base fare" or "Base" followed by amount
        base_match = re.search(
            r"(?:Base\s*(?:fare)?)\s*[:\s]*\$?\s*([\d,]+\.?\d*)", raw_text, re.IGNORECASE
        )
        if base_match:
            breakdown.base_fare_usd = _parse_amount(base_match.group(1))

        # Extract tax lines: pattern like "YQ  12.34" or "YQ: $12.34"
        tax_pattern = re.compile(
            r"([A-Z]{2})\s+(?:.*?)\s*\$?\s*([\d,]+\.?\d*)", re.MULTILINE
        )
        for match in tax_pattern.finditer(raw_text):
            code = match.group(1)
            amount = _parse_amount(match.group(2))
            if amount > 0:
                tax_lines.append(TaxLine(code=code, description="", amount_usd=amount))

        # Categorize taxes
        for tax in tax_lines:
            if tax.code == "YQ":
                breakdown.yq_total_usd += tax.amount_usd
            elif tax.code == "YR":
                breakdown.yr_total_usd += tax.amount_usd
            else:
                breakdown.other_taxes_usd += tax.amount_usd

        breakdown.tax_lines = tax_lines

        # Extract total: look for "Total" followed by amount
        total_match = re.search(
            r"(?:Total)\s*[:\s]*\$?\s*([\d,]+\.?\d*)", raw_text, re.IGNORECASE
        )
        if total_match:
            breakdown.total_price_usd = _parse_amount(total_match.group(1))
        else:
            # Calculate total if not found
            breakdown.total_price_usd = (
                breakdown.base_fare_usd
                + breakdown.yq_total_usd
                + breakdown.yr_total_usd
                + breakdown.other_taxes_usd
            )

        # Extract segments: look for airport pairs with carriers
        segment_pattern = re.compile(
            r"([A-Z]{3})\s*[-–→]\s*([A-Z]{3})\s+(?:.*?)([A-Z]{2})\s+(?:.*?)([A-Z]\w{3,10})"
        )
        for match in segment_pattern.finditer(raw_text):
            breakdown.segments.append(
                SegmentInfo(
                    origin=match.group(1),
                    destination=match.group(2),
                    operating_carrier=match.group(3),
                    ticketing_carrier=match.group(3),
                    fare_basis=match.group(4),
                )
            )

        breakdown.success = True

    except Exception as e:
        breakdown.success = False
        breakdown.error_message = f"Text parse error: {str(e)}"
        logger.error("Failed to parse fare text: %s", e)

    return breakdown


def _parse_amount(amount_str: str) -> float:
    """Parse a dollar amount string to float, handling commas."""
    try:
        return float(amount_str.replace(",", ""))
    except (ValueError, AttributeError):
        return 0.0


async def detect_bot_check(page: Any) -> bool:
    """
    Check if ITA Matrix has triggered bot detection (CAPTCHA, redirect, etc.).

    Returns True if bot detection is detected.
    """
    try:
        # Check for common CAPTCHA indicators
        captcha_selectors = [
            "[class*='captcha']",
            "[id*='captcha']",
            "[class*='challenge']",
            "iframe[src*='recaptcha']",
            "iframe[src*='hcaptcha']",
        ]
        for selector in captcha_selectors:
            element = await page.query_selector(selector)
            if element:
                logger.warning("Bot detection triggered: found %s", selector)
                return True

        # Check for redirect away from matrix.itasoftware.com
        current_url = page.url
        if "matrix.itasoftware.com" not in current_url and "google.com/flights" not in current_url:
            logger.warning("Bot detection: redirected to %s", current_url)
            return True

    except Exception as e:
        logger.error("Error checking for bot detection: %s", e)

    return False
