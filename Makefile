SHELL := /bin/bash
PYTHON ?= python3.11
VENV ?= .venv
export PATH := $(VENV)/bin:$(PATH)

.PHONY: help
help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

.PHONY: setup
setup: ## Create virtualenv and install dev dependencies
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements-dev.txt

.PHONY: run
run: ## Run the app locally against Redis (docker compose)
	docker compose up --build

.PHONY: test
test: ## Run unit tests with coverage
	$(VENV)/bin/pytest --cov=app --cov-report=term-missing

.PHONY: lint
lint: ## Lint and format with ruff
	$(VENV)/bin/ruff check .
	$(VENV)/bin/ruff format --check .

.PHONY: security
security: ## Local security checks (bandit + pip-audit)
	$(VENV)/bin/bandit -c pyproject.toml -r app -lll
	$(VENV)/bin/pip-audit -r requirements.txt

.PHONY: precommit
precommit: ## Install pre-commit hooks
	$(VENV)/bin/pre-commit install

.PHONY: sbom
sbom: ## Generate CycloneDX SBOM
	$(VENV)/bin/cyclonedx-py environment -o sbom.json

.PHONY: licenses
licenses: ## Generate license report and enforce policy
	$(VENV)/bin/pip-licenses --format=csv --output-file=licenses.csv
	$(VENV)/bin/python scripts/license_check.py licenses.csv

.PHONY: helm-lint
helm-lint: ## Lint and render the Helm chart
	helm lint helm/appointment-service
	helm template appointment-service helm/appointment-service -f helm/appointment-service/values-dev.yaml > /tmp/rendered.yaml

.PHONY: secrets
secrets: ## Scan for leaked secrets with Gitleaks
	gitleaks detect --config=.gitleaks.toml --source=. --report-path=gitleaks-report.json
