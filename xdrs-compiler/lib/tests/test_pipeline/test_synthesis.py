from pathlib import Path
from unittest.mock import MagicMock, patch

from xdrs_compiler.pipeline.state import (
    GeneratedDoc,
    PolicyProposal,
    ProposalsMap,
    SkillProposal,
)
from xdrs_compiler.pipeline.synthesis import (
    generate_policies_node,
    generate_skills_node,
    review_node,
    write_output_node,
)

_POLICY_CONTENT = "---\nname: test-adr-policy-001-example\n---\n# Example Policy\n"
_SKILL_CONTENT = "---\nname: test-edr-skill-001-example\n---\n## Overview\n"


def _base_state(tmp_path: Path) -> dict:
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


def _mock_llm_response(content: str) -> MagicMock:
    resp = MagicMock()
    resp.content = content
    return resp


class TestGeneratePoliciesNode:
    def test_generates_one_policy_per_proposal(self, tmp_path: Path) -> None:
        with patch("xdrs_compiler.pipeline.synthesis.ChatOpenAI") as mock_cls:
            mock_cls.return_value.invoke.return_value = _mock_llm_response(_POLICY_CONTENT)
            result = generate_policies_node(_base_state(tmp_path))  # type: ignore[arg-type]

        assert len(result["generated"]) == 1
        doc = result["generated"][0]
        assert doc.doc_type == "policy"
        assert "call-center-behavior" in doc.output_path
        assert doc.content == _POLICY_CONTENT

    def test_records_error_on_llm_failure(self, tmp_path: Path) -> None:
        with patch("xdrs_compiler.pipeline.synthesis.ChatOpenAI") as mock_cls:
            mock_cls.return_value.invoke.side_effect = RuntimeError("LLM error")
            result = generate_policies_node(_base_state(tmp_path))  # type: ignore[arg-type]

        assert len(result["generated"]) == 0
        assert len(result["errors"]) == 1

    def test_returns_empty_on_no_proposals(self, tmp_path: Path) -> None:
        state = {**_base_state(tmp_path), "proposals": ProposalsMap()}
        result = generate_policies_node(state)  # type: ignore[arg-type]
        assert result["generated"] == []


class TestGenerateSkillsNode:
    def test_generates_one_skill_per_proposal(self, tmp_path: Path) -> None:
        state = {
            **_base_state(tmp_path),
            "generated": [
                GeneratedDoc(
                    output_path="adrs/application/001-call-center-behavior.md",
                    content=_POLICY_CONTENT,
                    related_input_files=["presentation.pdf.md"],
                    doc_type="policy",
                )
            ],
        }
        with patch("xdrs_compiler.pipeline.synthesis.ChatOpenAI") as mock_cls:
            mock_cls.return_value.invoke.return_value = _mock_llm_response(_SKILL_CONTENT)
            result = generate_skills_node(state)  # type: ignore[arg-type]

        assert len(result["generated"]) == 2  # 1 policy (carried forward) + 1 skill
        skill = next(d for d in result["generated"] if d.doc_type == "skill")
        assert "call-handling-procedure" in skill.output_path
        assert "SKILL.md" in skill.output_path

    def test_carries_forward_existing_generated(self, tmp_path: Path) -> None:
        existing_doc = GeneratedDoc(
            output_path="adrs/application/001-foo.md",
            content="policy",
            related_input_files=[],
            doc_type="policy",
        )
        state = {**_base_state(tmp_path), "generated": [existing_doc], "proposals": ProposalsMap()}
        result = generate_skills_node(state)  # type: ignore[arg-type]
        assert len(result["generated"]) == 1  # existing doc preserved
        assert result["generated"][0].output_path == existing_doc.output_path


class TestReviewNode:
    def test_review_updates_content(self, tmp_path: Path) -> None:
        doc = GeneratedDoc(
            output_path="adrs/application/001-test.md",
            content="original content",
            related_input_files=[],
            doc_type="policy",
        )
        state = {
            **_base_state(tmp_path),
            "generated": [doc],
        }
        reviewed_content = "---\nname: testscope-adr-policy-001-test\n---\n# Improved"
        with patch("xdrs_compiler.pipeline.synthesis.ChatOpenAI") as mock_cls:
            mock_cls.return_value.invoke.return_value = _mock_llm_response(reviewed_content)
            result = review_node(state)  # type: ignore[arg-type]

        assert result["generated"][0].content == reviewed_content

    def test_keeps_original_on_review_failure(self, tmp_path: Path) -> None:
        doc = GeneratedDoc(
            output_path="adrs/application/001-test.md",
            content="original content",
            related_input_files=[],
            doc_type="policy",
        )
        state = {**_base_state(tmp_path), "generated": [doc]}
        with patch("xdrs_compiler.pipeline.synthesis.ChatOpenAI") as mock_cls:
            mock_cls.return_value.invoke.side_effect = RuntimeError("review failed")
            result = review_node(state)  # type: ignore[arg-type]

        assert result["generated"][0].content == "original content"
        assert len(result["errors"]) == 1


class TestWriteOutputNode:
    def test_writes_files_to_xdrs_root(self, tmp_path: Path) -> None:
        doc = GeneratedDoc(
            output_path="adrs/application/001-test.md",
            content="# Test Policy",
            related_input_files=[],
            doc_type="policy",
        )
        state = {**_base_state(tmp_path), "generated": [doc]}
        write_output_node(state)  # type: ignore[arg-type]

        expected = tmp_path / ".xdrs" / "testscope" / "adrs" / "application" / "001-test.md"
        assert expected.exists()
        assert expected.read_text(encoding="utf-8") == "# Test Policy"

    def test_records_error_on_write_failure(self, tmp_path: Path) -> None:
        doc = GeneratedDoc(
            output_path="adrs/application/001-test.md",
            content="# Policy",
            related_input_files=[],
            doc_type="policy",
        )
        state = {**_base_state(tmp_path), "generated": [doc]}
        with patch("pathlib.Path.write_text", side_effect=OSError("no space")):
            result = write_output_node(state)  # type: ignore[arg-type]

        assert len(result["errors"]) == 1
