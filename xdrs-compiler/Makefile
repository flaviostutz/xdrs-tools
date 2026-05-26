SHELL := /bin/bash
MISE := mise exec --
ROOT_DIR := $(abspath .)
export UV_PROJECT_ENVIRONMENT := $(ROOT_DIR)/.venv
export UV_CACHE_DIR := $(ROOT_DIR)/.cache/uv

all: build lint test

setup:
	mise install
	$(MAKE) install

install:
	$(MAKE) -C lib install

build:
	$(MAKE) -C lib build

lint:
	$(MAKE) -C lib lint

lint-fix:
	$(MAKE) -C lib lint-fix

test: test-unit test-examples

test-unit:
	$(MAKE) -C lib test-unit

test-examples: build
	@for dir in examples/*; do \
		if [ -f "$$dir/pyproject.toml" ]; then \
			echo ">>> Running $$dir"; \
			UV_PROJECT_ENVIRONMENT="$(UV_PROJECT_ENVIRONMENT)" UV_CACHE_DIR="$(UV_CACHE_DIR)" $(MISE) uv sync --project "$$dir" --frozen || exit 1; \
			UV_PROJECT_ENVIRONMENT="$(UV_PROJECT_ENVIRONMENT)" UV_CACHE_DIR="$(UV_CACHE_DIR)" $(MISE) uv pip install --python "$(UV_PROJECT_ENVIRONMENT)/bin/python" lib/dist/*.whl || exit 1; \
			UV_PROJECT_ENVIRONMENT="$(UV_PROJECT_ENVIRONMENT)" UV_CACHE_DIR="$(UV_CACHE_DIR)" $(MISE) uv run --project "$$dir" python "$$dir/main.py" || exit 1; \
		fi; \
	done

clean:
	$(MAKE) -C lib clean
	rm -rf .cache
	rm -rf .venv

update-lockfile:
	$(MAKE) -C lib update-lockfile
