"""Evaluation script for the compile workflow — simple cases slice.

Loads every record from dataset_simple/simple-cases.jsonl, writes source documents
to a temporary directory, runs the compiler against real LLMs, and logs per-sample
and aggregate metrics to a local MLflow experiment.

Usage:
    # From xdrs-compiler/ root (after make build):
    OPENAI_API_KEY=sk-... make eval
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import mlflow

# Ensure the installed library is importable when running via uv run
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib" / "src"))

from xdrs_compiler.compiler import Compiler
from xdrs_compiler.config import CompilerConfig

DATASET_PATH = Path(__file__).parent / "dataset_simple" / "simple-cases.jsonl"
EXPERIMENT_NAME = "xdrs-compiler/compile/simple"
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


def _load_samples() -> list[dict]:
    return [
        json.loads(line)
        for line in DATASET_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _run_sample(sample: dict, xdrs_root: str, work_dir: str, input_dir: str) -> dict:
    """Write source docs to input_dir, run compiler, return metrics dict."""
    for doc in sample["source_docs"]:
        (Path(input_dir) / doc["filename"]).write_text(doc["content"], encoding="utf-8")

    config = CompilerConfig(
        input_dir=input_dir,
        xdrs_root=xdrs_root,
        scope="eval",
        model=MODEL,
        work_dir=work_dir,
    )
    result = Compiler(config).compile()

    policy_count = sum(
        1 for p in Path(xdrs_root).rglob("*.md") if "adrs" in str(p)
    )
    skill_count = sum(
        1 for p in Path(xdrs_root).rglob("SKILL.md")
    )
    passed = (
        policy_count >= sample["expected_min_policies"]
        and skill_count >= sample["expected_min_skills"]
        and result.success
    )
    return {
        "pass": int(passed),
        "policy_count": policy_count,
        "skill_count": skill_count,
        "error_count": len(result.errors),
        "compiled_count": len(result.compiled),
    }


def main() -> None:
    mlflow.set_experiment(EXPERIMENT_NAME)
    samples = _load_samples()
    results: list[dict] = []

    with mlflow.start_run(run_name="eval-simple"):
        mlflow.log_param("model", MODEL)
        mlflow.log_param("dataset", "dataset_simple/simple-cases.jsonl")
        mlflow.log_param("sample_count", len(samples))

        for sample in samples:
            with tempfile.TemporaryDirectory() as tmp:
                input_dir = str(Path(tmp) / "input")
                xdrs_root = str(Path(tmp) / "xdrs")
                work_dir = str(Path(tmp) / "work")
                Path(input_dir).mkdir()

                with mlflow.start_run(run_name=sample["id"], nested=True):
                    mlflow.log_param("sample_id", sample["id"])
                    mlflow.log_param("description", sample["description"])
                    metrics = _run_sample(sample, xdrs_root, work_dir, input_dir)
                    mlflow.log_metrics(metrics)
                    results.append({"id": sample["id"], **metrics})

        pass_count = sum(r["pass"] for r in results)
        mlflow.log_metric("pass_count", pass_count)
        mlflow.log_metric("fail_count", len(results) - pass_count)
        mlflow.log_metric("accuracy", pass_count / len(results) if results else 0.0)

    print(f"Results: {pass_count}/{len(results)} passed")
    for r in results:
        status = "PASS" if r["pass"] else "FAIL"
        print(f"  [{status}] {r['id']}  policies={r['policy_count']}  skills={r['skill_count']}")

    sys.exit(0 if pass_count == len(results) else 1)


if __name__ == "__main__":
    main()
