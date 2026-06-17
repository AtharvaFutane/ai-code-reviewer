# Phase 2 — Complete Reference Guide (For Your Learning)

> **What was Phase 2 about?**  
> Building the actual AI brain of the application — the 5 specialist reviewer agents, the merge node that combines their findings, and the LangGraph pipeline that runs them all in parallel. This is the CORE of the entire project.

---

## 🧠 The Big Picture: What Did We Build?

Imagine you're a tech lead and you need to review a code change (a "pull request"). Instead of reviewing it alone, you call in 5 specialists:

1. 🔒 **Security Expert** — Finds vulnerabilities (SQL injection, leaked keys, missing auth)
2. ⚡ **Performance Expert** — Finds slowness (N+1 queries, infinite loops, sequential code)
3. 🐛 **Correctness Expert** — Finds bugs (null crashes, undefined variables, wrong logic)
4. 🎨 **Style Expert** — Finds maintainability issues (type safety, hardcoded values, long functions)
5. 🧪 **Test Expert** — Finds missing tests (edge cases, error paths, security tests)

All 5 review the SAME code simultaneously (in parallel), then a **merge coordinator** collects their findings, removes duplicates, and produces a single unified report.

That's exactly what our LangGraph pipeline does — but with AI models instead of humans.

```
                    ┌──► 🔒 Security Agent ──────┐
                    ├──► ⚡ Performance Agent ───┤
   Code Diff ──►    ├──► 🐛 Correctness Agent ──┼──► 📋 Merge Node ──► Final Report
                    ├──► 🎨 Style Agent ─────────┤
                    └──► 🧪 Test Coverage Agent ─┘
                    
                    ← All 5 run SIMULTANEOUSLY →    ← Waits for all 5 →
```

---

## 📁 Files Created in Phase 2

| File | Purpose | Lines of Code |
|------|---------|--------------|
| `app/graph/prompts.py` | Instructions for each of the 5 AI agents | ~340 lines |
| `app/graph/agents.py` | Functions that call the AI and parse results | ~80 lines |
| `app/graph/merge.py` | Combines all findings into one report | ~200 lines |
| `app/graph/pipeline.py` | Wires everything together as a LangGraph | ~65 lines |

---

## File 1: `app/graph/prompts.py` — "The instruction manuals"

### What Are System Prompts?

When you talk to an AI chatbot, there are TWO types of messages:
1. **System prompt** — Instructions the developer gives the AI about HOW to behave (the user doesn't see this)
2. **User message** — What the user actually asks

Example:
```
System: "You are a security expert. Only find security bugs. Return JSON."
User: "Review this code: def get_user(id): query = f'SELECT * FROM users WHERE id = {id}'"
AI: {"findings": [{"title": "SQL Injection", "severity": "critical", ...}]}
```

The system prompt is like giving an employee a job description before they start work.

### Why 5 Separate Prompts?

Each agent has a DIFFERENT system prompt because they look for DIFFERENT things:

| Agent | What Their Prompt Says to Look For |
|-------|-----------------------------------|
| Security | SQL injection, hardcoded secrets, missing auth, XSS, plaintext passwords, IDOR |
| Performance | N+1 queries, infinite loops, sequential async, missing pagination |
| Correctness | Null dereference, undefined variables, resource leaks, NaN propagation |
| Style | `any` type usage, hardcoded config values, functions too long, dead code |
| Test Coverage | Missing null tests, missing error tests, missing idempotency tests |

### How Each Prompt is Structured

Every prompt follows the same pattern:
```
1. "You are a [specialist role] reviewer..."     ← Tell the AI WHO it is
2. "Look for these specific issues:"              ← LIST every bug class
3. "1. [BUG CLASS NAME]"                          ← Describe each class in detail
   "   Look for: [specific code patterns]"        ← Give concrete examples
   "   Example: [real code that has this bug]"    ← Show what BAD code looks like
4. "Output format — return ONLY valid JSON..."    ← Tell it EXACTLY what shape to return
5. "If you find no issues, return: {}"            ← Handle the "no bugs" case
6. "Severity guidelines: critical = ..."          ← Define what each severity means
```

### Why Are the Prompts So Detailed?

AI models are MUCH better when you:
- Give specific examples of what to look for (not just "find bugs")
- Show them the exact output format you want
- Tell them what severity level to assign
- List every specific pattern to check

A vague prompt like "review this code" gives vague results. Our prompts are ~60 lines each because PRECISION = QUALITY.

### The `build_user_message()` Function

```python
def build_user_message(diff: str, language: str, context: str | None) -> str:
```

All 5 agents get the SAME user message — only the system prompt differs. The user message contains:
1. The language (PYTHON, JAVASCRIPT, TYPESCRIPT)
2. Optional context ("This PR adds a refund endpoint...")
3. The full diff wrapped in a code block

This is smart because:
- Each agent sees the SAME code
- Each agent applies its OWN specialty lens
- No code duplication — one function builds the message for all 5

---

## File 2: `app/graph/agents.py` — "The workers"

### The DRY Pattern: `_run_agent()`

All 5 agents do the SAME steps:
1. Create a Groq LLM client
2. Build the user message from the state
3. Call the LLM with the system prompt + user message
4. Parse the JSON response into a list of findings
5. Return the findings

Instead of writing this 5 times, we wrote ONE shared function `_run_agent()`:

```python
async def _run_agent(state, system_prompt, category):
    llm = get_llm()                                    # Step 1
    user_message = build_user_message(...)              # Step 2
    raw_response = await invoke_llm_with_retry(...)     # Step 3
    findings = parse_raw_findings(raw_response, ...)    # Step 4
    return findings                                     # Step 5
```

Then each agent is just a thin wrapper:
```python
async def security_reviewer_node(state):
    findings = await _run_agent(state, SECURITY_SYSTEM_PROMPT, "security")
    return {"security_findings": findings}  # Writes to ITS OWN field
```

**DRY = Don't Repeat Yourself** — one of the most important principles in programming. If you need to change the agent logic, you change it in ONE place, not five.

### Error Handling: Never Crash

```python
try:
    raw_response = await invoke_llm_with_retry(llm, system_prompt, user_message)
    findings = parse_raw_findings(raw_response, category, MAX_FINDINGS)
    return findings
except Exception as exc:
    logger.error(f"[{category}] agent failed after retries: {exc}")
    return []  # ← Return EMPTY list, don't crash!
```

**Why this matters**: If the security agent fails (Groq is down, rate limited, etc.), we DON'T want the entire review to fail. We want the other 4 agents to still return their findings. So a failed agent returns `[]` (no findings) instead of crashing.

**Analogy**: If one of your 5 doctors gets sick, you don't cancel all the other doctors' appointments. You just proceed without that one.

### Why Each Agent Returns a Dict with ONE Key

```python
return {"security_findings": findings}     # ← Just ONE key
return {"performance_findings": findings}  # ← Different key
```

LangGraph updates the state by MERGING the return value with the existing state. So when the security agent returns `{"security_findings": [...]}`, LangGraph updates ONLY the `security_findings` field in the state, leaving everything else untouched.

This is how 5 agents can run in parallel without overwriting each other's results.

### What Does `async` Mean Here?

```python
async def security_reviewer_node(state):
    findings = await _run_agent(...)
```

- `async def` = "This function can be paused and resumed"
- `await` = "Pause here until the result comes back, but let OTHER code run while waiting"

Without `async`, our code would:
1. Call security agent → wait 5 seconds (doing NOTHING)
2. Call performance agent → wait 5 seconds
3. Call correctness agent → wait 5 seconds
4. ... Total: 25 seconds

With `async`, LangGraph can:
1. Start ALL 5 agents simultaneously
2. While waiting for security (5s), performance is also running, correctness is also running...
3. Total: ~5-8 seconds (the time of the SLOWEST agent, not the SUM)

---

## File 3: `app/graph/merge.py` — "The coordinator"

This is the most complex file. Let's break down each step.

### Step 1: Collect All Findings

```python
all_raw_findings = []
all_raw_findings.extend(state.get("security_findings", []))
all_raw_findings.extend(state.get("performance_findings", []))
all_raw_findings.extend(state.get("correctness_findings", []))
all_raw_findings.extend(state.get("style_findings", []))
all_raw_findings.extend(state.get("test_coverage_findings", []))
```

Simple — gather all findings from all 5 agents into one big list. If an agent returned 5 findings and another returned 3, we now have 8 total (plus whatever the other 3 agents found).

### Step 2: Deduplicate

**The Problem**: Sometimes two agents find the SAME issue. For example:
- Security agent: "Line 7: SQL injection in query" (severity: critical)
- Correctness agent: "Line 8: Missing input validation in query" (severity: high)

These are about the same bug on adjacent lines. We don't want to report it twice.

**The Rule**: Two findings are duplicates if:
1. They have the **same category** (e.g., both "security"), AND
2. Their **line numbers are within 2 lines** of each other

When duplicates are found, we keep the one with **higher severity**. If equal severity, we keep the one with the **longer description** (more detail).

```python
def _deduplicate_findings(findings):
    seen = []  # Already processed findings
    for candidate in findings:
        is_duplicate = False
        for i, existing in enumerate(seen):
            if existing["category"] != candidate["category"]:
                continue  # Different categories → not duplicates
            if abs(existing["line"] - candidate["line"]) <= 2:
                # Same category, nearby lines → DUPLICATE!
                # Keep the more severe one
                if candidate_severity > existing_severity:
                    seen[i] = candidate  # Replace with better one
                is_duplicate = True
                break
        if not is_duplicate:
            seen.append(candidate)  # New unique finding
    return seen
```

**Note**: Findings from DIFFERENT categories on the same line are NOT duplicates. A security issue and a correctness issue on line 7 are genuinely two different problems.

### Step 3: Sort and Assign IDs

```python
def _sort_and_assign_ids(findings):
    sorted_findings = sorted(findings, key=lambda f: (-severity_rank, line_number))
    for idx, finding in enumerate(sorted_findings, start=1):
        finding["id"] = f"F-{idx:03d}"  # F-001, F-002, F-003, ...
    return sorted_findings
```

- **Sort by severity first** (critical → high → medium → low), then by line number
- **Assign sequential IDs**: F-001 is always the most critical finding

This makes the report easy to read — the worst issues are at the top.

### Step 4: Compute Overall Severity

```python
def _compute_overall_severity(findings):
    if not findings:
        return "clean"  # No issues found!
    # Return the HIGHEST severity found
    # If ANY finding is "critical", overall is "critical"
```

Simple rule: the overall severity is the MAX of all individual findings.

### Step 5: Compute Verdict

```python
def _compute_verdict(overall_severity):
    if overall_severity in ("critical", "high"):
        return "request_changes"    # "STOP! Don't merge this code!"
    if overall_severity == "medium":
        return "needs_discussion"   # "Let's talk about this first"
    return "approve"                # "Looks good, ship it!"
```

| Overall Severity | Verdict | Meaning |
|-----------------|---------|---------|
| critical / high | `request_changes` | Code has serious issues, must fix before merging |
| medium | `needs_discussion` | Some issues, human should decide if they matter |
| low / clean | `approve` | Code is fine to merge |

### Step 6: Count Agent Findings

```python
agent_counts = {"security": 0, "performance": 0, "correctness": 0, "style": 0, "test_coverage": 0}
for finding in final_findings:
    agent_counts[finding["category"]] += 1
```

Just counts how many findings each agent contributed. Shown in the final report so you can see which agent found the most issues.

### Step 7: LLM Summary Call

We make ONE MORE call to the AI (using a lighter/cheaper model: `gemma2-9b-it`) to generate:
- **pr_summary**: "Adds a refund endpoint and modifies transaction query logic"
- **verdict_reason**: "Critical SQL injection vulnerabilities require immediate fixes"
- **positive_observations**: ["Function names are clear", "Error responses are consistent"]

**Why a separate LLM call?**: The 5 agents only find bugs. We need a separate "summarizer" to describe what the PR does and say nice things about it. This uses a cheaper model because summarization is an easier task than bug detection.

**Why defaults exist**:
```python
pr_summary = "This PR adds new functionality to the codebase."  # Default
# ... try to call LLM ...
# If LLM fails, we use the defaults — review still succeeds
```

### Step 8: Processing Time

```python
elapsed_ms = int((time.perf_counter() - state["start_time"]) * 1000)
```

Remember `start_time` was set in `make_initial_state()` (Phase 1)? Here we compute how long the entire review took in milliseconds. This appears in the final report.

### Step 9: Build Report Dict

All the pieces are assembled into one dictionary that matches the `ReviewReport` Pydantic model from Phase 1.

---

## File 4: `app/graph/pipeline.py` — "The assembly line"

### What is a StateGraph?

LangGraph's `StateGraph` is like a flowchart:
- **Nodes** = Boxes (functions that do work)
- **Edges** = Arrows (connections between boxes)
- **State** = A clipboard passed from box to box

### How We Built It

```python
workflow = StateGraph(ReviewState)  # "Use ReviewState as the clipboard shape"
```

**Step 1: Register all nodes** (add the boxes to the flowchart)
```python
workflow.add_node("security_reviewer", security_reviewer_node)
workflow.add_node("performance_reviewer", performance_reviewer_node)
workflow.add_node("correctness_reviewer", correctness_reviewer_node)
workflow.add_node("style_reviewer", style_reviewer_node)
workflow.add_node("test_coverage_reviewer", test_coverage_reviewer_node)
workflow.add_node("merge", merge_node)
```

Each node has a name (string) and a function. When LangGraph "runs" a node, it calls that function with the current state.

**Step 2: Fan-out edges** (START → all 5 agents)
```python
workflow.add_edge(START, "security_reviewer")
workflow.add_edge(START, "performance_reviewer")
workflow.add_edge(START, "correctness_reviewer")
workflow.add_edge(START, "style_reviewer")
workflow.add_edge(START, "test_coverage_reviewer")
```

`START` is a special LangGraph constant meaning "the beginning." By connecting START to ALL 5 agents, LangGraph knows to run them **in parallel** (simultaneously).

**Step 3: Fan-in edges** (all 5 agents → merge)
```python
workflow.add_edge("security_reviewer", "merge")
workflow.add_edge("performance_reviewer", "merge")
workflow.add_edge("correctness_reviewer", "merge")
workflow.add_edge("style_reviewer", "merge")
workflow.add_edge("test_coverage_reviewer", "merge")
```

This tells LangGraph: "Don't run merge until ALL 5 agents are done." It automatically waits.

**Step 4: Final edge** (merge → END)
```python
workflow.add_edge("merge", END)
```

`END` is another special constant meaning "we're done."

**Step 5: Compile** (freeze the flowchart into a runnable thing)
```python
compiled = workflow.compile()
```

Once compiled, the graph is immutable (can't be changed). This is efficient because we compile ONCE at startup and reuse it for every request.

### The Module-Level Singleton

```python
pipeline = build_pipeline()  # Runs ONCE when the module is imported
```

This means the graph is compiled when the server starts, not when each request arrives. Every review request uses the same compiled graph.

### Why Fan-Out/Fan-In Matters for the Rubric

The assignment specifically evaluates "LangGraph architecture" as its own line item. A clean fan-out/fan-in topology (START → 5 parallel nodes → merge → END) demonstrates:

1. You understand parallel execution
2. You used LangGraph's native capabilities (not just running agents sequentially)
3. The architecture is clean, visual, and maintainable

Running agents sequentially (`agent1 → agent2 → agent3 → ...`) would work but would be **slower** and wouldn't demonstrate LangGraph's value.

---

## 🔑 Key Concepts Explained

### What is LangGraph?

**LangGraph** is built on top of LangChain. While LangChain handles individual LLM calls, LangGraph handles **orchestrating multiple LLM calls** in complex patterns.

Think of it this way:
- **LangChain** = "Call ONE AI model"
- **LangGraph** = "Call FIVE AI models in parallel, combine their results, handle failures"

### What is a "Node" in LangGraph?

A node is just an async function that:
1. **Takes** the current state (a dictionary)
2. **Does something** (usually calls an LLM)
3. **Returns** a dict with ONLY the fields it wants to update

```python
async def security_reviewer_node(state: ReviewState) -> dict:
    # state has: diff, language, context, start_time, all findings lists, etc.
    findings = await _run_agent(state, SECURITY_SYSTEM_PROMPT, "security")
    return {"security_findings": findings}  # Only updates THIS field
```

### What is "Fan-Out / Fan-In"?

- **Fan-Out** = One input splits into multiple parallel paths (like a river splitting into 5 streams)
- **Fan-In** = Multiple parallel paths converge back into one (like 5 streams merging into a river)

```
     Fan-Out                          Fan-In
     START ──┬──► Agent 1 ──┐
             ├──► Agent 2 ──┤
             ├──► Agent 3 ──┼──► Merge
             ├──► Agent 4 ──┤
             └──► Agent 5 ──┘
```

### What is "Deduplication"?

When 5 agents independently review the same code, they might find the same bug. For example:
- Security agent: "Line 4: SQL injection" (critical)
- Correctness agent: "Line 5: No input sanitization" (high)

These are essentially the same issue (both about line 4-5's SQL query). Deduplication detects this overlap and keeps only the more important one (critical > high), so the final report doesn't have redundant findings.

### What is a "Verdict"?

The verdict is the final decision about the code:
- **approve** = "This code is fine to merge" ✅
- **needs_discussion** = "There are some concerns, let's talk" 💬
- **request_changes** = "This code has serious issues, fix them first" ❌

Our merge node decides the verdict based on the most severe finding.

---

## 🔄 Data Flow: How a Review Actually Works

Here's what happens step by step when a review request comes in:

```
1. User sends:  POST /review {"diff": "...", "language": "python"}

2. State is created:
   {
     diff: "...",
     language: "python",
     context: null,
     start_time: 1718624000.0,
     security_findings: [],
     performance_findings: [],
     correctness_findings: [],
     style_findings: [],
     test_coverage_findings: [],
     review_report: null
   }

3. LangGraph starts pipeline.ainvoke(state)

4. Fan-Out: All 5 agents start SIMULTANEOUSLY
   - Security agent calls Groq with SECURITY_SYSTEM_PROMPT
   - Performance agent calls Groq with PERFORMANCE_SYSTEM_PROMPT
   - Correctness agent calls Groq with CORRECTNESS_SYSTEM_PROMPT
   - Style agent calls Groq with STYLE_SYSTEM_PROMPT
   - Test coverage agent calls Groq with TEST_COVERAGE_SYSTEM_PROMPT

5. Each agent finishes and returns its findings:
   Security: {"security_findings": [{line:4, title:"SQL Injection",...}, ...]}
   Performance: {"performance_findings": []}
   Correctness: {"correctness_findings": [{line:8, title:"Null check",...}]}
   Style: {"style_findings": []}
   Test: {"test_coverage_findings": [{line:19, title:"Missing tests",...}]}

6. LangGraph merges these into the state (each agent wrote to its OWN field)

7. Fan-In: Merge node runs
   - Collects ALL findings from all 5 fields
   - Deduplicates (removes overlapping findings)
   - Sorts by severity
   - Assigns IDs (F-001, F-002, ...)
   - Computes verdict
   - Calls Groq ONE MORE TIME for summary
   - Returns {"review_report": {...final report...}}

8. pipeline.ainvoke() returns the final state with review_report filled in

9. Route handler extracts state["review_report"], validates with Pydantic, stores, returns to user
```

---

## ✅ Phase 2 Verification Results

| Check | Result |
|-------|--------|
| `prompts.py` — All 5 prompts defined | ✅ |
| `agents.py` — All 5 agent nodes implemented | ✅ |
| `merge.py` — Deduplication, scoring, verdict, LLM summary | ✅ |
| `pipeline.py` — StateGraph compiles | ✅ `"Graph compiled OK"` |
| Server boots with pipeline loaded | ✅ `/health` returns 200 |
| Groq connected | ✅ `groq_connected: true` |

---

## 🔜 What's Next (Phase 3)?

Phase 3 connects the pipeline to the API:
1. **`POST /review` endpoint** — Takes a diff, runs the pipeline, returns the report
2. **`run_reviews.py` script** — Reads all 3 diff files and posts them to the API
3. **Test against all 3 diffs** — Verify the AI finds the planted bugs
