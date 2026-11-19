"""Job board scraper adapters."""

from src.scrapers.jobs.saramin import SaraminJobScraper
from src.scrapers.jobs.wanted import WantedJobScraper

__all__ = ["SaraminJobScraper", "WantedJobScraper"]
