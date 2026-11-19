"""Hybrid Dual-Axis scoring engine, hard vetoes, semantic matcher, and pitch generator."""

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

__all__ = [
    "BUZZWORD_FLUFF",
    "MAX_REPOST_THRESHOLD",
    "MIN_JD_LENGTH",
    "PITCH_THRESHOLD",
    "SemanticMatcher",
    "TECH_DEPTH_SIGNALS",
    "TOXIC_REVIEW_SIGNALS",
    "check_hard_veto",
    "compute_workplace_risk_score",
    "draft_pitch",
    "eval_jd_specificity",
    "generate_interview_prep",
    "infer_bottlenecks",
    "match_pr_patterns",
    "score_reviews",
]
