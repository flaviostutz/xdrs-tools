import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from xdrs_compiler.__main__ import main
from xdrs_compiler.compiler import CompilationResult, Compiler


@pytest.fixture()
def source_dir(tmp_path):
    d = tmp_path / "src"
    d.mkdir()
    (d / "adr-001.md").write_text("# ADR 001\nContent.", encoding="utf-8")
    (d / "edr-002.yaml").write_text("name: edr-002\n", encoding="utf-8")
    return d


@pytest.fixture()
def output_dir(tmp_path):
    return tmp_path / "out"


class TestCompilationResult:
    def test_summary_format(self) -> None:
        result = CompilationResult(compiled=["a"], skipped=["b", "c"], errors=[])
        assert result.summary() == "compiled=1 skipped=2 errors=0"

    def test_success_when_no_errors(self) -> None:
        assert CompilationResult().success is True

    def test_failure_when_errors_present(self) -> None:
        assert CompilationResult(errors=["oops"]).success is False


class TestCompiler:
    def test_compile_processes_supported_files(self, source_dir, output_dir) -> None:
        compiler = Compiler(source_dir, output_dir)
        result = compiler.compile()

        assert len(result.errors) == 0
        assert len(result.compiled) == 2
        assert len(result.skipped) == 0

    def test_incremental_skips_unchanged_files(self, source_dir, output_dir) -> None:
        compiler = Compiler(source_dir, output_dir)
        compiler.compile()

        result = compiler.compile()
        assert len(result.compiled) == 0
        assert len(result.skipped) == 2

    def test_incremental_recompiles_changed_file(self, source_dir, output_dir) -> None:
        compiler = Compiler(source_dir, output_dir)
        compiler.compile()

        (source_dir / "adr-001.md").write_text("# Updated", encoding="utf-8")
        result = compiler.compile()

        assert len(result.compiled) == 1
        assert len(result.skipped) == 1

    def test_output_files_are_created(self, source_dir, output_dir) -> None:
        compiler = Compiler(source_dir, output_dir)
        compiler.compile()

        assert (output_dir / "adr-001.md").exists()
        assert (output_dir / "edr-002.yaml").exists()

    def test_manifest_is_persisted(self, source_dir, output_dir) -> None:
        compiler = Compiler(source_dir, output_dir)
        compiler.compile()

        assert (output_dir / Compiler.MANIFEST_FILENAME).exists()

    def test_unsupported_files_are_ignored(self, source_dir, output_dir) -> None:
        (source_dir / "ignore.bin").write_bytes(b"\x00\x01")
        compiler = Compiler(source_dir, output_dir)
        result = compiler.compile()

        assert not any("ignore.bin" in c for c in result.compiled)

    def test_creates_output_dir_if_missing(self, source_dir, output_dir) -> None:
        assert not output_dir.exists()
        compiler = Compiler(source_dir, output_dir)
        compiler.compile()
        assert output_dir.exists()

    def test_compile_records_errors_on_failure(self, source_dir, output_dir) -> None:
        compiler = Compiler(source_dir, output_dir)
        with patch.object(Compiler, "_process_file", side_effect=RuntimeError("boom")):
            result = compiler.compile()
        assert len(result.errors) == 2
        assert result.success is False

    def test_corrupt_manifest_is_ignored(self, source_dir, output_dir) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / Compiler.MANIFEST_FILENAME).write_text("not-json", encoding="utf-8")
        compiler = Compiler(source_dir, output_dir)
        result = compiler.compile()
        assert len(result.compiled) == 2


class TestMain:
    def test_main_exits_zero_on_success(self, source_dir, output_dir, tmp_path) -> None:
        with patch("sys.argv", ["xdrs-compiler", str(source_dir), str(output_dir)]):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 0

    def test_main_exits_one_on_failure(self, source_dir, output_dir) -> None:
        with patch("sys.argv", ["xdrs-compiler", str(source_dir), str(output_dir)]):
            with patch("xdrs_compiler.__main__.Compiler.compile") as mock_compile:
                mock_compile.return_value = CompilationResult(errors=["oops"])
                with pytest.raises(SystemExit) as exc_info:
                    main()
        assert exc_info.value.code == 1
