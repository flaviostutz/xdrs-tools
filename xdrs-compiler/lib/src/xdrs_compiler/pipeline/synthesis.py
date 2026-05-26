from __future__ import annotations

from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .state import CompilerState, GeneratedDoc

_POLICY_SYSTEM = """\
You are an expert at writing XDRS Policy documents. Write a complete, authoritative policy \
document using the mandatory format below.

FORMAT:
```
---
name: {scope}-adr-policy-{number:03d}-{kebab-title}
description: {one sentence: what the policy covers and when to apply it}
apply-to: All {scope} contexts
valid-from: {today ISO date}
---

# {scope}-adr-policy-{number:03d}: {Title}

## Context and Problem Statement

{Describe the situation, problem, or need this policy addresses.}

## Decision Outcome

**{Short statement of the decision made}**

{Detailed explanation of the decision and its rationale.}

### Details

- {Rule or constraint 1}
- {Rule or constraint 2}
...
```

Rules:
- Be authoritative and concise. Focus on the decision and constraints.
- Use valid-from date: today's date.
- Draw on all related document content provided.
- Output ONLY the policy document content, no extra text or markdown fences."""

_SKILL_SYSTEM = """\
You are an expert at writing XDRS Skill documents (agentskills format). Write a complete \
SKILL.md following the format below.

FORMAT:
```
---
name: {scope}-edr-skill-{number:03d}-{kebab-title}
description: >
  {What this skill does and when an agent should use it. Max 200 chars.}
---

## Overview

{Brief objective, expected outcome, and prerequisites.}

## Instructions

{Numbered step-by-step instructions. Each step self-contained and imperative.}

## Examples

{Concrete input/output examples illustrating correct behavior.}

## Edge Cases

{Known gotchas and how to handle them.}
```

Rules:
- Write steps imperatively. Each step must be self-contained and unambiguous.
- Include verification criteria at the end of Instructions.
- Draw on all related document content provided.
- Output ONLY the SKILL.md content, no extra text or markdown fences."""

_REVIEW_SYSTEM = """\
You are an XDRS document reviewer. Review the given document against XDRS standards and return \
an improved version that fixes any issues found. Make minimal changes — only fix real problems.

For POLICY documents verify:
- YAML frontmatter present with: name, description, apply-to, valid-from
- name format: {scope}-[adr|bdr|edr]-policy-[number]-[title]
- Sections present: "Context and Problem Statement", "Decision Outcome"
- Authoritative, concise language focused on the decision

For SKILL documents verify:
- YAML frontmatter present with: name, description
- name format: {scope}-[adr|bdr|edr]-skill-[number]-[title]
- Sections present: Overview, Instructions, Examples, Edge Cases
- Instructions are numbered and imperative

Return ONLY the corrected document content, no commentary."""


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


def generate_policies_node(state: CompilerState) -> dict:
    """Generate XDRS policy documents for each proposed policy."""
    proposals = state.get("proposals")
    if not proposals or not proposals.proposed_policies:
        return {"generated": [], "errors": []}

    model = state["model"]
    scope = state["scope"]
    llm = ChatOpenAI(model=model)
    generated: list[GeneratedDoc] = []
    errors: list[str] = []

    for idx, (title, proposal) in enumerate(proposals.proposed_policies.items(), start=1):
        try:
            related_content = _get_related_content(proposal.related_docs, state["converted_files"])
            prompt = (
                f"Scope: '{scope}'\n"
                f"Policy title: {title}\n"
                f"Abstract: {proposal.abstract}\n"
                f"Policy number: {idx:03d}\n\n"
                f"Related document content:\n{related_content}"
            )
            resp = llm.invoke([SystemMessage(_POLICY_SYSTEM), HumanMessage(prompt)])
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
    llm = ChatOpenAI(model=model)
    generated: list[GeneratedDoc] = list(existing)
    errors: list[str] = []

    for idx, (title, proposal) in enumerate(proposals.proposed_skills.items(), start=1):
        try:
            related_content = _get_related_content(proposal.related_docs, state["converted_files"])
            prompt = (
                f"Scope: '{scope}'\n"
                f"Skill title: {title}\n"
                f"Abstract: {proposal.abstract}\n"
                f"Skill number: {idx:03d}\n\n"
                f"Related document content:\n{related_content}"
            )
            resp = llm.invoke([SystemMessage(_SKILL_SYSTEM), HumanMessage(prompt)])
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
    llm = ChatOpenAI(model=model)
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
                [SystemMessage(_REVIEW_SYSTEM.format(scope=scope)), HumanMessage(prompt)]
            )
            reviewed_content = resp.content if hasattr(resp, "content") else str(resp)
            reviewed.append(doc.model_copy(update={"content": str(reviewed_content)}))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"review/{doc.output_path}: {exc}")
            reviewed.append(doc)  # keep original on review failure

    return {"generated": reviewed, "errors": errors}


def write_output_node(state: CompilerState) -> dict:
    """Write all reviewed documents to the xdrs_root/scope directory."""
    xdrs_root = Path(state["xdrs_root"])
    scope = state["scope"]
    errors: list[str] = []

    for doc in state.get("generated") or []:
        try:
            out_path = xdrs_root / scope / doc.output_path
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(doc.content, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"write/{doc.output_path}: {exc}")

    return {"errors": errors}
