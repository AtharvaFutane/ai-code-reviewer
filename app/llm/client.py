# app/llm/client.py
from __future__ import annotations

import json
import os
import re
import asyncio
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


def get_llm(model_override: Optional[str] = None) -> ChatGroq:
    """
    Return a ChatGroq instance configured from environment variables.
    
    Model priority:
      1. model_override (for merge node which uses a lighter model)
      2. GROQ_PRIMARY_MODEL (default: llama3-70b-8192) for all agents
    
    Temperature is always 0 for reproducible, deterministic reviews.
    """
    model = model_override or os.getenv("GROQ_PRIMARY_MODEL", "llama3-70b-8192")
    return ChatGroq(
        model=model,
        temperature=float(os.getenv("LLM_TEMPERATURE", "0")),
        api_key=os.getenv("GROQ_API_KEY"),
        # max_tokens deliberately not set — let the model decide response length
    )


_llm_semaphore = asyncio.Semaphore(2)

@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def _invoke_single_llm(
    llm: ChatGroq,
    messages: list,
) -> str:
    async with _llm_semaphore:
        response = await llm.ainvoke(messages)
        return response.content


async def invoke_llm_with_retry(
    llm: ChatGroq,
    system_prompt: str,
    user_message: str,
) -> str:
    """
    Call the LLM with retry logic (handles Groq rate limits gracefully).
    Returns the raw string content of the model response.
    
    Retry policy: up to 3 attempts, exponential backoff 2s→4s→8s.
    On final failure, it will attempt to use the fallback model configured in GROQ_FALLBACK_MODEL.
    """
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ]
    try:
        return await _invoke_single_llm(llm, messages)
    except Exception as e:
        fallback_model = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant")
        if getattr(llm, "model_name", "") != fallback_model:
            import logging
            logging.getLogger(__name__).warning(f"Model {getattr(llm, 'model_name', 'unknown')} failed: {e}. Falling back to {fallback_model}.")
            fallback_llm = get_llm(model_override=fallback_model)
            return await _invoke_single_llm(fallback_llm, messages)
        raise


def extract_json_from_response(text: str) -> Dict[str, Any]:
    """
    Robustly extract a JSON object from an LLM response.
    
    LLMs sometimes wrap JSON in markdown fences or add explanation text.
    This function handles all common failure modes:
    
    1. Pure JSON (ideal case)
    2. JSON wrapped in ```json ... ``` 
    3. JSON wrapped in ``` ... ```
    4. JSON object anywhere in the text
    5. Fallback: return {"findings": []}
    """
    text = text.strip()

    # Attempt 1: direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Attempt 2: extract from ```json ... ``` fences
    match = re.search(r"```json\s*([\s\S]*?)\s*```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Attempt 3: extract from ``` ... ``` fences (no language tag)
    match = re.search(r"```\s*([\s\S]*?)\s*```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Attempt 4: find the first { ... } block in the text
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Fallback: empty findings — agent found nothing (or LLM failed)
    return {"findings": []}


def parse_raw_findings(
    response_text: str,
    category: str,
    max_findings: int = 10,
) -> List[Dict]:
    """
    Parse LLM response into a list of RawFinding dicts.
    
    - Extracts JSON from the response
    - Normalises field names (handles minor LLM deviations)
    - Injects the category field
    - Caps at max_findings to prevent bloated reports
    - Silently skips malformed findings rather than crashing
    """
    data = extract_json_from_response(response_text)
    raw_findings = data.get("findings", [])

    if not isinstance(raw_findings, list):
        return []

    normalised: List[Dict] = []
    for item in raw_findings[:max_findings]:
        if not isinstance(item, dict):
            continue

        # Normalise severity — default to "medium" if missing/invalid
        severity = str(item.get("severity", "medium")).lower()
        if severity not in {"critical", "high", "medium", "low"}:
            severity = "medium"

        # Best-effort extraction; skip findings missing critical fields
        line_val = item.get("line", 0)
        try:
            line_val = int(line_val)
        except (ValueError, TypeError):
            line_val = 0

        title = str(item.get("title", "")).strip()
        description = str(item.get("description", "")).strip()

        if not title or not description:
            continue  # Skip structurally empty findings

        normalised.append({
            "line": line_val,
            "line_content": str(item.get("line_content", "")).strip(),
            "category": category,
            "severity": severity,
            "title": title,
            "description": description,
            "suggestion": str(item.get("suggestion", "No suggestion provided")).strip(),
        })

    return normalised
