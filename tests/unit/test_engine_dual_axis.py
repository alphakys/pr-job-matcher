from __future__ import annotations

import unittest

from src.models import JobPost, Review
from src.pr_extractor import extract_pr_spec
from src.scorer import score_job
from src.scrapers.base import RateLimitError
from src.scrapers.jobs import SaraminJobScraper, WantedJobScraper
from src.scrapers.reviews import JobplanetReviewScraper


class TestEngineDualAxisAndScrapers(unittest.TestCase):
    def setUp(self) -> None:
        self.prs = [
            extract_pr_spec(
                pr_id=101,
                title="Gateway Fallback & Idempotency",
                problem="Upstream timeouts caused duplicate settlement",
                action="Added Gateway Fallback + MariaDB idempotency checks",
                impact="100% retry consistency",
            ),
            extract_pr_spec(
                pr_id=102,
                title="Loki + Grafana Observability",
                problem="450+ cron jobs lacked centralized logging",
                action="Built Promtail/Loki/Grafana pipeline",
                impact="Triage time cut to <2m",
            ),
        ]

    def test_dual_axis_separates_tech_fit_from_workplace_risk(self) -> None:
        jd = JobPost(
            job_id="toxic-1",
            company="ToxicCommerce",
            title="Backend Engineer",
            body=(
                "We operate 300+ legacy Python cron pipelines and FastAPI services. "
                "Looking for an engineer to lead refactoring, build Promtail/Loki/Grafana observability, "
                "and stabilize API gateway fallback + MariaDB transaction idempotency under high load."
            ),
            repost_90d=1,
        )
        reviews = [
            Review(source="interview", rating=2.0, text="면접 준비 부족"),
            Review(source="employee", rating=1.3, text="주먹구구 운영, 야근 강요, micromanage, 퇴사율 심각"),
        ]
        res = score_job(jd, reviews, self.prs)
        self.assertEqual(res.decision, "SKIP")
        self.assertGreaterEqual(res.tech_fit_score, 75.0)
        self.assertGreaterEqual(res.workplace_risk_score, 65.0)
        self.assertGreaterEqual(len(res.interview_prep), 2)

    def test_si_outsourcing_exclusion_veto(self) -> None:
        jd = JobPost(
            job_id="si-1",
            company="OutsourcingHub",
            title="백엔드 개발자 (고객사 상주 외주 / SI 파견)",
            body=(
                "Python Django/FastAPI 기반 엔터프라이즈 백엔드 시스템 운영 및 고객사 상주 외주 프로젝트를 수행합니다. "
                "기존 대용량 배치 파이프라인 리팩토링, MariaDB 트랜잭션 유지보수 및 로그 모니터링 업무를 전담하게 되며, "
                "고객사 내부망 환경에서 장기 상주하며 API 연동 개발과 장애 대응을 함께 진행합니다."
            ),
            repost_90d=0,
        )
        res = score_job(jd, [], self.prs, exclude_si=True)
        self.assertEqual(res.status, "SKIP")
        self.assertEqual(res.reason, "excluded_si_outsourcing")

    def test_scraper_retry_handles_rate_limit_and_fixtures(self) -> None:
        sleep_calls: list[float] = []
        scraper = WantedJobScraper(use_fixtures=True, max_retries=3, base_delay=0.1, sleep_fn=sleep_calls.append)
        attempts = {"count": 0}

        def _flaky() -> str:
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise RateLimitError("429", retry_after=0.2)
            return "ok"

        self.assertEqual(scraper.execute_with_retry("test_retry", _flaky), "ok")
        self.assertEqual(attempts["count"], 2)
        self.assertEqual(len(sleep_calls), 1)

    def test_fixture_parsers_for_wanted_saramin_and_jobplanet(self) -> None:
        wanted_payload = {
            "data": [
                {
                    "id": 555,
                    "position": "Backend Engineer",
                    "company": {"name": "ScaleLab"},
                    "detail": {"intro": "Python FastAPI", "main_tasks": "Refactor cron"},
                }
            ]
        }
        w_jobs = WantedJobScraper.parse_api_payload(wanted_payload)
        self.assertEqual(len(w_jobs), 1)
        self.assertEqual(w_jobs[0].job_id, "wanted-555")

        saramin_html = (
            '<article data-rec-idx="777"><span class="corp_name">PayCore</span>'
            '<h2 class="job_tit">Server Dev</h2>'
            '<div class="job_desc">MariaDB transaction &amp; observability</div></article>'
        )
        s_jobs = SaraminJobScraper.parse_html_listings(saramin_html)
        self.assertEqual(len(s_jobs), 1)
        self.assertEqual(s_jobs[0].company, "PayCore")

        jp_revs = JobplanetReviewScraper.parse_reviews_json(
            "PayCore",
            {"reviews": [{"type": "interview", "rating": 4.5, "body": "Deep architecture interview"}]},
        )
        self.assertEqual(len(jp_revs), 1)
        self.assertEqual(jp_revs[0].source, "interview")


if __name__ == "__main__":
    unittest.main()
