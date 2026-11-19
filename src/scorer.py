from __future__ import annotations

from typing import Optional

from src.engine.pitch_generator import draft_pitch, generate_interview_prep
from src.engine.rubric import (
    BUZZWORD_FLUFF,
    PITCH_THRESHOLD,
    TECH_DEPTH_SIGNALS,
    TOXIC_REVIEW_SIGNALS,
    compute_workplace_risk_score,
    eval_jd_specificity,
    score_reviews,
)
from src.engine.semantic_matcher import SemanticMatcher, infer_bottlenecks, match_pr_patterns
from src.engine.vetoes import MAX_REPOST_THRESHOLD, MIN_JD_LENGTH, check_hard_veto
from src.models import JobPost, MatchResult, PRSpec, Review
from src.observability import log_stage

__all__ = [
    "BUZZWORD_FLUFF",
    "MAX_REPOST_THRESHOLD",
    "MIN_JD_LENGTH",
    "PITCH_THRESHOLD",
    "TECH_DEPTH_SIGNALS",
    "TOXIC_REVIEW_SIGNALS",
    "draft_pitch",
    "eval_jd_specificity",
    "match_pr_patterns",
    "score_job",
    "score_reviews",
]


def score_job(
    jd: JobPost,
    reviews: list[Review],
    prs: list[PRSpec],
    *,
    exclude_si: bool = False,
    pitch_threshold: float = PITCH_THRESHOLD,
    review_weights: tuple[float, float] = (0.4, 0.6),
    semantic_matcher: Optional[SemanticMatcher] = None,
) -> MatchResult:
    """Evaluate a job posting using Dual-Axis (Tech Fit vs Workplace Risk) scoring."""
    with log_stage("score_job", job_id=jd.job_id, metadata={"company": jd.company}) as ctx:
        culture = score_reviews(reviews, weights=review_weights)
        veto_reason = check_hard_veto(jd, exclude_si=exclude_si)
        if veto_reason is not None:
            workplace_risk = compute_workplace_risk_score(jd, reviews, culture_norm=culture)
            ctx["decision"] = "SKIP"
            ctx["reason"] = veto_reason
            return MatchResult(
                status="SKIP",
                decision="SKIP",
                score=0.0,
                tech_fit_score=0.0,
                workplace_risk_score=max(workplace_risk, 60.0) if veto_reason != "low_effort_short_jd" else workplace_risk,
                reason=veto_reason,
            )

        if semantic_matcher is not None:
            tech_fit, matched_prs, bottlenecks = semantic_matcher.analyze(jd, reviews, prs)
        else:
            tech_fit, matched_prs = match_pr_patterns(jd.body, prs)
            bottlenecks = infer_bottlenecks(jd.body)

        jd_depth = eval_jd_specificity(jd.body)
        tech_fit_score = round(max(0.0, min(100.0, ((tech_fit * 0.55) + (jd_depth * 0.45)) * 100.0)), 2)
        workplace_risk_score = compute_workplace_risk_score(jd, reviews, culture_norm=culture)

        raw_score = (tech_fit * 35.0) + (jd_depth * 30.0) + (culture * 35.0) - (jd.repost_90d * 10.0)
        total = round(max(0.0, min(100.0, raw_score)), 2)

        if total >= pitch_threshold:
            ctx["decision"] = "PITCH"
            ctx["score"] = total
            return MatchResult(
                status="PITCH",
                decision="PITCH",
                score=total,
                tech_fit_score=tech_fit_score,
                workplace_risk_score=workplace_risk_score,
                reason="strong_tech_fit_and_healthy_signals",
                matched_prs=[pr.pr_id for pr in matched_prs],
                pitch_points=draft_pitch(jd, matched_prs),
                interview_prep=generate_interview_prep(jd, reviews, matched_prs, bottlenecks=bottlenecks),
                bottlenecks=bottlenecks,
            )

        ctx["decision"] = "SKIP"
        ctx["score"] = total
        return MatchResult(
            status="SKIP",
            decision="SKIP",
            score=total,
            tech_fit_score=tech_fit_score,
            workplace_risk_score=workplace_risk_score,
            reason="below_threshold_or_culture_risk",
            matched_prs=[pr.pr_id for pr in matched_prs],
            interview_prep=generate_interview_prep(jd, reviews, matched_prs, bottlenecks=bottlenecks),
            bottlenecks=bottlenecks,
        )
