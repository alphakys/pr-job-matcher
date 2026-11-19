from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any, Optional, Tuple

from src.fixtures.seed_data import SEED_RAW_PRS
from src.ingestion.sanitizer import extract_pr_spec, strip_secrets
from src.models import PRSpec
from src.observability import log_stage

try:
    import httpx

    HAS_HTTPX = True
except ImportError:  # pragma: no cover - zero-install stdlib fallback
    HAS_HTTPX = False


def _parse_pr_sections(safe_body: str, safe_title: str) -> Tuple[str, str, str]:
    """Extract Problem / Action / Impact from a pre-sanitized PR body."""
    sections: dict[str, str] = {}
    current: Optional[str] = None
    buffer: list[str] = []

    for line in safe_body.splitlines():
        header = re.match(r"^#{1,3}\s*(problem|context|action|changes|solution|impact|result)\b", line.strip(), re.I)
        if header:
            if current and buffer:
                sections[current] = " ".join(buffer).strip()
            key = header.group(1).lower()
            if key in {"problem", "context"}:
                current = "problem"
            elif key in {"action", "changes", "solution"}:
                current = "action"
            else:
                current = "impact"
            buffer = []
        elif line.strip():
            buffer.append(line.strip())

    if current and buffer:
        sections[current] = " ".join(buffer).strip()

    problem = sections.get("problem") or f"Addressed engineering bottleneck described in '{safe_title}'."
    action = sections.get("action") or (safe_body.strip()[:220] if safe_body.strip() else safe_title)
    impact = sections.get("impact") or "Improved system reliability and maintainability in production."
    return problem, action, impact


class GitHubPRClient:
    """Ingests merged GitHub PRs, scrubbing all secrets prior to parsing or storage."""

    def __init__(
        self,
        token: str = "",
        base_url: str = "https://api.github.com",
        custom_terms: Tuple[str, ...] = (),
        timeout: float = 10.0,
    ) -> None:
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.custom_terms = custom_terms
        self.timeout = timeout

    def _get_json(self, url: str) -> Any:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "pr-job-matcher/2.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        if HAS_HTTPX:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers=headers)
                resp.raise_for_status()
                return resp.json()

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def fetch_merged_prs(
        self,
        repos: Optional[list[str]] = None,
        *,
        limit: int = 20,
        dry_run: bool = False,
    ) -> list[PRSpec]:
        with log_stage("github_pr_ingest", metadata={"dry_run": dry_run, "repo_count": len(repos or [])}) as ctx:
            if dry_run or not self.token or not repos:
                ctx["mode"] = "fixture"
                specs = [
                    extract_pr_spec(
                        pr_id=int(item["pr_id"]),  # type: ignore[arg-type]
                        repo=str(item.get("repo", "local/seed")),
                        title=str(item["title"]),
                        problem=str(item["problem"]),
                        action=str(item["action"]),
                        impact=str(item["impact"]),
                        custom_terms=self.custom_terms,
                    )
                    for item in SEED_RAW_PRS
                ]
                ctx["ingested_count"] = len(specs)
                return specs

            ctx["mode"] = "github_api"
            specs: list[PRSpec] = []
            for repo in repos:
                url = f"{self.base_url}/repos/{repo}/pulls?state=closed&sort=updated&direction=desc&per_page={limit}"
                try:
                    pulls = self._get_json(url)
                except (urllib.error.URLError, Exception) as exc:
                    ctx.setdefault("warnings", []).append(f"{repo}: {exc}")
                    continue

                for pr in pulls:
                    if not pr.get("merged_at"):
                        continue
                    safe_title = strip_secrets(str(pr.get("title") or ""), custom_terms=self.custom_terms)
                    safe_body = strip_secrets(str(pr.get("body") or ""), custom_terms=self.custom_terms)
                    problem, action, impact = _parse_pr_sections(safe_body, safe_title)
                    specs.append(
                        extract_pr_spec(
                            pr_id=int(pr["number"]),
                            repo=repo,
                            title=safe_title,
                            problem=problem,
                            action=action,
                            impact=impact,
                            custom_terms=self.custom_terms,
                        )
                    )
            ctx["ingested_count"] = len(specs)
            return specs
