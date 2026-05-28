from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage

from xdrs_compiler.workflows.compile.agents import analyze_docs_node, judge_node, plan_xdrs_node
from xdrs_compiler.workflows.compile.states import (
    FileAnalysis,
    JudgementResult,
    PolicyProposal,
    ProposalsMap,
    SkillProposal,
    VerificationResult,
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
        "verification_iteration": 0,
        "verification_passed": False,
        "verification_feedback": "",
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
        with patch("xdrs_compiler.workflows.compile.agents.ChatOpenAI") as mock_cls:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = expected
            mock_cls.return_value.with_structured_output.return_value = mock_llm
            result = analyze_docs_node(_make_state())  # type: ignore[arg-type]

        assert "doc.pdf.md" in result["analysis"]
        assert result["analysis"]["doc.pdf.md"].abstract == "Policy about call center"

    def test_records_error_on_llm_failure(self) -> None:
        with patch("xdrs_compiler.workflows.compile.agents.ChatOpenAI") as mock_cls:
            mock_llm = MagicMock()
            mock_llm.invoke.side_effect = RuntimeError("LLM unavailable")
            mock_cls.return_value.with_structured_output.return_value = mock_llm
            result = analyze_docs_node(_make_state())  # type: ignore[arg-type]

        assert len(result["errors"]) == 1
        assert "LLM unavailable" in result["errors"][0]

    def test_handles_empty_converted_files(self) -> None:
        with patch("xdrs_compiler.workflows.compile.agents.ChatOpenAI"):
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
        with patch("xdrs_compiler.workflows.compile.agents.ChatOpenAI") as mock_cls:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = expected
            mock_cls.return_value.with_structured_output.return_value = mock_llm
            result = plan_xdrs_node(self._make_state_with_analysis())  # type: ignore[arg-type]

        assert "call-center-behavior" in result["proposals"].proposed_policies
        assert "call-handling-procedure" in result["proposals"].proposed_skills

    def test_returns_empty_proposals_on_empty_analysis(self) -> None:
        with patch("xdrs_compiler.workflows.compile.agents.ChatOpenAI"):
            result = plan_xdrs_node(_make_state(analysis={}))  # type: ignore[arg-type]
        assert result["proposals"] == ProposalsMap()

    def test_records_error_on_llm_failure(self) -> None:
        with patch("xdrs_compiler.workflows.compile.agents.ChatOpenAI") as mock_cls:
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
        with patch("xdrs_compiler.workflows.compile.agents.ChatOpenAI") as mock_cls:
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
        with patch("xdrs_compiler.workflows.compile.agents.ChatOpenAI") as mock_cls:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = expected
            mock_cls.return_value.with_structured_output.return_value = mock_llm
            result = judge_node(self._make_judge_state())  # type: ignore[arg-type]

        assert result["judge_approved"] is False
        assert result["judge_feedback"] == "Merge overlapping policies into one."

    def test_increments_iteration_counter(self) -> None:
        expected = JudgementResult(approved=True)
        with patch("xdrs_compiler.workflows.compile.agents.ChatOpenAI") as mock_cls:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = expected
            mock_cls.return_value.with_structured_output.return_value = mock_llm
            result = judge_node(self._make_judge_state(analysis_iteration=0))  # type: ignore[arg-type]

        assert result["analysis_iteration"] == 1

    def test_approves_on_llm_failure_to_not_block_pipeline(self) -> None:
        with patch("xdrs_compiler.workflows.compile.agents.ChatOpenAI") as mock_cls:
            mock_llm = MagicMock()
            mock_llm.invoke.side_effect = RuntimeError("judge unreachable")
            mock_cls.return_value.with_structured_output.return_value = mock_llm
            result = judge_node(self._make_judge_state())  # type: ignore[arg-type]

        assert result["judge_approved"] is True
        assert len(result["errors"]) == 1

    def test_feedback_injected_into_analyze_docs_on_rerun(self) -> None:
        """Verify that judge_feedback appears in the LLM prompt on a re-run."""
        captured_messages: list = []

        def fake_invoke(messages: list) -> FileAnalysis:
            captured_messages.extend(messages)
            return FileAnalysis(abstract="improved", topic_policies=["policy"])

        with patch("xdrs_compiler.workflows.compile.agents.ChatOpenAI") as mock_cls:
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


class TestGeneratePoliciesNode:
    from xdrs_compiler.workflows.compile.agents import generate_policies_node

    def _base_state(self, tmp_path) -> dict:  # type: ignore[no-untyped-def]
        from xdrs_compiler.workflows.compile.states import (
            PolicyProposal,
            ProposalsMap,
            SkillProposal,
        )

        return {
            "model": "gpt-4o-mini",
            "scope": "testscope",
            "xdrs_root": str(tmp_path / ".xdrs"),
            "converted_files": {"presentation.pdf.md": "content about call center behavior " * 20},
            "proposals": ProposalsMap(
                proposed_policies={
                    "call-center-behavior": PolicyProposal(
                        abstract="Expected behavior on calls",
                        related_docs=["presentation.pdf.md"],
                    )
                },
                proposed_skills={
                    "call-handling-procedure": SkillProposal(
                        abstract="Steps to handle calls",
                        related_docs=["presentation.pdf.md"],
                    )
                },
            ),
            "generated": [],
            "errors": [],
        }

    def test_generates_one_policy_per_proposal(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        from unittest.mock import MagicMock, patch

        from xdrs_compiler.workflows.compile.agents import generate_policies_node

        def _mock_llm_response(content: str) -> MagicMock:
            resp = MagicMock()
            resp.content = content
            return resp

        _POLICY_CONTENT = "---\nname: test-adr-policy-001-example\n---\n# Example Policy\n"
        with patch("xdrs_compiler.workflows.compile.agents.ChatOpenAI") as mock_cls:
            mock_cls.return_value.invoke.return_value = _mock_llm_response(_POLICY_CONTENT)
            result = generate_policies_node(self._base_state(tmp_path))  # type: ignore[arg-type]

        assert len(result["generated"]) == 1
        doc = result["generated"][0]
        assert doc.doc_type == "policy"
        assert "call-center-behavior" in doc.output_path
        assert doc.content == _POLICY_CONTENT

    def test_records_error_on_llm_failure(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        from xdrs_compiler.workflows.compile.agents import generate_policies_node

        with patch("xdrs_compiler.workflows.compile.agents.ChatOpenAI") as mock_cls:
            mock_cls.return_value.invoke.side_effect = RuntimeError("LLM error")
            result = generate_policies_node(self._base_state(tmp_path))  # type: ignore[arg-type]

        assert len(result["generated"]) == 0
        assert len(result["errors"]) == 1

    def test_returns_empty_on_no_proposals(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        from xdrs_compiler.workflows.compile.agents import generate_policies_node
        from xdrs_compiler.workflows.compile.states import ProposalsMap

        state = {**self._base_state(tmp_path), "proposals": ProposalsMap()}
        result = generate_policies_node(state)  # type: ignore[arg-type]
        assert result["generated"] == []


class TestGenerateSkillsNode:
    def _base_state(self, tmp_path) -> dict:  # type: ignore[no-untyped-def]
        from xdrs_compiler.workflows.compile.states import (
            PolicyProposal,
            ProposalsMap,
            SkillProposal,
        )

        return {
            "model": "gpt-4o-mini",
            "scope": "testscope",
            "xdrs_root": str(tmp_path / ".xdrs"),
            "converted_files": {"presentation.pdf.md": "content about call center behavior " * 20},
            "proposals": ProposalsMap(
                proposed_policies={
                    "call-center-behavior": PolicyProposal(
                        abstract="Expected behavior on calls",
                        related_docs=["presentation.pdf.md"],
                    )
                },
                proposed_skills={
                    "call-handling-procedure": SkillProposal(
                        abstract="Steps to handle calls",
                        related_docs=["presentation.pdf.md"],
                    )
                },
            ),
            "generated": [],
            "errors": [],
        }

    def test_generates_one_skill_per_proposal(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        from xdrs_compiler.workflows.compile.agents import generate_skills_node
        from xdrs_compiler.workflows.compile.states import GeneratedDoc

        _POLICY_CONTENT = "---\nname: test-adr-policy-001-example\n---\n# Example Policy\n"
        _SKILL_CONTENT = "---\nname: test-edr-skill-001-example\n---\n## Overview\n"

        def _mock_llm_response(content: str) -> MagicMock:
            resp = MagicMock()
            resp.content = content
            return resp

        state = {
            **self._base_state(tmp_path),
            "generated": [
                GeneratedDoc(
                    output_path="adrs/application/001-call-center-behavior.md",
                    content=_POLICY_CONTENT,
                    related_input_files=["presentation.pdf.md"],
                    doc_type="policy",
                )
            ],
        }
        with patch("xdrs_compiler.workflows.compile.agents.ChatOpenAI") as mock_cls:
            mock_cls.return_value.invoke.return_value = _mock_llm_response(_SKILL_CONTENT)
            result = generate_skills_node(state)  # type: ignore[arg-type]

        assert len(result["generated"]) == 2  # 1 policy (carried forward) + 1 skill
        skill = next(d for d in result["generated"] if d.doc_type == "skill")
        assert "call-handling-procedure" in skill.output_path
        assert "SKILL.md" in skill.output_path

    def test_carries_forward_existing_generated(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        from xdrs_compiler.workflows.compile.agents import generate_skills_node
        from xdrs_compiler.workflows.compile.states import GeneratedDoc, ProposalsMap

        existing_doc = GeneratedDoc(
            output_path="adrs/application/001-foo.md",
            content="policy",
            related_input_files=[],
            doc_type="policy",
        )
        state = {
            **self._base_state(tmp_path),
            "generated": [existing_doc],
            "proposals": ProposalsMap(),
        }
        result = generate_skills_node(state)  # type: ignore[arg-type]
        assert len(result["generated"]) == 1  # existing doc preserved
        assert result["generated"][0].output_path == existing_doc.output_path


class TestReviewNode:
    def _base_state(self, tmp_path) -> dict:  # type: ignore[no-untyped-def]
        from xdrs_compiler.workflows.compile.states import ProposalsMap

        return {
            "model": "gpt-4o-mini",
            "scope": "testscope",
            "xdrs_root": str(tmp_path / ".xdrs"),
            "converted_files": {},
            "proposals": ProposalsMap(),
            "generated": [],
            "errors": [],
        }

    def test_review_updates_content(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        from xdrs_compiler.workflows.compile.agents import review_node
        from xdrs_compiler.workflows.compile.states import GeneratedDoc

        doc = GeneratedDoc(
            output_path="adrs/application/001-test.md",
            content="original content",
            related_input_files=[],
            doc_type="policy",
        )
        state = {**self._base_state(tmp_path), "generated": [doc]}
        reviewed_content = "---\nname: testscope-adr-policy-001-test\n---\n# Improved"

        def _mock_llm_response(content: str) -> MagicMock:
            resp = MagicMock()
            resp.content = content
            return resp

        with patch("xdrs_compiler.workflows.compile.agents.ChatOpenAI") as mock_cls:
            mock_cls.return_value.invoke.return_value = _mock_llm_response(reviewed_content)
            result = review_node(state)  # type: ignore[arg-type]

        assert result["generated"][0].content == reviewed_content

    def test_keeps_original_on_review_failure(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        from xdrs_compiler.workflows.compile.agents import review_node
        from xdrs_compiler.workflows.compile.states import GeneratedDoc

        doc = GeneratedDoc(
            output_path="adrs/application/001-test.md",
            content="original content",
            related_input_files=[],
            doc_type="policy",
        )
        state = {**self._base_state(tmp_path), "generated": [doc]}
        with patch("xdrs_compiler.workflows.compile.agents.ChatOpenAI") as mock_cls:
            mock_cls.return_value.invoke.side_effect = RuntimeError("review failed")
            result = review_node(state)  # type: ignore[arg-type]

        assert result["generated"][0].content == "original content"
        assert len(result["errors"]) == 1


class TestVerifyOutputNode:
    def _base_state(self, tmp_path) -> dict:  # type: ignore[no-untyped-def]
        from xdrs_compiler.workflows.compile.states import GeneratedDoc, ProposalsMap

        return {
            "model": "gpt-4o-mini",
            "scope": "testscope",
            "xdrs_root": str(tmp_path / ".xdrs"),
            "converted_files": {},
            "proposals": ProposalsMap(),
            "generated": [
                GeneratedDoc(
                    output_path="adrs/application/001-test.md",
                    content="# Policy",
                    related_input_files=["doc.md"],
                    doc_type="policy",
                )
            ],
            "verification_iteration": 0,
            "verification_feedback": "",
            "errors": [],
        }

    def test_verification_passes_when_llm_approves(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        from xdrs_compiler.workflows.compile.agents import verify_output_node

        with patch("xdrs_compiler.workflows.compile.agents.ChatOpenAI") as mock_cls:
            verify_llm = MagicMock()
            verify_llm.invoke.return_value = VerificationResult(approved=True, score=1.0)
            mock_cls.return_value.with_structured_output.return_value = verify_llm
            result = verify_output_node(self._base_state(tmp_path))  # type: ignore[arg-type]

        assert result["verification_passed"] is True
        assert result["verification_iteration"] == 1

    def test_verification_requests_retry_on_failure(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        from xdrs_compiler.workflows.compile.agents import verify_output_node

        with patch("xdrs_compiler.workflows.compile.agents.ChatOpenAI") as mock_cls:
            verify_llm = MagicMock()
            verify_llm.invoke.return_value = VerificationResult(
                approved=False,
                reason="Missing required sections",
                feedback="Regenerate with complete sections.",
            )
            mock_cls.return_value.with_structured_output.return_value = verify_llm
            result = verify_output_node(self._base_state(tmp_path))  # type: ignore[arg-type]

        assert result["verification_passed"] is False
        assert result["verification_feedback"] == "Regenerate with complete sections."
        assert result["errors"] == []

    def test_verification_adds_error_at_retry_limit(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        from xdrs_compiler.workflows.compile.agents import verify_output_node

        state = {**self._base_state(tmp_path), "verification_iteration": 1}
        with patch("xdrs_compiler.workflows.compile.agents.ChatOpenAI") as mock_cls:
            verify_llm = MagicMock()
            verify_llm.invoke.return_value = VerificationResult(
                approved=False,
                reason="Still invalid",
                feedback="Retry with a valid draft.",
            )
            mock_cls.return_value.with_structured_output.return_value = verify_llm
            result = verify_output_node(state)  # type: ignore[arg-type]

        assert result["verification_iteration"] == 2
        assert result["errors"] == ["verify_output: Still invalid"]
