from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any, Literal, Optional, Type, TypeVar

try:
    from pydantic import BaseModel, ConfigDict, Field, model_validator

    HAS_PYDANTIC = True
except ImportError:  # pragma: no cover - zero-install stdlib fallback
    HAS_PYDANTIC = False

T = TypeVar("T")


if HAS_PYDANTIC:

    class _SchemaBase(BaseModel):
        model_config = ConfigDict(frozen=True, populate_by_name=True)

        def to_dict(self) -> dict[str, Any]:
            return self.model_dump()

    class Review(_SchemaBase):
        source: Literal["interview", "employee"]
        rating: float = Field(ge=1.0, le=5.0)
        text: str
        company_normalized: str = ""
        source_platform: str = "jobplanet"

    class PRSpec(_SchemaBase):
        pr_id: int
        title: str
        domain_tags: list[str]
        problem: str
        action: str
        impact: str
        repo: str = "local/repo"

    class JobPost(_SchemaBase):
        job_id: str
        company: str
        title: str
        body: str
        repost_90d: int = 0
        url: str = ""
        source: str = "wanted"

    class MatchResult(_SchemaBase):
        status: Literal["PITCH", "SKIP"]
        score: float
        reason: str
        matched_prs: list[int] = Field(default_factory=list)
        pitch_points: list[str] = Field(default_factory=list)
        tech_fit_score: float = 0.0
        workplace_risk_score: float = 0.0
        decision: Optional[Literal["PITCH", "SKIP"]] = None
        interview_prep: list[str] = Field(default_factory=list)
        bottlenecks: list[str] = Field(default_factory=list)

        @model_validator(mode="after")
        def _sync_decision(self) -> "MatchResult":
            if self.decision is None:
                object.__setattr__(self, "decision", self.status)
            return self

else:

    class _StdlibSchemaMixin:
        def model_dump(self) -> dict[str, Any]:
            return asdict(self)  # type: ignore[arg-type]

        def to_dict(self) -> dict[str, Any]:
            return self.model_dump()

        def model_copy(self: T, *, update: Optional[dict[str, Any]] = None) -> T:
            return replace(self, **(update or {}))  # type: ignore[type-var]

        @classmethod
        def model_validate(cls: Type[T], data: dict[str, Any]) -> T:
            return cls(**data)

    @dataclass(frozen=True)
    class Review(_StdlibSchemaMixin):  # type: ignore[no-redef]
        source: Literal["interview", "employee"]
        rating: float
        text: str
        company_normalized: str = ""
        source_platform: str = "jobplanet"

        def __post_init__(self) -> None:
            if not (1.0 <= float(self.rating) <= 5.0):
                raise ValueError(f"Review rating must be between 1.0 and 5.0, got {self.rating}")

    @dataclass(frozen=True)
    class PRSpec(_StdlibSchemaMixin):  # type: ignore[no-redef]
        pr_id: int
        title: str
        domain_tags: list[str]
        problem: str
        action: str
        impact: str
        repo: str = "local/repo"

    @dataclass(frozen=True)
    class JobPost(_StdlibSchemaMixin):  # type: ignore[no-redef]
        job_id: str
        company: str
        title: str
        body: str
        repost_90d: int = 0
        url: str = ""
        source: str = "wanted"

    @dataclass(frozen=True)
    class MatchResult(_StdlibSchemaMixin):  # type: ignore[no-redef]
        status: Literal["PITCH", "SKIP"]
        score: float
        reason: str
        matched_prs: list[int] = field(default_factory=list)
        pitch_points: list[str] = field(default_factory=list)
        tech_fit_score: float = 0.0
        workplace_risk_score: float = 0.0
        decision: Optional[Literal["PITCH", "SKIP"]] = None
        interview_prep: list[str] = field(default_factory=list)
        bottlenecks: list[str] = field(default_factory=list)

        def __post_init__(self) -> None:
            if self.decision is None:
                object.__setattr__(self, "decision", self.status)
