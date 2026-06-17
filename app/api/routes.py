# app/api/routes.py
"""
All four API endpoints for the Code Reviewer service.

POST /review         → Submit a diff for review; returns ReviewReport
GET  /review/{id}   → Retrieve a previously generated review
GET  /reviews        → List all reviews in this session
GET  /health         → Service status + Groq connectivity check
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import List

from fastapi import APIRouter, HTTPException

from app.api.models import (
    Finding,
    HealthResponse,
    ReviewReport,
    ReviewRequest,
    ReviewSummary,
)
from app.graph.pipeline import pipeline
from app.graph.state import make_initial_state
from app.storage.store import review_store

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/review", response_model=ReviewReport, status_code=200)
async def create_review(request: ReviewRequest) -> ReviewReport:
    """
    Submit a PR diff for multi-agent AI review.
    
    Runs 5 specialist LLM reviewer agents in parallel via LangGraph,
    then merges their findings into a structured ReviewReport.
    Processing typically takes 5-15 seconds depending on diff size.
    """
    logger.info(f"New review request: language={request.language}, diff_len={len(request.diff)}")

    if not request.diff.strip():
        raise HTTPException(status_code=400, detail="diff cannot be empty")
    if not request.language.strip():
        raise HTTPException(status_code=400, detail="language is required")

    # Build initial LangGraph state
    initial_state = make_initial_state(
        diff=request.diff,
        language=request.language,
        context=request.context,
    )

    # Run the pipeline (parallel agents + merge)
    try:
        result_state = await pipeline.ainvoke(initial_state)
    except Exception as exc:
        logger.error(f"Pipeline execution failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Review pipeline failed: {str(exc)}")

    report_dict = result_state.get("review_report")
    if not report_dict:
        raise HTTPException(status_code=500, detail="Pipeline produced no report")

    # Validate findings with Pydantic and build ReviewReport
    validated_findings: List[Finding] = []
    for raw in report_dict.get("findings", []):
        try:
            validated_findings.append(Finding(**raw))
        except Exception as e:
            logger.warning(f"Skipping malformed finding: {e}")

    report = ReviewReport(
        review_id=str(uuid.uuid4()),
        pr_summary=report_dict.get("pr_summary", ""),
        verdict=report_dict.get("verdict", "needs_discussion"),
        verdict_reason=report_dict.get("verdict_reason", ""),
        overall_severity=report_dict.get("overall_severity", "low"),
        findings=validated_findings,
        positive_observations=report_dict.get("positive_observations", []),
        missing_tests=report_dict.get("missing_tests", []),
        agent_findings_count=report_dict.get("agent_findings_count", {}),
        processing_time_ms=report_dict.get("processing_time_ms", 0),
    )

    # Persist to in-memory store
    await review_store.save(report, language=request.language)

    logger.info(
        f"Review {report.review_id} complete: verdict={report.verdict}, "
        f"findings={len(report.findings)}, time={report.processing_time_ms}ms"
    )
    return report


@router.get("/review/{review_id}", response_model=ReviewReport)
async def get_review(review_id: str) -> ReviewReport:
    """Retrieve a previously generated review by its ID."""
    report = await review_store.get(review_id)
    if not report:
        raise HTTPException(
            status_code=404,
            detail=f"Review {review_id} not found. Reviews are stored in-memory and reset on restart.",
        )
    return report


@router.get("/reviews", response_model=List[ReviewSummary])
async def list_reviews() -> List[ReviewSummary]:
    """List all reviews generated in this session, most recent first."""
    return await review_store.list_all()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Service health check including Groq API connectivity verification."""
    groq_connected = False
    model = os.getenv("GROQ_PRIMARY_MODEL", "llama-3.3-70b-versatile")

    try:
        from app.llm.client import get_llm
        from langchain_core.messages import HumanMessage

        llm = get_llm()
        response = await llm.ainvoke([HumanMessage(content="Reply with the word: ok")])
        groq_connected = "ok" in response.content.lower()
    except Exception as exc:
        logger.warning(f"Groq health check failed: {exc}")

    return HealthResponse(
        status="healthy" if groq_connected else "degraded",
        groq_connected=groq_connected,
        total_reviews=await review_store.count(),
        model=model,
    )
