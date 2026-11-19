from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Optional

from src.ingestion.sanitizer import TAG_KEYWORDS
from src.models import JobPost, PRSpec, Review
from src.observability import log_stage

try:
    import httpx

    HAS_HTTPX = True
except ImportError:  # pragma: no cover - zero-install stdlib fallback
    HAS_HTTPX = False

BOTTLENECK_LABELS: dict[str, str] = {
    "gateway-fallback": "Upstream timeout isolation & API gateway fallback",
    "raw-sql-tx": "Concurrent transaction locking & idempotency enforcement",
    "observability": "Centralized structured logging & real-time incident observability",
    "python-batch": "Legacy cron/batch modularization & pipeline stability",
    "llm-pipeline": "Automated LLM workflow & operational briefing pipelines",
}


def infer_bottlenecks(jd_body: str) -> list[str]:
    text = jd_body.lower()
    tags = [tag for tag, kws in TAG_KEYWORDS.items() if any(kw in text for kw in kws)]
    return [BOTTLENECK_LABELS.get(tag, tag) for tag in tags]


def match_pr_patterns(jd_body: str, prs: list[PRSpec]) -> tuple[float, list[PRSpec]]:
    text = jd_body.lower()
    needed_tags = {tag for tag, kws in TAG_KEYWORDS.items() if any(kw in text for kw in kws)}
    if not needed_tags or not prs:
        return 0.0, []

    scored_prs: list[tuple[int, PRSpec]] = []
    for pr in prs:
        overlap = len(needed_tags.intersection(pr.domain_tags))
        if overlap > 0:
            scored_prs.append((overlap, pr))

    scored_prs.sort(key=lambda x: x[0], reverse=True)
    matched = [pr for _, pr in scored_prs[:3]]
    fit_ratio = min(len(matched) / min(len(prs), 2), 1.0) if matched else 0.0
    return round(fit_ratio, 4), matched


class SemanticMatcher:
    """Combines deterministic PR tag matching with optional OpenAI-compatible LLM extraction."""

    def __init__(
        self,
        *,
        api_key: str = "",
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        dry_run: bool = True,
        timeout: float = 12.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.dry_run = dry_run
        self.timeout = timeout

    def _call_llm_json(self, jd: JobPost, reviews: list[Review], prs: list[PRSpec]) -> Optional[dict[str, Any]]:
        if self.dry_run or not self.api_key:
            return None

        pr_catalog = [
            {"pr_id": pr.pr_id, "title": pr.title, "tags": pr.domain_tags, "impact": pr.impact}
            for pr in prs
        ]
        review_snippets = [f"[{r.source}:{r.rating}] {r.text[:160]}" for r in reviews[:6]]
        prompt = {
            "job": {"company": jd.company, "title": jd.title, "body": jd.body[:2000]},
            "reviews": review_snippets,
            "prs": pr_catalog,
            "instruction": (
                "Return JSON with keys: bottlenecks (list[str]), "
                "matched_pr_ids (list[int]), semantic_fit_bonus (float 0..0.15)."
            ),
        }
        payload = json.dumps(
            {
                "model": self.model,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": "You analyze backend JDs against sanitized PR specs."},
                    {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                ],
                "temperature": 0.1,
            }
        ).encode("utf-8")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/chat/completions"

        try:
            if HAS_HTTPX:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(url, content=payload, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
            else:
                req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
        except (urllib.error.URLError, KeyError, ValueError, Exception):
            return None

    def analyze(
        self,
        jd: JobPost,
        reviews: list[Review],
        prs: list[PRSpec],
    ) -> tuple[float, list[PRSpec], list[str]]:
        with log_stage("semantic_match", job_id=jd.job_id, metadata={"dry_run": self.dry_run}) as ctx:
            fit_ratio, matched_prs = match_pr_patterns(jd.body, prs)
            bottlenecks = infer_bottlenecks(jd.body)

            llm_result = self._call_llm_json(jd, reviews, prs)
            if llm_result:
                ctx["engine"] = "hybrid_llm"
                bonus = max(0.0, min(0.15, float(llm_result.get("semantic_fit_bonus", 0.0))))
                fit_ratio = round(min(1.0, fit_ratio + bonus), 4)
                extra_bottlenecks = [str(b) for b in llm_result.get("bottlenecks", []) if b]
                for item in extra_bottlenecks:
                    if item not in bottlenecks:
                        bottlenecks.append(item)
            else:
                ctx["engine"] = "deterministic_fallback"

            ctx["matched_pr_count"] = len(matched_prs)
            return fit_ratio, matched_prs, bottlenecks
