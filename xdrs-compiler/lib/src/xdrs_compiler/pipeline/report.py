from __future__ import annotations

import json
from pathlib import Path

from .state import CompilerState

REPORT_FILENAME = ".xdrs-compiler.report"


def report_node(state: CompilerState) -> dict:
    """Generate a .xdrs-compiler.report JSON file mapping output docs to their source files."""
    xdrs_root = Path(state["xdrs_root"])
    scope = state["scope"]
    report: dict[str, dict] = {}

    for doc in state.get("generated") or []:
        full_out_path = str(xdrs_root / scope / doc.output_path)
        report[full_out_path] = {"related_input_files": doc.related_input_files}

    report_path = Path(REPORT_FILENAME)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    return {}
