from __future__ import annotations

import abc
import random
import time
import urllib.error
import urllib.request
from typing import Callable, Optional, TypeVar

from src.models import JobPost, Review
from src.observability import log_stage

try:
    import httpx

    HAS_HTTPX = True
except ImportError:  # pragma: no cover - zero-install stdlib fallback
    HAS_HTTPX = False

T = TypeVar("T")


class RateLimitError(RuntimeError):
    """Raised when an upstream board responds with HTTP 429."""

    def __init__(self, message: str, retry_after: Optional[float] = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class BaseScraper(abc.ABC):
    """Abstract base scraper providing jittered exponential backoff and JSON stage logs."""

    source_name: str = "base"

    def __init__(
        self,
        *,
        use_fixtures: bool = True,
        max_retries: int = 3,
        base_delay: float = 0.25,
        timeout: float = 10.0,
        sleep_fn: Optional[Callable[[float], None]] = None,
    ) -> None:
        self.use_fixtures = use_fixtures
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.timeout = timeout
        self._sleep = sleep_fn or time.sleep

    def _compute_backoff(self, attempt: int, retry_after: Optional[float] = None) -> float:
        if retry_after is not None and retry_after > 0:
            return float(retry_after) + random.uniform(0.05, 0.25)
        exp_delay = self.base_delay * (2**attempt)
        jitter = random.uniform(0.0, self.base_delay)
        return exp_delay + jitter

    def execute_with_retry(self, stage_name: str, fn: Callable[[], T]) -> T:
        last_exc: Optional[Exception] = None
        with log_stage(stage_name, metadata={"source": self.source_name, "use_fixtures": self.use_fixtures}) as ctx:
            for attempt in range(self.max_retries):
                try:
                    result = fn()
                    ctx["attempts"] = attempt + 1
                    return result
                except RateLimitError as exc:
                    last_exc = exc
                    if attempt == self.max_retries - 1:
                        break
                    self._sleep(self._compute_backoff(attempt, retry_after=exc.retry_after))
                except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
                    last_exc = exc
                    if attempt == self.max_retries - 1:
                        break
                    self._sleep(self._compute_backoff(attempt))
            assert last_exc is not None
            raise last_exc

    def http_get_text(self, url: str, headers: Optional[dict[str, str]] = None) -> str:
        req_headers = {
            "User-Agent": "Mozilla/5.0 (compatible; PRJobMatcherBot/2.0)",
            "Accept": "application/json, text/html;q=0.9",
            **(headers or {}),
        }
        if HAS_HTTPX:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                resp = client.get(url, headers=req_headers)
                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After")
                    raise RateLimitError(
                        f"429 rate limited on {url}",
                        retry_after=float(retry_after) if retry_after else None,
                    )
                resp.raise_for_status()
                return resp.text

        req = urllib.request.Request(url, headers=req_headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                raise RateLimitError(
                    f"429 rate limited on {url}",
                    retry_after=float(retry_after) if retry_after else None,
                ) from exc
            raise


class JobScraper(BaseScraper, abc.ABC):
    """Abstract job board adapter."""

    @abc.abstractmethod
    def fetch_jobs(self, query: str = "backend", limit: int = 20) -> list[JobPost]:
        raise NotImplementedError


class ReviewScraper(BaseScraper, abc.ABC):
    """Abstract interview/employee review adapter."""

    @abc.abstractmethod
    def fetch_reviews(self, company: str) -> list[Review]:
        raise NotImplementedError
