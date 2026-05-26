from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class CompilerConfig:
    """Configuration for the XDRS compiler pipeline."""

    input_dir: str
    xdrs_root: str
    scope: str
    model: str = "gpt-4o-mini"
    work_dir: str = ".work"

    @staticmethod
    def load(path: str | Path = ".xdrs-compiler.yml") -> CompilerConfig:
        """Load config from a YAML file."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        with p.open("r", encoding="utf-8") as f:
            data: dict = yaml.safe_load(f) or {}
        for required in ("input_dir", "xdrs_root", "scope"):
            if required not in data:
                raise ValueError(f"Missing required config field: '{required}'")
        return CompilerConfig(
            input_dir=data["input_dir"],
            xdrs_root=data["xdrs_root"],
            scope=data["scope"],
            model=data.get("model", "gpt-4o-mini"),
            work_dir=data.get("work_dir", ".work"),
        )

    def save(self, path: str | Path = ".xdrs-compiler.yml") -> None:
        """Save config to a YAML file."""
        p = Path(path)
        data = {
            "input_dir": self.input_dir,
            "xdrs_root": self.xdrs_root,
            "scope": self.scope,
            "model": self.model,
            "work_dir": self.work_dir,
        }
        with p.open("w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=True)
