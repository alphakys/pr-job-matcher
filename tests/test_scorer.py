import unittest

from src.models import JobPost, Review
from src.pr_extractor import extract_pr_spec, strip_secrets
from src.scorer import score_job


def _sample_prs():
    return [
        extract_pr_spec(
            pr_id=14,
            title="API Gateway Fallback & Idempotency",
            problem="External API timeouts caused duplicate notifications",
            action="Implemented Gateway fallback + idempotency key checks",
            impact="100% consistency under concurrent retries",
        ),
        extract_pr_spec(
            pr_id=21,
            title="Loki + Grafana Batch Observability",
            problem="450+ cron jobs failed silently without alerts",
            action="Built Promtail/Loki/Grafana centralized logging pipeline",
            impact="Reduced incident detection time to real-time",
        ),
    ]


class TestScorer(unittest.TestCase):
    def test_skip_low_effort_one_liner_jd(self):
        jd = JobPost(job_id="1", company="LazyCo", title="Dev", body="백엔드 급구. 열정 있는 분.", repost_90d=0)
        res = score_job(jd, [], _sample_prs())
        self.assertEqual(res.status, "SKIP")
        self.assertEqual(res.reason, "low_effort_short_jd")

    def test_skip_high_repost_churn(self):
        jd = JobPost(
            job_id="2",
            company="ChurnCo",
            title="Backend",
            body="A" * 200 + " python refactoring observability gateway fallback",
            repost_90d=3,
        )
        res = score_job(jd, [], _sample_prs())
        self.assertEqual(res.status, "SKIP")
        self.assertEqual(res.reason, "excessive_repost_churn")

    def test_toxic_culture_penalty_triggers_skip(self):
        jd = JobPost(
            job_id="3",
            company="ToxicCo",
            title="Backend",
            body="Looking for Python refactoring, observability, and gateway fallback experience across 200+ cron jobs.",
            repost_90d=1,
        )
        reviews = [
            Review(source="interview", rating=2.0, text="Disorganized interviewers"),
            Review(source="employee", rating=1.5, text="주먹구구 경영, 야근 강요, 퇴사율 심각"),
        ]
        res = score_job(jd, reviews, _sample_prs())
        self.assertEqual(res.status, "SKIP")
        self.assertLess(res.score, 70.0)

    def test_high_fit_scaling_job_returns_pitch_with_pr_points(self):
        jd = JobPost(
            job_id="4",
            company="GoodScale",
            title="Backend Engineer",
            body=(
                "We need a backend engineer to refactor 3,000 legacy Python cron scripts, "
                "add centralized Loki/Grafana observability, and stabilize external API gateway fallback "
                "and idempotency for our growing D2C commerce platform."
            ),
            repost_90d=0,
        )
        reviews = [
            Review(source="interview", rating=4.5, text="Respectful, deep architecture discussion"),
            Review(source="employee", rating=4.4, text="Strong engineering culture and autonomy"),
        ]
        res = score_job(jd, reviews, _sample_prs())
        self.assertEqual(res.status, "PITCH")
        self.assertGreaterEqual(res.score, 70.0)
        self.assertGreaterEqual(len(res.pitch_points), 1)

    def test_secret_stripping_masks_keys(self):
        raw = "Configured api_key=sk-1234567890abcdef1234567890 and contact admin@company.com"
        cleaned = strip_secrets(raw)
        self.assertNotIn("sk-1234567890", cleaned)
        self.assertNotIn("admin@company.com", cleaned)
        self.assertIn("[REDACTED]", cleaned)


if __name__ == "__main__":
    unittest.main()
