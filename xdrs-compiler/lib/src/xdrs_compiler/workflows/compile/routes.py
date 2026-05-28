from __future__ import annotations

from .states import CompilerState

_MAX_ANALYSIS_ITERATIONS = 2
_MAX_VERIFICATION_ITERATIONS = 2


def route_after_judge(state: CompilerState) -> str:
    """Continue to synthesis when the judge approves or the iteration limit is reached."""
    if (
        state.get("judge_approved")
        or state.get("analysis_iteration", 0) >= _MAX_ANALYSIS_ITERATIONS
    ):
        return "generate_policies"
    return "analyze_docs"


def route_after_verification(state: CompilerState) -> str:
    """Write approved docs, retry failed verification, or stop after the retry limit."""
    if state.get("verification_passed"):
        return "write_output"
    if state.get("verification_iteration", 0) >= _MAX_VERIFICATION_ITERATIONS:
        return "report"
    return "generate_policies"
