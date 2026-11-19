from __future__ import annotations

import io
import json
import logging
import tempfile
import unittest
from pathlib import Path

from src.cli import main, run_pipeline
from src.observability import JsonFormatter
from src.storage import Database, Repository


class TestPipelineE2E(unittest.TestCase):
    def test_run_dry_run_end_to_end_and_idempotency(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "e2e_test.db"
            db_url = f"sqlite:///{db_path}"

            # Capture structured JSON logs emitted by the pipeline logger
            log_stream = io.StringIO()
            logger = logging.getLogger("pr_job_matcher")
            handler = logging.StreamHandler(log_stream)
            handler.setFormatter(JsonFormatter())
            logger.addHandler(handler)
            try:
                first = run_pipeline(dry_run=True, db_url=db_url)
                second = run_pipeline(dry_run=True, db_url=db_url)
            finally:
                logger.removeHandler(handler)

            self.assertEqual(first["prs"], 4)
            self.assertEqual(first["crawl"]["jobs"], 5)
            self.assertEqual(first["score"]["pitch"], 2)
            self.assertEqual(first["score"]["skip"], 3)
            self.assertEqual(first["digest"]["delivered_count"], 2)

            digest_text = first["digest"]["digest_text"]
            self.assertIn("ScaleCommerce", digest_text)
            self.assertIn("CorePayPlatform", digest_text)
            self.assertIn("ChaosAgency", digest_text)
            self.assertIn("ChurnFinTech", digest_text)
            self.assertIn("ToxicCommerce", digest_text)
            self.assertIn("below_threshold_or_culture_risk", digest_text)
            self.assertIn("Reverse-Interview Questions", digest_text)

            # Second run must be idempotent: same job count and zero duplicate deliveries
            self.assertEqual(second["score"]["scored"], 5)
            self.assertEqual(second["digest"]["delivered_count"], 0)

            db = Database(db_url)
            repo = Repository(db)
            self.assertEqual(len(repo.list_jobs()), 5)
            self.assertEqual(len(repo.list_pr_specs()), 4)
            db.close()

            # Verify structured JSON log records satisfy observability contract
            log_lines = [line for line in log_stream.getvalue().splitlines() if line.strip()]
            self.assertGreaterEqual(len(log_lines), 5)
            parsed = [json.loads(line) for line in log_lines]
            for entry in parsed:
                for key in ("job_id", "stage", "status", "latency_ms", "error"):
                    self.assertIn(key, entry)

    def test_cli_entry_points_legacy_and_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_url = f"sqlite:///{Path(tmpdir) / 'cli_test.db'}"
            rc_run = main(["run", "--dry-run", "--db-url", db_url])
            self.assertEqual(rc_run, 0)
            rc_legacy = main([])
            self.assertEqual(rc_legacy, 0)


if __name__ == "__main__":
    unittest.main()
