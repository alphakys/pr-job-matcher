from __future__ import annotations

import unittest

from src.ingestion.github_pr_client import GitHubPRClient
from src.ingestion.sanitizer import extract_pr_spec, strip_secrets


class TestSanitizer(unittest.TestCase):
    def test_masks_tokens_keys_jwts_and_db_urls(self) -> None:
        raw = (
            "api_key=my_super_secret_value_123 "
            "ghp_1234567890abcdefghij1234567890 "
            "sk-proj-abcdefghijklmnopqrstuvwxyz123456 "
            "AKIA1234567890ABCDEF "
            "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3OCJ9.signature12345678 "
            "Bearer abcdefghijklmnopqrstuvwxyz1234 "
            "mysql+pymysql://admin:pa55w0rd@db.prod.local:3306/orders"
        )
        cleaned = strip_secrets(raw)
        for leaked in (
            "my_super_secret_value_123",
            "ghp_1234567890",
            "sk-proj-",
            "AKIA1234567890ABCDEF",
            "eyJhbGciOiJIUzI1NiJ9",
            "abcdefghijklmnopqrstuvwxyz1234",
            "pa55w0rd",
            "db.prod.local",
        ):
            self.assertNotIn(leaked, cleaned)
        self.assertIn("[REDACTED]", cleaned)

    def test_masks_emails_private_ips_internal_hosts_and_custom_clients(self) -> None:
        raw = (
            "Alert from 10.24.18.9 and 192.168.1.50 talking to billing.internal:8080 "
            "for AcmePrivateCorp; contact oncall@acme.kr."
        )
        cleaned = strip_secrets(raw, custom_terms=("AcmePrivateCorp",))
        self.assertNotIn("10.24.18.9", cleaned)
        self.assertNotIn("192.168.1.50", cleaned)
        self.assertNotIn("billing.internal", cleaned)
        self.assertNotIn("AcmePrivateCorp", cleaned)
        self.assertNotIn("oncall@acme.kr", cleaned)

    def test_github_client_dry_run_strips_secrets_from_seed_prs(self) -> None:
        client = GitHubPRClient(token="")
        specs = client.fetch_merged_prs(dry_run=True)
        self.assertGreaterEqual(len(specs), 3)
        joined = " ".join(f"{s.title} {s.problem} {s.action} {s.impact}" for s in specs)
        self.assertNotIn("ghp_mock", joined)
        self.assertNotIn("internal-pg.corp", joined)
        self.assertIn("[REDACTED]", joined)

    def test_extract_pr_spec_infers_multiple_domain_tags(self) -> None:
        spec = extract_pr_spec(
            pr_id=77,
            title="Stabilize MariaDB Transaction & Gateway Timeout",
            problem="Upstream timeout caused SQL lock contention",
            action="Added Gateway Fallback + idempotency transaction guard",
            impact="Zero duplicate settlements",
        )
        self.assertIn("gateway-fallback", spec.domain_tags)
        self.assertIn("raw-sql-tx", spec.domain_tags)


if __name__ == "__main__":
    unittest.main()
