# ============================================================================
# Makefile for arena-improver
# ============================================================================
# Convenient commands for common development tasks.
#
# Usage:
#   make help          Show this help message
#   make install       Install project dependencies
#   make dev           Install development dependencies
#   make test          Run tests
#   make lint          Run linters
#   make format        Format code
#   make clean         Clean build artifacts
#
# Last updated: 2025-11-11
# ============================================================================

.PHONY: help
help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

# ----------------------------------------------------------------------------
# Installation & Setup
# ----------------------------------------------------------------------------

.PHONY: install
install: ## Install production dependencies
	pip install --upgrade pip
	pip install -r requirements.txt

.PHONY: dev
dev: ## Install development dependencies
	pip install --upgrade pip
	pip install -r requirements-dev.txt

.PHONY: dev-editable
dev-editable: ## Install in editable mode with dev dependencies
	pip install --upgrade pip
	pip install -e ".[dev]"

.PHONY: hooks
hooks: ## Install pre-commit hooks
	pre-commit install
	pre-commit install --hook-type commit-msg

# ----------------------------------------------------------------------------
# Code Quality
# ----------------------------------------------------------------------------

.PHONY: lint
lint: ## Run all linters
	@echo "Running Ruff linter..."
	ruff check .
	@echo "Running MyPy type checker..."
	mypy .
	@echo "Running Bandit security linter..."
	bandit -r . -c pyproject.toml
	@echo "Running Pylint..."
	@if [ -d src ]; then pylint src/; else echo "Warning: src/ directory not found, skipping pylint."; fi

.PHONY: lint-fix
lint-fix: ## Run linters with auto-fix
	ruff check --fix .
	ruff format .

.PHONY: format
format: ## Format code with Ruff and Black
	ruff format .
	ruff check --fix .
	isort .

.PHONY: type-check
type-check: ## Run type checking
	mypy .

.PHONY: security
security: ## Run security checks
	bandit -r . -c pyproject.toml
	pip-audit
	safety check

# ----------------------------------------------------------------------------
# Testing
# ----------------------------------------------------------------------------

.PHONY: test
test: ## Run tests
	pytest

.PHONY: test-verbose
test-verbose: ## Run tests with verbose output
	pytest -v

.PHONY: test-coverage
test-coverage: ## Run tests with coverage report
	pytest --cov=. --cov-report=html --cov-report=term-missing

.PHONY: test-fast
test-fast: ## Run tests in parallel
	pytest -n auto

.PHONY: test-watch
test-watch: ## Run tests in watch mode
	ptw -- -v

.PHONY: test-workflows
test-workflows: ## Run workflow YAML validation tests
	pytest tests/unit/test_workflow_yaml.py -v --noconftest

# ----------------------------------------------------------------------------
# Pre-commit
# ----------------------------------------------------------------------------

.PHONY: pre-commit
pre-commit: ## Run pre-commit on all files
	pre-commit run --all-files

.PHONY: pre-commit-update
pre-commit-update: ## Update pre-commit hooks
	pre-commit autoupdate

# ----------------------------------------------------------------------------
# Documentation
# ----------------------------------------------------------------------------

.PHONY: docs
docs: ## Build documentation
	cd docs && make html

.PHONY: docs-serve
docs-serve: ## Serve documentation locally
	cd docs && python -m http.server 8000 --directory _build/html

.PHONY: docs-clean
docs-clean: ## Clean documentation build
	cd docs && make clean

# ----------------------------------------------------------------------------
# Dependencies
# ----------------------------------------------------------------------------

.PHONY: deps-compile
deps-compile: ## Compile requirements files
	pip-compile requirements.in -o requirements.txt
	pip-compile requirements-dev.in -o requirements-dev.txt

.PHONY: deps-upgrade
deps-upgrade: ## Upgrade all dependencies
	pip-compile --upgrade requirements.in -o requirements.txt
	pip-compile --upgrade requirements-dev.in -o requirements-dev.txt

.PHONY: deps-sync
deps-sync: ## Sync installed packages with requirements
	pip-sync requirements.txt requirements-dev.txt

.PHONY: deps-tree
deps-tree: ## Show dependency tree
	pipdeptree

.PHONY: deps-audit
deps-audit: ## Audit dependencies for vulnerabilities
	pip-audit
	safety check

# ----------------------------------------------------------------------------
# Build & Distribution
# ----------------------------------------------------------------------------

.PHONY: build
build: ## Build distribution packages
	python -m build

.PHONY: build-check
build-check: ## Check distribution package
	twine check dist/*

.PHONY: upload-test
upload-test: ## Upload to TestPyPI
	twine upload --repository testpypi dist/*

.PHONY: upload
upload: ## Upload to PyPI
	twine upload dist/*

# ----------------------------------------------------------------------------
# Cleanup
# ----------------------------------------------------------------------------

.PHONY: clean
clean: ## Clean build artifacts and cache files
	@echo "Cleaning build artifacts..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .eggs/
	@echo "Cleaning Python cache..."
	find . -type d -name '__pycache__' -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
	find . -type f -name '*.pyo' -delete
	find . -type f -name '*.py,cover' -delete
	@echo "Cleaning test artifacts..."
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	@echo "Cleaning documentation..."
	rm -rf docs/_build/
	@echo "Done!"

.PHONY: clean-all
clean-all: clean ## Clean everything including virtual environments
	rm -rf .venv/
	rm -rf venv/
	rm -rf .tox/

# ----------------------------------------------------------------------------
# Development Utilities
# ----------------------------------------------------------------------------

.PHONY: shell
shell: ## Start IPython shell
	ipython

.PHONY: check
check: lint type-check test test-workflows ## Run all checks (lint, type-check, test, workflow validation)

.PHONY: ci
ci: check security ## Run CI pipeline locally

.PHONY: version
version: ## Show Python and tool versions
	@echo "Python version:"
	@python --version
	@echo "\nPip version:"
	@pip --version
	@echo "\nInstalled tools:"
	@pip list | grep -E "(pytest|ruff|mypy|black|isort)" || true

.PHONY: requirements-check
requirements-check: ## Check if requirements are synced
	pip check

# ----------------------------------------------------------------------------
# Git Utilities
# ----------------------------------------------------------------------------

.PHONY: git-clean
git-clean: ## Clean git ignored files (use with caution)
	git clean -fdX

.PHONY: git-reset-hard
git-reset-hard: ## Hard reset to HEAD (use with caution)
	@echo "Warning: This will discard all uncommitted changes!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		git reset --hard HEAD; \
	fi

# ============================================================================
# Default target
# ============================================================================

.DEFAULT_GOAL := help

# ============================================================================
# Notes:
# ============================================================================
# - Run 'make help' to see all available targets
# - Most targets assume you're in a virtual environment
# - Some targets require additional tools to be installed
# - For production builds, always run 'make ci' first
# ============================================================================
