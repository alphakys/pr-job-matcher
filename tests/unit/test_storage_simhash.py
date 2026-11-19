from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from src.models import JobPost, MatchResult, PRSpec
from src.storage import Database, Repository, compute_simhash, hamming_distance


class TestStorageAndSimHash(unittest.TestCase):
    def setUp(self) -> None:
        self.db = Database(":memory:")
        self.repo = Repository(self.db)

    def tearDown(self) -> None:
        self.db.close()

    def test_simhash_typo_tolerance(self) -> None:
        base = (
            "We run 450 Python cron pipelines and build centralized Loki Grafana observability "
            "plus API gateway fallback across MariaDB transactions."
        )
        minor_edit = (
            "We run 450 Python cron pipelines and build centralized Loki Grafana observability "
            "plus API gateway fallback across MariaDB transactions!"
        )
        dist = hamming_distance(compute_simhash(base), compute_simhash(minor_edit))
        self.assertLessEqual(dist, 12)

    def test_idempotent_recrawl_and_90d_repost_churn(self) -> None:
        now = datetime(2026, 11, 20, tzinfo=timezone.utc)
        body = (
            "Python FastAPI backend engineer needed to refactor legacy cron pipelines, "
            "implement API gateway fallback, and improve MariaDB idempotency."
        )
        job1 = JobPost(job_id="wanted-1", source="wanted", company="(주)ScaleCo", title="Backend Engineer", body=body)
        # Initial sighting -> 0 reposts
        self.assertEqual(self.repo.upsert_job_and_track_churn(job1, seen_at=now - timedelta(days=60)), 0)
        # Re-crawling same job_id with typo edit must NOT double-count as a repost
        job1_typo = JobPost(
            job_id="wanted-1", source="wanted", company="(주)ScaleCo", title="Backend Engineer", body=body + " "
        )
        self.assertEqual(self.repo.upsert_job_and_track_churn(job1_typo, seen_at=now - timedelta(days=59)), 0)

        # Reposted under new external IDs within 90 days
        job2 = JobPost(job_id="wanted-2", source="wanted", company="ScaleCo", title="Backend Engineer", body=body)
        job3 = JobPost(job_id="wanted-3", source="wanted", company="ScaleCo", title="Backend Engineer", body=body)
        self.assertEqual(self.repo.upsert_job_and_track_churn(job2, seen_at=now - timedelta(days=30)), 1)
        self.assertEqual(self.repo.upsert_job_and_track_churn(job3, seen_at=now), 2)

        # Very old sighting (>90 days ago) should not inflate current 90d count
        old_job = JobPost(job_id="wanted-0", source="wanted", company="ScaleCo", title="Backend Engineer", body=body)
        self.repo.upsert_job_and_track_churn(old_job, seen_at=now - timedelta(days=120))
        self.assertEqual(self.repo.upsert_job_and_track_churn(job3, seen_at=now), 2)

    def test_pr_upsert_and_one_time_notification_tracking(self) -> None:
        pr = PRSpec(
            pr_id=10,
            repo="alpha/api",
            title="Gateway Fallback",
            domain_tags=["gateway-fallback"],
            problem="Upstream outages stalled checkout",
            action="Added timeout and fallback guard",
            impact="99.98% uptime",
        )
        self.repo.upsert_pr_spec(pr)
        self.repo.upsert_pr_spec(pr)
        self.assertEqual(len(self.repo.list_pr_specs()), 1)

        job = JobPost(job_id="w-100", company="GoodCo", title="Backend", body="Python refactoring observability " * 10)
        self.repo.upsert_job_and_track_churn(job)
        self.repo.save_match_result(
            "w-100",
            MatchResult(
                status="PITCH",
                decision="PITCH",
                score=85.0,
                tech_fit_score=90.0,
                workplace_risk_score=12.0,
                reason="strong_tech_fit_and_healthy_signals",
                matched_prs=[10],
                pitch_points=["PR #10 talking point"],
                interview_prep=["Question 1?"],
            ),
        )
        self.assertEqual(len(self.repo.get_unnotified_pitches()), 1)
        self.repo.mark_notified(["w-100"])
        self.assertEqual(len(self.repo.get_unnotified_pitches()), 0)


if __name__ == "__main__":
    unittest.main()
