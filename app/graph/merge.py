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
