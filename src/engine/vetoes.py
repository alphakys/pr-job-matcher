from __future__ import annotations

from typing import Optional

from src.models import JobPost

MIN_JD_LENGTH = 150
MAX_REPOST_THRESHOLD = 3

SI_EXCLUSION_KEYWORDS = (
    "상주 외주",
    "si 파견",
    "인력 파견",
    "파견직",
    "고객사 상주",
)

CONCRETE_TECH_CONTEXT = (
    "python",
    "django",
    "fastapi",
    "celery",
    "node",
    "nestjs",
    "typescript",
    "mysql",
    "mariadb",
    "postgres",
    "sql",
    "api",
    "gateway",
    "refactor",
    "observability",
    "grafana",
    "loki",
    "transaction",
    "fallback",
    "cron",
    "batch",
    "백엔드",
    "서버",
    "트랜잭션",
    "리팩토링",
    "파이프라인",
    "로깅",
    "장애",
)


def check_hard_veto(jd: JobPost, *, exclude_si: bool = False) -> Optional[str]:
    """Return a veto reason string if the job must be immediately skipped, else None."""
    body = jd.body.strip()
    if len(body) < MIN_JD_LENGTH:
        return "low_effort_short_jd"

    if jd.repost_90d >= MAX_REPOST_THRESHOLD:
        return "excessive_repost_churn"

    lowered = f"{jd.title} {body}".lower()
    if exclude_si and any(kw in lowered for kw in SI_EXCLUSION_KEYWORDS):
        return "excluded_si_outsourcing"

    if not any(kw in lowered for kw in CONCRETE_TECH_CONTEXT):
        return "zero_technical_context"

    return None
