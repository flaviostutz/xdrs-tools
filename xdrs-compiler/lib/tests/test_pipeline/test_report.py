import json
from pathlib import Path

from xdrs_compiler.pipeline.report import REPORT_FILENAME, report_node
from xdrs_compiler.pipeline.state import GeneratedDoc


def _make_state(tmp_path: Path, generated: list[GeneratedDoc]) -> dict:
    return {
        "xdrs_root": str(tmp_path / ".xdrs"),
        "scope": "testscope",
        "generated": generated,
        "errors": [],
    }


class TestReportNode:
    def test_writes_report_file(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        doc = GeneratedDoc(
            output_path="adrs/application/001-test.md",
            content="# Policy",
            related_input_files=["docs/source.pdf"],
            doc_type="policy",
        )
        report_node(_make_state(tmp_path, [doc]))  # type: ignore[arg-type]
        assert (tmp_path / REPORT_FILENAME).exists()

    def test_report_maps_output_to_inputs(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        doc = GeneratedDoc(
            output_path="adrs/application/001-test.md",
            content="# Policy",
            related_input_files=["docs/memo.pdf", "docs/notes.txt"],
            doc_type="policy",
        )
        report_node(_make_state(tmp_path, [doc]))  # type: ignore[arg-type]

        data = json.loads((tmp_path / REPORT_FILENAME).read_text(encoding="utf-8"))
        expected_key = str(
            tmp_path / ".xdrs" / "testscope" / "adrs" / "application" / "001-test.md"
        )
        assert expected_key in data
        assert data[expected_key]["related_input_files"] == ["docs/memo.pdf", "docs/notes.txt"]

    def test_report_empty_when_no_generated(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        report_node(_make_state(tmp_path, []))  # type: ignore[arg-type]
        data = json.loads((tmp_path / REPORT_FILENAME).read_text(encoding="utf-8"))
        assert data == {}

    def test_report_contains_all_generated_docs(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        docs = [
            GeneratedDoc(
                output_path=f"adrs/application/{i:03d}-policy.md",
                content="# Policy",
                related_input_files=["doc.pdf"],
                doc_type="policy",
            )
            for i in range(1, 4)
        ]
        report_node(_make_state(tmp_path, docs))  # type: ignore[arg-type]
        data = json.loads((tmp_path / REPORT_FILENAME).read_text(encoding="utf-8"))
        assert len(data) == 3
