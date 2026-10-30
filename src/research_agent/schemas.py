"""Core Pydantic data contract for all agent inputs, internal results, and final outputs."""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

AnswerStatus = Literal[
    "answered",
    "partial",
    "insufficient_evidence",
    "out_of_scope",
    "invalid_input",
    "error",
]


class Confidence(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class SourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    url: str


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statement: str
    source_ids: list[str] = Field(..., min_length=1)
    support: Literal["supported", "weak"] = "supported"


class FinalAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    status: AnswerStatus
    short_answer: str
    key_findings: list[Finding] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)
    confidence: Confidence = Confidence.low
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_reasons: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class RunMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_time_s: float = 0.0
    llm_calls: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0


class RunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    answer: FinalAnswer
    plan: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)
    rejected: list[dict[str, Any]] = Field(default_factory=list)
    metrics: RunMetrics = Field(default_factory=RunMetrics)

