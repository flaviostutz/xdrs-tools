from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .state import CompilerState, FileAnalysis, JudgementResult, ProposalsMap

_ANALYZE_SYSTEM = """\
You are an expert document analyst. For the given document, extract the following fields and \
return valid JSON matching the schema exactly:

- date: the approximate date the content was produced (ISO format YYYY-MM-DD), or null if unknown
- abstract: a concise summary focused on problem statement and decision/outcomes (<30 words)
- topic_policies: list of topic titles with potential to become XDRS policy documents \
  (<10 words each). A policy captures a decision, rule, constraint, or required behavior.
- topic_skills: list of topic titles with potential to become XDRS skill documents (<10 words each).
  A skill captures a reusable step-by-step procedure or workflow.

Return only the JSON object, no surrounding text."""

_PLAN_SYSTEM = """\
You are an expert at structuring organizational knowledge into XDRS policy and skill documents.

Given per-document analysis results, consolidate and deduplicate topics into a coherent set of \
proposed XDRS elements. Group related topics from multiple documents into single items where \
appropriate.

Return a JSON object with exactly two keys:
- proposed_policies: dict mapping kebab-case title ->
  {abstract: str (<20 words), related_docs: [source paths]}
- proposed_skills: dict mapping kebab-case title ->
  {abstract: str (<20 words), related_docs: [source paths]}

Use descriptive kebab-case titles (e.g. "production-deployment-requirements").
Return only the JSON object, no surrounding text."""

_JUDGE_SYSTEM = """\
You are a senior XDRS architect reviewing a proposed set of policies and skills.
Evaluate the proposals against ALL of the following criteria:

1. Usefulness — each document provides reusable organizational knowledge worth keeping in a \
shared XDRS scope. Reject overly context-specific or one-off documents.
2. Defined scope — each document has a clear, well-bounded topic. A document covering too many \
unrelated topics should be split.
3. No duplicates — no two proposed documents cover the same topic; merge duplicates.
4. Focus — the scope of each document is not too broad or too diverse.
5. Source relevance — each document's related_docs list contains source files whose contents \
actually relate to the proposed policy or skill.
6. Full coverage — the set of proposed policies and skills collectively covers all useful \
information present in the source documents (nothing important is omitted).
7. Source traceability — every proposed document has at least one meaningful related_doc.

Return a JSON object with:
- approved: true if all criteria are satisfied, false otherwise
- issues: list of specific problems found (empty if approved)
- feedback: concise actionable guidance for the next analysis iteration (empty if approved)

Return only the JSON object, no surrounding text."""


def _feedback_suffix(state: CompilerState) -> str:
    feedback = state.get("judge_feedback", "")
    if not feedback:
        return ""
    iteration = state.get("analysis_iteration", 0)
    return (
        f"\n\nNOTE — This is revision {iteration + 1}. A previous plan was rejected.\n"
        f"Judge feedback:\n{feedback}\n"
        "Adjust your output to address the issues raised above."
    )


def analyze_docs_node(state: CompilerState) -> dict:
    """LLM-analyzes each converted document to extract topics and metadata."""
    model = state["model"]
    llm = ChatOpenAI(model=model).with_structured_output(FileAnalysis)
    analysis: dict[str, FileAnalysis] = {}
    errors: list[str] = []
    suffix = _feedback_suffix(state)

    for path, text in state["converted_files"].items():
        try:
            result = llm.invoke(
                [
                    SystemMessage(_ANALYZE_SYSTEM),
                    HumanMessage(f"Document path: {path}\n\nContent:\n{text[:8000]}{suffix}"),
                ]
            )
            analysis[path] = result  # type: ignore[assignment]
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path}: analysis failed: {exc}")

    return {"analysis": analysis, "errors": errors}


def plan_xdrs_node(state: CompilerState) -> dict:
    """LLM aggregates all per-doc analysis into a unified proposals map."""
    model = state["model"]
    llm = ChatOpenAI(model=model).with_structured_output(ProposalsMap)

    if not state["analysis"]:
        return {"proposals": ProposalsMap(), "errors": []}

    analysis_text = "\n\n".join(
        f"=== {path} ===\n"
        f"Date: {a.date or 'unknown'}\n"
        f"Abstract: {a.abstract}\n"
        f"Policy topics: {', '.join(a.topic_policies) or 'none'}\n"
        f"Skill topics: {', '.join(a.topic_skills) or 'none'}"
        for path, a in state["analysis"].items()
    )

    suffix = _feedback_suffix(state)
    errors: list[str] = []
    proposals = ProposalsMap()
    try:
        result = llm.invoke(
            [
                SystemMessage(_PLAN_SYSTEM),
                HumanMessage(f"Document analysis results:\n\n{analysis_text}{suffix}"),
            ]
        )
        proposals = result  # type: ignore[assignment]
    except Exception as exc:  # noqa: BLE001
        errors.append(f"plan_xdrs: failed: {exc}")

    return {"proposals": proposals, "errors": errors}


def judge_node(state: CompilerState) -> dict:
    """LLM judge evaluates proposals against XDRS quality criteria.

    Increments analysis_iteration on every call. Sets judge_approved and
    judge_feedback so the conditional edge can decide whether to loop back.
    """
    model = state["model"]
    llm = ChatOpenAI(model=model).with_structured_output(JudgementResult)

    proposals = state.get("proposals") or ProposalsMap()
    analysis = state.get("analysis") or {}

    # Build a rich context for the judge
    proposals_text = "PROPOSED POLICIES:\n"
    for title, p in proposals.proposed_policies.items():
        proposals_text += (
            f"  [{title}]\n"
            f"  Abstract: {p.abstract}\n"
            f"  Related docs: {', '.join(p.related_docs) or 'none'}\n\n"
        )
    proposals_text += "\nPROPOSED SKILLS:\n"
    for title, s in proposals.proposed_skills.items():
        proposals_text += (
            f"  [{title}]\n"
            f"  Abstract: {s.abstract}\n"
            f"  Related docs: {', '.join(s.related_docs) or 'none'}\n\n"
        )

    source_summary = "\nSOURCE DOCUMENTS ANALYSED:\n" + "\n".join(
        f"  {path}: {a.abstract}" for path, a in analysis.items()
    )

    new_iteration = state.get("analysis_iteration", 0) + 1
    errors: list[str] = []
    judgement = JudgementResult(approved=True)

    try:
        result = llm.invoke(
            [
                SystemMessage(_JUDGE_SYSTEM),
                HumanMessage(proposals_text + source_summary),
            ]
        )
        judgement = result  # type: ignore[assignment]
    except Exception as exc:  # noqa: BLE001
        errors.append(f"judge: evaluation failed: {exc}")
        # On judge failure, approve so the pipeline can proceed

    return {
        "judge_approved": judgement.approved,  # type: ignore[union-attr]
        "judge_feedback": judgement.feedback if not judgement.approved else "",  # type: ignore[union-attr]
        "analysis_iteration": new_iteration,
        "errors": errors,
    }
