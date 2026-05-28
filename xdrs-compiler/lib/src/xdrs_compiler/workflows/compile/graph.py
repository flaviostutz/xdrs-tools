from __future__ import annotations

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from .agents import (
    analyze_docs_node,
    generate_policies_node,
    generate_skills_node,
    judge_node,
    plan_xdrs_node,
    review_node,
    verify_output_node,
)
from .nodes import conversion_node, discovery_node, filter_node, report_node, write_output_node
from .routes import route_after_judge, route_after_verification
from .states import CompilerState


def _build_graph() -> CompiledStateGraph:
    """Build and compile the XDRS compiler LangGraph pipeline.

    Graph topology:
      discovery → conversion → filter
        → analyze_docs → plan_xdrs → judge
             ↑ (loop if not approved and iteration < 2) ↓ (proceed when approved or limit reached)
        → generate_policies → generate_skills → review → verify_output
            → write_output → report → END
            → generate_policies (retry when verification fails)
    """
    g: StateGraph = StateGraph(CompilerState)

    # Phase 1: Preparation
    g.add_node("discovery", discovery_node)
    g.add_node("conversion", conversion_node)
    g.add_node("filter", filter_node)

    # Phase 2: Analysis (with judge loop)
    g.add_node("analyze_docs", analyze_docs_node)
    g.add_node("plan_xdrs", plan_xdrs_node)
    g.add_node("judge", judge_node)

    # Phase 3: Synthesis
    g.add_node("generate_policies", generate_policies_node)
    g.add_node("generate_skills", generate_skills_node)
    g.add_node("review", review_node)
    g.add_node("verify_output", verify_output_node)
    g.add_node("write_output", write_output_node)

    # Phase 4: Report
    g.add_node("report", report_node)

    # Phase 1 edges
    g.set_entry_point("discovery")
    g.add_edge("discovery", "conversion")
    g.add_edge("conversion", "filter")
    g.add_edge("filter", "analyze_docs")

    # Phase 2 edges (with conditional loop)
    g.add_edge("analyze_docs", "plan_xdrs")
    g.add_edge("plan_xdrs", "judge")
    g.add_conditional_edges("judge", route_after_judge)

    # Phase 3 edges
    g.add_edge("generate_policies", "generate_skills")
    g.add_edge("generate_skills", "review")
    g.add_edge("review", "verify_output")
    g.add_conditional_edges("verify_output", route_after_verification)

    # Phase 4 edge
    g.add_edge("write_output", "report")
    g.add_edge("report", END)

    return g.compile()


graph: CompiledStateGraph = _build_graph()
