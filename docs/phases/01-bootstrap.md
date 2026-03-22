# Phase 01: Bootstrap

## Intent

Create the local repo, project structure, docs, CLI shell, schema module, and Alembic wiring.

## Implementation Decisions

- initialize git inside `ibkr/`
- use `uv` and a repo-local `.venv`
- use SQLite as the only database backend
- keep raw data and derived outputs out of git
- create the schema in code and keep Alembic available for future migrations

## Interfaces Touched

- `uv sync`
- `source .venv/bin/activate`
- `ibkr-trace --help`

## Acceptance Tests

- project installs into `.venv`
- `ibkr-trace --help` works
- database path resolves under `data/db/`

## PR Checklist

- repo initialized
- docs committed
- `.gitignore` committed
- `pyproject.toml` committed
- schema module committed
- Alembic scaffolding committed
