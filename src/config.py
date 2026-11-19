from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    from pydantic import Field
    from pydantic_settings import BaseSettings, SettingsConfigDict

    HAS_PYDANTIC_SETTINGS = True
except ImportError:  # pragma: no cover - zero-install stdlib fallback
    HAS_PYDANTIC_SETTINGS = False


def _load_dotenv(env_path: Path) -> dict[str, str]:
    if not env_path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        values[key.strip()] = val.strip().strip("'\"")
    return values


def _parse_bool(val: str, default: bool) -> bool:
    if val == "":
        return default
    return val.lower() in {"1", "true", "yes", "on"}


def _parse_csv(val: str) -> list[str]:
    return [item.strip() for item in val.split(",") if item.strip()]


if HAS_PYDANTIC_SETTINGS:

    class Settings(BaseSettings):
        """Application configuration backed by pydantic-settings."""

        model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

        database_url: str = Field(default="sqlite:///pr_job_matcher.db")
        github_token: str = Field(default="")
        github_username: str = Field(default="backend-eng")
        github_repos: str = Field(default="owner/core-api,owner/batch-workers")

        llm_api_key: str = Field(default="")
        llm_base_url: str = Field(default="https://api.openai.com/v1")
        llm_model: str = Field(default="gpt-4o-mini")

        slack_webhook_url: str = Field(default="")
        discord_webhook_url: str = Field(default="")

        min_jd_length: int = Field(default=150)
        max_repost_threshold: int = Field(default=3)
        pitch_threshold: float = Field(default=70.0)
        exclude_si: bool = Field(default=True)
        review_weight_interview: float = Field(default=0.4)
        review_weight_employee: float = Field(default=0.6)
        proprietary_terms: str = Field(default="")

        @property
        def repo_list(self) -> list[str]:
            return _parse_csv(self.github_repos)

        @property
        def proprietary_term_tuple(self) -> tuple[str, ...]:
            return tuple(_parse_csv(self.proprietary_terms))

else:

    @dataclass
    class Settings:  # type: ignore[no-redef]
        """Zero-dependency settings loader mirroring Pydantic Settings API."""

        database_url: str = "sqlite:///pr_job_matcher.db"
        github_token: str = ""
        github_username: str = "backend-eng"
        github_repos: str = "owner/core-api,owner/batch-workers"

        llm_api_key: str = ""
        llm_base_url: str = "https://api.openai.com/v1"
        llm_model: str = "gpt-4o-mini"

        slack_webhook_url: str = ""
        discord_webhook_url: str = ""

        min_jd_length: int = 150
        max_repost_threshold: int = 3
        pitch_threshold: float = 70.0
        exclude_si: bool = True
        review_weight_interview: float = 0.4
        review_weight_employee: float = 0.6
        proprietary_terms: str = ""
        _extra: dict[str, str] = field(default_factory=dict, repr=False)

        @classmethod
        def from_env(cls, env_file: Optional[str] = ".env") -> "Settings":
            file_vals = _load_dotenv(Path(env_file)) if env_file else {}

            def _get(name: str, default: str = "") -> str:
                return os.environ.get(name, file_vals.get(name, default))

            return cls(
                database_url=_get("DATABASE_URL", "sqlite:///pr_job_matcher.db"),
                github_token=_get("GITHUB_TOKEN", ""),
                github_username=_get("GITHUB_USERNAME", "backend-eng"),
                github_repos=_get("GITHUB_REPOS", "owner/core-api,owner/batch-workers"),
                llm_api_key=_get("LLM_API_KEY", ""),
                llm_base_url=_get("LLM_BASE_URL", "https://api.openai.com/v1"),
                llm_model=_get("LLM_MODEL", "gpt-4o-mini"),
                slack_webhook_url=_get("SLACK_WEBHOOK_URL", ""),
                discord_webhook_url=_get("DISCORD_WEBHOOK_URL", ""),
                min_jd_length=int(_get("MIN_JD_LENGTH", "150")),
                max_repost_threshold=int(_get("MAX_REPOST_THRESHOLD", "3")),
                pitch_threshold=float(_get("PITCH_THRESHOLD", "70.0")),
                exclude_si=_parse_bool(_get("EXCLUDE_SI", "true"), True),
                review_weight_interview=float(_get("REVIEW_WEIGHT_INTERVIEW", "0.4")),
                review_weight_employee=float(_get("REVIEW_WEIGHT_EMPLOYEE", "0.6")),
                proprietary_terms=_get("PROPRIETARY_TERMS", ""),
            )

        @property
        def repo_list(self) -> list[str]:
            return _parse_csv(self.github_repos)

        @property
        def proprietary_term_tuple(self) -> tuple[str, ...]:
            return tuple(_parse_csv(self.proprietary_terms))


def load_settings(env_file: Optional[str] = ".env", **overrides: object) -> Settings:
    if HAS_PYDANTIC_SETTINGS:
        kwargs = {k: v for k, v in overrides.items() if v is not None}
        if env_file:
            return Settings(_env_file=env_file, **kwargs)
        return Settings(**kwargs)
    settings = Settings.from_env(env_file=env_file)
    for k, v in overrides.items():
        if v is not None and hasattr(settings, k):
            setattr(settings, k, v)
    return settings
