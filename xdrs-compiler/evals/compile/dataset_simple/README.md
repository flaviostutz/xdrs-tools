# dataset_simple

Evaluation dataset for the `compile` workflow — simple single-document cases.

## Purpose

Each record provides one or more synthetic source documents and the minimum number of XDRS
policies and skills that a correct compile run must produce.

## Creation procedure

Records were authored manually to cover three structural patterns:

1. Pure policy source (architecture decision record)
2. Pure skill source (operational runbook)
3. Mixed source (API standards doc with both policy and procedure content)

## Data quality

All source documents are synthetic and self-contained. They contain enough content (>10 words)
to pass the compiler's filter node. Expected minimums are conservative (≥1) to tolerate
LLM non-determinism while still asserting meaningful output.

## Consuming the dataset

```python
import json
from pathlib import Path

samples = [
    json.loads(line)
    for line in Path("simple-cases.jsonl").read_text().splitlines()
    if line.strip()
]
for sample in samples:
    print(sample["id"], sample["source_docs"][0]["filename"])
```
