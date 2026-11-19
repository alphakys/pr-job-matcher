from __future__ import annotations

import json
import urllib.parse
from typing import Any

from src.fixtures.seed_data import SEED_JOBS_AND_REVIEWS
from src.models import JobPost
from src.scrapers.base import JobScraper


class WantedJobScraper(JobScraper):
    """Adapter for Wanted Korea public job API v4 with offline fixture replay."""

    source_name = "wanted"
    api_url = "https://www.wanted.co.kr/api/v4/jobs"

    @staticmethod
    def parse_api_payload(payload: dict[str, Any]) -> list[JobPost]:
        jobs: list[JobPost] = []
        for item in payload.get("data", []):
            company_info = item.get("company") or {}
            detail = item.get("detail") or {}
            body = " ".join(
                part
                for part in [
                    str(detail.get("intro") or ""),
                    str(detail.get("main_tasks") or ""),
                    str(detail.get("requirements") or ""),
                    str(detail.get("preferred_points") or ""),
                ]
                if part
            ).strip()
            job_id = f"wanted-{item['id']}"
            jobs.append(
                JobPost(
                    job_id=job_id,
                    source="wanted",
                    company=str(company_info.get("name") or "Unknown"),
                    title=str(item.get("position") or "Backend Engineer"),
                    body=body or str(item.get("position") or ""),
                    url=f"https://www.wanted.co.kr/wd/{item['id']}",
                )
            )
        return jobs

    def fetch_jobs(self, query: str = "backend", limit: int = 20) -> list[JobPost]:
        def _run() -> list[JobPost]:
            if self.use_fixtures:
                return [job for job, _ in SEED_JOBS_AND_REVIEWS if job.source == "wanted"][:limit]

            params = urllib.parse.urlencode({"country": "kr", "tag_type_ids": "872", "limit": limit, "query": query})
            raw = self.http_get_text(f"{self.api_url}?{params}")
            return self.parse_api_payload(json.loads(raw))

        return self.execute_with_retry("scrape_jobs_wanted", _run)
