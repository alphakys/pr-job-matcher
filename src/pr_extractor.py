"""Backward-compatible wrapper around src.ingestion.sanitizer."""

from src.ingestion.sanitizer import SECRET_PATTERNS, TAG_KEYWORDS, extract_pr_spec, strip_secrets

__all__ = ["SECRET_PATTERNS", "TAG_KEYWORDS", "extract_pr_spec", "strip_secrets"]
