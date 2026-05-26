from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from xdrs_compiler.__main__ import main
from xdrs_compiler.compiler import CompilationResult, Compiler
from xdrs_compiler.config import CompilerConfig
from xdrs_compiler.pipeline.state import GeneratedDoc


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


def _make_pipeline_mock(generated: list[GeneratedDoc] | None = None) -> MagicMock:
    mock_pipeline = MagicMock()
    mock_pipeline.invoke.return_value = {
        "generated": generated or [],
        "errors": [],
    }
    return mock_pipeline


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
        with patch("xdrs_compiler.compiler.build_graph") as mock_build:
            mock_build.return_value = _make_pipeline_mock(generated)
            result = Compiler(config).compile()

        assert result.success
        assert len(result.compiled) == 1
        mock_build.return_value.invoke.assert_called_once()

    def test_incremental_skips_unchanged_files(self, config: CompilerConfig) -> None:
        with patch("xdrs_compiler.compiler.build_graph") as mock_build:
            mock_build.return_value = _make_pipeline_mock()
            compiler = Compiler(config)
            compiler.compile()
            result = compiler.compile()

        assert mock_build.return_value.invoke.call_count == 1
        assert len(result.skipped) == 2

    def test_incremental_reruns_when_file_changes(self, config: CompilerConfig) -> None:
        source = Path(config.input_dir)
        with patch("xdrs_compiler.compiler.build_graph") as mock_build:
            mock_build.return_value = _make_pipeline_mock()
            compiler = Compiler(config)
            compiler.compile()
            (source / "adr-001.md").write_text("# Updated", encoding="utf-8")
            result = compiler.compile()

        assert mock_build.return_value.invoke.call_count == 2
        assert len(result.skipped) == 1

    def test_manifest_persisted_in_work_dir(self, config: CompilerConfig) -> None:
        with patch("xdrs_compiler.compiler.build_graph") as mock_build:
            mock_build.return_value = _make_pipeline_mock()
            Compiler(config).compile()

        assert (Path(config.work_dir) / Compiler.MANIFEST_FILENAME).exists()

    def test_unsupported_files_ignored(self, config: CompilerConfig) -> None:
        Path(config.input_dir).joinpath("ignore.bin").write_bytes(b"\x00\x01")
        with patch("xdrs_compiler.compiler.build_graph") as mock_build:
            mock_build.return_value = _make_pipeline_mock()
            result = Compiler(config).compile()

        assert not any("ignore.bin" in c for c in result.compiled)

    def test_creates_work_dir_if_missing(self, config: CompilerConfig) -> None:
        assert not Path(config.work_dir).exists()
        with patch("xdrs_compiler.compiler.build_graph") as mock_build:
            mock_build.return_value = _make_pipeline_mock()
            Compiler(config).compile()
        assert Path(config.work_dir).exists()

    def test_compile_records_pipeline_errors(self, config: CompilerConfig) -> None:
        with patch("xdrs_compiler.compiler.build_graph") as mock_build:
            mock_pipeline = MagicMock()
            mock_pipeline.invoke.return_value = {"generated": [], "errors": ["boom"]}
            mock_build.return_value = mock_pipeline
            result = Compiler(config).compile()

        assert not result.success
        assert "boom" in result.errors

    def test_corrupt_manifest_ignored(self, config: CompilerConfig) -> None:
        work = Path(config.work_dir)
        work.mkdir(parents=True, exist_ok=True)
        (work / Compiler.MANIFEST_FILENAME).write_text("not-json", encoding="utf-8")
        with patch("xdrs_compiler.compiler.build_graph") as mock_build:
            mock_build.return_value = _make_pipeline_mock()
            result = Compiler(config).compile()

        assert result.success
        mock_build.return_value.invoke.assert_called_once()

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


class TestMain:
    def test_main_exits_zero_on_success(
        self, config: CompilerConfig, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        cfg_file = tmp_path / ".xdrs-compiler.yml"
        config.save(cfg_file)
        with patch("sys.argv", ["xdrs-compiler", "--config", str(cfg_file)]):
            with patch("xdrs_compiler.__main__.Compiler") as mock_cls:
                mock_cls.return_value.compile.return_value = CompilationResult()
                with pytest.raises(SystemExit) as exc_info:
                    main()
        assert exc_info.value.code == 0

    def test_main_exits_one_on_failure(
        self, config: CompilerConfig, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        cfg_file = tmp_path / ".xdrs-compiler.yml"
        config.save(cfg_file)
        with patch("sys.argv", ["xdrs-compiler", "--config", str(cfg_file)]):
            with patch("xdrs_compiler.__main__.Compiler") as mock_cls:
                mock_cls.return_value.compile.return_value = CompilationResult(errors=["oops"])
                with pytest.raises(SystemExit) as exc_info:
                    main()
        assert exc_info.value.code == 1

    def test_main_exits_one_without_api_key(self, monkeypatch) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with patch("sys.argv", ["xdrs-compiler"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 1

    def test_main_saves_config_when_args_given(
        self, source_dir: Path, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        cfg_file = tmp_path / "written.yml"
        with patch(
            "sys.argv",
            [
                "xdrs-compiler",
                "--input-dir",
                str(source_dir),
                "--xdrs-root",
                str(tmp_path / ".xdrs"),
                "--scope",
                "myteam",
                "--config",
                str(cfg_file),
            ],
        ):
            with patch("xdrs_compiler.__main__.Compiler") as mock_cls:
                mock_cls.return_value.compile.return_value = CompilationResult()
                with pytest.raises(SystemExit):
                    main()
        assert cfg_file.exists()

    def test_main_exits_one_when_config_missing(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        missing = tmp_path / "no-such-file.yml"
        with patch("sys.argv", ["xdrs-compiler", "--config", str(missing)]):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 1
