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

    print(f"\n{'-' * 60}")
    print(f"  {diff_name}")
    print(f"{'-' * 60}")
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
            print(f"{'OK' if groq_ok else 'WARNING: Groq not connected'}")
            if not groq_ok:
                print("WARNING: Groq API not responding. Reviews may fail or use fallback.")
        except Exception as e:
            print(f"FAILED ({e})")
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
                print(f"Done ({elapsed:.1f}s)")

                # Save JSON response
                parts = diff_file.stem.split("_", 1)  # ['diff1', 'python']
                output_filename = f"{parts[0]}_review.json"
                output_path = REVIEWS_DIR / output_filename

                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(report, f, indent=2, default=str)

                print(f"  Saved -> {output_path}")
                print_summary(diff_file.name, report)
                success_count += 1

            except httpx.HTTPStatusError as e:
                print(f"HTTP {e.response.status_code}: {e.response.text[:200]}")
            except httpx.TimeoutException:
                print(f"TIMEOUT after {args.timeout}s")
            except Exception as e:
                print(f"ERROR: {e}")

    print(f"\n{'=' * 60}")
    print(f"  Results: {success_count}/{len(diff_files)} reviews completed")
    print(f"  Output:  ./{REVIEWS_DIR}/")
    print(f"{'=' * 60}\n")

    return 0 if success_count == len(diff_files) else 1


if __name__ == "__main__":
    sys.exit(main())
