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
