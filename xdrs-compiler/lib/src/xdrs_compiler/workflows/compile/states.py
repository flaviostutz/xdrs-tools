from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from pydantic import BaseModel, Field


class FileAnalysis(BaseModel):
    """Per-document analysis output from the LLM."""

    date: str | None = None
    abstract: str = ""
    topic_policies: list[str] = Field(default_factory=list)
    topic_skills: list[str] = Field(default_factory=list)


class PolicyProposal(BaseModel):
    abstract: str = ""
    related_docs: list[str] = Field(default_factory=list)


class SkillProposal(BaseModel):
    abstract: str = ""
    related_docs: list[str] = Field(default_factory=list)


class ProposalsMap(BaseModel):
    proposed_policies: dict[str, PolicyProposal] = Field(default_factory=dict)
    proposed_skills: dict[str, SkillProposal] = Field(default_factory=dict)


class JudgementResult(BaseModel):
    """Output of the analysis judge."""

    approved: bool
    issues: list[str] = Field(default_factory=list)
    feedback: str = ""  # guidance for the next iteration when not approved


class VerificationResult(BaseModel):
    """Output of the synthesis verification node."""

    approved: bool
    score: float | None = None
    reason: str = ""
    feedback: str = ""


class GeneratedDoc(BaseModel):
    output_path: str  # relative to {xdrs_root}/{scope}/
    content: str
    related_input_files: list[str]
    doc_type: str  # "policy" or "skill"


class CompilerState(TypedDict):
    # Config fields (passed through unchanged)
    input_dir: str
    xdrs_root: str
    scope: str
    model: str
    work_dir: str
    # Phase 1: Preparation
    source_files: list[str]  # absolute paths as strings
    converted_files: dict[str, str]  # work-relative "foo.pdf.md" -> md text
    # Phase 2: Analysis (with judge loop, max 2 iterations)
    analysis: dict[str, FileAnalysis]
    proposals: ProposalsMap
    analysis_iteration: int  # incremented by judge each pass (0 → 1 → 2)
    judge_approved: bool  # True when judge accepts the proposals
    judge_feedback: str  # guidance from judge for the next re-analysis
    # Phase 3: Synthesis + output
    verification_iteration: int
    verification_passed: bool
    verification_feedback: str
    generated: list[GeneratedDoc]
    written_output_paths: list[str]
    # Accumulates across all nodes via operator.add
    errors: Annotated[list[str], operator.add]
