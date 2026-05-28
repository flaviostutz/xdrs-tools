from pathlib import Path
from unittest.mock import patch

import pytest

from xdrs_compiler.__main__ import main
from xdrs_compiler.compiler import CompilationResult
from xdrs_compiler.config import CompilerConfig


@pytest.fixture()
def source_dir(tmp_path: Path) -> Path:
    d = tmp_path / "src"
    d.mkdir()
    (d / "adr-001.md").write_text("# ADR 001\nContent here.", encoding="utf-8")
    return d


@pytest.fixture()
def config(tmp_path: Path, source_dir: Path) -> CompilerConfig:
    return CompilerConfig(
        input_dir=str(source_dir),
        xdrs_root=str(tmp_path / ".xdrs"),
        scope="testscope",
        work_dir=str(tmp_path / ".work"),
    )


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
