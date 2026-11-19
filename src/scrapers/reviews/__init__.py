"""Review platform scraper adapters."""

from src.scrapers.reviews.blind import BlindReviewScraper
from src.scrapers.reviews.jobplanet import JobplanetReviewScraper

__all__ = ["BlindReviewScraper", "JobplanetReviewScraper"]
