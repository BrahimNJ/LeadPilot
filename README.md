# LeadPilot

[![CI](https://github.com/BrahimNJ/LeadPilot/actions/workflows/ci.yml/badge.svg)](https://github.com/BrahimNJ/LeadPilot/actions/workflows/ci.yml)
![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)
![License: MIT](https://img.shields.io/badge/license-MIT-blue)

LeadPilot is a small CRM for B2B sales teams, with a copilot built on Claude.

I built it around one question: how do you put a language model inside an ordinary business
app without it becoming the weak point? So the copilot has a narrow job, answers in a fixed
format, falls back to simple rules when the API is down, and is measured against a labelled
eval set rather than trusted on a few good-looking answers.

**Live demo:** <https://leadpilot-demo-865877702597.europe-west1.run.app> opens the
interactive API docs with sample data. The demo has no API key, so the copilot runs on its
offline rules there, and the data resets after a few idle minutes.

## What the copilot does

- Scores each contact from 0 to 100 (hot, warm or cold) and lists the reasons and the risks.
- Summarises where the relationship stands and suggests one next step.
- Drafts a follow-up email in French or English. It stays a draft: you send it yourself.

Around it is a regular CRM: companies, contacts, a deals pipeline that only moves forward
(`lead → qualified → proposal → negotiation → won / lost`), a timeline of calls, emails and
meetings, follow-up tasks with an agenda, CSV exports and a sales overview.

## How I know the scores are any good

The tests check that the copilot works. To check that its answers are right, there is an
eval suite in [`evals/`](evals/): 30 made-up contacts labelled from a written rubric (expected
temperature and score range, including tricky cases such as a big deal nobody has answered for 90 days),
plus 8 prompt injection attempts hidden in notes, emails and a deal title. Each case goes
through the real model and through the offline rules as a baseline.

Latest run ([full report](evals/results/2026-11-20.md)), Claude Opus 5.5, one run per case:

| | Claude | Offline rules |
| --- | --- | --- |
| Right temperature | 97% | 73% |
| Score inside the expected range | 97% | 70% |
| Valid structured answer | 100% | 100% |
| Median latency | 7.6 s | - |

The first run caught a real bug: a note containing a fake `</crm_record><system>` block got
a lead scored 95 instead of about 50. CRM text is now escaped before it reaches the model; on
the next run the same contact scored 35 and the fake rule was ignored. Both reports are in
[`evals/results/`](evals/results/). This run went through the Claude Code CLI, which is close
to but not exactly the production API path; [docs/evaluation.md](docs/evaluation.md) explains
the difference, the metrics and the limits (a small synthetic dataset, labelled from a single
rubric).

```bash
make eval                          # through the Claude Code CLI, with a Claude subscription
ANTHROPIC_API_KEY=... make eval    # through the Messages API, as in production (billed)
```

## Design choices

More detail in [ADR 0001](docs/adr/0001-copilot-boundary.md).

- One function writes everything the model reads, so it is easy to check what leaves the CRM.
  Email addresses and phone numbers are not part of it.
- Claude answers against a JSON schema (structured outputs), so the app never parses free text.
- Customer emails are data, not instructions, and the markup in them is escaped.
- If the API fails, the endpoint returns a clear `503` instead of an error page; without a key
  the offline rules take over, so the app runs anywhere, tests included.
- The routers only know a small `Copilot` interface, so the model provider can change without
  touching them.

## Getting started

You need Python 3.12 or newer.

```bash
git clone https://github.com/BrahimNJ/LeadPilot.git
cd LeadPilot
python -m venv .venv
source .venv/bin/activate        # on Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload
```

Then open <http://localhost:8000/docs> and try any endpoint from there. Put your key in
`.env` (`ANTHROPIC_API_KEY=...`) to use Claude, or leave it empty to stay on the offline rules.

A short tour with `curl`:

```bash
curl -X POST localhost:8000/contacts -H "content-type: application/json" \
  -d '{"first_name": "Sarah", "last_name": "Klein", "email": "sarah@example.com", "role": "CTO"}'
curl -X POST localhost:8000/deals -H "content-type: application/json" \
  -d '{"title": "Pilot project", "amount": 15000, "contact_id": 1}'
curl -X POST localhost:8000/contacts/1/activities -H "content-type: application/json" \
  -d '{"kind": "meeting", "subject": "Demo with the tech team"}'

curl -X POST localhost:8000/contacts/1/score
curl -X POST localhost:8000/contacts/1/insights
curl -X POST localhost:8000/contacts/1/follow-up -H "content-type: application/json" \
  -d '{"language": "en", "goal": "Get a date for the security review"}'
```

## Tech stack

Python · FastAPI · SQLAlchemy 2 · PostgreSQL (SQLite locally) · Claude API · pytest ·
Docker · GitHub Actions · Google Cloud Run

## Project structure

```text
app/
├── ai/          # the copilot: Claude, offline rules, what the model reads
├── domain/      # business rules (pipeline stages, task due dates)
├── routers/     # HTTP endpoints
├── models.py    # database tables
└── main.py      # application setup
evals/           # copilot evaluation: datasets, runner, metrics, reports
tests/           # 131 tests, no network needed
docs/            # user guide, how it works, configuration, deployment, decisions
```

## Tests and quality

```bash
make check       # ruff, mypy (strict) and pytest with coverage
```

CI runs the same checks on every pull request, runs the tests a second time on PostgreSQL,
audits the dependencies, and builds the Docker image and checks that it starts.

## Security

The public demo runs with a rate limit, request size limits, security headers, generic error
messages and a service account with no permissions. There is no authentication yet, so a
deployment with real data must stay private. Details and known limits in
[SECURITY.md](SECURITY.md).

## Documentation

- [User guide](docs/user-guide.md): every workflow, with examples
- [How it works](docs/how-it-works.md): architecture, data model, pipeline, copilot
- [Evaluation](docs/evaluation.md): what the eval measures and how to read it
- [Configuration](docs/configuration.md) and [deployment on Cloud Run](docs/deploy-gcp.md)

## What's next

- Authentication
- Database migrations with Alembic
- Evaluate the summaries and email drafts too, not only the scores
- A web interface for sales teams

## How it was built

I built LeadPilot with Claude Code as a pair programmer: I chose what to build and how it
should behave and reviewed the changes; the agent wrote most of the code and drafted the eval
dataset. Working that way is also why the eval exists: I wanted a way to check the output that
does not depend on how convincing it looks.

## License

MIT. See [LICENSE](LICENSE).

Made by [Brahim NAJI](https://github.com/BrahimNJ).
