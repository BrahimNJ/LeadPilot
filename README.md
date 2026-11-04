# LeadPilot

[![CI](https://github.com/BrahimNJ/LeadPilot/actions/workflows/ci.yml/badge.svg)](https://github.com/BrahimNJ/LeadPilot/actions/workflows/ci.yml)
![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)
![License: MIT](https://img.shields.io/badge/license-MIT-blue)

LeadPilot is a small CRM with an AI copilot.

You keep your contacts, companies and deals in one place, you log your calls and
meetings, and the copilot helps with the questions that come back every morning:

- **Who should I call first?** Each contact gets a score from 0 to 100, with the reasons.
- **Where are we with this client?** A short summary and the next step to take.
- **What do I write?** A follow-up email draft, in French or English, that you review and send yourself.

I built it to learn how to put a language model inside a real application: with tests,
clear limits on what the model sees, and a version that still works when the AI does not.

## Features

- Contacts and companies, with search and pagination
- A deals pipeline (`lead → qualified → proposal → negotiation → won / lost`) that only moves forward
- A timeline of notes, calls, emails and meetings for each contact
- Lead scoring, relationship summaries and follow-up drafts powered by Claude
- An offline mode: without an API key, simple rules take over, so the app runs anywhere

## Tech stack

Python · FastAPI · SQLAlchemy 2 · PostgreSQL (SQLite locally) · Claude API ·
pytest · Docker · GitHub Actions · Google Cloud Run

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

Then open <http://localhost:8000/docs>: every endpoint can be tried from there.

To use Claude, put your key in `.env` (`ANTHROPIC_API_KEY=...`). Leave it empty to stay
in offline mode.

## Try it

```bash
# Create a contact, a deal and a meeting
curl -X POST localhost:8000/contacts -H "content-type: application/json" \
  -d '{"first_name": "Sarah", "last_name": "Klein", "email": "sarah@example.com", "role": "CTO"}'

curl -X POST localhost:8000/deals -H "content-type: application/json" \
  -d '{"title": "Pilot project", "amount": 15000, "contact_id": 1}'

curl -X POST localhost:8000/contacts/1/activities -H "content-type: application/json" \
  -d '{"kind": "meeting", "subject": "Demo with the tech team"}'

# Ask the copilot
curl -X POST localhost:8000/contacts/1/score
curl -X POST localhost:8000/contacts/1/insights
curl -X POST localhost:8000/contacts/1/follow-up -H "content-type: application/json" \
  -d '{"language": "en", "goal": "Get a date for the security review"}'
```

## How the AI part works

A few choices I made, explained in more detail in [ADR 0001](docs/adr/0001-copilot-boundary.md):

- **The model only sees what we send.** One function builds the text sent to Claude, so it
  is easy to check what leaves the CRM.
- **Answers have a fixed shape.** Claude replies in a format checked against a schema
  (structured outputs), so the app never has to guess what the text means.
- **Customer emails are treated as data.** If a prospect writes "ignore your
  instructions", the copilot reads it as a sentence, not as an order.
- **Failures stay readable.** If the AI is down, the API answers `503` with a clear
  message instead of crashing.
- **A human decides.** Email drafts are only drafts: nothing is sent automatically.

## Project structure

```text
app/
├── ai/          # the copilot: Claude, offline rules, what the model reads
├── domain/      # business rules (pipeline stages)
├── routers/     # HTTP endpoints
├── models.py    # database tables
└── main.py      # application setup
tests/           # 43 tests, no network needed
docs/            # architecture decision and deployment guide
```

## Tests

```bash
ruff check . && mypy app && pytest
```

The same checks run on every pull request, and CI also builds the Docker image and
checks that it starts.

## Deployment

LeadPilot is meant to run on Google Cloud Run with a Cloud SQL database. The steps are in
[docs/deploy-gcp.md](docs/deploy-gcp.md).

## What's next

- Put a live demo online
- Add authentication
- Database migrations with Alembic
- Search the timeline by meaning, not only by keyword
- A simple web interface

## License

MIT. See [LICENSE](LICENSE).

---

Made by [Brahim NAJI](https://github.com/BrahimNJ). Feedback and questions are welcome
in the issues.
