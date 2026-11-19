from __future__ import annotations

import re
from typing import Tuple

from src.models import PRSpec

SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password|passwd|client[_-]?secret)\s*[:=]\s*['\"]?[\w\-./+=]{8,}['\"]?"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9\-._~+/]{16,}=*"),
    re.compile(r"(?:postgres|postgresql|mysql|mariadb|mongodb|redis)(?:\+\w+)?://[^\s'\"`]+"),
    re.compile(r"\b(?:10\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.\d{1,3}\.\d{1,3}(?::\d+)?\b"),
    re.compile(r"\b[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.(?:internal|corp|local|lan|intranet)(?::\d+)?\b"),
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
]

TAG_KEYWORDS: dict[str, tuple[str, ...]] = {
    "gateway-fallback": (
        "gateway", "fallback", "timeout", "circuit", "upstream", "proxy",
        "게이트웨이", "장애 격리", "타임아웃", "서킷",
    ),
    "raw-sql-tx": (
        "sql", "transaction", "rollback", "idempotency", "mariadb", "mysql", "lock",
        "트랜잭션", "멱등", "락", "정산",
    ),
    "observability": (
        "loki", "grafana", "promtail", "logging", "monitoring", "alert", "trace",
        "observability", "관측", "로깅", "모니터링",
    ),
    "python-batch": (
        "python", "cron", "batch", "celery", "lambda", "scraper", "refactor",
        "배치", "파이프라인", "리팩토링", "스케줄",
    ),
    "llm-pipeline": (
        "llm", "chatgpt", "openai", "prompt", "agent", "briefing",
        "리포팅", "요약", "자동화",
    ),
}


def strip_secrets(text: str, custom_terms: Tuple[str, ...] = ()) -> str:
    """Scrub credentials, tokens, emails, private IPs, internal hostnames, and client names."""
    sanitized = text
    for pattern in SECRET_PATTERNS:
        sanitized = pattern.sub("[REDACTED]", sanitized)
    for term in custom_terms:
        cleaned_term = term.strip()
        if cleaned_term:
            sanitized = re.sub(re.escape(cleaned_term), "[REDACTED]", sanitized, flags=re.IGNORECASE)
    return sanitized


def extract_pr_spec(
    pr_id: int,
    title: str,
    problem: str,
    action: str,
    impact: str,
    repo: str = "local/repo",
    custom_terms: Tuple[str, ...] = (),
) -> PRSpec:
    """Sanitize PR text before inferring domain tags and building an abstracted PRSpec."""
    safe_title = strip_secrets(title, custom_terms=custom_terms)
    safe_problem = strip_secrets(problem, custom_terms=custom_terms)
    safe_action = strip_secrets(action, custom_terms=custom_terms)
    safe_impact = strip_secrets(impact, custom_terms=custom_terms)

    combined = f"{safe_title} {safe_problem} {safe_action} {safe_impact}".lower()
    tags = [tag for tag, kws in TAG_KEYWORDS.items() if any(kw in combined for kw in kws)]
    return PRSpec(
        pr_id=pr_id,
        repo=repo,
        title=safe_title,
        domain_tags=tags or ["general-backend"],
        problem=safe_problem,
        action=safe_action,
        impact=safe_impact,
    )
