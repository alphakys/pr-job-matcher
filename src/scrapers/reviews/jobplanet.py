from __future__ import annotations

import json
import urllib.parse

from src.fixtures.seed_data import SEED_JOBS_AND_REVIEWS
from src.models import Review
from src.scrapers.base import ReviewScraper
from src.storage.repository import normalize_text


class JobplanetReviewScraper(ReviewScraper):
    """Adapter for Jobplanet interview & employee reviews with fixture replay."""

    source_name = "jobplanet"
    base_url = "https://www.jobplanet.co.kr/api/v1/companies"

    @staticmethod
    def parse_reviews_json(company: str, payload: dict[str, object]) -> list[Review]:
        company_norm = normalize_text(company)
        reviews: list[Review] = []
        for item in payload.get("reviews", []):  # type: ignore[union-attr]
            rev_type = "interview" if item.get("type") == "interview" else "employee"
            reviews.append(
                Review(
                    source=rev_type,
                    rating=float(item.get("rating", 3.0)),
                    text=str(item.get("body") or ""),
                    company_normalized=company_norm,
                    source_platform="jobplanet",
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
                        collected.extend(r for r in revs if r.source_platform == "jobplanet")
                return collected

            encoded = urllib.parse.quote(company)
            raw = self.http_get_text(f"{self.base_url}/search?q={encoded}")
            return self.parse_reviews_json(company, json.loads(raw))

        return self.execute_with_retry("scrape_reviews_jobplanet", _run)
