# Contributing

Thanks for taking the time to look at LeadPilot. Issues and pull requests are welcome.

## Set up

```bash
python -m venv .venv
source .venv/bin/activate        # on Windows: .venv\Scripts\activate
make install                     # or: pip install -e ".[dev]" && pre-commit install
make run                         # http://localhost:8000/docs
```

Without `ANTHROPIC_API_KEY` the copilot runs on its offline rules, so you don't need a key
to work on the project. Tests never call the real API.

## Before you open a pull request

```bash
make check     # ruff, ruff format, mypy (strict) and pytest with coverage
```

CI runs the same checks, runs the tests a second time on PostgreSQL 17, audits the
dependencies, and builds the Docker image and checks that it starts.

To run the tests on PostgreSQL yourself, point `TEST_DATABASE_URL` at an empty database:

```bash
docker run -d --name leadpilot-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=leadpilot_test \
  -p 5432:5432 postgres:17
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/leadpilot_test pytest
```

The tests drop and recreate every table in that database.

## Conventions

- **One issue per pull request.** Open an issue first for anything bigger than a small fix.
- **Commit messages** follow [Conventional Commits](https://www.conventionalcommits.org/):
  `feat(deals): ...`, `fix(db): ...`, `test: ...`, `docs: ...`, `ci: ...`, `chore: ...`
- **Small commits** that each pass the checks: the history is merged as is.
- **Tests come with the change.** A bug fix starts with a test that shows the bug.
- **Business rules stay in `app/domain/`**, free of FastAPI and SQLAlchemy.
- **Anything sent to the model goes through `app/ai/context.py`**: see
  [ADR 0001](docs/adr/0001-copilot-boundary.md) before changing the copilot.
