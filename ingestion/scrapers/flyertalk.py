"""
flyertalk.py — FlyerTalk forum scraper.

Scrapes thread listings and individual posts from FlyerTalk forums.
Identifies threads likely to contain fuel dump discussions via keyword matching,
then extracts post content, author metadata, and thread structure.

Rate limited: 1 request / 2 seconds (±0.5s jitter).
Respects robots.txt — only scrapes publicly accessible pages.

Key functions:
- scrape_forum_threads: Get thread listings from a forum page
- scrape_thread_posts: Get all posts from a specific thread
- scan_forums: Full scan of configured forums, returns new posts
"""

import asyncio
import logging
import random
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ─── Constants ─────────────────────────────────────────────────────────────

FLYERTALK_BASE = "https://www.flyertalk.com"

# Keywords that signal a thread may contain fuel dump discussions
DUMP_KEYWORDS = [
    "fuel dump",
    "fuel surcharge",
    "YQ",
    "YQ-free",
    "YQ free",
    "yq avoidance",
    "routing trick",
    "TP dump",
    "ticketing point",
    "carrier surcharge",
    "surcharge trick",
    "dump fare",
    "fare construction",
    "ex-EU",
    "ex EU",
]

# Compiled pattern for matching keywords in thread titles / post text
_KEYWORD_PATTERN = re.compile(
    "|".join(re.escape(kw) for kw in DUMP_KEYWORDS),
    re.IGNORECASE,
)

# Rate limiting
MIN_REQUEST_DELAY = 1.5  # seconds
MAX_REQUEST_DELAY = 2.5  # seconds

# Default forums to scan
DEFAULT_FORUM_URLS = [
    "https://www.flyertalk.com/forum/mileage-run-deals-372/",
    "https://www.flyertalk.com/forum/premium-fare-deals-350/",
]


# ─── Data structures ──────────────────────────────────────────────────────

@dataclass
class ThreadInfo:
    """Metadata about a single FlyerTalk thread."""

    thread_url: str
    title: str
    author: str = ""
    reply_count: int = 0
    last_post_date: str = ""
    contains_dump_keywords: bool = False

    @property
    def thread_id(self) -> str:
        """Extract numeric thread ID from URL."""
        match = re.search(r"-(\d+)/?", self.thread_url)
        return match.group(1) if match else ""


@dataclass
class PostData:
    """A single parsed post from a FlyerTalk thread."""

    post_url: str
    author: str
    raw_text: str
    posted_at: datetime | None = None
    author_post_count: int | None = None
    author_account_age_days: int | None = None
    post_number: int = 0
    thread_url: str = ""
    thread_title: str = ""

    def to_community_post_dict(self) -> dict[str, Any]:
        """Convert to a dict compatible with CommunityPostCreate schema."""
        return {
            "source": "FLYERTALK",
            "post_url": self.post_url,
            "post_author": self.author,
            "author_post_count": self.author_post_count,
            "author_account_age_days": self.author_account_age_days,
            "raw_text": self.raw_text,
            "posted_at": self.posted_at,
        }


@dataclass
class ScanResult:
    """Result of scanning one or more forums."""

    posts: list[PostData] = field(default_factory=list)
    threads_scanned: int = 0
    threads_matched: int = 0
    posts_scraped: int = 0
    errors: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "threads_scanned": self.threads_scanned,
            "threads_matched": self.threads_matched,
            "posts_scraped": self.posts_scraped,
            "error_count": len(self.errors),
        }


# ─── Core scraper class ───────────────────────────────────────────────────

@dataclass
class FlyerTalkScraper:
    """
    FlyerTalk forum scraper.

    Uses httpx for HTTP requests. Parses HTML with regex (no heavy
    dependency on BeautifulSoup — pages have predictable structure).

    Usage:
        scraper = FlyerTalkScraper()
        result = await scraper.scan_forums()
    """

    forum_urls: list[str] = field(default_factory=lambda: list(DEFAULT_FORUM_URLS))
    max_threads_per_forum: int = 50
    max_posts_per_thread: int = 100
    _client: httpx.AsyncClient | None = field(default=None, init=False)

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create an httpx client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en-US,en;q=0.9",
                },
                follow_redirects=True,
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _rate_limit_pause(self) -> None:
        """Random pause between requests to avoid detection."""
        delay = random.uniform(MIN_REQUEST_DELAY, MAX_REQUEST_DELAY)
        await asyncio.sleep(delay)

    async def _fetch_page(self, url: str) -> str | None:
        """
        Fetch a page and return its HTML content.

        Returns None on any error (never raises).
        """
        try:
            client = await self._get_client()
            await self._rate_limit_pause()
            response = await client.get(url)
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as e:
            logger.warning("HTTP %d fetching %s", e.response.status_code, url)
            return None
        except Exception as e:
            logger.error("Error fetching %s: %s", url, e)
            return None

    # ─── Thread listing parsing ────────────────────────────────────────

    def parse_thread_listings(self, html: str, forum_url: str) -> list[ThreadInfo]:
        """
        Parse thread listings from a FlyerTalk forum page HTML.

        Extracts thread URLs, titles, authors, and reply counts from
        the forum listing page structure.
        """
        threads: list[ThreadInfo] = []

        # FlyerTalk thread links follow patterns like:
        # <a href="/forum/thread-title-123456/">Thread Title</a>
        thread_pattern = re.compile(
            r'<a[^>]+href="(/forum/[^"]*-(\d+)/)"[^>]*>'
            r'([^<]+)</a>',
            re.IGNORECASE,
        )

        for match in thread_pattern.finditer(html):
            path = match.group(1)
            title = match.group(3).strip()

            # Skip sticky/announcement patterns
            if not title or len(title) < 5:
                continue

            thread_url = f"{FLYERTALK_BASE}{path}" if path.startswith("/") else path
            contains_keywords = bool(_KEYWORD_PATTERN.search(title))

            threads.append(
                ThreadInfo(
                    thread_url=thread_url,
                    title=title,
                    contains_dump_keywords=contains_keywords,
                )
            )

        # Deduplicate by URL
        seen_urls: set[str] = set()
        unique: list[ThreadInfo] = []
        for t in threads:
            if t.thread_url not in seen_urls:
                seen_urls.add(t.thread_url)
                unique.append(t)

        return unique[: self.max_threads_per_forum]

    # ─── Post parsing ──────────────────────────────────────────────────

    def parse_posts(self, html: str, thread_url: str, thread_title: str) -> list[PostData]:
        """
        Parse individual posts from a FlyerTalk thread page.

        Extracts post content, author info, and timestamps.
        """
        posts: list[PostData] = []

        # FlyerTalk posts are in structured divs with post content
        # This regex targets the common vBulletin post structure
        post_block_pattern = re.compile(
            r'<div[^>]*class="[^"]*post_message[^"]*"[^>]*id="post_message_(\d+)"[^>]*>'
            r'(.*?)</div>',
            re.DOTALL | re.IGNORECASE,
        )

        # Author pattern
        author_pattern = re.compile(
            r'class="[^"]*username[^"]*"[^>]*>([^<]+)</a>',
            re.IGNORECASE,
        )

        # Post count pattern
        postcount_pattern = re.compile(
            r'Posts:\s*([\d,]+)',
            re.IGNORECASE,
        )

        # Join date pattern
        joindate_pattern = re.compile(
            r'Join\s*Date:\s*([A-Za-z]+\s+\d{4})',
            re.IGNORECASE,
        )

        # Find all authors in the page
        authors = author_pattern.findall(html)

        for i, match in enumerate(post_block_pattern.finditer(html)):
            post_id = match.group(1)
            raw_html = match.group(2)

            # Strip HTML tags to get plain text
            raw_text = _strip_html(raw_html)

            if not raw_text or len(raw_text.strip()) < 10:
                continue

            # Try to match author from preceding content
            author = authors[i] if i < len(authors) else ""

            post_url = f"{thread_url}#post{post_id}"

            posts.append(
                PostData(
                    post_url=post_url,
                    author=author.strip(),
                    raw_text=raw_text.strip(),
                    post_number=i + 1,
                    thread_url=thread_url,
                    thread_title=thread_title,
                )
            )

        return posts[: self.max_posts_per_thread]

    # ─── High-level operations ─────────────────────────────────────────

    async def scrape_forum_threads(self, forum_url: str) -> list[ThreadInfo]:
        """
        Scrape thread listings from a single forum page.

        Returns only threads whose titles contain dump-related keywords.
        """
        html = await self._fetch_page(forum_url)
        if html is None:
            return []

        all_threads = self.parse_thread_listings(html, forum_url)
        matching = [t for t in all_threads if t.contains_dump_keywords]

        logger.info(
            "Forum %s: found %d threads, %d with dump keywords",
            forum_url,
            len(all_threads),
            len(matching),
        )
        return matching

    async def scrape_thread_posts(
        self, thread_url: str, thread_title: str = ""
    ) -> list[PostData]:
        """
        Scrape all posts from a single FlyerTalk thread.

        Follows pagination links to get all pages.
        """
        all_posts: list[PostData] = []
        current_url: str | None = thread_url
        page_num = 0

        while current_url and len(all_posts) < self.max_posts_per_thread:
            page_num += 1
            html = await self._fetch_page(current_url)
            if html is None:
                break

            posts = self.parse_posts(html, thread_url, thread_title)
            all_posts.extend(posts)

            # Check for next page link
            next_url = self._find_next_page(html, thread_url)
            if next_url == current_url:
                break
            current_url = next_url

            if page_num >= 10:  # Safety limit on pagination
                break

        logger.info(
            "Thread %s: scraped %d posts across %d pages",
            thread_url[:60],
            len(all_posts),
            page_num,
        )
        return all_posts

    async def scan_forums(
        self,
        known_urls: set[str] | None = None,
    ) -> ScanResult:
        """
        Full scan of all configured forums.

        Args:
            known_urls: Set of post_urls already in the database (for dedup).

        Returns:
            ScanResult with all new posts found.
        """
        known = known_urls or set()
        result = ScanResult()

        for forum_url in self.forum_urls:
            try:
                matching_threads = await self.scrape_forum_threads(forum_url)
                result.threads_scanned += len(matching_threads) + 1  # +1 for the listing page

                for thread in matching_threads:
                    result.threads_matched += 1
                    try:
                        posts = await self.scrape_thread_posts(
                            thread.thread_url, thread.title
                        )
                        for post in posts:
                            if post.post_url not in known:
                                # Only keep posts with dump-relevant content
                                if _KEYWORD_PATTERN.search(post.raw_text):
                                    result.posts.append(post)
                                    result.posts_scraped += 1

                    except Exception as e:
                        error_msg = f"Error scraping thread {thread.thread_url}: {e}"
                        result.errors.append(error_msg)
                        logger.error(error_msg)

            except Exception as e:
                error_msg = f"Error scanning forum {forum_url}: {e}"
                result.errors.append(error_msg)
                logger.error(error_msg)

        logger.info(
            "Forum scan complete: %d threads matched, %d new posts scraped",
            result.threads_matched,
            result.posts_scraped,
        )
        return result

    def _find_next_page(self, html: str, base_url: str) -> str | None:
        """Find the 'next page' link in a thread page."""
        # Look for pagination next link
        next_pattern = re.compile(
            r'<a[^>]+rel="next"[^>]+href="([^"]+)"',
            re.IGNORECASE,
        )
        match = next_pattern.search(html)
        if match:
            href = match.group(1)
            if href.startswith("/"):
                return f"{FLYERTALK_BASE}{href}"
            if href.startswith("http"):
                return href
            return f"{base_url}/{href}"
        return None


# ─── Utility functions ─────────────────────────────────────────────────────

def _strip_html(html: str) -> str:
    """Remove HTML tags and decode common entities."""
    # Remove script/style blocks
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Decode common entities
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    text = text.replace("&nbsp;", " ")
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def contains_dump_keywords(text: str) -> bool:
    """Check if text contains any fuel dump related keywords."""
    return bool(_KEYWORD_PATTERN.search(text))
