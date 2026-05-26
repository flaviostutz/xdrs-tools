from pathlib import Path
from unittest.mock import MagicMock, patch

from xdrs_compiler.pipeline.graph import build_graph
from xdrs_compiler.pipeline.state import (
    FileAnalysis,
    JudgementResult,
    PolicyProposal,
    ProposalsMap,
    SkillProposal,
)


def _mock_analysis_llm(analysis: FileAnalysis) -> MagicMock:
    m = MagicMock()
    m.invoke.return_value = analysis
    return m


def _mock_proposals_llm(proposals: ProposalsMap) -> MagicMock:
    m = MagicMock()
    m.invoke.return_value = proposals
    return m


def _mock_text_llm(content: str) -> MagicMock:
    resp = MagicMock()
    resp.content = content
    m = MagicMock()
    m.invoke.return_value = resp
    return m


class TestBuildGraph:
    def test_graph_compiles_without_error(self) -> None:
        graph = build_graph()
        assert graph is not None

    def test_full_pipeline_end_to_end(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        src = tmp_path / "src"
        src.mkdir()
        (src / "doc.md").write_text(
            "This document has enough words to pass the filter and discuss policies. " * 3,
            encoding="utf-8",
        )

        fake_analysis = FileAnalysis(
            abstract="A doc about policies",
            topic_policies=["required safety checks"],
            topic_skills=["how to perform safety checks"],
        )
        fake_proposals = ProposalsMap(
            proposed_policies={
                "safety-checks": PolicyProposal(
                    abstract="Required safety checks before deployment",
                    related_docs=["doc.md.md"],
                )
            },
            proposed_skills={
                "safety-check-procedure": SkillProposal(
                    abstract="Steps to perform safety checks",
                    related_docs=["doc.md.md"],
                )
            },
        )

        with (
            patch("xdrs_compiler.pipeline.analysis.ChatOpenAI") as mock_analysis_cls,
            patch("xdrs_compiler.pipeline.synthesis.ChatOpenAI") as mock_synthesis_cls,
        ):
            # analyze_docs uses with_structured_output for FileAnalysis
            analysis_llm = MagicMock()
            analysis_llm.invoke.return_value = fake_analysis
            # plan_xdrs uses with_structured_output for ProposalsMap
            proposals_llm = MagicMock()
            proposals_llm.invoke.return_value = fake_proposals
            # judge node uses with_structured_output for JudgementResult — approve immediately
            judge_llm = MagicMock()
            judge_llm.invoke.return_value = JudgementResult(approved=True)

            def structured_output_side_effect(schema: type) -> MagicMock:
                if schema is FileAnalysis:
                    return analysis_llm
                if schema is JudgementResult:
                    return judge_llm
                return proposals_llm

            mock_analysis_cls.return_value.with_structured_output.side_effect = (
                structured_output_side_effect
            )

            # synthesis uses plain ChatOpenAI (no structured output)
            resp = MagicMock()
            resp.content = "---\nname: testscope-adr-policy-001-safety-checks\n---\n# Policy"
            mock_synthesis_cls.return_value.invoke.return_value = resp

            graph = build_graph()
            final_state = graph.invoke(
                {
                    "input_dir": str(src),
                    "xdrs_root": str(tmp_path / ".xdrs"),
                    "scope": "testscope",
                    "model": "gpt-4o-mini",
                    "work_dir": str(tmp_path / ".work"),
                    "source_files": [],
                    "converted_files": {},
                    "analysis": {},
                    "proposals": ProposalsMap(),
                    "analysis_iteration": 0,
                    "judge_approved": False,
                    "judge_feedback": "",
                    "generated": [],
                    "errors": [],
                }
            )

        assert isinstance(final_state["generated"], list)
        assert len(final_state["generated"]) >= 1
        # Report file should exist
        assert (tmp_path / ".xdrs-compiler.report").exists()
