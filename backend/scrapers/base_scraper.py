"""Base scraper utility class."""

import logging
import httpx
import asyncio
from bs4 import BeautifulSoup
from app.utils.helpers import utc_now

logger = logging.getLogger(__name__)


class BaseScraper:
    """Base Class that contains core functions for fetching, parsing, and logging scrapers."""

    def __init__(self, country: str):
        self.country = country

    async def fetch_page_html(
        self,
        url: str,
        retries: int = 3,
        backoff_seconds: float = 2.0,
    ) -> str:
        """Fetch HTML content of a page with retries and exponential backoff."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

        async with httpx.AsyncClient(headers=headers, timeout=20.0) as client:
            for attempt in range(retries):
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    return response.text
                except Exception as e:
                    logger.warning(
                        f"Attempt {attempt + 1} failed for {url}: {e}. Retrying..."
                    )
                    if attempt == retries - 1:
                        logger.error(f"Failed to fetch {url} after {retries} attempts.")
                        raise e
                    await asyncio.sleep(backoff_seconds * (attempt + 1))

        return ""

    def get_soup(self, html: str) -> BeautifulSoup:
        """Parse HTML string into a BeautifulSoup object."""
        return BeautifulSoup(html, "html.parser")

    async def log_run(
        self,
        db,
        status: str,
        scraped_count: int,
        error_msg: str | None = None,
    ) -> None:
        """Write execution metrics to the scraper_logs collection."""
        log_entry = {
            "country": self.country,
            "status": status,
            "items_scraped": scraped_count,
            "error_message": error_msg,
            "created_at": utc_now().isoformat(),
        }
        await db.scraper_logs.insert_one(log_entry)
        logger.info(f"Scraper logs recorded for {self.country}: {log_entry}")
