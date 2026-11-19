from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Optional

from src.models import JobPost, MatchResult
from src.observability import log_stage
from src.storage.repository import Repository

try:
    import httpx

    HAS_HTTPX = True
except ImportError:  # pragma: no cover - zero-install stdlib fallback
    HAS_HTTPX = False


class DigestNotifier:
    """Formats Dual-Axis match digests and dispatches one-time webhook alerts."""

    def __init__(
        self,
        *,
        slack_webhook_url: str = "",
        discord_webhook_url: str = "",
        timeout: float = 10.0,
    ) -> None:
        self.slack_webhook_url = slack_webhook_url
        self.discord_webhook_url = discord_webhook_url
        self.timeout = timeout

    @staticmethod
    def format_digest(
        pitches: list[tuple[JobPost, MatchResult]],
        all_results: Optional[list[tuple[JobPost, MatchResult]]] = None,
    ) -> str:
        lines: list[str] = [
            "========================================================================",
            "PR-TO-JOB MATCHER v2 :: DUAL-AXIS OPPORTUNITY DIGEST",
            "========================================================================",
        ]

        if not pitches:
            lines.append("No new unnotified PITCH opportunities in this cycle.")
        else:
            lines.append(f"New High-Signal Opportunities ({len(pitches)}):")
            lines.append("")
            for job, res in pitches:
                lines.append(
                    f"[PITCH] {job.company} — {job.title} ({job.source}: {job.job_id})"
                )
                lines.append(
                    f"  Total Score: {res.score:.2f}/100 | "
                    f"Tech Fit: {res.tech_fit_score:.1f}/100 | "
                    f"Workplace Risk: {res.workplace_risk_score:.1f}/100 (lower=safer)"
                )
                if job.url:
                    lines.append(f"  URL: {job.url}")
                if res.bottlenecks:
                    lines.append(f"  Inferred Bottlenecks: {', '.join(res.bottlenecks)}")
                lines.append("  Tailored PR Talking Points:")
                for pt in res.pitch_points:
                    lines.append(f"    * {pt}")
                if res.interview_prep:
                    lines.append("  Reverse-Interview Questions (Debt vs Dysfunction Check):")
                    for q in res.interview_prep:
                        lines.append(f"    ? {q}")
                lines.append("")

        if all_results:
            skips = [(j, r) for j, r in all_results if (r.decision or r.status) == "SKIP"]
            if skips:
                lines.append("------------------------------------------------------------------------")
                lines.append(f"Filtered Out / SKIP Audit ({len(skips)}):")
                for job, res in skips:
                    lines.append(
                        f"  [SKIP] {job.company} ({job.title}) -> "
                        f"Total: {res.score:.2f} | Tech Fit: {res.tech_fit_score:.1f} | "
                        f"Risk: {res.workplace_risk_score:.1f} | Reason: {res.reason}"
                    )
        lines.append("========================================================================")
        return "\n".join(lines)

    def _post_webhook(self, url: str, body: dict[str, Any]) -> None:
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if HAS_HTTPX:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, content=raw, headers=headers)
                resp.raise_for_status()
            return
        req = urllib.request.Request(url, data=raw, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            resp.read()

    def deliver_unnotified(
        self,
        repo: Repository,
        *,
        dry_run: bool = False,
        mark_delivered: bool = True,
    ) -> dict[str, Any]:
        with log_stage("digest_delivery", metadata={"dry_run": dry_run}) as ctx:
            unnotified = repo.get_unnotified_pitches()
            all_results = repo.get_all_match_results()
            digest_text = self.format_digest(unnotified, all_results=all_results)

            webhook_sent = False
            if unnotified and not dry_run:
                if self.slack_webhook_url:
                    try:
                        self._post_webhook(self.slack_webhook_url, {"text": digest_text})
                        webhook_sent = True
                    except (urllib.error.URLError, Exception) as exc:
                        ctx.setdefault("warnings", []).append(f"slack: {exc}")
                if self.discord_webhook_url:
                    try:
                        self._post_webhook(self.discord_webhook_url, {"content": digest_text[:1950]})
                        webhook_sent = True
                    except (urllib.error.URLError, Exception) as exc:
                        ctx.setdefault("warnings", []).append(f"discord: {exc}")

            notified_ids = [job.job_id for job, _ in unnotified]
            if mark_delivered and notified_ids:
                repo.mark_notified(notified_ids)

            ctx["delivered_count"] = len(notified_ids)
            ctx["webhook_sent"] = webhook_sent
            return {
                "delivered_count": len(notified_ids),
                "delivered_job_ids": notified_ids,
                "webhook_sent": webhook_sent,
                "digest_text": digest_text,
            }
