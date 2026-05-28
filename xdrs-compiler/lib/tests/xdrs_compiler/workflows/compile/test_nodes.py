import json
from pathlib import Path
from unittest.mock import patch

import pytest

from xdrs_compiler.workflows.compile.nodes import (
    REPORT_FILENAME,
    SUPPORTED_EXTENSIONS,
    conversion_node,
    discovery_node,
    filter_node,
    report_node,
    write_output_node,
)
from xdrs_compiler.workflows.compile.states import GeneratedDoc


@pytest.fixture()
def base_state(tmp_path: Path) -> dict:
    src = tmp_path / "src"
    src.mkdir()
    (src / "doc.md").write_text("# Hello\nThis is a document.", encoding="utf-8")
    (src / "notes.txt").write_text("Short.", encoding="utf-8")
    (src / "binary.bin").write_bytes(b"\x00\x01")
    return {
        "input_dir": str(src),
        "work_dir": str(tmp_path / ".work"),
        "source_files": [],
        "converted_files": {},
    }


class TestDiscoveryNode:
    def test_finds_supported_files(self, base_state: dict) -> None:
        result = discovery_node(base_state)  # type: ignore[arg-type]
        paths = result["source_files"]
        assert any("doc.md" in p for p in paths)
        assert any("notes.txt" in p for p in paths)

    def test_ignores_unsupported_files(self, base_state: dict) -> None:
        result = discovery_node(base_state)  # type: ignore[arg-type]
        assert not any("binary.bin" in p for p in result["source_files"])

    def test_supported_extensions_coverage(self) -> None:
        # Ensure well-known formats are covered
        for ext in (".md", ".pdf", ".docx", ".pptx", ".xlsx", ".html", ".txt"):
            assert ext in SUPPORTED_EXTENSIONS

    def test_returns_sorted_paths(self, base_state: dict) -> None:
        result = discovery_node(base_state)  # type: ignore[arg-type]
        paths = result["source_files"]
        assert paths == sorted(paths)


class TestConversionNode:
    def test_converts_md_file(self, base_state: dict, tmp_path: Path) -> None:
        src = Path(base_state["input_dir"])
        state = {**base_state, "source_files": [str(src / "doc.md")]}
        result = conversion_node(state)  # type: ignore[arg-type]
        assert "doc.md.md" in result["converted_files"]
        assert "Hello" in result["converted_files"]["doc.md.md"]

    def test_writes_work_file(self, base_state: dict, tmp_path: Path) -> None:
        src = Path(base_state["input_dir"])
        state = {**base_state, "source_files": [str(src / "doc.md")]}
        conversion_node(state)  # type: ignore[arg-type]
        work_path = tmp_path / ".work" / "doc.md.md"
        assert work_path.exists()

    def test_records_error_on_failure(self, base_state: dict) -> None:
        src = Path(base_state["input_dir"])
        state = {**base_state, "source_files": [str(src / "doc.md")]}
        with patch("xdrs_compiler.workflows.compile.nodes.MarkItDown") as mock_mid:
            mock_mid.return_value.convert.side_effect = RuntimeError("boom")
            result = conversion_node(state)  # type: ignore[arg-type]
        assert len(result["errors"]) == 1
        assert "boom" in result["errors"][0]


class TestFilterNode:
    def test_keeps_files_with_enough_words(self) -> None:
        state = {
            "converted_files": {
                "rich.md.md": "This document has more than ten words in it so it qualifies",
                "tiny.txt.md": "Too short",
            }
        }
        result = filter_node(state)  # type: ignore[arg-type]
        assert "rich.md.md" in result["converted_files"]
        assert "tiny.txt.md" not in result["converted_files"]

    def test_removes_files_below_threshold(self) -> None:
        state = {"converted_files": {"a.md.md": "one two three"}}
        result = filter_node(state)  # type: ignore[arg-type]
        assert result["converted_files"] == {}

    def test_keeps_exactly_ten_words(self) -> None:
        state = {"converted_files": {"a.md.md": "one two three four five six seven eight nine ten"}}
        result = filter_node(state)  # type: ignore[arg-type]
        assert "a.md.md" in result["converted_files"]


class TestWriteOutputNode:
    def _base_state(self, tmp_path: Path) -> dict:
        return {
            "xdrs_root": str(tmp_path / ".xdrs"),
            "scope": "testscope",
            "generated": [],
            "written_output_paths": [],
            "errors": [],
        }

    def test_writes_files_to_xdrs_root(self, tmp_path: Path) -> None:
        doc = GeneratedDoc(
            output_path="adrs/application/001-test.md",
            content="# Test Policy",
            related_input_files=[],
            doc_type="policy",
        )
        state = {**self._base_state(tmp_path), "generated": [doc]}
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
        state = {**self._base_state(tmp_path), "generated": [doc]}
        with patch("pathlib.Path.write_text", side_effect=OSError("no space")):
            result = write_output_node(state)  # type: ignore[arg-type]

        assert len(result["errors"]) == 1


class TestReportNode:
    def _make_state(self, tmp_path: Path, generated: list[GeneratedDoc]) -> dict:
        return {
            "xdrs_root": str(tmp_path / ".xdrs"),
            "scope": "testscope",
            "generated": generated,
            "written_output_paths": [doc.output_path for doc in generated],
            "errors": [],
        }

    def test_writes_report_file(self, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.chdir(tmp_path)
        doc = GeneratedDoc(
            output_path="adrs/application/001-test.md",
            content="# Policy",
            related_input_files=["docs/source.pdf"],
            doc_type="policy",
        )
        report_node(self._make_state(tmp_path, [doc]))  # type: ignore[arg-type]
        assert (tmp_path / REPORT_FILENAME).exists()

    def test_report_maps_output_to_inputs(self, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.chdir(tmp_path)
        doc = GeneratedDoc(
            output_path="adrs/application/001-test.md",
            content="# Policy",
            related_input_files=["docs/memo.pdf", "docs/notes.txt"],
            doc_type="policy",
        )
        report_node(self._make_state(tmp_path, [doc]))  # type: ignore[arg-type]

        data = json.loads((tmp_path / REPORT_FILENAME).read_text(encoding="utf-8"))
        expected_key = str(
            tmp_path / ".xdrs" / "testscope" / "adrs" / "application" / "001-test.md"
        )
        assert expected_key in data
        assert data[expected_key]["related_input_files"] == ["docs/memo.pdf", "docs/notes.txt"]

    def test_report_empty_when_no_generated(self, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.chdir(tmp_path)
        report_node(self._make_state(tmp_path, []))  # type: ignore[arg-type]
        data = json.loads((tmp_path / REPORT_FILENAME).read_text(encoding="utf-8"))
        assert data == {}
