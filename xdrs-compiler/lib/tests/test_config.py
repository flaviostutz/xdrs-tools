from pathlib import Path

import pytest
import yaml

from xdrs_compiler.config import CompilerConfig


class TestCompilerConfigLoad:
    def test_load_valid_yaml(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / ".xdrs-compiler.yml"
        cfg_file.write_text(
            "input_dir: ./docs\nxdrs_root: .xdrs\nscope: myteam\n", encoding="utf-8"
        )
        config = CompilerConfig.load(cfg_file)
        assert config.input_dir == "./docs"
        assert config.xdrs_root == ".xdrs"
        assert config.scope == "myteam"
        assert config.model == "gpt-4o-mini"
        assert config.work_dir == ".work"

    def test_load_with_optional_fields(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / ".xdrs-compiler.yml"
        cfg_file.write_text(
            "input_dir: ./docs\nxdrs_root: .xdrs\nscope: myteam\nmodel: gpt-4o\nwork_dir: .tmp\n",
            encoding="utf-8",
        )
        config = CompilerConfig.load(cfg_file)
        assert config.model == "gpt-4o"
        assert config.work_dir == ".tmp"

    def test_load_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            CompilerConfig.load(tmp_path / "nonexistent.yml")

    def test_load_missing_required_field_raises(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / ".xdrs-compiler.yml"
        cfg_file.write_text("input_dir: ./docs\nxdrs_root: .xdrs\n", encoding="utf-8")
        with pytest.raises(ValueError, match="scope"):
            CompilerConfig.load(cfg_file)


class TestCompilerConfigSave:
    def test_save_round_trip(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / ".xdrs-compiler.yml"
        original = CompilerConfig(
            input_dir="./docs",
            xdrs_root=".xdrs",
            scope="myteam",
            model="gpt-4o",
            work_dir=".tmp",
        )
        original.save(cfg_file)
        loaded = CompilerConfig.load(cfg_file)
        assert loaded.input_dir == original.input_dir
        assert loaded.xdrs_root == original.xdrs_root
        assert loaded.scope == original.scope
        assert loaded.model == original.model
        assert loaded.work_dir == original.work_dir

    def test_save_produces_valid_yaml(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / ".xdrs-compiler.yml"
        config = CompilerConfig(input_dir="./docs", xdrs_root=".xdrs", scope="test")
        config.save(cfg_file)
        data = yaml.safe_load(cfg_file.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert data["scope"] == "test"
