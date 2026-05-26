from pathlib import Path
from unittest.mock import patch

import pytest

from xdrs_compiler.pipeline.preparation import (
    SUPPORTED_EXTENSIONS,
    conversion_node,
    discovery_node,
    filter_node,
)


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
        with patch("xdrs_compiler.pipeline.preparation.MarkItDown") as mock_mid:
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
