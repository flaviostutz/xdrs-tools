from __future__ import annotations

import os

import mlflow
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import AzureChatOpenAI, ChatOpenAI

from .prompts import (
    ANALYZE_SYSTEM,
    JUDGE_SYSTEM,
    PLAN_SYSTEM,
    POLICY_SYSTEM,
    REVIEW_SYSTEM,
    SKILL_SYSTEM,
    VERIFY_SYSTEM,
)
from .states import (
    CompilerState,
    FileAnalysis,
    GeneratedDoc,
    JudgementResult,
    ProposalsMap,
    VerificationResult,
)


def _get_llm(model: str) -> ChatOpenAI | AzureChatOpenAI:
    """Return an LLM client for OpenAI or Azure OpenAI, selected by OPENAI_API_TYPE env var."""
    if os.environ.get("OPENAI_API_TYPE") == "azure":
        return AzureChatOpenAI(
            azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT", model),
            openai_api_version=os.environ.get("OPENAI_API_VERSION", "2024-02-01"),  # type: ignore[call-arg]
        )
    return ChatOpenAI(model=model)


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


def _verification_feedback_suffix(state: CompilerState) -> str:
    feedback = state.get("verification_feedback", "")
    if not feedback:
        return ""
    iteration = state.get("verification_iteration", 0)
    return (
        f"\n\nNOTE — Verification attempt {iteration} failed.\n"
        f"Verification feedback:\n{feedback}\n"
        "Regenerate the document so the issues above are resolved."
    )


def _log_verification_metrics(result: VerificationResult, attempt: int) -> None:
    if mlflow.active_run() is None:
        return
    mlflow.log_metric("verification_attempt", attempt)
    mlflow.log_metric("verification_pass", 1 if result.approved else 0)
    if result.score is not None:
        mlflow.log_metric("verification_score", result.score)


def _get_related_content(related_docs: list[str], converted_files: dict[str, str]) -> str:
    """Match related_docs (source paths) to converted_files keys (work-relative .md paths)."""
    parts: list[str] = []
    for doc_path in related_docs:
        for work_key, text in converted_files.items():
            # work_key is like "subdir/foo.pdf.md"; strip the trailing .md to get source rel path
            src_rel = work_key[: -len(".md")] if work_key.endswith(".md") else work_key
            if src_rel == doc_path or src_rel.endswith(doc_path) or work_key == doc_path:
                parts.append(f"=== {doc_path} ===\n{text[:4000]}")
                break
    return "\n\n".join(parts) if parts else "(no related content found)"


def analyze_docs_node(state: CompilerState) -> dict:
    """LLM-analyzes each converted document to extract topics and metadata."""
    model = state["model"]
    llm = _get_llm(model).with_structured_output(FileAnalysis)
    analysis: dict[str, FileAnalysis] = {}
    errors: list[str] = []
    suffix = _feedback_suffix(state)

    for path, text in state["converted_files"].items():
        try:
            result = llm.invoke(
                [
                    SystemMessage(ANALYZE_SYSTEM),
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
    llm = _get_llm(model).with_structured_output(ProposalsMap)

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
                SystemMessage(PLAN_SYSTEM),
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
    llm = _get_llm(model).with_structured_output(JudgementResult)

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
                SystemMessage(JUDGE_SYSTEM),
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


def generate_policies_node(state: CompilerState) -> dict:
    """Generate XDRS policy documents for each proposed policy."""
    proposals = state.get("proposals")
    if not proposals or not proposals.proposed_policies:
        return {"generated": [], "errors": []}

    model = state["model"]
    scope = state["scope"]
    llm = _get_llm(model)
    generated: list[GeneratedDoc] = []
    errors: list[str] = []
    verification_suffix = _verification_feedback_suffix(state)

    for idx, (title, proposal) in enumerate(proposals.proposed_policies.items(), start=1):
        try:
            related_content = _get_related_content(proposal.related_docs, state["converted_files"])
            prompt = (
                f"Scope: '{scope}'\n"
                f"Policy title: {title}\n"
                f"Abstract: {proposal.abstract}\n"
                f"Policy number: {idx:03d}\n\n"
                f"Related document content:\n{related_content}{verification_suffix}"
            )
            resp = llm.invoke([SystemMessage(POLICY_SYSTEM), HumanMessage(prompt)])
            content = resp.content if hasattr(resp, "content") else str(resp)
            generated.append(
                GeneratedDoc(
                    output_path=f"adrs/application/{idx:03d}-{title}.md",
                    content=str(content),
                    related_input_files=proposal.related_docs,
                    doc_type="policy",
                )
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"generate_policy/{title}: {exc}")

    return {"generated": generated, "errors": errors}


def generate_skills_node(state: CompilerState) -> dict:
    """Generate XDRS skill documents for each proposed skill."""
    # Always carry forward previously generated policies
    existing: list[GeneratedDoc] = list(state.get("generated") or [])

    proposals = state.get("proposals")
    if not proposals or not proposals.proposed_skills:
        return {"generated": existing, "errors": []}

    model = state["model"]
    scope = state["scope"]
    llm = _get_llm(model)
    generated: list[GeneratedDoc] = list(existing)
    errors: list[str] = []
    verification_suffix = _verification_feedback_suffix(state)

    for idx, (title, proposal) in enumerate(proposals.proposed_skills.items(), start=1):
        try:
            related_content = _get_related_content(proposal.related_docs, state["converted_files"])
            prompt = (
                f"Scope: '{scope}'\n"
                f"Skill title: {title}\n"
                f"Abstract: {proposal.abstract}\n"
                f"Skill number: {idx:03d}\n\n"
                f"Related document content:\n{related_content}{verification_suffix}"
            )
            resp = llm.invoke([SystemMessage(SKILL_SYSTEM), HumanMessage(prompt)])
            content = resp.content if hasattr(resp, "content") else str(resp)
            generated.append(
                GeneratedDoc(
                    output_path=f"edrs/application/skills/{idx:03d}-{title}/SKILL.md",
                    content=str(content),
                    related_input_files=proposal.related_docs,
                    doc_type="skill",
                )
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"generate_skill/{title}: {exc}")

    return {"generated": generated, "errors": errors}


def review_node(state: CompilerState) -> dict:
    """LLM reviews each generated document and returns an improved version."""
    model = state["model"]
    scope = state["scope"]
    llm = _get_llm(model)
    reviewed: list[GeneratedDoc] = []
    errors: list[str] = []

    for doc in state.get("generated") or []:
        try:
            prompt = (
                f"Scope: {scope}\n"
                f"Document type: {doc.doc_type}\n"
                f"Output path: {doc.output_path}\n\n"
                f"Document content to review:\n{doc.content}"
            )
            resp = llm.invoke(
                [SystemMessage(REVIEW_SYSTEM.format(scope=scope)), HumanMessage(prompt)]
            )
            reviewed_content = resp.content if hasattr(resp, "content") else str(resp)
            reviewed.append(doc.model_copy(update={"content": str(reviewed_content)}))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"review/{doc.output_path}: {exc}")
            reviewed.append(doc)  # keep original on review failure

    return {"generated": reviewed, "errors": errors}


def verify_output_node(state: CompilerState) -> dict:
    """Verify reviewed documents before they are written to disk."""
    docs = state.get("generated") or []
    if not docs:
        result = VerificationResult(
            approved=False,
            reason="No documents were generated for verification.",
            feedback="Generate at least one valid document before verification.",
        )
        new_iteration = state.get("verification_iteration", 0) + 1
        _log_verification_metrics(result, new_iteration)
        return {
            "verification_passed": False,
            "verification_feedback": result.feedback,
            "verification_iteration": new_iteration,
            "errors": ["verify_output: no generated documents to verify"],
        }

    model = state["model"]
    llm = _get_llm(model).with_structured_output(VerificationResult)
    new_iteration = state.get("verification_iteration", 0) + 1
    docs_text = "\n\n".join(
        (
            f"Output path: {doc.output_path}\n"
            f"Document type: {doc.doc_type}\n"
            f"Related source files: {', '.join(doc.related_input_files) or 'none'}\n"
            f"Content:\n{doc.content[:6000]}"
        )
        for doc in docs
    )

    try:
        invoke_result = llm.invoke(
            [
                SystemMessage(VERIFY_SYSTEM),
                HumanMessage(f"Verify this generated document batch:\n\n{docs_text}"),
            ]
        )
        result = VerificationResult.model_validate(invoke_result)
    except Exception as exc:  # noqa: BLE001
        result = VerificationResult(
            approved=False,
            reason=f"Verification call failed: {exc}",
            feedback="Retry generation with clearer, more complete XDRS documents.",
        )

    _log_verification_metrics(result, new_iteration)

    errors: list[str] = []
    if not result.approved and new_iteration >= 2:
        errors.append(f"verify_output: {result.reason or 'verification failed after retry limit'}")

    return {
        "verification_passed": result.approved,
        "verification_feedback": "" if result.approved else result.feedback,
        "verification_iteration": new_iteration,
        "errors": errors,
    }
