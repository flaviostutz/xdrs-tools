from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from .config import CompilerConfig
from .pipeline.graph import build_graph
from .pipeline.preparation import SUPPORTED_EXTENSIONS
from .pipeline.state import CompilerState, ProposalsMap


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
            "generated": [],
            "errors": [],
        }
        pipeline = build_graph()
        final_state: dict = pipeline.invoke(initial_state)  # type: ignore[assignment]

        errors: list[str] = final_state.get("errors") or []

        # Update manifest: only persist hashes when there are no errors
        if not errors:
            manifest.update(current_hashes)
        self._save_manifest(manifest)

        compiled = [doc.output_path for doc in (final_state.get("generated") or [])]
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
