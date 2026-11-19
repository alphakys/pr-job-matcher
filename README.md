# PR-to-Job Matcher & Toxic-Company Filter (v2)

An always-on **PR-to-Job Matcher & Toxic-Company Filter** pipeline that ingests your merged GitHub PRs, scrubs all credentials and proprietary infrastructure details, crawls backend job postings + interview/employee reviews, scores **Technical Bottleneck Fit** separately from **Workplace Risk**, and delivers tailored resume talking points alongside reverse-interview questions.

---

## Key Features (v2 Architecture)

- **Secret-Scrubbing PR Ingestion (`src/ingestion/`)**: Fetches merged PRs via GitHub REST API (or curated offline fixtures) and strips API keys, GitHub/OpenAI/AWS tokens, JWTs, Bearer headers, DB credentials, private IPs, internal hostnames, emails, and custom client terms **before** persistence or LLM calls.
- **90-Day SimHash Repost Churn Detection (`src/storage/`)**: Persists `pr_specs`, `jobs`, `job_snapshots`, `reviews`, and `match_results` in SQLite (or PostgreSQL via `DATABASE_URL`). Uses 64-bit SimHash locality hashing so minor JD typo edits are never double-counted, while recurring 90-day reposts are penalized (`-10/repost`) or hard-vetoed (`>= 3`).
- **Resilient Pluggable Scrapers (`src/scrapers/`)**: Abstract `BaseScraper` with jittered exponential backoff, HTTP `429 Retry-After` handling, and fixture replay adapters for Wanted, Saramin, Jobplanet, and Blind.
- **Dual-Axis Scoring & Hybrid Semantic Engine (`src/engine/`)**:
  - **Hard Vetoes**: Short/low-effort JDs (`< 150` chars), zero concrete technical context, `>= 3` reposts in 90 days, and optional SI/outsourcing exclusion (`EXCLUDE_SI=true`).
  - **Dual-Axis Output**: Reports `tech_fit_score` (0–100) independently from `workplace_risk_score` (0–100, lower is safer) so high-tech-fit toxic workplaces (e.g., `ToxicCommerce`) are transparently audited rather than hidden in a single number.
  - **Tailored Pitch & Reverse-Interview Prep**: Outputs `Problem -> Action -> Impact` PR bullets and 2–3 targeted reverse-interview questions to verify whether pain stems from fixable engineering debt or management dysfunction.
- **Structured Observability & One-Time Delivery (`src/observability.py`, `src/delivery/`)**: Every pipeline stage emits structured JSON logs (`job_id`, `stage`, `status`, `latency_ms`, `error`) and tracks `notified_at` to deliver each `PITCH` once.

---

## Project Layout

```text
pr-job-matcher/
├── pyproject.toml                 # PEP 621 / uv dependency manifest & tool config
├── .env.example                   # Environment configuration template
├── .github/workflows/
│   └── daily_digest.yml           # Scheduled daily cron & CI verification workflow
├── src/
│   ├── config.py                  # Pydantic Settings (+ zero-install env fallback)
│   ├── observability.py           # Structured JSON stage logger
│   ├── models/                    # Pydantic v2 domain schemas & SQLite/SQLAlchemy ORM
│   ├── ingestion/                 # GitHub PR client & regex/term sanitizer
│   ├── scrapers/                  # BaseScraper retry/backoff + Wanted/Saramin/Jobplanet/Blind
│   ├── engine/                    # Hard vetoes, rubric, semantic matcher, pitch generator
│   ├── storage/                   # SQLite persistence & SimHash snapshot churn repository
│   ├── delivery/                  # Digest formatter & one-time Slack/Discord notifier
│   ├── fixtures/                  # Realistic Korean/English dry-run seed dataset
│   └── cli.py                     # Typer / argparse CLI (`ingest-prs`, `crawl`, `score`, `digest`, `run`)
└── tests/
    ├── test_scorer.py             # Preserved v1 unit test suite
    ├── unit/                      # Sanitizer, SimHash storage, Dual-Axis & scraper tests
    └── integration/               # End-to-end offline pipeline & idempotency tests
```

---

## Dependency Manifest (`pyproject.toml`)

Declared dependencies for `uv` / `pip`:
- **Runtime**: `pydantic>=2.7.0`, `pydantic-settings>=2.2.0`, `sqlalchemy>=2.0.30`, `httpx>=0.27.0`, `typer>=0.12.3`, `rich>=13.7.1`
- **Dev**: `pytest>=8.2.0`, `pytest-cov>=5.0.0`, `ruff>=0.4.4`, `mypy>=1.10.0`

*(All modules include clean stdlib shims so the codebase also runs out-of-the-box on standard Python without installing packages.)*

---

## Quickstart & CLI Usage

```bash
# Run end-to-end offline dry-run pipeline (ingest -> crawl -> score -> digest)
python3 -m src.cli run --dry-run

# Run individual stages
python3 -m src.cli ingest-prs --dry-run
python3 -m src.cli crawl --dry-run
python3 -m src.cli score --dry-run
python3 -m src.cli digest --dry-run

# Legacy MVP sample output
python3 -m src.cli

# Run full test suite
python3 -m unittest discover -s tests -p "test_*.py" -v
```

### With `uv` (Production / CI)

```bash
uv sync --extra dev
uv run ruff check .
uv run pytest -v
uv run pr-job-matcher run --dry-run
```

---

## Sample `--dry-run` Digest Output

```text
========================================================================
PR-TO-JOB MATCHER v2 :: DUAL-AXIS OPPORTUNITY DIGEST
========================================================================
New High-Signal Opportunities (2):

[PITCH] ScaleCommerce — Backend & Automation Engineer (wanted: wanted-9004)
  Total Score: 90.53/100 | Tech Fit: 92.6/100 | Workplace Risk: 8.4/100 (lower=safer)
  Tailored PR Talking Points:
    * PR #102 (Promtail + Loki + Grafana Observability Stack for Batch Fleet): ...
    * PR #103 (MariaDB Explicit Transaction & Idempotency Key Guard): ...
    * PR #101 (Gateway Fallback & Timeout Isolation for External Notifications): ...
  Reverse-Interview Questions (Debt vs Dysfunction Check):
    ? [ScaleCommerce Tech Debt Ownership] Are legacy script refactoring and ...

------------------------------------------------------------------------
Filtered Out / SKIP Audit (3):
  [SKIP] ToxicCommerce (Backend Engineer (Python / MySQL)) -> Total: 51.90 | Tech Fit: 90.1 | Risk: 70.5 | Reason: below_threshold_or_culture_risk
  [SKIP] ChurnFinTech (Python/Node.js Backend Engineer) -> Total: 0.00 | Tech Fit: 0.0 | Risk: 60.1 | Reason: excessive_repost_churn
  [SKIP] ChaosAgency (Backend Rockstar (급구)) -> Total: 0.00 | Tech Fit: 0.0 | Risk: 100.0 | Reason: low_effort_short_jd
========================================================================
```
