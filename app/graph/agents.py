# app/graph/agents.py
"""
Five specialist reviewer agent nodes for the LangGraph pipeline.

Each agent:
  1. Gets the full diff from state
  2. Calls Groq LLM with its specialist system prompt
  3. Parses the JSON response into a list of RawFinding dicts
  4. Returns a dict updating ONLY its own findings field in state

All functions are async — required for true parallel execution in LangGraph.
"""
from __future__ import annotations

import logging
import os

from app.graph.state import ReviewState
from app.graph.prompts import (
    CORRECTNESS_SYSTEM_PROMPT,
    PERFORMANCE_SYSTEM_PROMPT,
    SECURITY_SYSTEM_PROMPT,
    STYLE_SYSTEM_PROMPT,
    TEST_COVERAGE_SYSTEM_PROMPT,
    build_user_message,
)
from app.llm.client import get_llm, invoke_llm_with_retry, parse_raw_findings

logger = logging.getLogger(__name__)

MAX_FINDINGS = int(os.getenv("MAX_FINDINGS_PER_AGENT", "10"))


async def _run_agent(
    state: ReviewState,
    system_prompt: str,
    category: str,
) -> list:
    """
    Shared agent runner — keeps the 5 agent functions DRY.
    
    Returns a list of RawFinding dicts on success, or [] on any failure.
    Failures are logged but never propagate — a failing agent returns empty
    findings rather than crashing the entire review pipeline.
    """
    llm = get_llm()
    user_message = build_user_message(
        diff=state["diff"],
        language=state["language"],
        context=state.get("context"),
    )
    try:
        raw_response = await invoke_llm_with_retry(llm, system_prompt, user_message)
        findings = parse_raw_findings(raw_response, category, MAX_FINDINGS)
        logger.info(f"[{category}] agent found {len(findings)} issues")
        return findings
    except Exception as exc:
        logger.error(f"[{category}] agent failed after retries: {exc}")
        return []


async def security_reviewer_node(state: ReviewState) -> dict:
    findings = await _run_agent(state, SECURITY_SYSTEM_PROMPT, "security")
    return {"security_findings": findings}


async def performance_reviewer_node(state: ReviewState) -> dict:
    findings = await _run_agent(state, PERFORMANCE_SYSTEM_PROMPT, "performance")
    return {"performance_findings": findings}


async def correctness_reviewer_node(state: ReviewState) -> dict:
    findings = await _run_agent(state, CORRECTNESS_SYSTEM_PROMPT, "correctness")
    return {"correctness_findings": findings}


async def style_reviewer_node(state: ReviewState) -> dict:
    findings = await _run_agent(state, STYLE_SYSTEM_PROMPT, "style")
    return {"style_findings": findings}


async def test_coverage_reviewer_node(state: ReviewState) -> dict:
    findings = await _run_agent(state, TEST_COVERAGE_SYSTEM_PROMPT, "test_coverage")
    return {"test_coverage_findings": findings}
