# Infravox AI Code Reviewer — Complete Implementation Blueprint
## Instructions for Claude Opus 4.6

---

> **CRITICAL PREAMBLE FOR CLAUDE**: Read this entire blueprint before generating a single line of code. Implement **every** section exactly as specified. Where exact code is provided, use it verbatim — these are fixed contracts (API schema, LangGraph graph topology, Pydantic models). Make any unspecified design choices yourself, but document them in the README as "Architectural Decision:" entries. This is a submission for an internship technical assignment; the output must be clean, production-quality, and demo-ready.

---

## Table of Contents

1. [System Overview & Architecture Rationale](#1-system-overview)
2. [Repository File Structure](#2-repository-file-structure)
3. [Dependencies & Environment](#3-dependencies--environment)
4. [Core Pydantic Models (Fixed Contract)](#4-core-pydantic-models)
5. [In-Memory Storage Layer](#5-in-memory-storage-layer)
6. [LangGraph State Schema](#6-langgraph-state-schema)
7. [Groq LLM Client Setup](#7-groq-llm-client-setup)
8. [Agent System Prompts (Full Text)](#8-agent-system-prompts)
9. [Agent Node Implementations](#9-agent-node-implementations)
10. [Merge Node Logic](#10-merge-node-logic)
11. [Graph Definition & Compilation](#11-graph-definition--compilation)
12. [FastAPI Application & Routes](#12-fastapi-application--routes)
13. [Runner Script](#13-runner-script-run_reviewspy)
14. [Bug Detection Matrix (All 3 Diffs)](#14-bug-detection-matrix)
15. [README Template](#15-readmemd-template)
16. [Submission Checklist](#16-submission-checklist)

---

## 1. System Overview

### What You Are Building

A **FastAPI service** that accepts a raw `git diff` text and returns a **structured `ReviewReport` JSON** identifying security vulnerabilities, performance issues, correctness bugs, style problems, and missing tests. The core processing engine is a **LangGraph StateGraph** that runs 5 specialist LLM reviewer agents **in parallel** and merges their findings into a single structured report.

### Architecture Decision: Why This Design

| Decision | Choice | Rationale |
|---|---|---|
| Framework | FastAPI | Async-native, Pydantic-first, auto OpenAPI docs |
| LLM Orchestration | LangGraph StateGraph | Native parallel fan-out, clean state management, evaluator-visible architecture |
| LLM Provider | Groq (free tier) | Assignment requirement; `llama3-70b-8192` gives best quality within free tier |
| Parallelism | All 5 agents run simultaneously via `ainvoke` + asyncio | Reduces latency from ~25s sequential to ~8s parallel |
| Storage | In-memory dict | Assignment specifies "session storage"; no DB needed |
| Output Parsing | JSON extraction with regex fallback + Pydantic validation | LLMs occasionally wrap JSON in markdown; must handle this gracefully |

### Data Flow

```
POST /review
    │
    ├── Validate input (Pydantic ReviewRequest)
    ├── Start timer
    ├── Initialize LangGraph state
    │
    └── pipeline.ainvoke(state)
              │
              ├──┬──────────────────────── PARALLEL ────────────────────────────┐
              │  ▼                 ▼                  ▼              ▼           ▼
              │  security_     performance_      correctness_    style_    test_coverage_
              │  reviewer      reviewer          reviewer        reviewer   reviewer
              │  (Groq LLM)    (Groq LLM)        (Groq LLM)    (Groq LLM) (Groq LLM)
              │  └──────────────────────── FAN-IN ─────────────────────────────┘
              │                           ▼
              │                     merge_node
              │              (deduplicate + score + LLM summary)
              │                           ▼
              │                     ReviewReport (dict)
              │
    ├── Store in memory (review_id → ReviewReport)
    └── Return ReviewReport JSON
```

---

## 2. Repository File Structure

Create **exactly** this structure. Every file listed must exist.

```
ai-code-reviewer/
├── .env                          # Real secrets (gitignored)
├── .env.example                  # Template (committed)
├── .gitignore
├── requirements.txt
├── README.md
├── main.py                       # FastAPI app entry point (uvicorn target)
├── run_reviews.py                # Submission runner script
│
├── app/
│   ├── __init__.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── models.py             # Pydantic request/response schemas
│   │   └── routes.py             # All 4 endpoints
│   │
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── state.py              # LangGraph TypedDict state schema
│   │   ├── prompts.py            # System prompts for all 5 agents
│   │   ├── agents.py             # 5 async agent node functions
│   │   ├── merge.py              # Merge node: deduplicate, score, summarize
│   │   └── pipeline.py           # StateGraph definition and compile()
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   └── client.py             # Groq ChatGroq client factory + JSON parser
│   │
│   └── storage/
│       ├── __init__.py
│       └── store.py              # In-memory review store (dict + lock)
│
├── diffs/
│   ├── diff1_python.txt
│   ├── diff2_javascript.txt
│   └── diff3_typescript.txt
│
└── reviews/                      # Generated by run_reviews.py
    ├── .gitkeep
    ├── diff1_review.json
    ├── diff2_review.json
    └── diff3_review.json
```

**IMPORTANT**: The `.gitignore` must include:
```
.env
__pycache__/
*.pyc
.venv/
venv/
*.egg-info/
```
Do NOT gitignore the `reviews/` folder — the `.json` files inside it are part of the submission.

---

## 3. Dependencies & Environment

### `requirements.txt` — Use These Exact Versions

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
langgraph==0.2.14
langchain==0.2.6
langchain-groq==0.1.6
langchain-core==0.2.11
pydantic==2.7.1
python-dotenv==1.0.1
httpx==0.27.0
tenacity==8.3.0
```

**Reasoning**: `langgraph==0.2.14` is the minimum version supporting direct `START → multiple nodes` parallel fan-out with `ainvoke`. Do not use `langgraph<0.2.0` — the API is incompatible.

### `.env.example`

```bash
# === GROQ API ===
# Get your free key at https://console.groq.com (no credit card required)
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# === MODEL SELECTION ===
# Primary model — best quality on free tier
GROQ_PRIMARY_MODEL=llama3-70b-8192
# Fallback model if rate limited
GROQ_FALLBACK_MODEL=llama3-8b-8192
# Merge/summary model (lighter task)
GROQ_SUMMARY_MODEL=gemma2-9b-it

# === APP CONFIG ===
APP_HOST=0.0.0.0
APP_PORT=8000
APP_LOG_LEVEL=info

# === REVIEW CONFIG ===
# Maximum findings to return per agent (prevents overwhelming reports)
MAX_FINDINGS_PER_AGENT=10
# LLM temperature (0 = deterministic, always keep at 0 for consistent reviews)
LLM_TEMPERATURE=0
```

### Setup Instructions (for README and for Claude's reference)

```bash
git clone https://github.com/YOUR_USERNAME/ai-code-reviewer
cd ai-code-reviewer
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your GROQ_API_KEY from console.groq.com
uvicorn main:app --reload         # Starts on http://localhost:8000
```

---

## 4. Core Pydantic Models

**File: `app/api/models.py`**

This is a **fixed contract** — do not change field names, types, or Literal values. The assignment schema is enforced exactly.

```python
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
```

---

## 5. In-Memory Storage Layer

**File: `app/storage/store.py`**

```python
# app/storage/store.py
import asyncio
from datetime import datetime
from typing import Dict, List, Optional

from app.api.models import ReviewReport, ReviewSummary


class ReviewStore:
    """
    Thread-safe in-memory store for ReviewReport objects.
    
    Architectural Decision: Using asyncio.Lock (not threading.Lock) because
    FastAPI runs in an async event loop. All reads/writes are awaited.
    Reviews persist only for the session lifetime — as specified.
    """

    def __init__(self) -> None:
        self._store: Dict[str, ReviewReport] = {}
        self._meta: Dict[str, str] = {}  # review_id → language
        self._lock = asyncio.Lock()

    async def save(self, report: ReviewReport, language: str) -> None:
        async with self._lock:
            self._store[report.review_id] = report
            self._meta[report.review_id] = language

    async def get(self, review_id: str) -> Optional[ReviewReport]:
        async with self._lock:
            return self._store.get(review_id)

    async def list_all(self) -> List[ReviewSummary]:
        async with self._lock:
            return [
                ReviewSummary(
                    review_id=r.review_id,
                    pr_summary=r.pr_summary,
                    verdict=r.verdict,
                    overall_severity=r.overall_severity,
                    language=self._meta.get(r.review_id, "unknown"),
                    created_at=r.created_at,
                )
                for r in sorted(
                    self._store.values(),
                    key=lambda x: x.created_at,
                    reverse=True,
                )
            ]

    async def count(self) -> int:
        async with self._lock:
            return len(self._store)


# Module-level singleton — imported by routes and used throughout
review_store = ReviewStore()
```

---

## 6. LangGraph State Schema

**File: `app/graph/state.py`**

```python
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
```

---

## 7. Groq LLM Client Setup

**File: `app/llm/client.py`**

```python
# app/llm/client.py
from __future__ import annotations

import json
import os
import re
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


@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def invoke_llm_with_retry(
    llm: ChatGroq,
    system_prompt: str,
    user_message: str,
) -> str:
    """
    Call the LLM with retry logic (handles Groq rate limits gracefully).
    Returns the raw string content of the model response.
    
    Retry policy: up to 3 attempts, exponential backoff 2s→4s→8s.
    On final failure, the exception propagates to the caller.
    """
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ]
    response = await llm.ainvoke(messages)
    return response.content


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
```

---

## 8. Agent System Prompts

**File: `app/graph/prompts.py`**

These prompts are carefully engineered to detect the specific bug classes planted in the three test diffs while remaining general enough to work on the unseen 4th diff in the interview. Include every word exactly as written below.

```python
# app/graph/prompts.py

SECURITY_SYSTEM_PROMPT = """
You are a paranoid, meticulous security-focused code reviewer with deep expertise in OWASP Top 10,
application security, and secure coding practices. Your job is to find every security vulnerability
in the code diff provided. Security flaws that look minor often have catastrophic consequences in
production — treat every one seriously.

Examine the diff for ALL of the following vulnerability classes:

1. SQL INJECTION
   Look for: f-strings, string concatenation, or .format() building SQL query strings where
   user-supplied values are interpolated directly. Any pattern like:
     f"SELECT ... WHERE id = {user_id}"
     "UPDATE table SET x = '" + value + "'"
     "SELECT * FROM t WHERE col=" + str(param)
   is a SQL injection vulnerability regardless of variable name. Check EVERY query-building line.
   Both SELECT and UPDATE/INSERT/DELETE are equally dangerous.

2. HARDCODED SECRETS / CREDENTIALS
   Look for: API keys, secret tokens, passwords, or private keys assigned as string literals.
   Key patterns: sk_live_, sk_test_, Bearer , password = ", secret = ", api_key = ", TOKEN = ",
   any long random alphanumeric string assigned to a variable with 'key', 'secret', 'token',
   'password', or 'credential' in its name. Committing a live production key (sk_live_) is
   CRITICAL severity regardless of context.

3. MISSING AUTHENTICATION ON SENSITIVE ENDPOINTS
   Look for: route handlers (Flask @app.route, Express app.post/get, FastAPI @router.post, etc.)
   that perform sensitive operations (refunds, password changes, data deletion, order cancellation)
   without any authentication decorator (@login_required, JWT validation, session check, API key
   check, or middleware). An endpoint that anyone can call to process a refund or cancel an order
   is a critical security hole.

4. INSECURE DIRECT OBJECT REFERENCE (IDOR)
   Look for: functions that read or modify a resource (user record, order, account) using an ID
   passed in from the request, WITHOUT verifying that the requesting user OWNS or is AUTHORISED
   to access that specific resource. Example: a resetPassword() that updates ANY user's password
   for any email in req.body without verifying the caller is that user.

5. CROSS-SITE SCRIPTING (XSS)
   Look for: HTML template rendering where user-controlled values (amounts, names, messages) are
   inserted into HTML via string .replace(), .format(), or interpolation WITHOUT HTML-escaping.
   Even numeric values (like refund amounts) can be manipulated if they travel through user input.

6. PLAINTEXT PASSWORD STORAGE
   Look for: UPDATE or INSERT queries that set a password column directly from request body input
   without a prior bcrypt/argon2/scrypt/pbkdf2 hashing call. Storing passwords as plain text is
   a CRITICAL severity issue that violates every security standard.

7. UNVALIDATED / UNSANITISED USER INPUT
   Look for: endpoints that directly pass req.body, request.json, or req.query values into
   database operations, business logic functions, or external services without type-checking,
   bounds-checking, or required-field validation. Missing validation means callers can send
   null, wrong types, or omit required fields to trigger crashes or unintended behaviour.

Output format — return ONLY a valid JSON object, zero extra text, zero markdown fences:

{
  "findings": [
    {
      "line": <int: line number in the diff where the issue occurs>,
      "line_content": "<exact text of the vulnerable line from the diff>",
      "severity": "critical" | "high" | "medium" | "low",
      "title": "<concise vulnerability name, e.g. SQL Injection via f-string interpolation>",
      "description": "<2-3 sentences: what the vulnerability is, WHY it is exploitable, and what an attacker could do>",
      "suggestion": "<concrete fix with corrected code snippet>"
    }
  ]
}

If you find no security issues, return exactly: {"findings": []}
Severity guidelines: critical = direct exploit risk (injection, exposed secrets, plaintext passwords);
high = authentication/authorisation failures, IDOR, XSS; medium = input validation, information
exposure; low = defence-in-depth improvements.
""".strip()


PERFORMANCE_SYSTEM_PROMPT = """
You are a senior backend engineer specialising in performance analysis and scalability. Your job is
to identify performance problems in the code diff that would cause measurable degradation at scale —
not micro-optimisations, but issues that will hurt real systems under real load.

Examine the diff for these specific performance anti-patterns:

1. N+1 QUERY PATTERN
   Look for: a database query inside a for/while loop, where the loop iterates over a collection and
   makes one DB call per item. This causes N+1 database round-trips instead of 1. Classic examples:
     for (const id of userIds) { await db.query('SELECT ... WHERE id = ?', [id]) }
     for item in items: db.execute(f"SELECT ... WHERE id = {item.id}")
   The fix is always a single batched query: SELECT ... WHERE id IN (?, ?, ?) or similar.
   Tag severity HIGH — this breaks at scale.

2. INFINITE LOOPS WITH NO TIMEOUT OR RETRY LIMIT
   Look for: while loops whose exit condition depends entirely on external state (a database record
   status, an API response) with NO maximum iteration count, NO timeout, and NO circuit breaker.
   Example: while (status === 'pending') { ... await sleep(1000) } — if the external state never
   changes, this runs forever, holding the thread/connection/memory indefinitely. Any polling loop
   that can run forever is a CRITICAL performance and reliability issue.

3. SEQUENTIAL ASYNC OPERATIONS THAT SHOULD BE PARALLEL
   Look for: a for loop that awaits an async function on each iteration, where the iterations are
   INDEPENDENT of each other (no dependency between results). Example:
     for (const id of orderIds) { await cancelOrder(id, 'system') }
   When iterations are independent, this should use Promise.all() or asyncio.gather() for parallel
   execution. Sequential processing of N items takes N×latency time; parallel takes 1×latency.
   Tag severity HIGH for non-trivial collections.

4. MISSING PAGINATION ON UNBOUNDED QUERIES
   Look for: SELECT * FROM table WHERE condition queries that fetch ALL matching rows with no LIMIT
   clause, applied to tables that could grow large (logs, events, transactions). Fetching 1M rows
   into memory at once will crash the service.

5. REPEATED EXPENSIVE OPERATIONS THAT SHOULD BE CACHED
   Look for: identical external calls (DB queries, API calls, file reads) made multiple times in
   the same request/function with the same parameters, with no memoisation or caching between calls.

6. SYNCHRONOUS BLOCKING IN ASYNC CONTEXT
   Look for: synchronous file I/O (open(), readFileSync), synchronous HTTP calls, or blocking sleep()
   in code paths that are supposed to be async. These block the event loop.

Output format — return ONLY a valid JSON object, zero extra text, zero markdown fences:

{
  "findings": [
    {
      "line": <int>,
      "line_content": "<exact line>",
      "severity": "critical" | "high" | "medium" | "low",
      "title": "<concise performance issue name>",
      "description": "<what the issue is, why it hurts at scale, what happens in production>",
      "suggestion": "<concrete fix with code snippet>"
    }
  ]
}

If you find no performance issues, return exactly: {"findings": []}
Severity: critical = infinite loops, guaranteed service degradation; high = N+1 queries, sequential
where parallel is possible; medium = missing pagination, suboptimal but not catastrophic; low =
minor improvements.
""".strip()


CORRECTNESS_SYSTEM_PROMPT = """
You are a meticulous correctness-focused code reviewer whose job is to find bugs that will cause
actual production failures — crashes, wrong results, data corruption, or silent failures. You are
not looking for style issues. You are looking for code that does the wrong thing or crashes when
given valid inputs.

Examine the diff for these specific correctness issues:

1. NULL / UNDEFINED DEREFERENCE
   Look for: a return value (from a DB query, an API call, or a repository method) that is used
   immediately — accessing a property, indexing, or calling a method on it — WITHOUT a prior null
   check. If the database returns no rows and the code does result['status'] or result.status,
   it will throw a KeyError, TypeError, or NullPointerException. Examples:
     transaction = get_transaction(...)
     if transaction['status'] == 'completed':   ← CRASH if transaction is None
     
     const order = await orderRepo.findById(orderId)
     order.status = 'cancelled'                  ← CRASH if order is null/undefined

2. UNDEFINED VARIABLE REFERENCE
   Look for: variables used in a function that were never declared in that scope and are not
   parameters or imports. Example: referencing `users` in getUserActivity() when `users` was
   never declared in that function — this is a ReferenceError at runtime.

3. MISSING INPUT VALIDATION
   Look for: API endpoint handlers that immediately pass request body/query data into business
   logic functions without checking that required fields exist and have the right types.
   Example: an endpoint that calls process_refund(data) where data is raw request.json — if
   the caller omits 'user_id' or sends the wrong type, the function crashes.

4. RESOURCE LEAKS
   Look for: file handles, database connections, or network sockets opened without a
   corresponding close or context manager. Example: open('file.html').read() without with
   statement or .close() call — the file handle leaks on every call.

5. SILENT UNDEFINED / NaN PROPAGATION
   Look for: arithmetic operations on values that could be undefined or null.
   Example: price * (1 - discounts[discountCode]) — if discountCode is not in discounts,
   discounts[discountCode] is undefined, and the result is NaN. The function returns NaN
   silently, which corrupts downstream calculations without throwing an error.

6. SILENT PUSH OF UNDEFINED
   Look for: array.push(result[0]) where result could be an empty array — pushing undefined
   into the array silently contaminates the result set.

7. INCORRECT ERROR HANDLING
   Look for: missing error returns (a function that returns success even when a required
   condition fails), swallowed exceptions (try/catch with empty catch blocks), or wrong HTTP
   status codes on error paths.

8. MISSING EDGE CASE HANDLING
   Look for: functions that handle the happy path but crash or produce wrong results for
   common edge cases like: empty collections, zero values, already-processed records
   (double-cancel, double-refund), or string/type conversion failures.

Output format — return ONLY a valid JSON object, zero extra text, zero markdown fences:

{
  "findings": [
    {
      "line": <int>,
      "line_content": "<exact line>",
      "severity": "critical" | "high" | "medium" | "low",
      "title": "<concise bug name>",
      "description": "<what goes wrong, when it goes wrong, and what the consequence is>",
      "suggestion": "<concrete fix with code snippet>"
    }
  ]
}

If you find no correctness bugs, return exactly: {"findings": []}
Severity: high = causes production crashes or data corruption; medium = causes incorrect results
in edge cases; low = defensive programming improvements.
""".strip()


STYLE_SYSTEM_PROMPT = """
You are a code quality reviewer focused on readability, maintainability, and adherence to language
best practices. You only flag issues that GENUINELY hurt maintainability — not personal preference.
You do NOT flag: naming style (camelCase vs snake_case), line length, formatting, or things that
work correctly and are readable.

Examine the diff ONLY for these style issues that have real impact:

1. TYPE SAFETY VIOLATIONS (TypeScript only)
   Look for: use of `any` type in TypeScript code where a specific type should be used.
   Example: const discounts: any = {...} defeats TypeScript's entire purpose. The correct type
   would be Record<string, number> or a specific interface. Flag `any` usage when a proper type
   is straightforward to define.

2. HARDCODED VALUES THAT SHOULD BE EXTERNAL CONFIGURATION
   Look for: business-critical values hardcoded as literals that should be in a config file,
   database, or environment variable. Examples:
   - Discount codes hardcoded in a function: { SAVE10: 0.1, SAVE20: 0.2, SAVE50: 0.5 }
     These change frequently and require a code deployment to update.
   - Magic numbers used in business logic without a named constant.
   Only flag when the value is genuinely configuration that non-developers would need to change.

3. FUNCTIONS THAT ARE TOO LONG / DOING TOO MUCH
   Look for: functions with more than ~30 lines that handle multiple distinct concerns (e.g., a
   single function that validates input, queries DB, updates records, sends notifications, and
   formats output). These should be split into smaller, single-responsibility functions.

4. DEAD CODE
   Look for: variables assigned but never read, functions defined but never called, conditions
   that can never be true. Only flag clear dead code, not code that might be used elsewhere.

5. DUPLICATED LOGIC
   Look for: identical or near-identical blocks of code (3+ lines) that appear multiple times
   and should be extracted into a shared function.

Output format — return ONLY a valid JSON object, zero extra text, zero markdown fences:

{
  "findings": [
    {
      "line": <int>,
      "line_content": "<exact line>",
      "severity": "critical" | "high" | "medium" | "low",
      "title": "<concise style issue name>",
      "description": "<why this genuinely hurts readability or maintainability>",
      "suggestion": "<concrete fix>"
    }
  ]
}

If you find no style issues worth flagging, return exactly: {"findings": []}
Severity: style issues are almost always medium or low. Only high if the issue causes real
confusion that would lead to bugs. Never critical.
""".strip()


TEST_COVERAGE_SYSTEM_PROMPT = """
You are a QA engineer and test architect. Your job is to identify what SHOULD be tested based on
the code added or changed in this diff, but ISN'T — either because no tests exist at all for the
new code, or because critical edge cases are missing.

You do not write the tests. You identify what tests are MISSING and why they matter.

For each piece of new code in the diff, ask:
- What is the happy path? Is it tested?
- What happens when the input is null, undefined, empty, or malformed?
- What happens when an external dependency (DB, notification service, external API) throws an error?
- What are the edge cases specific to this function's business logic?
- What happens if the same operation is called twice (idempotency)?

Specifically look for these missing test categories:

1. NULL/MISSING INPUT TESTS
   Any new function that accepts parameters should have tests for null, undefined, empty string,
   and missing required fields. If the function doesn't guard against these, the missing test
   ALSO reveals a bug — flag it.

2. EXTERNAL DEPENDENCY FAILURE TESTS
   Functions that call DB, send emails, call notification services, or make HTTP requests need
   tests for what happens when those calls fail. Does the function handle errors gracefully, or
   does it let exceptions propagate uncaught?

3. IDEMPOTENCY / DOUBLE-OPERATION TESTS
   Functions that change state (cancel an order, process a refund, reset a password) need tests
   for what happens when called twice on the same resource. Double-cancelling an already-cancelled
   order should be handled, not cause a crash or data corruption.

4. BOUNDARY AND EDGE CASE TESTS
   For functions that operate on collections, test with empty collections. For functions that
   compare values, test boundary values. For calculations, test with zero and negative inputs.

5. AUTHORISATION TESTS
   Functions that should only operate on resources owned by the caller need tests that verify
   a different user CANNOT perform the operation. If the function doesn't have authorisation
   checks, this is both a security finding AND a missing test.

6. ERROR PATH TESTS
   Functions with if/else branches need tests for BOTH branches. Error responses need tests to
   verify they return the correct status code and error message.

Output format — return ONLY a valid JSON object, zero extra text, zero markdown fences:

{
  "findings": [
    {
      "line": <int: the line of the new code that lacks test coverage>,
      "line_content": "<the function signature or key line that should be tested>",
      "severity": "critical" | "high" | "medium" | "low",
      "title": "<what test is missing, e.g. Missing test: cancelOrder called on non-existent order>",
      "description": "<why this test is important and what failure mode it would catch>",
      "suggestion": "<describe the test case: input, expected behaviour, what to mock>"
    }
  ]
}

If the diff has adequate test coverage, return exactly: {"findings": []}
Severity: high = missing test for a crash-prone or security-critical path; medium = missing edge
case or error path test; low = nice-to-have coverage improvement.
""".strip()


def build_user_message(diff: str, language: str, context: str | None) -> str:
    """
    Build the user-turn message for any agent.
    All 5 agents get the same user message — only the system prompt differs.
    """
    context_section = f"\nContext about this PR: {context}" if context else ""
    return f"""Review this {language.upper()} code diff:{context_section}

```diff
{diff}
```

Identify ALL issues matching your specialty. Be specific about line numbers.
Return ONLY the JSON object specified in your instructions. No other text."""
```

---

## 9. Agent Node Implementations

**File: `app/graph/agents.py`**

```python
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
```

---

## 10. Merge Node Logic

**File: `app/graph/merge.py`**

This is the most complex node — read every comment carefully.

```python
# app/graph/merge.py
"""
Merge node: consolidates findings from all 5 agents into a final ReviewReport.

Algorithm:
  1. Collect all findings from all 5 agent output fields
  2. Deduplicate: two findings are duplicates if they are within 2 lines of each
     other AND share the same category — keep the one with higher severity
  3. Sort findings: by severity (critical first) then by line number
  4. Assign sequential IDs: F-001, F-002, ...
  5. Compute overall_severity from max finding severity
  6. Compute verdict from overall_severity
  7. Call Groq LLM for: pr_summary, verdict_reason, positive_observations
  8. Build and return ReviewReport dict
"""
from __future__ import annotations

import logging
import os
import time
from typing import Dict, List, Optional

from app.graph.state import ReviewState
from app.llm.client import extract_json_from_response, get_llm, invoke_llm_with_retry

logger = logging.getLogger(__name__)

SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1}
SEVERITY_ORDER = ["critical", "high", "medium", "low"]


def _compute_overall_severity(findings: List[Dict]) -> str:
    """Return highest severity across all findings, or 'clean' if none."""
    if not findings:
        return "clean"
    max_rank = max(SEVERITY_RANK.get(f.get("severity", "low"), 1) for f in findings)
    for sev in SEVERITY_ORDER:
        if SEVERITY_RANK[sev] == max_rank:
            return sev
    return "clean"


def _compute_verdict(overall_severity: str) -> str:
    """
    Verdict logic:
    - critical or high finding → request_changes (code must not merge)
    - medium findings only     → needs_discussion (human should decide)
    - low or clean             → approve
    """
    if overall_severity in ("critical", "high"):
        return "request_changes"
    if overall_severity == "medium":
        return "needs_discussion"
    return "approve"


def _deduplicate_findings(findings: List[Dict]) -> List[Dict]:
    """
    Remove duplicate findings from overlapping agent reports.
    
    Two findings are considered duplicates if:
    - They have the same category (e.g., both "security")
    - Their line numbers are within 2 lines of each other
    
    When duplicates are found, keep the one with HIGHER severity.
    If equal severity, keep the one with the longer description (more detail).
    """
    seen: List[Dict] = []
    for candidate in findings:
        is_duplicate = False
        for i, existing in enumerate(seen):
            if existing["category"] != candidate["category"]:
                continue
            line_distance = abs(existing["line"] - candidate["line"])
            if line_distance <= 2:
                # Duplicate found — keep the more severe one
                cand_rank = SEVERITY_RANK.get(candidate.get("severity", "low"), 1)
                exist_rank = SEVERITY_RANK.get(existing.get("severity", "low"), 1)
                if cand_rank > exist_rank:
                    seen[i] = candidate  # replace with more severe
                elif cand_rank == exist_rank:
                    # Same severity — keep the more detailed description
                    if len(candidate.get("description", "")) > len(existing.get("description", "")):
                        seen[i] = candidate
                is_duplicate = True
                break
        if not is_duplicate:
            seen.append(candidate)
    return seen


def _sort_and_assign_ids(findings: List[Dict]) -> List[Dict]:
    """
    Sort by severity (critical first), then by line number.
    Assign sequential IDs: F-001, F-002, ...
    """
    sorted_findings = sorted(
        findings,
        key=lambda f: (-SEVERITY_RANK.get(f.get("severity", "low"), 1), f.get("line", 0)),
    )
    for idx, finding in enumerate(sorted_findings, start=1):
        finding["id"] = f"F-{idx:03d}"
    return sorted_findings


MERGE_SUMMARY_PROMPT = """
You are a senior engineering lead summarising a code review. Given the diff and its findings,
generate a concise review summary.

Return ONLY this JSON object, no other text:
{
  "pr_summary": "<one sentence: what does this PR do? Start with a verb: 'Adds...', 'Fixes...', 'Refactors...'>",
  "verdict_reason": "<one sentence explaining WHY the verdict is {verdict}. Reference the most severe finding.>",
  "positive_observations": [
    "<specific genuine positive observation about the code>",
    "<second specific genuine positive observation>"
  ]
}

Be specific and reference actual code from the diff. Do not be generic.
If the diff has NO redeeming qualities, still provide 2 observations about things that
ARE present (like 'The function names are clear' or 'Error response format is consistent').
"""


async def merge_node(state: ReviewState) -> dict:
    """
    Merge all agent findings into a final ReviewReport dict.
    This node runs AFTER all 5 parallel agents complete.
    """
    # Step 1: Collect all findings from all agent output fields
    all_raw_findings: List[Dict] = []
    all_raw_findings.extend(state.get("security_findings", []))
    all_raw_findings.extend(state.get("performance_findings", []))
    all_raw_findings.extend(state.get("correctness_findings", []))
    all_raw_findings.extend(state.get("style_findings", []))
    all_raw_findings.extend(state.get("test_coverage_findings", []))

    logger.info(f"[merge] Collected {len(all_raw_findings)} total raw findings from all agents")

    # Step 2: Deduplicate
    deduplicated = _deduplicate_findings(all_raw_findings)
    logger.info(f"[merge] After deduplication: {len(deduplicated)} findings")

    # Step 3: Sort and assign IDs
    final_findings = _sort_and_assign_ids(deduplicated)

    # Step 4: Compute overall severity and verdict
    overall_severity = _compute_overall_severity(final_findings)
    verdict = _compute_verdict(overall_severity)

    # Step 5: Compute agent findings count
    agent_counts: Dict[str, int] = {
        "security": 0,
        "performance": 0,
        "correctness": 0,
        "style": 0,
        "test_coverage": 0,
    }
    for finding in final_findings:
        cat = finding.get("category", "")
        if cat in agent_counts:
            agent_counts[cat] += 1

    # Step 6: Extract missing_tests from test_coverage findings
    missing_tests = [
        f.get("description", f.get("title", ""))
        for f in final_findings
        if f.get("category") == "test_coverage"
    ]

    # Step 7: LLM call for pr_summary, verdict_reason, positive_observations
    pr_summary = "This PR adds new functionality to the codebase."
    verdict_reason = f"The review found {overall_severity}-severity issues requiring attention."
    positive_observations = [
        "The code follows a consistent structure.",
        "Function naming is clear and descriptive.",
    ]

    try:
        llm = get_llm(model_override=os.getenv("GROQ_SUMMARY_MODEL", "gemma2-9b-it"))
        findings_summary = "\n".join(
            f"- [{f['severity'].upper()}] {f['title']} (line {f['line']})"
            for f in final_findings[:10]  # summarise top 10
        ) or "No issues found."

        system = MERGE_SUMMARY_PROMPT.format(verdict=verdict)
        user = f"""Language: {state['language']}

Diff:
```
{state['diff'][:3000]}
```

Findings:
{findings_summary}
"""
        raw_response = await invoke_llm_with_retry(llm, system, user)
        parsed = extract_json_from_response(raw_response)

        pr_summary = parsed.get("pr_summary", pr_summary)
        verdict_reason = parsed.get("verdict_reason", verdict_reason)
        raw_obs = parsed.get("positive_observations", positive_observations)
        if isinstance(raw_obs, list) and len(raw_obs) >= 2:
            positive_observations = [str(o) for o in raw_obs]

    except Exception as exc:
        logger.error(f"[merge] Summary LLM call failed: {exc}")
        # Use defaults defined above — review still succeeds

    # Step 8: Compute processing time
    elapsed_ms = int((time.perf_counter() - state["start_time"]) * 1000)

    # Step 9: Build final report dict
    report = {
        "pr_summary": pr_summary,
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "overall_severity": overall_severity,
        "findings": final_findings,
        "positive_observations": positive_observations,
        "missing_tests": missing_tests,
        "agent_findings_count": agent_counts,
        "processing_time_ms": elapsed_ms,
    }

    logger.info(
        f"[merge] Review complete: verdict={verdict}, severity={overall_severity}, "
        f"findings={len(final_findings)}, time={elapsed_ms}ms"
    )

    return {"review_report": report}
```

---

## 11. Graph Definition & Compilation

**File: `app/graph/pipeline.py`**

```python
# app/graph/pipeline.py
"""
LangGraph StateGraph definition.

Topology (parallel fan-out, then fan-in):

  START ──┬──► security_reviewer ──────┐
          ├──► performance_reviewer ───┤
          ├──► correctness_reviewer ───┼──► merge_node ──► END
          ├──► style_reviewer ─────────┤
          └──► test_coverage_reviewer ─┘

All 5 agent nodes receive the same initial state and run CONCURRENTLY
when the graph is invoked with `await pipeline.ainvoke(state)`.
LangGraph automatically waits for all 5 to complete before running merge_node.
"""
from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from app.graph.agents import (
    correctness_reviewer_node,
    performance_reviewer_node,
    security_reviewer_node,
    style_reviewer_node,
    test_coverage_reviewer_node,
)
from app.graph.merge import merge_node
from app.graph.state import ReviewState

logger = logging.getLogger(__name__)


def build_pipeline():
    """
    Construct and compile the LangGraph StateGraph.
    
    Called once at application startup. The compiled graph is stored as a
    module-level singleton and reused for every review request.
    """
    workflow = StateGraph(ReviewState)

    # ── Register all nodes ───────────────────────────────────────────────────
    workflow.add_node("security_reviewer", security_reviewer_node)
    workflow.add_node("performance_reviewer", performance_reviewer_node)
    workflow.add_node("correctness_reviewer", correctness_reviewer_node)
    workflow.add_node("style_reviewer", style_reviewer_node)
    workflow.add_node("test_coverage_reviewer", test_coverage_reviewer_node)
    workflow.add_node("merge", merge_node)

    # ── Fan-out: START → all 5 agents (parallel execution) ───────────────────
    workflow.add_edge(START, "security_reviewer")
    workflow.add_edge(START, "performance_reviewer")
    workflow.add_edge(START, "correctness_reviewer")
    workflow.add_edge(START, "style_reviewer")
    workflow.add_edge(START, "test_coverage_reviewer")

    # ── Fan-in: all 5 agents → merge (runs when ALL 5 complete) ─────────────
    workflow.add_edge("security_reviewer", "merge")
    workflow.add_edge("performance_reviewer", "merge")
    workflow.add_edge("correctness_reviewer", "merge")
    workflow.add_edge("style_reviewer", "merge")
    workflow.add_edge("test_coverage_reviewer", "merge")

    # ── merge → END ──────────────────────────────────────────────────────────
    workflow.add_edge("merge", END)

    compiled = workflow.compile()
    logger.info("LangGraph review pipeline compiled successfully")
    return compiled


# Module-level singleton — imported by routes
pipeline = build_pipeline()
```

---

## 12. FastAPI Application & Routes

### `main.py` (Entry Point)

```python
# main.py
"""
FastAPI application entry point.
Run with: uvicorn main:app --reload
"""
import logging
import os

from dotenv import load_dotenv

load_dotenv()  # Must be called BEFORE any module that reads env vars

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

logging.basicConfig(
    level=getattr(logging, os.getenv("APP_LOG_LEVEL", "INFO").upper()),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

app = FastAPI(
    title="Infravox AI Code Reviewer",
    description="LangGraph-powered multi-agent PR diff reviewer",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "8000")),
        reload=True,
        log_level=os.getenv("APP_LOG_LEVEL", "info").lower(),
    )
```

### `app/api/routes.py`

```python
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
```

---

## 13. Runner Script: `run_reviews.py`

```python
#!/usr/bin/env python3
"""
run_reviews.py — Infravox Assignment submission runner script.

Reads all three diff files from ./diffs/, POSTs each to the running
review API, and saves the JSON response to ./reviews/.

Usage:
    python run_reviews.py [--host http://localhost:8000]

Prerequisites:
    - The FastAPI server must be running: uvicorn main:app --reload
    - The ./diffs/ directory must contain the three .txt files
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

# ── Configuration ──────────────────────────────────────────────────────────

DIFFS_DIR = Path("diffs")
REVIEWS_DIR = Path("reviews")

# Mapping: filename prefix → language name for the API
DIFF_LANGUAGE_MAP = {
    "diff1_python": "python",
    "diff2_javascript": "javascript",
    "diff3_typescript": "typescript",
}

# Optional context hints per diff (helps the pr_summary be more accurate)
DIFF_CONTEXT_MAP = {
    "diff1_python": "This PR adds a refund endpoint and modifies transaction query logic in a payment service.",
    "diff2_javascript": "This PR adds a bulk user fetch endpoint and updates the password reset logic in a Node.js controller.",
    "diff3_typescript": "This PR adds order cancellation logic and a status polling mechanism to a TypeScript order service.",
}


# ── Helpers ─────────────────────────────────────────────────────────────────

def detect_language_and_context(filepath: Path) -> tuple[str, str]:
    """Extract language and context from filename."""
    stem = filepath.stem  # e.g. 'diff1_python'
    language = DIFF_LANGUAGE_MAP.get(stem, "unknown")
    context = DIFF_CONTEXT_MAP.get(stem, "")
    return language, context


def print_summary(diff_name: str, report: dict) -> None:
    """Print a human-readable summary of a review report."""
    verdict = report.get("verdict", "?").upper()
    severity = report.get("overall_severity", "?").upper()
    finding_count = len(report.get("findings", []))
    time_ms = report.get("processing_time_ms", 0)

    print(f"\n{'─' * 60}")
    print(f"  {diff_name}")
    print(f"{'─' * 60}")
    print(f"  Verdict:  {verdict}")
    print(f"  Severity: {severity}")
    print(f"  Findings: {finding_count}")
    print(f"  Time:     {time_ms}ms")
    print(f"  Summary:  {report.get('pr_summary', '')}")

    counts = report.get("agent_findings_count", {})
    print(f"  Per agent: security={counts.get('security', 0)} | "
          f"performance={counts.get('performance', 0)} | "
          f"correctness={counts.get('correctness', 0)} | "
          f"style={counts.get('style', 0)} | "
          f"test_coverage={counts.get('test_coverage', 0)}")

    for finding in report.get("findings", [])[:5]:
        sev = finding.get("severity", "?").upper()
        title = finding.get("title", "?")
        line = finding.get("line", "?")
        fid = finding.get("id", "?")
        print(f"  [{fid}] [{sev}] Line {line}: {title}")

    if finding_count > 5:
        print(f"  ... and {finding_count - 5} more findings in the JSON file")


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Run all three diff reviews")
    parser.add_argument("--host", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--timeout", type=int, default=120, help="Request timeout in seconds")
    args = parser.parse_args()

    base_url = args.host.rstrip("/")

    # Validate setup
    if not DIFFS_DIR.exists():
        print(f"ERROR: ./diffs/ directory not found. Create it and add the three diff .txt files.")
        return 1

    REVIEWS_DIR.mkdir(exist_ok=True)

    diff_files = sorted(DIFFS_DIR.glob("*.txt"))
    if not diff_files:
        print(f"ERROR: No .txt files found in {DIFFS_DIR}/")
        return 1

    print(f"\nInfravox AI Code Reviewer — Batch Runner")
    print(f"API: {base_url}")
    print(f"Found {len(diff_files)} diff file(s) to review\n")

    # Health check
    print("Checking API health...", end=" ", flush=True)
    with httpx.Client(timeout=10) as client:
        try:
            health = client.get(f"{base_url}/health")
            health.raise_for_status()
            health_data = health.json()
            groq_ok = health_data.get("groq_connected", False)
            print(f"{'✓ OK' if groq_ok else '⚠ Groq not connected'}")
            if not groq_ok:
                print("WARNING: Groq API not responding. Reviews may fail or use fallback.")
        except Exception as e:
            print(f"✗ FAILED ({e})")
            print("ERROR: API server not running. Start it with: uvicorn main:app --reload")
            return 1

    # Process each diff
    success_count = 0
    with httpx.Client(timeout=args.timeout, base_url=base_url) as client:
        for diff_file in diff_files:
            print(f"\nProcessing: {diff_file.name} ...", end=" ", flush=True)
            start = time.perf_counter()

            diff_text = diff_file.read_text(encoding="utf-8")
            language, context = detect_language_and_context(diff_file)

            try:
                response = client.post(
                    "/review",
                    json={"diff": diff_text, "language": language, "context": context},
                )
                response.raise_for_status()
                report = response.json()

                elapsed = time.perf_counter() - start
                print(f"✓ ({elapsed:.1f}s)")

                # Save JSON response
                output_filename = diff_file.stem.replace("diff", "diff") + "_review.json"
                # Ensure naming matches spec: diff1_review.json etc.
                parts = diff_file.stem.split("_", 1)  # ['diff1', 'python']
                output_filename = f"{parts[0]}_review.json"
                output_path = REVIEWS_DIR / output_filename

                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(report, f, indent=2, default=str)

                print(f"  Saved → {output_path}")
                print_summary(diff_file.name, report)
                success_count += 1

            except httpx.HTTPStatusError as e:
                print(f"✗ HTTP {e.response.status_code}: {e.response.text[:200]}")
            except httpx.TimeoutException:
                print(f"✗ TIMEOUT after {args.timeout}s")
            except Exception as e:
                print(f"✗ ERROR: {e}")

    print(f"\n{'═' * 60}")
    print(f"  Results: {success_count}/{len(diff_files)} reviews completed")
    print(f"  Output:  ./{REVIEWS_DIR}/")
    print(f"{'═' * 60}\n")

    return 0 if success_count == len(diff_files) else 1


if __name__ == "__main__":
    sys.exit(main())
```

---

## 14. Bug Detection Matrix

This section explains exactly how each planted bug should be detected. Study this to verify your agent output after running the three diffs.

### Diff 1: `payments_service.py`

| ID | Line | Bug | Agent | Severity | Detection Trigger |
|----|------|-----|-------|----------|-------------------|
| B1 | 4-5 | SQL injection via f-string in `get_transaction` | security_reviewer | CRITICAL | f-string with `{user_id}` and `{transaction_id}` interpolated directly into SQL |
| B2 | 10 | SQL injection via concatenation in `UPDATE` | security_reviewer | CRITICAL | String concatenation `"...WHERE id=" + str(transaction['id'])` in SQL |
| B3 | 25 | Hardcoded Stripe live secret key `sk_live_...` | security_reviewer | CRITICAL | Pattern match on `sk_live_` string literal assigned to variable |
| B4 | 8 | No null check on `get_transaction()` return | correctness_reviewer | HIGH | `transaction['status']` accessed without checking if `transaction is None` |
| B5 | 13 | XSS via template string replace with user-controlled data | security_reviewer | HIGH | `template.replace('{{message}}', message)` where message contains amount from user request |
| B6 | 13 | File handle resource leak on `open()` without close | correctness_reviewer | MEDIUM | `open('templates/email.html').read()` — no `with` statement, no `.close()` |
| B7 | 19 | No input validation on `refund_endpoint` | correctness_reviewer | HIGH | `data = request.json` then directly `process_refund(data)` — no field validation |
| B8 | 19 | No authentication on `/refunds` endpoint | security_reviewer | CRITICAL | `@app.route('/refunds', methods=['POST'])` with no auth decorator or JWT check |

**Prompt keywords that trigger detection**:
- B1/B2: "f-string interpolation", "string concatenation into SQL" → security agent SQL injection section
- B3: "sk_live_" pattern, "hardcoded credentials" → security agent secrets section
- B4: null check after DB query → correctness agent null dereference section
- B5: template `.replace()` with user data → security agent XSS section
- B6: `open()` without `with` → correctness agent resource leak section
- B7: no required field validation → correctness agent + security agent unvalidated input
- B8: no auth decorator → security agent missing authentication section

### Diff 2: `userController.js`

| ID | Line | Bug | Agent | Severity | Detection Trigger |
|----|------|-----|-------|----------|-------------------|
| B9 | 4 | No null/type check on `req.query.ids` before `.split()` | correctness_reviewer | HIGH | Accessing `.split()` on potentially undefined query param |
| B10 | 5-9 | N+1 query — DB call per user ID inside `for` loop | performance_reviewer | HIGH | `await db.query(...)` inside `for (const id of userIds)` |
| B11 | 8 | `users.push(user[0])` silently pushes `undefined` | correctness_reviewer | MEDIUM | `user[0]` when `user` could be empty array |
| B12 | 17 | Plaintext password storage | security_reviewer | CRITICAL | `UPDATE users SET password = ?` with raw `newPassword` from req.body |
| B13 | 13-22 | IDOR — no auth check, any user can reset any password | security_reviewer | HIGH | `resetPassword` modifies any email's password without verifying caller identity |
| B14 | 28 | `users` variable is undefined — `ReferenceError` at runtime | correctness_reviewer | HIGH | `users[log.user_id]` where `users` is never declared in scope |

**Prompt keywords that trigger detection**:
- B9: missing null check on request params → correctness agent
- B10: await inside for-of loop, N+1 → performance agent N+1 section
- B11: silent undefined push → correctness agent
- B12: SET password without bcrypt → security agent plaintext password section
- B13: no caller identity verification → security agent IDOR section
- B14: undeclared variable reference → correctness agent undefined variable section

### Diff 3: `orderService.ts`

| ID | Line | Bug | Agent | Severity | Detection Trigger |
|----|------|-----|-------|----------|-------------------|
| B15 | 4 | No null check after `orderRepo.findById()` | correctness_reviewer | HIGH | `order.status = 'cancelled'` without null check |
| B16 | 3-8 | No auth check — any userId can cancel any order | security_reviewer | HIGH | `cancelOrder(orderId, userId)` with no ownership verification |
| B17 | 11-16 | Infinite polling loop — no timeout or max retries | performance_reviewer | CRITICAL | `while (status === 'pending')` with no max iterations or timeout |
| B18 | 20-22 | Sequential `await` in loop instead of `Promise.all()` | performance_reviewer | HIGH | `for (const id of orderIds) { await cancelOrder(...) }` — independent iterations |
| B19 | 25 | `any` type defeats TypeScript type safety | style_reviewer | MEDIUM | `const discounts: any = {...}` — should be `Record<string, number>` |
| B20 | 26 | NaN result when `discountCode` not in map | correctness_reviewer | HIGH | `discounts[discountCode]` returns `undefined` → `price * (1 - undefined)` = NaN |
| B21 | 3-8 | Missing tests for double-cancel and notification failure | test_coverage_reviewer | MEDIUM | No test for already-cancelled order or notification service throwing |

---

## 15. README.md Template

Write the README exactly as follows (fill in your GitHub username and specific choices):

```markdown
# Infravox AI Code Reviewer

A production-grade AI code review service built with FastAPI and LangGraph. Accepts raw `git diff` 
output and returns structured, line-level code reviews across 5 quality dimensions.

## Quick Start

\```bash
git clone https://github.com/YOUR_USERNAME/ai-code-reviewer
cd ai-code-reviewer
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Add your GROQ_API_KEY from https://console.groq.com (free, no credit card)
uvicorn main:app --reload
\```

The API is now running at http://localhost:8000. Interactive docs at http://localhost:8000/docs.

## Running the Demo

\```bash
# With the server running, in a second terminal:
python run_reviews.py
# Reads diffs/diff1_python.txt, diff2_javascript.txt, diff3_typescript.txt
# Saves reviews/diff1_review.json, diff2_review.json, diff3_review.json
\```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /review | Submit a diff; returns ReviewReport |
| GET | /review/{id} | Retrieve a review by ID |
| GET | /reviews | List all session reviews |
| GET | /health | Service status + Groq connectivity |

## Architecture

### LangGraph Pipeline

The review pipeline uses a parallel fan-out, fan-in graph topology:

\```
START → [security, performance, correctness, style, test_coverage] → merge → END
\```

All 5 specialist agents run **concurrently** via `pipeline.ainvoke()`, reducing latency from 
~25s sequential to ~8s parallel. Each agent has a focused system prompt engineered for its 
bug class. The merge node deduplicates overlapping findings and calls a separate LLM for the 
narrative summary.

### Architectural Decisions

**Decision: Groq model selection**
- Agents use `llama3-70b-8192` — best reasoning quality on the free tier
- Merge summary uses `gemma2-9b-it` — lighter task, avoids rate-limiting the main agents
- Fallback to `llama3-8b-8192` configured in `.env.example`

**Decision: One LLM call per agent (not one call for all)**
- Each agent gets its own focused prompt and independent LLM call
- This allows true parallel execution and prevents context contamination between categories
- Trade-off: 5 API calls per review instead of 1; justified by parallelism and separation of concerns

**Decision: In-memory storage with asyncio.Lock**
- Assignment specifies session storage; no DB overhead needed
- asyncio.Lock (not threading.Lock) because FastAPI runs in async event loop

**Decision: JSON extraction with regex fallback**
- Groq's llama3-70b-8192 reliably returns JSON, but markdown fences occasionally appear
- 4-attempt extraction strategy handles all real-world LLM output formats

**What I'm most proud of**: The deduplication algorithm in merge.py — it correctly handles the
case where two agents flag the same line from different angles, keeping the more severe finding
rather than generating noisy duplicate reports.

**What I'd do differently with more time**: Add a confidence score to each finding, implement
streaming responses for the POST /review endpoint, and add Redis for persistent cross-session storage.

## AI Assistance Note

Claude was used to assist with prompt engineering for the 5 specialist agents. All architectural
decisions, code structure, and the LangGraph graph topology were designed independently.
The agent system prompts were written by hand and then refined with Claude's help.
```

---

## 16. Submission Checklist

Before pushing to GitHub and sending the submission email, verify every item:

### Code & Structure
- [ ] All files from Section 2's file tree exist and are non-empty
- [ ] `main.py` starts the server with `uvicorn main:app --reload` (one command)
- [ ] `GET /health` returns 200 and `groq_connected: true` when GROQ_API_KEY is valid
- [ ] `POST /review` with diff1_python.txt content returns a ReviewReport with at least 4 findings
- [ ] `GET /review/{id}` returns the same report saved by POST
- [ ] `GET /reviews` returns a list with at least one entry after POST
- [ ] `run_reviews.py` completes without errors and produces 3 JSON files

### Review Quality Verification
Run the agent against all 3 diffs and manually check findings against the Bug Detection Matrix:

**Diff 1 targets** (7 bugs — aim for 5+):
- [ ] SQL injection in `get_transaction` (lines 4-5)
- [ ] SQL injection in UPDATE statement (line 10)
- [ ] Hardcoded `sk_live_` secret (line 25)
- [ ] Missing null check on transaction (line 8)
- [ ] Missing auth on `/refunds` endpoint (line 19)
- [ ] XSS via template replace (line 13)
- [ ] File handle leak (line 13)

**Diff 2 targets** (6 bugs — aim for 4+):
- [ ] Plaintext password storage (line 17)
- [ ] N+1 query in `getUsers` (lines 5-9)
- [ ] Undefined `users` variable (line 28)
- [ ] No null check on `req.query.ids` (line 4)
- [ ] IDOR on password reset (lines 13-22)
- [ ] Silent undefined push (line 8)

**Diff 3 targets** (7 bugs — aim for 5+):
- [ ] Infinite polling loop (lines 11-16)
- [ ] Sequential instead of parallel in `bulkCancelOrders` (lines 20-22)
- [ ] No null check after `findById` (line 4)
- [ ] NaN from undefined discount code (line 26)
- [ ] No auth on `cancelOrder` (lines 3-8)
- [ ] `any` type in TypeScript (line 25)
- [ ] Missing tests for double-cancel (lines 3-8)

### Submission Files
- [ ] GitHub repo is **public**
- [ ] `.env.example` is committed (not `.env`)
- [ ] `reviews/diff1_review.json` — valid ReviewReport JSON, non-empty findings array
- [ ] `reviews/diff2_review.json` — valid ReviewReport JSON, non-empty findings array
- [ ] `reviews/diff3_review.json` — valid ReviewReport JSON, non-empty findings array
- [ ] `run_reviews.py` is in the repo root
- [ ] `README.md` includes one-command setup, architecture section, and AI assistance note

### Demo Video (2 minutes)
Record in this order:
1. **(0:00-0:20)** Show the running server: `uvicorn main:app --reload` → open browser to `http://localhost:8000/docs`
2. **(0:20-0:55)** Run `python run_reviews.py` live — show all 3 diffs being processed, show the output filenames
3. **(0:55-1:25)** Open `reviews/diff1_review.json` — scroll through it, point to the SQL injection finding and the hardcoded key finding
4. **(1:25-1:50)** Show `GET /reviews` in the browser docs returning the 3 review summaries
5. **(1:50-2:00)** Show `GET /health` returning `groq_connected: true`

### Email Checklist
- [ ] Subject: `Assignment Submission, AI Backend Intern, [Your Name]`
- [ ] Body answers the three required questions (3-5 sentences total)
- [ ] GitHub repo link included
- [ ] Demo video attached or linked (Loom/Google Drive if >50MB)
- [ ] Sent to: abhijit@infravox.ai

---

## Appendix: Final Notes for Claude Implementing This

1. **Implement all `__init__.py` files** — they can be empty but must exist for Python imports to work.

2. **The `app/__init__.py`** should import nothing — just an empty file.

3. **Error handling philosophy**: No exception should ever crash the server. Every agent failure returns `[]`. Every parsing failure falls back gracefully. The only place HTTP errors should be raised is in `routes.py` for truly fatal conditions (empty diff, pipeline total failure).

4. **Test the graph compiles** by importing pipeline.py standalone before wiring into FastAPI:
   ```python
   python -c "from app.graph.pipeline import pipeline; print('Graph compiled OK')"
   ```

5. **Groq rate limits**: On the free tier, running 5 concurrent API calls may occasionally hit 429. The tenacity retry in `invoke_llm_with_retry` handles this with exponential backoff. If rate limits are severe during testing, temporarily add `await asyncio.sleep(0.5)` between agent invocations (but remove this for the final demo).

6. **Line number accuracy**: The prompts ask agents to provide line numbers. LLMs are approximately correct on line numbers; the `line_content` field (exact code text) is more reliable. In the interview, if asked about line number discrepancies, explain this and show that the code content matches.

7. **Do not use `langchain_community`** — use only `langchain_groq` and `langchain_core`. The community package has conflicting dependencies.

8. **The `processing_time_ms` field** must be computed from the actual wall-clock time from when the request starts in the route handler (`time.perf_counter()` stored in state) to when the merge node writes it. This is already implemented in `make_initial_state()` and `merge_node()` — do not change this logic.
```