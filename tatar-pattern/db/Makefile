-include .env
export
PYTHON ?= ../backend/.venv/bin/python
.PHONY: help up down stop start ps logs psql backup migrate import reset
help:
	@echo 'up / stop / start / ps / logs / psql / backup / migrate'
	@echo 'Safe catalog import: see ../backend/README.md. reset is disabled.'
up:
	docker compose up -d
stop:
	docker compose stop
start:
	docker compose start
down:
	docker compose down
ps:
	docker compose ps
logs:
	docker compose logs -f db
psql:
	docker compose exec db psql -U $(POSTGRES_USER) -d $(POSTGRES_DB)
backup:
	cd ../backend && ../backend/.venv/bin/python -c 'from scripts.db_admin import backup; backup()'
migrate:
	cd ../backend && ../backend/.venv/bin/python -m scripts.migrate
import:
	@echo 'Raw SQL/annotations import is disabled. Use scripts.catalog_import validate, then import with approval digest.'
	@exit 1
reset:
	@echo 'reset is disabled: preserve user data, add migrations, make a backup.'
	@exit 1
