from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from xdrs_compiler.compiler import CompilationResult, Compiler
from xdrs_compiler.config import CompilerConfig
from xdrs_compiler.workflows.compile.states import GeneratedDoc


@pytest.fixture()
def source_dir(tmp_path: Path) -> Path:
    d = tmp_path / "src"
    d.mkdir()
    (d / "adr-001.md").write_text("# ADR 001\nContent here.", encoding="utf-8")
    (d / "edr-002.yaml").write_text("name: edr-002\n", encoding="utf-8")
    return d


@pytest.fixture()
def config(tmp_path: Path, source_dir: Path) -> CompilerConfig:
    return CompilerConfig(
        input_dir=str(source_dir),
        xdrs_root=str(tmp_path / ".xdrs"),
        scope="testscope",
        work_dir=str(tmp_path / ".work"),
    )


def _make_graph_mock(generated: list[GeneratedDoc] | None = None) -> MagicMock:
    docs = generated or []
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {
        "generated": docs,
        "written_output_paths": [doc.output_path for doc in docs],
        "errors": [],
    }
    return mock_graph


class TestCompilationResult:
    def test_summary_format(self) -> None:
        result = CompilationResult(compiled=["a"], skipped=["b", "c"], errors=[])
        assert result.summary() == "compiled=1 skipped=2 errors=0"

    def test_success_when_no_errors(self) -> None:
        assert CompilationResult().success is True

    def test_failure_when_errors_present(self) -> None:
        assert CompilationResult(errors=["oops"]).success is False


class TestCompiler:
    def test_compile_runs_pipeline_on_first_run(self, config: CompilerConfig) -> None:
        generated = [
            GeneratedDoc(
                output_path="adrs/application/001-test.md",
                content="# Test",
                related_input_files=["adr-001.md"],
                doc_type="policy",
            )
        ]
        mock_graph = _make_graph_mock(generated)
        with patch("xdrs_compiler.compiler.graph", mock_graph):
            result = Compiler(config).compile()

        assert result.success
        assert len(result.compiled) == 1
        mock_graph.invoke.assert_called_once()

    def test_incremental_skips_unchanged_files(self, config: CompilerConfig) -> None:
        mock_graph = _make_graph_mock()
        with patch("xdrs_compiler.compiler.graph", mock_graph):
            compiler = Compiler(config)
            compiler.compile()
            result = compiler.compile()

        assert mock_graph.invoke.call_count == 1
        assert len(result.skipped) == 2

    def test_incremental_reruns_when_file_changes(self, config: CompilerConfig) -> None:
        source = Path(config.input_dir)
        mock_graph = _make_graph_mock()
        with patch("xdrs_compiler.compiler.graph", mock_graph):
            compiler = Compiler(config)
            compiler.compile()
            (source / "adr-001.md").write_text("# Updated", encoding="utf-8")
            result = compiler.compile()

        assert mock_graph.invoke.call_count == 2
        assert len(result.skipped) == 1

    def test_manifest_persisted_in_work_dir(self, config: CompilerConfig) -> None:
        mock_graph = _make_graph_mock()
        with patch("xdrs_compiler.compiler.graph", mock_graph):
            Compiler(config).compile()

        assert (Path(config.work_dir) / Compiler.MANIFEST_FILENAME).exists()

    def test_unsupported_files_ignored(self, config: CompilerConfig) -> None:
        Path(config.input_dir).joinpath("ignore.bin").write_bytes(b"\x00\x01")
        mock_graph = _make_graph_mock()
        with patch("xdrs_compiler.compiler.graph", mock_graph):
            result = Compiler(config).compile()

        assert not any("ignore.bin" in c for c in result.compiled)

    def test_creates_work_dir_if_missing(self, config: CompilerConfig) -> None:
        assert not Path(config.work_dir).exists()
        mock_graph = _make_graph_mock()
        with patch("xdrs_compiler.compiler.graph", mock_graph):
            Compiler(config).compile()
        assert Path(config.work_dir).exists()

    def test_compile_records_pipeline_errors(self, config: CompilerConfig) -> None:
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"generated": [], "errors": ["boom"]}
        with patch("xdrs_compiler.compiler.graph", mock_graph):
            result = Compiler(config).compile()

        assert not result.success
        assert "boom" in result.errors

    def test_corrupt_manifest_ignored(self, config: CompilerConfig) -> None:
        work = Path(config.work_dir)
        work.mkdir(parents=True, exist_ok=True)
        (work / Compiler.MANIFEST_FILENAME).write_text("not-json", encoding="utf-8")
        mock_graph = _make_graph_mock()
        with patch("xdrs_compiler.compiler.graph", mock_graph):
            result = Compiler(config).compile()

        assert result.success
        mock_graph.invoke.assert_called_once()

    def test_empty_source_dir_returns_empty_result(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        cfg = CompilerConfig(
            input_dir=str(empty),
            xdrs_root=str(tmp_path / ".xdrs"),
            scope="test",
            work_dir=str(tmp_path / ".work"),
        )
        result = Compiler(cfg).compile()
        assert result.success
        assert result.compiled == [] and result.skipped == []
