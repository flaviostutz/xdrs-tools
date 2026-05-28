from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import mlflow

from .config import CompilerConfig
from .workflows.compile.graph import graph
from .workflows.compile.nodes import SUPPORTED_EXTENSIONS
from .workflows.compile.states import CompilerState, ProposalsMap


@dataclass
class CompilationResult:
    """Summary of a compilation run."""

    compiled: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"compiled={len(self.compiled)} skipped={len(self.skipped)} errors={len(self.errors)}"
        )

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


class Compiler:
    """Compiles source documents from a directory into XDRS policies and skills.

    The compiler discovers all supported files under *config.input_dir*, runs
    a holistic LangGraph agent pipeline (Preparation → Analysis → Synthesis → Report),
    and writes XDRS elements under *config.xdrs_root/config.scope/*.

    A content-hash manifest in *config.work_dir* enables incremental compilation:
    if no source file has changed since the last run, the pipeline is skipped entirely.
    """

    MANIFEST_FILENAME = ".xdrs-compiler-manifest.json"

    def __init__(self, config: CompilerConfig) -> None:
        self.config = config
        self._work_dir = Path(config.work_dir)
        self._manifest_path = self._work_dir / self.MANIFEST_FILENAME

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compile(self) -> CompilationResult:
        """Run a full (or incremental) compilation and return the result."""
        self._work_dir.mkdir(parents=True, exist_ok=True)
        source_dir = Path(self.config.input_dir)

        # Discover source files
        source_files: list[Path] = []
        for ext in SUPPORTED_EXTENSIONS:
            source_files.extend(source_dir.rglob(f"*{ext}"))
        source_files = sorted(set(source_files))

        if not source_files:
            return CompilationResult()

        # Load manifest and compute per-file hashes
        manifest = self._load_manifest()
        current_hashes = {str(f.relative_to(source_dir)): self._hash_file(f) for f in source_files}
        changed = [rel for rel, h in current_hashes.items() if manifest.get(rel) != h]
        skipped = [rel for rel in current_hashes if rel not in changed]

        if not changed:
            return CompilationResult(skipped=list(current_hashes.keys()))

        tracking_dir = (self._work_dir / "mlruns").resolve()
        tracking_dir.mkdir(parents=True, exist_ok=True)
        mlflow.set_tracking_uri(tracking_dir.as_uri())
        mlflow.set_experiment(f"xdrs-compiler/{self.config.scope}")

        # Run the full LangGraph pipeline
        initial_state: CompilerState = {
            "input_dir": self.config.input_dir,
            "xdrs_root": self.config.xdrs_root,
            "scope": self.config.scope,
            "model": self.config.model,
            "work_dir": self.config.work_dir,
            "source_files": [],
            "converted_files": {},
            "analysis": {},
            "proposals": ProposalsMap(),
            "analysis_iteration": 0,
            "judge_approved": False,
            "judge_feedback": "",
            "verification_iteration": 0,
            "verification_passed": False,
            "verification_feedback": "",
            "generated": [],
            "written_output_paths": [],
            "errors": [],
        }

        with mlflow.start_run():
            mlflow.log_param("model", self.config.model)
            mlflow.log_param("scope", self.config.scope)
            mlflow.log_param("input_dir", self.config.input_dir)
            mlflow.log_param("changed_files", len(changed))

            final_state: dict = graph.invoke(initial_state)  # type: ignore[assignment]

            errors: list[str] = final_state.get("errors") or []
            compiled = list(final_state.get("written_output_paths") or [])

            mlflow.log_metric("compiled_count", len(compiled))
            mlflow.log_metric("skipped_count", len(skipped))
            mlflow.log_metric("error_count", len(errors))

        # Update manifest: only persist hashes when there are no errors
        if not errors:
            manifest.update(current_hashes)
        self._save_manifest(manifest)

        return CompilationResult(compiled=compiled, skipped=skipped, errors=errors)

    # ------------------------------------------------------------------
    # Manifest helpers
    # ------------------------------------------------------------------

    def _load_manifest(self) -> dict[str, str]:
        if self._manifest_path.exists():
            try:
                return json.loads(self._manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_manifest(self, manifest: dict[str, str]) -> None:
        self._manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    @staticmethod
    def _hash_file(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()
