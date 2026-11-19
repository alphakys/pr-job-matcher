from __future__ import annotations

from typing import Optional

from src.models import JobPost, Review

PITCH_THRESHOLD = 70.0

TECH_DEPTH_SIGNALS = (
    "refactor",
    "리팩토링",
    "observability",
    "관측",
    "로깅",
    "grafana",
    "loki",
    "transaction",
    "트랜잭션",
    "fallback",
    "장애",
    "latency",
    "병목",
    "cron",
    "예약 작업",
    "pipeline",
    "파이프라인",
    "gateway",
    "idempotency",
    "멱등",
)

BUZZWORD_FLUFF = ("rockstar", "ninja", "가족같은", "열정", "만능", "급구")
TOXIC_REVIEW_SIGNALS = ("micromanage", "주먹구구", "체불", "야근", "burnout", "퇴사율", "독단", "갑질")


def eval_jd_specificity(body: str) -> float:
    text = body.lower()
    tech_hits = sum(1 for kw in TECH_DEPTH_SIGNALS if kw in text)
    fluff_hits = sum(1 for kw in BUZZWORD_FLUFF if kw in text)
    length_bonus = min(len(body.strip()) / 600.0, 1.0) * 0.35
    tech_score = min(tech_hits / 4.0, 1.0) * 0.65
    penalty = fluff_hits * 0.15
    return max(0.0, min(1.0, length_bonus + tech_score - penalty))


def score_reviews(reviews: list[Review], weights: tuple[float, float] = (0.4, 0.6)) -> float:
    if not reviews:
        return 0.5  # Neutral baseline when no reviews exist

    interview_revs = [r for r in reviews if r.source == "interview"]
    employee_revs = [r for r in reviews if r.source == "employee"]

    def _avg_norm(items: list[Review]) -> float:
        if not items:
            return 0.5
        base = sum((r.rating - 1.0) / 4.0 for r in items) / len(items)
        toxic_hits = sum(
            1 for r in items for kw in TOXIC_REVIEW_SIGNALS if kw in r.text.lower()
        )
        return max(0.0, base - (toxic_hits * 0.15))

    w_int, w_emp = weights
    if interview_revs and employee_revs:
        return round(_avg_norm(interview_revs) * w_int + _avg_norm(employee_revs) * w_emp, 4)
    if employee_revs:
        return round(_avg_norm(employee_revs), 4)
    return round(_avg_norm(interview_revs), 4)


def compute_workplace_risk_score(
    jd: JobPost,
    reviews: list[Review],
    culture_norm: Optional[float] = None,
) -> float:
    """Compute workplace risk on a 0-100 scale (lower is safer)."""
    norm = score_reviews(reviews) if culture_norm is None else culture_norm
    review_risk = (1.0 - max(0.0, min(1.0, norm))) * 65.0
    repost_risk = min(jd.repost_90d * 12.0, 25.0)
    fluff_hits = sum(1 for kw in BUZZWORD_FLUFF if kw in f"{jd.title} {jd.body}".lower())
    fluff_risk = min(fluff_hits * 8.0, 15.0)
    return round(max(0.0, min(100.0, review_risk + repost_risk + fluff_risk)), 2)
