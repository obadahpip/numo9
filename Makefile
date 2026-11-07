# Numo9 developer commands.  Requires Docker with Compose v2 and GNU Make.

COMPOSE_DEV := docker compose -f docker-compose.dev.yml
WAIT_TIMEOUT ?= 900

.PHONY: help up down restart ps logs build clean images

help: ## List available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-10s %s\n", $$1, $$2}'

up: ## Build and start the dev stack; waits until every service is healthy
	$(COMPOSE_DEV) up -d --build --wait --wait-timeout $(WAIT_TIMEOUT)
	$(COMPOSE_DEV) ps

down: ## Stop the dev stack (keeps data volumes)
	$(COMPOSE_DEV) down

restart: down up ## Restart the dev stack

ps: ## Show dev stack service status
	$(COMPOSE_DEV) ps

logs: ## Follow dev stack logs
	$(COMPOSE_DEV) logs -f --tail=100

build: ## Build dev images without starting
	$(COMPOSE_DEV) build

clean: ## Stop the dev stack and remove its data volumes
	$(COMPOSE_DEV) down -v

images: ## Build production (runtime) images for backend and frontend
	docker build --target runtime -t numo9-backend:local backend
	docker build -f frontend/Dockerfile --target runtime -t numo9-frontend:local .
