COMPOSE = docker compose --env-file src/.env -f compose.dev.yml

install:
	uv sync --locked

pre-commit.install:
	uv run pre-commit install

up:
	$(COMPOSE) up -d --build

up.nobuild:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

migrations:
	$(COMPOSE) exec backend alembic -c src/alembic.ini revision --autogenerate -m "$(m)"

migrate:
	$(COMPOSE) exec backend alembic -c src/alembic.ini upgrade head

downgrade:
	$(COMPOSE) exec backend alembic -c src/alembic.ini downgrade -1

migrations.check:
	$(COMPOSE) exec backend alembic -c src/alembic.ini check

lint:
	uv run ruff check src/
	uv run ruff format --check src/
	uv run mypy src/

test:
	uv run pytest
