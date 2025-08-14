dc = docker compose -f compose.dev.yaml

.PHONY: run-dev down-dev build-dev clean-dev logs-dev restart-dev ps-dev migrate-up-dev migrate-down-dev rebuild-dev

info:
	$(dc) ps

run-dev:
	$(dc) up

down-dev:
	$(dc) down

build-dev:
	$(dc) build

clean-dev:
	$(dc) down --rmi all --volumes --remove-orphans

logs-dev:
	$(dc) logs -f

restart-dev:
	$(dc) restart

ps-dev:
	$(dc) ps

rebuild-dev: clean-dev build-dev run-dev
