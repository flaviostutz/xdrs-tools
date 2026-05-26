# xdrs-compiler

Compiles documents in various formats into XDRS elements using agent graphs, with support for
incremental compilation and extensible tooling.

## Getting Started

```sh
make setup
make test
```

```python
from xdrs_compiler import Compiler

compiler = Compiler(source_dir="docs/", output_dir=".xdrs/")
result = compiler.compile()
print(result.summary())
```

## Development

```sh
make build
make lint
make test
```
