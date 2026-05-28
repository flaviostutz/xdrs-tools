"""Basic usage example for xdrs-compiler.

This example stays offline by patching the workflow graph with a deterministic
result while still exercising the published package as a consumer would.
"""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from xdrs_compiler import CompilationResult, Compiler, CompilerConfig
from xdrs_compiler.workflows.compile.states import GeneratedDoc


def _mock_invoke(_initial_state: dict) -> dict:
    return {
        "generated": [
            GeneratedDoc(
                output_path="adrs/application/001-use-python.md",
                content="# Use Python",
                related_input_files=["adr-001-use-python.md"],
                doc_type="policy",
            )
        ],
        "written_output_paths": ["adrs/application/001-use-python.md"],
        "errors": [],
    }


def _run_once(config: CompilerConfig) -> CompilationResult:
    with patch("xdrs_compiler.compiler.graph.invoke", side_effect=_mock_invoke):
        return Compiler(config).compile()


def main() -> None:
    with TemporaryDirectory(prefix="xdrs-compiler-example-") as tmp_dir:
        root = Path(tmp_dir)
        source = root / "src"
        output = root / ".xdrs"
        work = root / ".work"
        source.mkdir(parents=True, exist_ok=True)

        (source / "adr-001-use-python.md").write_text(
            "# ADR 001: Use Python\nDecided to use Python for this project.\n",
            encoding="utf-8",
        )
        (source / "edr-001-tooling.yaml").write_text(
            "name: edr-001\ndescription: Standard tooling\n",
            encoding="utf-8",
        )

        config = CompilerConfig(
            input_dir=str(source),
            xdrs_root=str(output),
            scope="examples",
            work_dir=str(work),
        )

        result = _run_once(config)
        print("First run:", result.summary())

        result2 = _run_once(config)
        print("Second run (incremental):", result2.summary())

        (source / "adr-001-use-python.md").write_text(
            "# ADR 001: Use Python (updated)\nRevised decision.\n",
            encoding="utf-8",
        )
        result3 = _run_once(config)
        print("Third run (after edit):", result3.summary())


if __name__ == "__main__":
    main()
