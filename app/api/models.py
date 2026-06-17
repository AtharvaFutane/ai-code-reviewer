# app/api/models.py
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field
import uuid


# ─── Inbound ────────────────────────────────────────────────────────────────

class ReviewRequest(BaseModel):
    """Body for POST /review."""
    diff: str = Field(..., description="Raw text output of git diff for the PR")
    language: str = Field(
        ...,
        description="Primary language: python, javascript, typescript, go, rust, etc.",
    )
    context: Optional[str] = Field(
        None,
        description="Optional one-sentence description of what this PR is supposed to do",
    )


# ─── Outbound: sub-types ────────────────────────────────────────────────────

SeverityLevel = Literal["critical", "high", "medium", "low"]
CategoryType = Literal["security", "performance", "correctness", "style", "test_coverage"]
VerdictType = Literal["approve", "request_changes", "needs_discussion"]
OverallSeverityType = Literal["critical", "high", "medium", "low", "clean"]


class Finding(BaseModel):
    """A single review finding — line-level, categorised, with fix suggestion."""
    id: str = Field(..., description="Sequential ID: F-001, F-002, ...")
    line: int = Field(..., description="Affected line number in the diff")
    line_content: str = Field(..., description="Exact line of code from the diff")
    category: CategoryType
    severity: SeverityLevel
    title: str = Field(..., description="Short label, e.g. 'SQL Injection via string interpolation'")
    description: str = Field(..., description="Clear explanation of the issue and why it matters")
    suggestion: str = Field(..., description="Concrete fix, ideally with a corrected code snippet")


class AgentFindingsCount(BaseModel):
    security: int = 0
    performance: int = 0
    correctness: int = 0
    style: int = 0
    test_coverage: int = 0


class ReviewReport(BaseModel):
    """
    Full review output — matches the exact schema from the Infravox assignment.
    Every POST /review returns this model. Every GET /review/{id} returns this model.
    """
    review_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pr_summary: str = Field(..., description="One sentence describing what this PR does")
    verdict: VerdictType
    verdict_reason: str = Field(..., description="One sentence explaining the verdict")
    overall_severity: OverallSeverityType
    findings: List[Finding] = Field(default_factory=list)
    positive_observations: List[str] = Field(
        default_factory=list,
        description="Things the PR does well, minimum 2 items",
    )
    missing_tests: List[str] = Field(
        default_factory=list,
        description="Specific test cases that should be added",
    )
    agent_findings_count: Dict[str, int] = Field(
        default_factory=lambda: {
            "security": 0,
            "performance": 0,
            "correctness": 0,
            "style": 0,
            "test_coverage": 0,
        }
    )
    processing_time_ms: int = Field(..., description="Wall-clock time from request to response in ms")
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ─── List endpoint ────────────────────────────────────────────────────────────

class ReviewSummary(BaseModel):
    """Lightweight summary for GET /reviews list."""
    review_id: str
    pr_summary: str
    verdict: VerdictType
    overall_severity: OverallSeverityType
    language: str
    created_at: datetime


class HealthResponse(BaseModel):
    status: str
    groq_connected: bool
    total_reviews: int
    model: str
