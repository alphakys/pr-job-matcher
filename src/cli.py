from __future__ import annotations

import argparse
import sys
from typing import Any, Optional

from src.config import Settings, load_settings
from src.delivery.notifier import DigestNotifier
from src.engine.semantic_matcher import SemanticMatcher
from src.ingestion.github_pr_client import GitHubPRClient
from src.models import JobPost, Review
from src.observability import log_stage
from src.pr_extractor import extract_pr_spec
from src.scorer import score_job
from src.scrapers.jobs import SaraminJobScraper, WantedJobScraper
from src.scrapers.reviews import BlindReviewScraper, JobplanetReviewScraper
from src.storage import Database, Repository


def _build_repo(db_url: Optional[str] = None, settings: Optional[Settings] = None) -> tuple[Settings, Database, Repository]:
    cfg = settings or load_settings(database_url=db_url)
    db = Database(db_url or cfg.database_url)
    return cfg, db, Repository(db)


def run_ingest_prs(*, dry_run: bool = False, db_url: Optional[str] = None) -> int:
    cfg, db, repo = _build_repo(db_url=db_url)
    try:
        client = GitHubPRClient(
            token=cfg.github_token,
            custom_terms=cfg.proprietary_term_tuple,
        )
        specs = client.fetch_merged_prs(repos=cfg.repo_list, dry_run=dry_run)
        for pr in specs:
            repo.upsert_pr_spec(pr)
        return len(specs)
    finally:
        db.close()


def run_crawl(*, dry_run: bool = False, db_url: Optional[str] = None) -> dict[str, int]:
    cfg, db, repo = _build_repo(db_url=db_url)
    try:
        use_fixtures = dry_run or not bool(cfg.github_token and cfg.llm_api_key)
        # Always allow explicit fixture mode when dry_run=True; when live, attempt live adapters with fixture fallback
        wanted = WantedJobScraper(use_fixtures=dry_run)
        saramin = SaraminJobScraper(use_fixtures=dry_run)
        jobplanet = JobplanetReviewScraper(use_fixtures=dry_run)
        blind = BlindReviewScraper(use_fixtures=dry_run)

        jobs: list[JobPost] = []
        for scraper in (wanted, saramin):
            try:
                jobs.extend(scraper.fetch_jobs())
            except Exception:
                if not dry_run and use_fixtures:
                    scraper.use_fixtures = True
                    jobs.extend(scraper.fetch_jobs())

        companies_seen: set[str] = set()
        review_count = 0
        for job in jobs:
            repo.upsert_job_and_track_churn(job)
            if job.company not in companies_seen:
                companies_seen.add(job.company)
                revs: list[Review] = []
                for rev_scraper in (jobplanet, blind):
                    try:
                        revs.extend(rev_scraper.fetch_reviews(job.company))
                    except Exception:
                        continue
                if revs:
                    repo.upsert_reviews(job.company, revs)
                    review_count += len(revs)

        return {"jobs": len(jobs), "reviews": review_count}
    finally:
        db.close()


def run_score(*, dry_run: bool = False, db_url: Optional[str] = None) -> dict[str, int]:
    cfg, db, repo = _build_repo(db_url=db_url)
    try:
        prs = repo.list_pr_specs()
        jobs = repo.list_jobs()
        matcher = SemanticMatcher(
            api_key=cfg.llm_api_key,
            base_url=cfg.llm_base_url,
            model=cfg.llm_model,
            dry_run=dry_run,
        )
        pitch_count = 0
        skip_count = 0
        for job in jobs:
            revs = repo.get_reviews_for_company(job.company)
            res = score_job(
                job,
                revs,
                prs,
                exclude_si=cfg.exclude_si,
                pitch_threshold=cfg.pitch_threshold,
                review_weights=(cfg.review_weight_interview, cfg.review_weight_employee),
                semantic_matcher=matcher,
            )
            repo.save_match_result(job.job_id, res)
            if (res.decision or res.status) == "PITCH":
                pitch_count += 1
            else:
                skip_count += 1
        return {"scored": len(jobs), "pitch": pitch_count, "skip": skip_count}
    finally:
        db.close()


def run_digest(*, dry_run: bool = False, db_url: Optional[str] = None) -> dict[str, Any]:
    cfg, db, repo = _build_repo(db_url=db_url)
    try:
        notifier = DigestNotifier(
            slack_webhook_url=cfg.slack_webhook_url,
            discord_webhook_url=cfg.discord_webhook_url,
        )
        return notifier.deliver_unnotified(repo, dry_run=dry_run)
    finally:
        db.close()


def run_pipeline(*, dry_run: bool = False, db_url: Optional[str] = None) -> dict[str, Any]:
    with log_stage("pipeline_run", metadata={"dry_run": dry_run}) as ctx:
        pr_count = run_ingest_prs(dry_run=dry_run, db_url=db_url)
        crawl_stats = run_crawl(dry_run=dry_run, db_url=db_url)
        score_stats = run_score(dry_run=dry_run, db_url=db_url)
        digest_stats = run_digest(dry_run=dry_run, db_url=db_url)
        ctx.update({"prs": pr_count, **crawl_stats, **score_stats, "delivered": digest_stats["delivered_count"]})
        return {
            "prs": pr_count,
            "crawl": crawl_stats,
            "score": score_stats,
            "digest": digest_stats,
        }


def run_legacy_sample_demo() -> None:
    """Preserve MVP `python3 -m src.cli` standalone sample output."""
    prs = [
        extract_pr_spec(
            pr_id=101,
            title="Gateway Fallback & Timeout Isolation",
            problem="External Alimtalk and payment API outages cascaded to core checkout",
            action="Built Gateway Fallback layer with explicit timeout and retry guards",
            impact="Prevented full-service downtime during upstream API failures",
        ),
        extract_pr_spec(
            pr_id=102,
            title="Promtail + Loki + Grafana Observability Stack",
            problem="Scattered cron and API logs delayed incident root-cause analysis",
            action="Deployed centralized Promtail/Loki/Grafana logging and alert dashboards",
            impact="Cut debugging and incident triage time across batch pipelines",
        ),
    ]

    sample_jobs = [
        (
            JobPost(
                job_id="job-bad-1",
                company="ChaosAgency",
                title="Backend Rockstar",
                body="백엔드 개발자 급구. 가족같은 분위기. 다양한 업무 가능자.",
                repost_90d=4,
            ),
            [Review(source="employee", rating=1.5, text="주먹구구 운영, 잦은 야근, 퇴사율 높음")],
        ),
        (
            JobPost(
                job_id="job-good-1",
                company="ScaleCommerce",
                title="Backend & Automation Engineer",
                body=(
                    "We run 450+ Python cron pipelines and Next.js internal dashboards. "
                    "Looking for an engineer to refactor legacy scripts into shared modules, "
                    "build centralized logging/observability, and harden external API fallback "
                    "and idempotency across high-concurrency MariaDB transactions."
                ),
                repost_90d=0,
            ),
            [
                Review(source="interview", rating=4.5, text="Technical interview focused on real architecture."),
                Review(source="employee", rating=4.3, text="Good engineering autonomy and clear goals."),
            ],
        ),
    ]

    for jd, revs in sample_jobs:
        res = score_job(jd, revs, prs)
        print(
            f"[{res.status}] {jd.company} ({res.score} pts | "
            f"TechFit={res.tech_fit_score} | Risk={res.workplace_risk_score}) -> {res.reason}"
        )
        for pt in res.pitch_points:
            print(f"   - {pt}")


try:
    import typer

    app = typer.Typer(help="PR-to-Job Matcher & Toxic-Company Filter CLI")

    @app.command("ingest-prs")
    def _cli_ingest_prs(
        dry_run: bool = typer.Option(False, "--dry-run", help="Use fixture PRs without GitHub API calls"),
        db_url: Optional[str] = typer.Option(None, "--db-url", help="Override DATABASE_URL"),
    ) -> None:
        count = run_ingest_prs(dry_run=dry_run, db_url=db_url)
        typer.echo(f"Ingested {count} sanitized PR specs.")

    @app.command("crawl")
    def _cli_crawl(
        dry_run: bool = typer.Option(False, "--dry-run", help="Replay fixture job boards & reviews"),
        db_url: Optional[str] = typer.Option(None, "--db-url", help="Override DATABASE_URL"),
    ) -> None:
        stats = run_crawl(dry_run=dry_run, db_url=db_url)
        typer.echo(f"Crawled {stats['jobs']} jobs and {stats['reviews']} reviews.")

    @app.command("score")
    def _cli_score(
        dry_run: bool = typer.Option(False, "--dry-run", help="Disable live LLM calls"),
        db_url: Optional[str] = typer.Option(None, "--db-url", help="Override DATABASE_URL"),
    ) -> None:
        stats = run_score(dry_run=dry_run, db_url=db_url)
        typer.echo(f"Scored {stats['scored']} jobs (PITCH={stats['pitch']}, SKIP={stats['skip']}).")

    @app.command("digest")
    def _cli_digest(
        dry_run: bool = typer.Option(False, "--dry-run", help="Format digest without sending webhooks"),
        db_url: Optional[str] = typer.Option(None, "--db-url", help="Override DATABASE_URL"),
    ) -> None:
        res = run_digest(dry_run=dry_run, db_url=db_url)
        typer.echo(res["digest_text"])

    @app.command("run")
    def _cli_run(
        dry_run: bool = typer.Option(False, "--dry-run", help="Execute full pipeline offline using fixtures"),
        db_url: Optional[str] = typer.Option(None, "--db-url", help="Override DATABASE_URL"),
    ) -> None:
        res = run_pipeline(dry_run=dry_run, db_url=db_url)
        typer.echo(res["digest"]["digest_text"])

    HAS_TYPER = True
except ImportError:  # pragma: no cover - zero-install stdlib fallback
    HAS_TYPER = False
    app = None  # type: ignore[assignment]


def _build_argparse_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pr-job-matcher",
        description="PR-to-Job Matcher & Toxic-Company Filter CLI (v2)",
    )
    sub = parser.add_subparsers(dest="command")
    for name in ("ingest-prs", "crawl", "score", "digest", "run"):
        cmd_parser = sub.add_parser(name)
        cmd_parser.add_argument("--dry-run", action="store_true", help="Run offline on curated fixtures")
        cmd_parser.add_argument("--db-url", default=None, help="SQLite/PostgreSQL DATABASE_URL override")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if not args_list:
        run_legacy_sample_demo()
        return 0

    if HAS_TYPER and argv is None:
        app()
        return 0

    parser = _build_argparse_parser()
    parsed = parser.parse_args(args_list)
    cmd = parsed.command
    if cmd == "ingest-prs":
        count = run_ingest_prs(dry_run=parsed.dry_run, db_url=parsed.db_url)
        print(f"Ingested {count} sanitized PR specs.")
    elif cmd == "crawl":
        stats = run_crawl(dry_run=parsed.dry_run, db_url=parsed.db_url)
        print(f"Crawled {stats['jobs']} jobs and {stats['reviews']} reviews.")
    elif cmd == "score":
        stats = run_score(dry_run=parsed.dry_run, db_url=parsed.db_url)
        print(f"Scored {stats['scored']} jobs (PITCH={stats['pitch']}, SKIP={stats['skip']}).")
    elif cmd == "digest":
        res = run_digest(dry_run=parsed.dry_run, db_url=parsed.db_url)
        print(res["digest_text"])
    elif cmd == "run":
        res = run_pipeline(dry_run=parsed.dry_run, db_url=parsed.db_url)
        print(res["digest"]["digest_text"])
    else:
        parser.print_help()
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
