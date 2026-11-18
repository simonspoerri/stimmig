# Local development. `make` alone lists the targets.
# Postgres runs in Docker (compose.yaml) on localhost:$(PG_PORT). If 5432 is
# taken, use e.g. `make dev PG_PORT=55432` (or put PG_PORT=55432 in .env).
# To use your own Postgres instead: NO_DOCKER=1 PGURL=postgresql://user@host:port

SHELL := /bin/bash
.DEFAULT_GOAL := help
-include .env
NO_DOCKER ?=
export PG_PORT ?= 5432
export PGURL ?= postgresql://postgres@localhost:$(PG_PORT)
PG_HOSTPORT := $(patsubst postgresql://%,%,$(PGURL))

# Node version from .nvmrc. With nvm installed, every target runs on that
# version, whatever your shell's default node is (no `nvm use` needed).
NODE_VERSION := $(shell cat .nvmrc)
NVM_DIR ?= $(HOME)/.nvm
HAS_NVM := $(wildcard $(NVM_DIR)/nvm.sh)
ifneq ($(HAS_NVM),)
NVM_NODE := $(shell . "$(NVM_DIR)/nvm.sh" --no-use && nvm which $(NODE_VERSION) 2>/dev/null)
ifneq ($(filter %/bin/node,$(NVM_NODE)),)
export PATH := $(patsubst %/node,%,$(NVM_NODE)):$(PATH)
endif
endif

.PHONY: help setup install tools deps db db-stop db-reset dev logs check fix evals api-types walkthrough

help: ## Show this help
	@awk 'BEGIN {FS = ":.*## "} /^[a-z-]+:.*## / {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: install db ## One-time setup: install tools and dependencies, start and create databases
	@echo; echo "Ready. Start everything with: make dev"

install: ## Install missing tools (Node via nvm, uv) and all Node and Python dependencies
	@$(MAKE) --no-print-directory tools
	@$(MAKE) --no-print-directory deps # new make, so it picks up a freshly installed node

tools: ## Install Node (.nvmrc) with nvm and uv with Homebrew, if missing (Docker you install yourself)
ifneq ($(HAS_NVM),)
	@. "$(NVM_DIR)/nvm.sh" --no-use && { nvm which $(NODE_VERSION) >/dev/null 2>&1 \
		&& echo "node $$(nvm version $(NODE_VERSION)) found (nvm)" || nvm install $(NODE_VERSION); }
endif
	@command -v uv >/dev/null && echo "uv $$(uv --version | cut -d' ' -f2) found" || { \
		command -v brew >/dev/null || { echo "uv is missing and Homebrew is not installed: see https://docs.astral.sh/uv/"; exit 1; }; \
		echo "installing uv with Homebrew"; brew install uv; }

deps: ## Install Node and Python dependencies (stop `make dev` first)
	@command -v node >/dev/null || { echo "Node.js $(NODE_VERSION) is required: install nvm and run make tools, or see https://nodejs.org"; exit 1; }
	@[[ "$$(node -v)" == v$(NODE_VERSION).* ]] || echo "warning: using node $$(node -v), this repo expects $(NODE_VERSION) (.nvmrc); install nvm and run make tools"
	@command -v uv >/dev/null || { echo "uv is required: run make tools, or see https://docs.astral.sh/uv/"; exit 1; }
	@! pgrep -f scripts/dev.sh >/dev/null || { echo "make dev is running: stop it first, npm ci replaces node_modules under it"; exit 1; }
	npm ci
	cd services/pipeline && uv sync

db: ## Start Postgres and create the dev and test databases
ifeq ($(NO_DOCKER),)
	@command -v docker >/dev/null || { echo "Docker is required (or run with NO_DOCKER=1 and your own Postgres)"; exit 1; }
	docker compose up -d --wait postgres
endif
	scripts/create-databases.sh

db-stop: ## Stop Postgres (data is kept)
	docker compose stop postgres

db-reset: ## Delete all local data and recreate empty databases
	docker compose down -v
	$(MAKE) db

dev: db ## Start identity, pipeline, admin and web (Ctrl-C stops all)
	scripts/dev.sh

logs: ## Follow the logs of all components (login codes are in identity.log)
	@mkdir -p .local/logs
	tail -F .local/logs/*.log

check: db ## Run all checks, as before committing
	TEST_DATABASE_URL=$(PGURL)/stimmig_identity_test npm run check
	cd services/pipeline && TEST_DATABASE_URL=postgresql+psycopg://$(PG_HOSTPORT)/stimmig_pipeline_test uv run poe check

fix: ## Auto-fix lint and formatting where possible
	npx eslint . --fix
	cd services/pipeline && uv run ruff check --fix . && uv run poe format

evals: ## Run the evals against recorded model answers (no API key needed)
	cd services/pipeline && uv run stimmig-evals

api-types: ## Regenerate packages/api-types after pipeline API changes
	npm run gen:api-types

walkthrough: ## Click through the whole process in a browser (needs `make dev` running and Playwright)
	node scripts/walkthrough.mjs
