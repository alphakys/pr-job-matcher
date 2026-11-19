from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.models import JobPost, MatchResult, PRSpec, Review
from src.storage.db import Database


def normalize_text(text: str) -> str:
    cleaned = re.sub(r"\(주\)|주식회사|㈜", " ", text.lower())
    cleaned = re.sub(r"[^\w가-힣\s]", " ", cleaned)
    return " ".join(cleaned.split())


def compute_simhash(text: str) -> str:
    """Compute a deterministic 64-bit SimHash hex digest over word and 3-gram tokens."""
    normalized = normalize_text(text)
    if not normalized:
        return "0" * 16

    words = normalized.split()
    tokens: list[str] = list(words)
    compact = normalized.replace(" ", "")
    for i in range(max(0, len(compact) - 2)):
        tokens.append(compact[i : i + 3])

    weights = [0] * 64
    for tok in tokens:
        digest = hashlib.md5(tok.encode("utf-8")).digest()
        value = int.from_bytes(digest[:8], "big")
        for bit in range(64):
            weights[bit] += 1 if (value >> bit) & 1 else -1

    fingerprint = 0
    for bit, score in enumerate(weights):
        if score >= 0:
            fingerprint |= 1 << bit
    return f"{fingerprint:016x}"


def hamming_distance(hex_a: str, hex_b: str) -> int:
    diff = int(hex_a, 16) ^ int(hex_b, 16)
    return bin(diff).count("1")


class Repository:
    """Idempotent persistence and 90-day SimHash repost churn tracking."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def upsert_pr_spec(self, pr: PRSpec, updated_at: Optional[datetime] = None) -> None:
        ts = (updated_at or datetime.now(timezone.utc)).isoformat()
        tags_json = json.dumps(pr.domain_tags, ensure_ascii=False)
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO pr_specs (repo, pr_number, title, domain_tags, problem, action, impact, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(pr_number) DO UPDATE SET
                    repo = excluded.repo,
                    title = excluded.title,
                    domain_tags = excluded.domain_tags,
                    problem = excluded.problem,
                    action = excluded.action,
                    impact = excluded.impact,
                    updated_at = excluded.updated_at
                """,
                (pr.repo, pr.pr_id, pr.title, tags_json, pr.problem, pr.action, pr.impact, ts),
            )

    def list_pr_specs(self) -> list[PRSpec]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT repo, pr_number, title, domain_tags, problem, action, impact FROM pr_specs ORDER BY pr_number ASC"
            ).fetchall()
        return [
            PRSpec(
                pr_id=int(row["pr_number"]),
                repo=str(row["repo"]),
                title=str(row["title"]),
                domain_tags=json.loads(row["domain_tags"]),
                problem=str(row["problem"]),
                action=str(row["action"]),
                impact=str(row["impact"]),
            )
            for row in rows
        ]

    def upsert_job_and_track_churn(
        self,
        job: JobPost,
        seen_at: Optional[datetime] = None,
        simhash_threshold: int = 12,
    ) -> int:
        now = seen_at or datetime.now(timezone.utc)
        now_iso = now.isoformat()
        cutoff_iso = (now - timedelta(days=90)).isoformat()

        company_norm = normalize_text(job.company)
        title_norm = normalize_text(job.title)
        content_hash = compute_simhash(job.body)

        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (id, source, external_id, company, title, body, url, base_repost_90d, first_seen_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, external_id) DO UPDATE SET
                    company = excluded.company,
                    title = excluded.title,
                    body = excluded.body,
                    url = excluded.url,
                    base_repost_90d = MAX(jobs.base_repost_90d, excluded.base_repost_90d),
                    last_seen_at = excluded.last_seen_at
                """,
                (
                    job.job_id,
                    job.source,
                    job.job_id,
                    job.company,
                    job.title,
                    job.body,
                    job.url,
                    int(job.repost_90d),
                    now_iso,
                    now_iso,
                ),
            )

            existing_same = conn.execute(
                "SELECT 1 FROM job_snapshots WHERE job_id = ? AND content_hash = ? LIMIT 1",
                (job.job_id, content_hash),
            ).fetchone()
            if existing_same is None:
                conn.execute(
                    """
                    INSERT INTO job_snapshots (job_id, company_normalized, title_normalized, content_hash, seen_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (job.job_id, company_norm, title_norm, content_hash, now_iso),
                )

            rows = conn.execute(
                """
                SELECT DISTINCT job_id, content_hash
                FROM job_snapshots
                WHERE company_normalized = ?
                  AND title_normalized = ?
                  AND seen_at >= ?
                """,
                (company_norm, title_norm, cutoff_iso),
            ).fetchall()

        similar_job_ids = {
            str(row["job_id"])
            for row in rows
            if hamming_distance(content_hash, str(row["content_hash"])) <= simhash_threshold
        }
        detected_reposts = max(0, len(similar_job_ids) - 1)
        return max(job.repost_90d, detected_reposts)

    def list_jobs(self) -> list[JobPost]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT id, source, company, title, body, url, base_repost_90d, last_seen_at FROM jobs ORDER BY id ASC"
            ).fetchall()

        jobs: list[JobPost] = []
        for row in rows:
            last_seen = datetime.fromisoformat(str(row["last_seen_at"]))
            base_job = JobPost(
                job_id=str(row["id"]),
                source=str(row["source"]),
                company=str(row["company"]),
                title=str(row["title"]),
                body=str(row["body"]),
                repost_90d=int(row["base_repost_90d"]),
                url=str(row["url"]),
            )
            repost_90d = max(base_job.repost_90d, self._count_reposts(base_job, last_seen))
            jobs.append(
                JobPost(
                    job_id=base_job.job_id,
                    source=base_job.source,
                    company=base_job.company,
                    title=base_job.title,
                    body=base_job.body,
                    repost_90d=repost_90d,
                    url=base_job.url,
                )
            )
        return jobs

    def _count_reposts(self, job: JobPost, as_of: datetime, simhash_threshold: int = 12) -> int:
        cutoff_iso = (as_of - timedelta(days=90)).isoformat()
        company_norm = normalize_text(job.company)
        title_norm = normalize_text(job.title)
        content_hash = compute_simhash(job.body)
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT job_id, content_hash
                FROM job_snapshots
                WHERE company_normalized = ?
                  AND title_normalized = ?
                  AND seen_at >= ?
                """,
                (company_norm, title_norm, cutoff_iso),
            ).fetchall()
        similar_job_ids = {
            str(row["job_id"])
            for row in rows
            if hamming_distance(content_hash, str(row["content_hash"])) <= simhash_threshold
        }
        return max(0, len(similar_job_ids) - 1)

    def upsert_reviews(self, company: str, reviews: list[Review], scraped_at: Optional[datetime] = None) -> None:
        ts = (scraped_at or datetime.now(timezone.utc)).isoformat()
        company_norm = normalize_text(company)
        with self.db.connect() as conn:
            for rev in reviews:
                norm = rev.company_normalized or company_norm
                conn.execute(
                    """
                    INSERT INTO reviews (company_normalized, source_platform, review_type, rating, body, scraped_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(company_normalized, source_platform, review_type, body) DO UPDATE SET
                        rating = excluded.rating,
                        scraped_at = excluded.scraped_at
                    """,
                    (norm, rev.source_platform, rev.source, float(rev.rating), rev.text, ts),
                )

    def get_reviews_for_company(self, company: str) -> list[Review]:
        company_norm = normalize_text(company)
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT company_normalized, source_platform, review_type, rating, body
                FROM reviews
                WHERE company_normalized = ?
                ORDER BY id ASC
                """,
                (company_norm,),
            ).fetchall()
        return [
            Review(
                source=row["review_type"],
                rating=float(row["rating"]),
                text=str(row["body"]),
                company_normalized=str(row["company_normalized"]),
                source_platform=str(row["source_platform"]),
            )
            for row in rows
        ]

    def save_match_result(self, job_id: str, result: MatchResult) -> None:
        decision = result.decision or result.status
        pitch_payload = json.dumps(
            {
                "matched_prs": result.matched_prs,
                "pitch_points": result.pitch_points,
                "interview_prep": result.interview_prep,
                "bottlenecks": result.bottlenecks,
            },
            ensure_ascii=False,
        )
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO match_results (
                    job_id, score, tech_fit_score, workplace_risk_score, decision, reason, pitch_payload, notified_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                ON CONFLICT(job_id) DO UPDATE SET
                    score = excluded.score,
                    tech_fit_score = excluded.tech_fit_score,
                    workplace_risk_score = excluded.workplace_risk_score,
                    decision = excluded.decision,
                    reason = excluded.reason,
                    pitch_payload = excluded.pitch_payload
                """,
                (
                    job_id,
                    float(result.score),
                    float(result.tech_fit_score),
                    float(result.workplace_risk_score),
                    decision,
                    result.reason,
                    pitch_payload,
                ),
            )

    def get_all_match_results(self) -> list[tuple[JobPost, MatchResult]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT j.id, j.source, j.company, j.title, j.body, j.url,
                       m.score, m.tech_fit_score, m.workplace_risk_score, m.decision, m.reason, m.pitch_payload, m.notified_at
                FROM match_results m
                JOIN jobs j ON j.id = m.job_id
                ORDER BY m.score DESC, j.id ASC
                """
            ).fetchall()
        return [self._row_to_pair(row) for row in rows]

    def get_unnotified_pitches(self) -> list[tuple[JobPost, MatchResult]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT j.id, j.source, j.company, j.title, j.body, j.url,
                       m.score, m.tech_fit_score, m.workplace_risk_score, m.decision, m.reason, m.pitch_payload, m.notified_at
                FROM match_results m
                JOIN jobs j ON j.id = m.job_id
                WHERE m.decision = 'PITCH' AND m.notified_at IS NULL
                ORDER BY m.score DESC, j.id ASC
                """
            ).fetchall()
        return [self._row_to_pair(row) for row in rows]

    def mark_notified(self, job_ids: list[str], notified_at: Optional[datetime] = None) -> None:
        if not job_ids:
            return
        ts = (notified_at or datetime.now(timezone.utc)).isoformat()
        with self.db.connect() as conn:
            for job_id in job_ids:
                conn.execute(
                    "UPDATE match_results SET notified_at = ? WHERE job_id = ?",
                    (ts, job_id),
                )

    @staticmethod
    def _row_to_pair(row: object) -> tuple[JobPost, MatchResult]:
        payload = json.loads(row["pitch_payload"])  # type: ignore[index]
        decision = row["decision"]  # type: ignore[index]
        job = JobPost(
            job_id=str(row["id"]),  # type: ignore[index]
            source=str(row["source"]),  # type: ignore[index]
            company=str(row["company"]),  # type: ignore[index]
            title=str(row["title"]),  # type: ignore[index]
            body=str(row["body"]),  # type: ignore[index]
            url=str(row["url"]),  # type: ignore[index]
        )
        result = MatchResult(
            status=decision,
            decision=decision,
            score=float(row["score"]),  # type: ignore[index]
            tech_fit_score=float(row["tech_fit_score"]),  # type: ignore[index]
            workplace_risk_score=float(row["workplace_risk_score"]),  # type: ignore[index]
            reason=str(row["reason"]),  # type: ignore[index]
            matched_prs=[int(x) for x in payload.get("matched_prs", [])],
            pitch_points=list(payload.get("pitch_points", [])),
            interview_prep=list(payload.get("interview_prep", [])),
            bottlenecks=list(payload.get("bottlenecks", [])),
        )
        return job, result
