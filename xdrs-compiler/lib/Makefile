SHELL := /bin/bash
MISE := mise exec --
ROOT_DIR := $(abspath ..)
export UV_PROJECT_ENVIRONMENT := $(ROOT_DIR)/.venv
export UV_CACHE_DIR := $(ROOT_DIR)/.cache/uv
export RUFF_CACHE_DIR := $(abspath .cache/ruff)
export PYTHONPYCACHEPREFIX := $(abspath .cache/pycache)
export COVERAGE_FILE := $(abspath .cache/coverage)

PACKAGE_NAME ?= xdrs_compiler

all: build lint test-unit

install:
	$(MISE) uv sync --project . --frozen --all-extras --dev

build: install
	rm -rf dist
	$(MISE) uv build --project . --out-dir dist

lint: install
	$(MISE) uv run --project . ruff format --check .
	$(MISE) uv run --project . ruff check .
	$(MISE) uv run --project . pyright
	$(MISE) uv run --project . pip-audit

lint-fix: install
	$(MISE) uv run --project . ruff format .
	$(MISE) uv run --project . ruff check . --fix
	$(MISE) uv run --project . pyright
	$(MISE) uv run --project . pip-audit

test-unit: install
	$(MISE) uv run --project . pytest -o cache_dir=.cache/pytest --cov=src/$(PACKAGE_NAME) --cov-branch --cov-report=term-missing --cov-report=html:.cache/htmlcov --cov-fail-under=80

run: install
	$(MISE) uv run --project . python -m $(PACKAGE_NAME)

dev: run

update-lockfile:
	$(MISE) uv lock --project . --upgrade

clean:
	rm -rf dist .cache
