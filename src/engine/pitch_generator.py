from __future__ import annotations

from typing import Optional

from src.engine.rubric import TOXIC_REVIEW_SIGNALS
from src.models import JobPost, PRSpec, Review


def draft_pitch(jd: JobPost, matched_prs: list[PRSpec]) -> list[str]:
    """Format top matched PRs into tailored Problem -> Action -> Impact talking points."""
    return [
        f"PR #{pr.pr_id} ({pr.title}): [Problem] {pr.problem} -> [Action] {pr.action} -> [Impact] {pr.impact}"
        for pr in matched_prs[:3]
    ]


def generate_interview_prep(
    jd: JobPost,
    reviews: list[Review],
    matched_prs: list[PRSpec],
    bottlenecks: Optional[list[str]] = None,
) -> list[str]:
    """Generate 2-3 reverse-interview questions distinguishing fixable debt from org dysfunction."""
    questions: list[str] = []
    tags = {tag for pr in matched_prs for tag in pr.domain_tags}
    review_text = " ".join(r.text.lower() for r in reviews)

    if "python-batch" in tags or "observability" in tags:
        questions.append(
            f"[{jd.company} Tech Debt Ownership] Are legacy script refactoring and Promtail/Loki/Grafana "
            "observability work allocated dedicated sprint capacity, or squeezed between feature hotfixes?"
        )

    if "gateway-fallback" in tags or "raw-sql-tx" in tags:
        questions.append(
            f"[{jd.company} Incident & Reliability] After an upstream timeout or transaction lock incident, "
            "do teams run blameless post-mortems that prioritize circuit breakers and idempotency guards?"
        )

    if any(sig in review_text for sig in TOXIC_REVIEW_SIGNALS) or jd.repost_90d > 0:
        questions.append(
            f"[{jd.company} Retention & Scope] This role or similar backend work appears to have high churn signals—"
            "what concrete engineering or management changes happened after recent departures?"
        )
    elif bottlenecks:
        questions.append(
            f"[{jd.company} Architecture Priorities] Among '{bottlenecks[0]}', what metric defines success "
            "for this engineer's first 90 days?"
        )

    if len(questions) < 2:
        questions.append(
            f"[{jd.company} Engineering Autonomy] How are database schema changes, raw SQL reviews, "
            "and deployment rollbacks owned between backend engineers and leadership?"
        )

    return questions[:3]
