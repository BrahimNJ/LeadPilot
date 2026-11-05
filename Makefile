.PHONY: install run test lint format check docker

install:  ## Install the app and the dev tools in the active virtualenv
	pip install -e ".[dev]"
	pre-commit install

run:  ## Start the API with auto-reload on http://localhost:8000
	uvicorn app.main:app --reload

test:  ## Run the test suite
	pytest

lint:  ## Lint, check formatting and types
	ruff check .
	ruff format --check .
	mypy app

format:  ## Fix lint issues and format the code
	ruff check --fix .
	ruff format .

check: lint test  ## Everything CI runs, except the container build

docker:  ## Build the image and run it in demo mode on http://localhost:8080
	docker build -t leadpilot .
	docker run --rm -p 8080:8080 -e DATABASE_URL=sqlite:////tmp/leadpilot.db -e SEED_DEMO=true leadpilot
