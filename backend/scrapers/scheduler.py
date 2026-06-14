"""Scraper scheduler runner."""

import logging
from scrapers.germany import GermanyScraper
from scrapers.usa import USAScraper
from scrapers.canada import CanadaScraper
from scrapers.uk import UKScraper
from scrapers.australia import AustraliaScraper

logger = logging.getLogger(__name__)


async def run_all_scrapers(db) -> dict:
    """Run all scraper scripts sequentially and return aggregated run outcomes."""
    scrapers = [
        GermanyScraper(),
        USAScraper(),
        CanadaScraper(),
        UKScraper(),
        AustraliaScraper()
    ]

    results = {}
    total_scraped = 0

    for s in scrapers:
        try:
            logger.info(f"Starting scheduled crawl for {s.country}...")
            count = await s.scrape(db)
            results[s.country] = {
                "status": "success",
                "items_scraped": count,
            }
            total_scraped += count
        except Exception as e:
            logger.error(f"Scraper execution error for country={s.country}: {e}")
            results[s.country] = {
                "status": "failed",
                "error": str(e),
                "items_scraped": 0,
            }

    return {
        "results": results,
        "total_scraped": total_scraped,
    }
