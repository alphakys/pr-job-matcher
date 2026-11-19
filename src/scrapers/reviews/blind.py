from __future__ import annotations

import json
import urllib.parse

from src.fixtures.seed_data import SEED_JOBS_AND_REVIEWS
from src.models import Review
from src.scrapers.base import ReviewScraper
from src.storage.repository import normalize_text


class BlindReviewScraper(ReviewScraper):
    """Adapter for Blind employee culture/management reviews with fixture replay."""

    source_name = "blind"
    base_url = "https://www.teamblind.com/kr/api/company"

    @staticmethod
    def parse_reviews_json(company: str, payload: dict[str, object]) -> list[Review]:
        company_norm = normalize_text(company)
        reviews: list[Review] = []
        for item in payload.get("posts", []):  # type: ignore[union-attr]
            reviews.append(
                Review(
                    source="employee",
                    rating=float(item.get("rating", 3.0)),
                    text=str(item.get("text") or ""),
                    company_normalized=company_norm,
                    source_platform="blind",
                )
            )
        return reviews

    def fetch_reviews(self, company: str) -> list[Review]:
        def _run() -> list[Review]:
            target_norm = normalize_text(company)
            if self.use_fixtures:
                collected: list[Review] = []
                for job, revs in SEED_JOBS_AND_REVIEWS:
                    if normalize_text(job.company) == target_norm:
                        collected.extend(r for r in revs if r.source_platform == "blind")
                return collected

            encoded = urllib.parse.quote(company)
            raw = self.http_get_text(f"{self.base_url}/reviews?company={encoded}")
            return self.parse_reviews_json(company, json.loads(raw))

        return self.execute_with_retry("scrape_reviews_blind", _run)
