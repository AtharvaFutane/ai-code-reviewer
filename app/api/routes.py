# app/api/routes.py
"""
API endpoints for the Code Reviewer service.
Phase 1: Placeholder health endpoint only.
Full endpoints will be added in Phase 3 and 4.
"""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter

from app.api.models import HealthResponse
from app.storage.store import review_store

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Service health check including Groq API connectivity verification."""
    groq_connected = False
    model = os.getenv("GROQ_PRIMARY_MODEL", "llama3-70b-8192")

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
