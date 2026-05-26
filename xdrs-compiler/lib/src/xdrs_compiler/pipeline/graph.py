from __future__ import annotations

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from .analysis import analyze_docs_node, judge_node, plan_xdrs_node
from .preparation import conversion_node, discovery_node, filter_node
from .report import report_node
from .state import CompilerState
from .synthesis import generate_policies_node, generate_skills_node, review_node, write_output_node

_MAX_ANALYSIS_ITERATIONS = 2


def _route_after_judge(state: CompilerState) -> str:
    """Continue to synthesis when the judge approves or the iteration limit is reached."""
    if (
        state.get("judge_approved")
        or state.get("analysis_iteration", 0) >= _MAX_ANALYSIS_ITERATIONS
    ):
        return "generate_policies"
    return "analyze_docs"


def build_graph() -> CompiledStateGraph:
    """Build and compile the XDRS compiler LangGraph pipeline.

    Graph topology:
      discovery → conversion → filter
        → analyze_docs → plan_xdrs → judge
             ↑ (loop if not approved and iteration < 2) ↓ (proceed when approved or limit reached)
        → generate_policies → generate_skills → review → write_output → report → END
    """
    graph: StateGraph = StateGraph(CompilerState)

    # Phase 1: Preparation
    graph.add_node("discovery", discovery_node)
    graph.add_node("conversion", conversion_node)
    graph.add_node("filter", filter_node)

    # Phase 2: Analysis (with judge loop)
    graph.add_node("analyze_docs", analyze_docs_node)
    graph.add_node("plan_xdrs", plan_xdrs_node)
    graph.add_node("judge", judge_node)

    # Phase 3: Synthesis
    graph.add_node("generate_policies", generate_policies_node)
    graph.add_node("generate_skills", generate_skills_node)
    graph.add_node("review", review_node)
    graph.add_node("write_output", write_output_node)

    # Phase 4: Report
    graph.add_node("report", report_node)

    # Phase 1 edges
    graph.set_entry_point("discovery")
    graph.add_edge("discovery", "conversion")
    graph.add_edge("conversion", "filter")
    graph.add_edge("filter", "analyze_docs")

    # Phase 2 edges (with conditional loop)
    graph.add_edge("analyze_docs", "plan_xdrs")
    graph.add_edge("plan_xdrs", "judge")
    graph.add_conditional_edges("judge", _route_after_judge)

    # Phase 3 edges
    graph.add_edge("generate_policies", "generate_skills")
    graph.add_edge("generate_skills", "review")
    graph.add_edge("review", "write_output")

    # Phase 4 edge
    graph.add_edge("write_output", "report")
    graph.add_edge("report", END)

    return graph.compile()
