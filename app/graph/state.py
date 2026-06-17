# app/graph/state.py
from __future__ import annotations

from typing import Dict, List, Optional, TypedDict


class RawFinding(TypedDict):
    """
    Raw finding dict as returned by each agent's LLM call, BEFORE Pydantic validation.
    Kept loose (all Optional) to handle imperfect LLM JSON output gracefully.
    """
    line: int
    line_content: str
    severity: str          # will be coerced to SeverityLevel
    title: str
    description: str
    suggestion: str
    # Note: 'category' is NOT here — it is injected by each agent node
    # after parsing, so agents don't need to remember their own category.


class ReviewState(TypedDict):
    """
    LangGraph graph state. Each field is written by exactly one node,
    so no reducer functions are needed (no concurrent writes to same field).
    
    Graph topology:
        START → [security, performance, correctness, style, test_coverage] (parallel)
             → merge
             → END
    """
    # ── Input (set before ainvoke, never modified) ──────────────────────────
    diff: str
    language: str
    context: Optional[str]
    start_time: float       # time.perf_counter() snapshot at request start

    # ── Agent outputs (each written by exactly ONE agent node) ───────────────
    security_findings: List[RawFinding]
    performance_findings: List[RawFinding]
    correctness_findings: List[RawFinding]
    style_findings: List[RawFinding]
    test_coverage_findings: List[RawFinding]

    # ── Merge output (written by merge node) ─────────────────────────────────
    review_report: Optional[Dict]   # The final ReviewReport as a dict


def make_initial_state(diff: str, language: str, context: Optional[str]) -> ReviewState:
    """
    Factory function to create the initial state dict for graph invocation.
    All list fields MUST be initialised to [] — LangGraph requires this.
    """
    import time
    return ReviewState(
        diff=diff,
        language=language,
        context=context,
        start_time=time.perf_counter(),
        security_findings=[],
        performance_findings=[],
        correctness_findings=[],
        style_findings=[],
        test_coverage_findings=[],
        review_report=None,
    )
