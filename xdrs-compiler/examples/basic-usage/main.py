"""Basic usage example for xdrs-compiler."""

from pathlib import Path
from xdrs_compiler import Compiler

# Create a small temporary source tree
source = Path("/tmp/xdrs-compiler-example/src")
output = Path("/tmp/xdrs-compiler-example/out")
source.mkdir(parents=True, exist_ok=True)

(source / "adr-001-use-python.md").write_text(
    "# ADR 001: Use Python\nDecided to use Python for this project.\n",
    encoding="utf-8",
)
(source / "edr-001-tooling.yaml").write_text(
    "name: edr-001\ndescription: Standard tooling\n",
    encoding="utf-8",
)

compiler = Compiler(source_dir=source, output_dir=output)
result = compiler.compile()
print("First run:", result.summary())

# Second run — nothing changed, both files skipped
result2 = compiler.compile()
print("Second run (incremental):", result2.summary())

# Modify one file — only that file recompiled
(source / "adr-001-use-python.md").write_text(
    "# ADR 001: Use Python (updated)\nRevised decision.\n",
    encoding="utf-8",
)
result3 = compiler.compile()
print("Third run (after edit):", result3.summary())
