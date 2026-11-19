from __future__ import annotations

import contextlib
import json
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Any, Iterator, Optional, TextIO


class JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON matching pipeline observability spec."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "job_id": getattr(record, "job_id", None),
            "stage": getattr(record, "stage", "general"),
            "status": getattr(record, "status", "info"),
            "latency_ms": getattr(record, "latency_ms", 0.0),
            "error": getattr(record, "error", None),
            "message": record.getMessage(),
        }
        metadata = getattr(record, "metadata", None)
        if metadata:
            payload["metadata"] = metadata
        return json.dumps(payload, ensure_ascii=False)


def get_logger(name: str = "pr_job_matcher", stream: Optional[TextIO] = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(stream or sys.stderr)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def emit_event(
    stage: str,
    status: str,
    *,
    job_id: Optional[str] = None,
    latency_ms: float = 0.0,
    error: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
    message: str = "",
    logger: Optional[logging.Logger] = None,
) -> dict[str, Any]:
    """Emit a structured JSON log event and return the payload dict."""
    target_logger = logger or get_logger()
    extra = {
        "job_id": job_id,
        "stage": stage,
        "status": status,
        "latency_ms": round(latency_ms, 2),
        "error": error,
        "metadata": metadata or {},
    }
    level = logging.ERROR if error else logging.INFO
    target_logger.log(level, message or f"{stage}:{status}", extra=extra)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "job_id": job_id,
        "stage": stage,
        "status": status,
        "latency_ms": round(latency_ms, 2),
        "error": error,
        "metadata": metadata or {},
    }


@contextlib.contextmanager
def log_stage(
    stage: str,
    *,
    job_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
    logger: Optional[logging.Logger] = None,
) -> Iterator[dict[str, Any]]:
    """Measure stage latency and emit structured JSON logs on completion or failure."""
    start = time.perf_counter()
    context: dict[str, Any] = dict(metadata or {})
    try:
        yield context
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        emit_event(
            stage,
            "failed",
            job_id=job_id,
            latency_ms=elapsed_ms,
            error=f"{type(exc).__name__}: {exc}",
            metadata=context,
            logger=logger,
        )
        raise
    else:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        emit_event(
            stage,
            "completed",
            job_id=job_id,
            latency_ms=elapsed_ms,
            error=None,
            metadata=context,
            logger=logger,
        )
