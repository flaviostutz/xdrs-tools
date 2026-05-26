from __future__ import annotations

from pathlib import Path

from markitdown import MarkItDown

from .state import CompilerState

SUPPORTED_EXTENSIONS: tuple[str, ...] = (
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".json",
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".html",
    ".htm",
    ".csv",
    ".epub",
    ".xml",
    ".msg",
)


def discovery_node(state: CompilerState) -> dict:
    """Discover all supported source files in input_dir."""
    source_dir = Path(state["input_dir"])
    files: set[Path] = set()
    for ext in SUPPORTED_EXTENSIONS:
        files.update(source_dir.rglob(f"*{ext}"))
    return {"source_files": sorted(str(f) for f in files)}


def conversion_node(state: CompilerState) -> dict:
    """Convert each source file to Markdown using markitdown, writing to work_dir."""
    source_dir = Path(state["input_dir"])
    work_dir = Path(state["work_dir"])
    mid = MarkItDown()
    converted: dict[str, str] = {}
    errors: list[str] = []

    for src_str in state["source_files"]:
        src = Path(src_str)
        try:
            rel = src.relative_to(source_dir)
        except ValueError:
            errors.append(f"{src_str}: not relative to input_dir")
            continue

        work_path = work_dir / f"{rel}.md"
        work_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            result = mid.convert(str(src))
            text = result.text_content or ""
            work_path.write_text(text, encoding="utf-8")
            converted[f"{rel}.md"] = text
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{rel}: conversion failed: {exc}")

    return {"converted_files": converted, "errors": errors}


def filter_node(state: CompilerState) -> dict:
    """Remove converted files that contain fewer than 10 words."""
    filtered = {
        path: text for path, text in state["converted_files"].items() if len(text.split()) >= 10
    }
    return {"converted_files": filtered}
