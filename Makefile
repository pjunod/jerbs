.PHONY: lint test preview preview-cards build help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

lint: ## Run linter and formatter check
	ruff check .
	ruff format --check .

format: ## Auto-format code
	ruff format .

test: ## Run unit tests
	python -m pytest tests/ -q

preview: ## Generate and open HTML results preview (terminal theme)
	@python shared/scripts/export_html.py tests/fixtures/sample_results.json tests/fixtures/preview.html
	@open tests/fixtures/preview.html

preview-cards: ## Generate and open HTML results preview (cards theme)
	@python shared/scripts/export_html.py tests/fixtures/sample_results.json tests/fixtures/preview.html --theme cards
	@open tests/fixtures/preview.html

build: ## Rebuild the claude-web .skill package
	./scripts/build_skill.sh

ci: lint test build ## Run full CI check locally
