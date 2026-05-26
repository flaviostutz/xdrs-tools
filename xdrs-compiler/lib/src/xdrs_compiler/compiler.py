from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path


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
    """Compiles source documents from a directory into XDRS elements.

    The compiler reads all supported source files under *source_dir*, converts
    them into XDRS elements, and writes the output under *output_dir*. A
    content-hash manifest is maintained so that subsequent runs only reprocess
    documents whose content has changed (incremental compilation).
    """

    SUPPORTED_EXTENSIONS: tuple[str, ...] = (".md", ".yaml", ".yml", ".json", ".txt")
    MANIFEST_FILENAME = ".xdrs-compiler-manifest.json"

    def __init__(self, source_dir: str | Path, output_dir: str | Path) -> None:
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir)
        self._manifest_path = self.output_dir / self.MANIFEST_FILENAME

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compile(self) -> CompilationResult:
        """Run a full (or incremental) compilation and return the result."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        manifest = self._load_manifest()
        result = CompilationResult()

        for source_file in self._discover_sources():
            rel = str(source_file.relative_to(self.source_dir))
            current_hash = self._hash_file(source_file)

            if manifest.get(rel) == current_hash:
                result.skipped.append(rel)
                continue

            try:
                self._process_file(source_file)
                manifest[rel] = current_hash
                result.compiled.append(rel)
            except Exception as exc:  # noqa: BLE001
                result.errors.append(f"{rel}: {exc}")

        self._save_manifest(manifest)
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _discover_sources(self) -> list[Path]:
        files: list[Path] = []
        for ext in self.SUPPORTED_EXTENSIONS:
            files.extend(self.source_dir.rglob(f"*{ext}"))
        return sorted(files)

    def _process_file(self, source_file: Path) -> None:
        """Stub: convert a source file into an XDRS element.

        Replace this with the actual agent-graph pipeline once the spec is defined.
        """
        relative = source_file.relative_to(self.source_dir)
        dest = self.output_dir / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(source_file.read_text(encoding="utf-8"), encoding="utf-8")

    # ------------------------------------------------------------------
    # Manifest
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
