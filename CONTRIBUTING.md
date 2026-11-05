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

CI runs the same checks and also builds the Docker image and checks that it starts.

## Conventions

- **One issue per pull request.** Open an issue first for anything bigger than a small fix.
- **Commit messages** follow [Conventional Commits](https://www.conventionalcommits.org/):
  `feat(deals): ...`, `fix(db): ...`, `test: ...`, `docs: ...`, `ci: ...`, `chore: ...`
- **Small commits** that each pass the checks: the history is merged as is.
- **Tests come with the change.** A bug fix starts with a test that shows the bug.
- **Business rules stay in `app/domain/`**, free of FastAPI and SQLAlchemy.
- **Anything sent to the model goes through `app/ai/context.py`**: see
  [ADR 0001](docs/adr/0001-copilot-boundary.md) before changing the copilot.
