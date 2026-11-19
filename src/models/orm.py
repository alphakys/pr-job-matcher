from __future__ import annotations

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS pr_specs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo TEXT NOT NULL,
    pr_number INTEGER NOT NULL UNIQUE,
    title TEXT NOT NULL,
    domain_tags TEXT NOT NULL,
    problem TEXT NOT NULL,
    action TEXT NOT NULL,
    impact TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    url TEXT NOT NULL DEFAULT '',
    base_repost_90d INTEGER NOT NULL DEFAULT 0,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    UNIQUE(source, external_id)
);

CREATE TABLE IF NOT EXISTS job_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    company_normalized TEXT NOT NULL,
    title_normalized TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    seen_at TEXT NOT NULL,
    FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_job_snapshots_lookup
    ON job_snapshots(company_normalized, title_normalized, seen_at);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_normalized TEXT NOT NULL,
    source_platform TEXT NOT NULL,
    review_type TEXT NOT NULL CHECK(review_type IN ('interview', 'employee')),
    rating REAL NOT NULL,
    body TEXT NOT NULL,
    scraped_at TEXT NOT NULL,
    UNIQUE(company_normalized, source_platform, review_type, body)
);

CREATE TABLE IF NOT EXISTS match_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL UNIQUE,
    score REAL NOT NULL,
    tech_fit_score REAL NOT NULL,
    workplace_risk_score REAL NOT NULL,
    decision TEXT NOT NULL CHECK(decision IN ('PITCH', 'SKIP')),
    reason TEXT NOT NULL,
    pitch_payload TEXT NOT NULL,
    notified_at TEXT,
    FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE
);
"""

from typing import Optional

try:
    from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

    class Base(DeclarativeBase):
        pass

    class PRSpecORM(Base):
        __tablename__ = "pr_specs"
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        repo: Mapped[str] = mapped_column(String(255), nullable=False)
        pr_number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
        title: Mapped[str] = mapped_column(String(500), nullable=False)
        domain_tags: Mapped[str] = mapped_column(Text, nullable=False)
        problem: Mapped[str] = mapped_column(Text, nullable=False)
        action: Mapped[str] = mapped_column(Text, nullable=False)
        impact: Mapped[str] = mapped_column(Text, nullable=False)
        updated_at: Mapped[str] = mapped_column(String(64), nullable=False)

    class JobORM(Base):
        __tablename__ = "jobs"
        __table_args__ = (UniqueConstraint("source", "external_id", name="uq_source_external_id"),)
        id: Mapped[str] = mapped_column(String(128), primary_key=True)
        source: Mapped[str] = mapped_column(String(64), nullable=False)
        external_id: Mapped[str] = mapped_column(String(128), nullable=False)
        company: Mapped[str] = mapped_column(String(255), nullable=False)
        title: Mapped[str] = mapped_column(String(500), nullable=False)
        body: Mapped[str] = mapped_column(Text, nullable=False)
        url: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
        base_repost_90d: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
        first_seen_at: Mapped[str] = mapped_column(String(64), nullable=False)
        last_seen_at: Mapped[str] = mapped_column(String(64), nullable=False)

    class JobSnapshotORM(Base):
        __tablename__ = "job_snapshots"
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
        company_normalized: Mapped[str] = mapped_column(String(255), nullable=False)
        title_normalized: Mapped[str] = mapped_column(String(255), nullable=False)
        content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
        seen_at: Mapped[str] = mapped_column(String(64), nullable=False)

    class ReviewORM(Base):
        __tablename__ = "reviews"
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        company_normalized: Mapped[str] = mapped_column(String(255), nullable=False)
        source_platform: Mapped[str] = mapped_column(String(64), nullable=False)
        review_type: Mapped[str] = mapped_column(String(32), nullable=False)
        rating: Mapped[float] = mapped_column(Float, nullable=False)
        body: Mapped[str] = mapped_column(Text, nullable=False)
        scraped_at: Mapped[str] = mapped_column(String(64), nullable=False)

    class MatchResultORM(Base):
        __tablename__ = "match_results"
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), unique=True)
        score: Mapped[float] = mapped_column(Float, nullable=False)
        tech_fit_score: Mapped[float] = mapped_column(Float, nullable=False)
        workplace_risk_score: Mapped[float] = mapped_column(Float, nullable=False)
        decision: Mapped[str] = mapped_column(String(16), nullable=False)
        reason: Mapped[str] = mapped_column(String(255), nullable=False)
        pitch_payload: Mapped[str] = mapped_column(Text, nullable=False)
        notified_at: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    HAS_SQLALCHEMY = True
except ImportError:  # pragma: no cover - zero-install stdlib fallback
    HAS_SQLALCHEMY = False
