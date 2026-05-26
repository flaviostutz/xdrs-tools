from unittest.mock import MagicMock, patch

from xdrs_compiler.pipeline.analysis import analyze_docs_node, judge_node, plan_xdrs_node
from xdrs_compiler.pipeline.state import (
    FileAnalysis,
    JudgementResult,
    PolicyProposal,
    ProposalsMap,
    SkillProposal,
)

_RICH_TEXT = "This document has rich content about policies and procedures " * 5


def _make_state(**overrides: object) -> dict:
    base: dict = {
        "model": "gpt-4o-mini",
        "converted_files": {"doc.pdf.md": _RICH_TEXT},
        "analysis": {},
        "proposals": ProposalsMap(),
        "analysis_iteration": 0,
        "judge_approved": False,
        "judge_feedback": "",
        "errors": [],
    }
    base.update(overrides)
    return base


class TestAnalyzeDocsNode:
    def test_returns_analysis_per_doc(self) -> None:
        expected = FileAnalysis(
            date="2024-01-01",
            abstract="Policy about call center",
            topic_policies=["expected behavior while on call"],
            topic_skills=["how to handle angry customers"],
        )
        with patch("xdrs_compiler.pipeline.analysis.ChatOpenAI") as mock_cls:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = expected
            mock_cls.return_value.with_structured_output.return_value = mock_llm
            result = analyze_docs_node(_make_state())  # type: ignore[arg-type]

        assert "doc.pdf.md" in result["analysis"]
        assert result["analysis"]["doc.pdf.md"].abstract == "Policy about call center"

    def test_records_error_on_llm_failure(self) -> None:
        with patch("xdrs_compiler.pipeline.analysis.ChatOpenAI") as mock_cls:
            mock_llm = MagicMock()
            mock_llm.invoke.side_effect = RuntimeError("LLM unavailable")
            mock_cls.return_value.with_structured_output.return_value = mock_llm
            result = analyze_docs_node(_make_state())  # type: ignore[arg-type]

        assert len(result["errors"]) == 1
        assert "LLM unavailable" in result["errors"][0]

    def test_handles_empty_converted_files(self) -> None:
        with patch("xdrs_compiler.pipeline.analysis.ChatOpenAI"):
            result = analyze_docs_node(_make_state(converted_files={}))  # type: ignore[arg-type]
        assert result["analysis"] == {}


class TestPlanXdrsNode:
    def _make_state_with_analysis(self) -> dict:
        return _make_state(
            analysis={
                "doc.pdf.md": FileAnalysis(
                    abstract="Call center procedures",
                    topic_policies=["required behavior on calls"],
                    topic_skills=["step-by-step call handling"],
                )
            }
        )

    def test_returns_proposals_map(self) -> None:
        expected = ProposalsMap(
            proposed_policies={
                "call-center-behavior": PolicyProposal(
                    abstract="Defines expected behavior",
                    related_docs=["doc.pdf.md"],
                )
            },
            proposed_skills={
                "call-handling-procedure": SkillProposal(
                    abstract="Steps to handle customer calls",
                    related_docs=["doc.pdf.md"],
                )
            },
        )
        with patch("xdrs_compiler.pipeline.analysis.ChatOpenAI") as mock_cls:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = expected
            mock_cls.return_value.with_structured_output.return_value = mock_llm
            result = plan_xdrs_node(self._make_state_with_analysis())  # type: ignore[arg-type]

        assert "call-center-behavior" in result["proposals"].proposed_policies
        assert "call-handling-procedure" in result["proposals"].proposed_skills

    def test_returns_empty_proposals_on_empty_analysis(self) -> None:
        with patch("xdrs_compiler.pipeline.analysis.ChatOpenAI"):
            result = plan_xdrs_node(_make_state(analysis={}))  # type: ignore[arg-type]
        assert result["proposals"] == ProposalsMap()

    def test_records_error_on_llm_failure(self) -> None:
        with patch("xdrs_compiler.pipeline.analysis.ChatOpenAI") as mock_cls:
            mock_llm = MagicMock()
            mock_llm.invoke.side_effect = RuntimeError("timeout")
            mock_cls.return_value.with_structured_output.return_value = mock_llm
            result = plan_xdrs_node(self._make_state_with_analysis())  # type: ignore[arg-type]
        assert any("timeout" in e for e in result["errors"])


class TestJudgeNode:
    def _make_judge_state(self, approved: bool = True, **overrides: object) -> dict:
        proposals = ProposalsMap(
            proposed_policies={
                "call-center-behavior": PolicyProposal(
                    abstract="Expected behavior on calls",
                    related_docs=["doc.pdf.md"],
                )
            },
            proposed_skills={},
        )
        analysis = {
            "doc.pdf.md": FileAnalysis(
                abstract="Call center doc",
                topic_policies=["required behavior on calls"],
            )
        }
        base = _make_state(proposals=proposals, analysis=analysis)
        base.update(overrides)
        return base

    def test_returns_approved_true(self) -> None:
        expected = JudgementResult(approved=True, issues=[], feedback="")
        with patch("xdrs_compiler.pipeline.analysis.ChatOpenAI") as mock_cls:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = expected
            mock_cls.return_value.with_structured_output.return_value = mock_llm
            result = judge_node(self._make_judge_state())  # type: ignore[arg-type]

        assert result["judge_approved"] is True
        assert result["judge_feedback"] == ""

    def test_returns_rejected_with_feedback(self) -> None:
        expected = JudgementResult(
            approved=False,
            issues=["duplicate policies detected"],
            feedback="Merge overlapping policies into one.",
        )
        with patch("xdrs_compiler.pipeline.analysis.ChatOpenAI") as mock_cls:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = expected
            mock_cls.return_value.with_structured_output.return_value = mock_llm
            result = judge_node(self._make_judge_state())  # type: ignore[arg-type]

        assert result["judge_approved"] is False
        assert result["judge_feedback"] == "Merge overlapping policies into one."

    def test_increments_iteration_counter(self) -> None:
        expected = JudgementResult(approved=True)
        with patch("xdrs_compiler.pipeline.analysis.ChatOpenAI") as mock_cls:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = expected
            mock_cls.return_value.with_structured_output.return_value = mock_llm
            result = judge_node(self._make_judge_state(analysis_iteration=0))  # type: ignore[arg-type]

        assert result["analysis_iteration"] == 1

    def test_approves_on_llm_failure_to_not_block_pipeline(self) -> None:
        with patch("xdrs_compiler.pipeline.analysis.ChatOpenAI") as mock_cls:
            mock_llm = MagicMock()
            mock_llm.invoke.side_effect = RuntimeError("judge unreachable")
            mock_cls.return_value.with_structured_output.return_value = mock_llm
            result = judge_node(self._make_judge_state())  # type: ignore[arg-type]

        assert result["judge_approved"] is True
        assert len(result["errors"]) == 1

    def test_feedback_injected_into_analyze_docs_on_rerun(self) -> None:
        """Verify that judge_feedback appears in the LLM prompt on a re-run."""
        from langchain_core.messages import HumanMessage

        captured_messages: list = []

        def fake_invoke(messages: list) -> FileAnalysis:
            captured_messages.extend(messages)
            return FileAnalysis(abstract="improved", topic_policies=["policy"])

        with patch("xdrs_compiler.pipeline.analysis.ChatOpenAI") as mock_cls:
            mock_llm = MagicMock()
            mock_llm.invoke.side_effect = fake_invoke
            mock_cls.return_value.with_structured_output.return_value = mock_llm
            analyze_docs_node(  # type: ignore[arg-type]
                _make_state(  # type: ignore[arg-type]
                    judge_feedback="Merge overlapping policies.",
                    analysis_iteration=1,
                )
            )

        human_msg_content = next(
            str(m.content) for m in captured_messages if isinstance(m, HumanMessage)
        )
        assert "Merge overlapping policies" in human_msg_content
