# xdrs-compiler

A Python library that compiles documents in various formats from a directory into XDRS elements.
It employs agent graphs and tools to convert, migrate, lint, and test XDRS scopes. It can also
watch for updates in existing sources and apply incremental compilations when source documents change.

## Overview

`xdrs-compiler` processes source documents (Markdown, YAML, JSON, and other formats) and compiles
them into well-structured XDRS (Cross-Domain Reference Standard) elements. The compilation pipeline
is powered by composable agent graphs that can be extended with custom converters, validators, and
migration tools.

Key capabilities:

- **Multi-format ingestion** — reads Markdown, YAML, JSON, and plain-text sources from a directory tree
- **Agent-graph pipeline** — orchestrates conversion, migration, linting, and testing steps through a directed graph of agents
- **Incremental compilation** — detects changed sources and recompiles only affected XDRS elements
- **Scope management** — organizes compiled output into typed XDRS scopes (ADR, BDR, EDR, etc.)
- **Extensible tooling** — plug in custom converters, validators, and post-processors

## Getting Started

```sh
make setup
make test
```

The published package lives in `lib/` and runnable consumer examples live in `examples/`.

## Usage

```python
from xdrs_compiler import Compiler

compiler = Compiler(source_dir="docs/", output_dir=".xdrs/")
result = compiler.compile()
print(result.summary())
```

## Development

```sh
make setup        # install tools and dependencies
make build        # build the package
make lint         # run all static checks
make lint-fix     # auto-fix lint issues
make test         # run all tests + examples
make test-unit    # run unit tests only
make clean        # remove build artifacts
```

## Architecture

The compilation pipeline is a directed acyclic graph (DAG) of agents. Each agent receives a list
of source documents and emits transformed or validated XDRS elements. Standard agents include:

- **Ingestion agent** — discovers and reads source files
- **Conversion agent** — transforms documents into the canonical XDRS element schema
- **Migration agent** — upgrades elements from older schema versions
- **Lint agent** — validates elements against XDRS formatting and content rules
- **Index agent** — builds scope indexes from compiled elements
- **Test agent** — runs user-defined acceptance tests against compiled output

Custom agents can be registered by implementing the `Agent` protocol and wiring them into the graph.

## Incremental Compilation

`xdrs-compiler` tracks a content-hash manifest of source files. On subsequent runs it re-processes
only the documents whose hash has changed, skipping unchanged elements. The manifest is stored
alongside the compiled output and is automatically updated after each successful compilation.
