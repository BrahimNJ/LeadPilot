# 1. A narrow boundary between the CRM and the language model

- Status: accepted
- Date: 2026-11-04

## Context

LeadPilot uses a language model to score leads and, later, to summarise relationships
and draft follow-ups. We want:

- tests that run offline, fast and for free;
- a fresh clone that works without an API key;
- the freedom to change model or provider without touching the routers;
- a clear answer to "what customer data leaves the CRM?".

## Decision

1. The routers depend on a small `Copilot` protocol (`app/ai/copilot.py`), never on an SDK.
2. Two implementations:
   - `ClaudeCopilot` calls Claude through the official `anthropic` SDK with **structured
     outputs**: the answer is validated against a Pydantic model (`LeadScore`) before the
     app sees it. Effort is configurable (`LLM_EFFORT`, default `medium`) and a refusal is
     retried on a fallback model by the API itself.
   - `OfflineCopilot` scores with a few transparent rules. It is selected automatically
     when `ANTHROPIC_API_KEY` is empty and is what the tests use.
3. Everything the model reads is produced by one function, `app/ai/context.py::render`,
   wrapped in `<crm_record>` tags. The system prompt states that this block is data, so a
   prospect's email that says "ignore your instructions" is just text to analyse.
4. Failures map to HTTP errors the client can act on: `503` when the provider is down or
   the answer cannot be read, `422` when the model declines. Never a `500`.
5. Each stored score keeps its explanation and the name of the model that produced it.

## Consequences

- Adding a provider means writing one class; no router changes.
- The SDK path is still tested: `tests/test_copilot.py` runs the real SDK against a fake
  HTTP transport and checks the request we send as well as how we read the answer.
- The offline rules are deliberately simple. They are a fallback and a test double,
  not a second scoring model to maintain.
