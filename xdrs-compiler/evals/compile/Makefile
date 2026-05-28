SHELL := /bin/bash
MISE := mise exec --
ROOT_DIR := $(abspath ../..)
export UV_PROJECT_ENVIRONMENT := $(ROOT_DIR)/.venv
export UV_CACHE_DIR := $(ROOT_DIR)/.cache/uv

eval: eval-simple

eval-simple:
	$(MISE) uv run --project $(ROOT_DIR)/lib python eval_simple.py
