# PInSilico top-level Makefile.
#
# Conventions:
#   - Recipes are POSIX sh, portable to macOS/Linux. Windows devs run the
#     equivalent commands manually or via Git Bash / WSL.
#   - `make ci` runs the same gates GitHub Actions does (BUILD_PROMPT.md §5).
#   - `make dev` runs the Python sidecar and the Tauri shell in parallel and
#     traps SIGINT so Ctrl-C kills both children cleanly.

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

# ----------------------------------------------------------------- paths
ROOT := $(CURDIR)
SIDECAR_DIR := $(ROOT)/sidecar
APP_DIR := $(ROOT)/app
PY ?= python3.11
VENV := $(SIDECAR_DIR)/.venv
PIP := $(VENV)/bin/pip
PYBIN := $(VENV)/bin/python

# ----------------------------------------------------------------- meta
.PHONY: help
help:  ## Show this help (default target)
	@awk 'BEGIN { FS = ":.*## "; printf "Targets:\n" } /^[a-zA-Z0-9_.-]+:.*## / { printf "  %-22s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# =================================================================== install
.PHONY: install
install: install-python install-frontend install-precommit  ## One-time setup: sidecar venv, pnpm deps, pre-commit hooks

.PHONY: install-python
install-python:  ## Create sidecar venv on Python 3.11 and install dev deps
	@command -v $(PY) >/dev/null || { echo "ERROR: $(PY) not on PATH (expected 3.11.x via pyenv)"; exit 1; }
	$(PY) -m venv $(VENV)
	$(PIP) install --upgrade pip wheel
	$(PIP) install -e "$(SIDECAR_DIR)[dev]"

.PHONY: install-frontend
install-frontend:  ## Install pnpm workspace dependencies
	@command -v pnpm >/dev/null || { echo "ERROR: pnpm not on PATH. Run 'corepack enable && corepack prepare pnpm@9 --activate'"; exit 1; }
	pnpm install --frozen-lockfile || pnpm install

.PHONY: install-precommit
install-precommit:  ## Install pre-commit hooks into .git/hooks
	@command -v pre-commit >/dev/null || { echo "ERROR: pre-commit not on PATH. Run 'pipx install pre-commit'"; exit 1; }
	pre-commit install --install-hooks

# =================================================================== dev
.PHONY: dev
dev:  ## Run sidecar + Tauri shell concurrently. Ctrl-C kills both.
	@trap 'echo; echo "Shutting down…"; kill 0' INT TERM EXIT; \
	$(MAKE) -s dev-sidecar & \
	SIDECAR_PID=$$!; \
	sleep 1; \
	$(MAKE) -s dev-app & \
	APP_PID=$$!; \
	wait $$APP_PID $$SIDECAR_PID

.PHONY: dev-sidecar
dev-sidecar:  ## Run only the Python sidecar (foreground)
	cd $(SIDECAR_DIR) && $(PYBIN) -m pinsilico

.PHONY: dev-app
dev-app:  ## Run only the Tauri shell + Vite (foreground)
	cd $(APP_DIR) && pnpm tauri dev

# =================================================================== test
.PHONY: test
test: test-python test-frontend test-rust  ## Run all three test suites

.PHONY: test-python
test-python:  ## Run sidecar pytest suite with coverage gate
	cd $(SIDECAR_DIR) && $(PYBIN) -m pytest

.PHONY: test-frontend
test-frontend:  ## Run vitest suite
	cd $(APP_DIR) && pnpm test

.PHONY: test-rust
test-rust:  ## Run Tauri Rust unit + integration tests
	cd $(APP_DIR)/src-tauri && cargo test --all-targets

# =================================================================== lint
.PHONY: lint
lint: lint-python lint-frontend lint-rust  ## Run all linters and format checks (zero warnings)

.PHONY: lint-python
lint-python:  ## ruff check + ruff format --check + mypy --strict
	cd $(SIDECAR_DIR) && $(PYBIN) -m ruff check .
	cd $(SIDECAR_DIR) && $(PYBIN) -m ruff format --check .
	cd $(SIDECAR_DIR) && $(PYBIN) -m mypy

.PHONY: lint-frontend
lint-frontend:  ## eslint + prettier --check + tsc --noEmit
	cd $(APP_DIR) && pnpm lint
	cd $(APP_DIR) && pnpm format:check
	cd $(APP_DIR) && pnpm typecheck

.PHONY: lint-rust
lint-rust:  ## cargo fmt --check + cargo clippy -- -D warnings
	cd $(APP_DIR)/src-tauri && cargo fmt --check
	cd $(APP_DIR)/src-tauri && cargo clippy --all-targets -- -D warnings

.PHONY: format
format:  ## Auto-fix formatting across all three stacks
	cd $(SIDECAR_DIR) && $(PYBIN) -m ruff check --fix .
	cd $(SIDECAR_DIR) && $(PYBIN) -m ruff format .
	cd $(APP_DIR) && pnpm format
	cd $(APP_DIR)/src-tauri && cargo fmt

# =================================================================== build
.PHONY: build
build: build-app  ## Build production artefacts (Tauri bundles)

.PHONY: build-app
build-app:  ## Build Tauri production bundle for the host OS
	cd $(APP_DIR) && pnpm tauri build

# =================================================================== ci
.PHONY: ci
ci: lint test  ## Run every gate CI runs (lint + test, all stacks)

# =================================================================== clean
.PHONY: clean
clean:  ## Remove build artefacts (target/, dist/, .venv/, caches)
	rm -rf $(VENV) $(SIDECAR_DIR)/.pytest_cache $(SIDECAR_DIR)/.mypy_cache $(SIDECAR_DIR)/.ruff_cache $(SIDECAR_DIR)/htmlcov $(SIDECAR_DIR)/.hypothesis $(SIDECAR_DIR)/coverage.xml
	rm -rf $(APP_DIR)/node_modules $(APP_DIR)/dist $(APP_DIR)/coverage
	rm -rf $(APP_DIR)/src-tauri/target
