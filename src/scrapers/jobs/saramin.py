from __future__ import annotations

import html
import re
import urllib.parse

from src.fixtures.seed_data import SEED_JOBS_AND_REVIEWS
from src.models import JobPost
from src.scrapers.base import JobScraper


class SaraminJobScraper(JobScraper):
    """Adapter for Saramin job board HTML/JSON feeds with offline fixture replay."""

    source_name = "saramin"
    search_url = "https://www.saramin.co.kr/zf_user/search/recruit"

    @staticmethod
    def parse_html_listings(raw_html: str) -> list[JobPost]:
        """Parse job cards from Saramin HTML markup fixtures."""
        pattern = re.compile(
            r'<article[^>]*data-rec-idx="(?P<rec_idx>[^"]+)"[^>]*>.*?'
            r'<span class="corp_name">(?P<company>.*?)</span>.*?'
            r'<h2 class="job_tit">(?P<title>.*?)</h2>.*?'
            r'<div class="job_desc">(?P<body>.*?)</div>.*?</article>',
            re.DOTALL | re.IGNORECASE,
        )
        jobs: list[JobPost] = []
        for match in pattern.finditer(raw_html):
            rec_idx = html.unescape(match.group("rec_idx")).strip()
            company = re.sub(r"<[^>]+>", "", html.unescape(match.group("company"))).strip()
            title = re.sub(r"<[^>]+>", "", html.unescape(match.group("title"))).strip()
            body = re.sub(r"<[^>]+>", " ", html.unescape(match.group("body"))).strip()
            body = " ".join(body.split())
            jobs.append(
                JobPost(
                    job_id=f"saramin-{rec_idx}",
                    source="saramin",
                    company=company,
                    title=title,
                    body=body,
                    url=f"https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx={rec_idx}",
                )
            )
        return jobs

    def fetch_jobs(self, query: str = "백엔드", limit: int = 20) -> list[JobPost]:
        def _run() -> list[JobPost]:
            if self.use_fixtures:
                return [job for job, _ in SEED_JOBS_AND_REVIEWS if job.source == "saramin"][:limit]

            params = urllib.parse.urlencode({"searchType": "search", "searchword": query})
            raw_html = self.http_get_text(f"{self.search_url}?{params}")
            return self.parse_html_listings(raw_html)[:limit]

        return self.execute_with_retry("scrape_jobs_saramin", _run)
