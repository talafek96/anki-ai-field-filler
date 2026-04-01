.PHONY: help install lint format test typecheck check build clean release

.DEFAULT_GOAL := help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install dev dependencies
	uv sync --group dev

lint: ## Run ruff linter
	uv run ruff check .

format: ## Auto-format code with ruff
	uv run ruff format .
	uv run ruff check . --fix

typecheck: ## Run mypy type checker
	uv run mypy --package ai_field_filler

test: ## Run tests
	uv run pytest tests/ -v

check: lint typecheck test ## Run all quality checks

build: ## Build .ankiaddon package
	python src/build_ankiaddon.py

clean: ## Remove build artifacts and caches
	rm -rf .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -f ai_field_filler.ankiaddon

release: ## Tag a release (vYYYY.MM.DD or vYYYY.MM.DD-N) and push
	@TODAY=$$(date -u +%Y.%m.%d); \
	EXISTING=$$(git tag -l "v$$TODAY" "v$$TODAY-*" | sort -V); \
	if [ -z "$$EXISTING" ]; then TAG="v$$TODAY"; \
	else LAST=$$(echo "$$EXISTING" | tail -1); \
		if [ "$$LAST" = "v$$TODAY" ]; then TAG="v$$TODAY-1"; \
		else N=$$(echo "$$LAST" | sed "s/v$$TODAY-//"); TAG="v$$TODAY-$$((N + 1))"; fi; \
	fi; \
	echo "Tagging: $$TAG"; git tag "$$TAG"; git push origin "$$TAG"
