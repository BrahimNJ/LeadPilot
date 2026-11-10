# LeadPilot user guide

This guide walks through a typical sales day with the API. Every example was run against
the app and can be copied as is.

## Where to try it

- **Public demo:** <https://leadpilot-demo-865877702597.europe-west1.run.app> opens the
  interactive docs, with sample data. Click an endpoint, then **Try it out**. The demo resets
  itself after a few idle minutes and allows 120 requests per minute.
- **On your machine:** follow [Getting started](../README.md#getting-started), then open
  <http://localhost:8000/docs>. To start with the sample data, set `SEED_DEMO=true` in `.env`.

The `curl` examples below use a local server. For the demo, replace `localhost:8000` with its
address and add `-d ''` to a `POST` that has no body: Google's front end requires a length.

## Companies and contacts

Create a company, then a contact who works there:

```bash
curl -X POST localhost:8000/companies -H "content-type: application/json" \
  -d '{"name": "Kibo Logistics", "domain": "kibo.example.com", "size": "201-1000"}'

curl -X POST localhost:8000/contacts -H "content-type: application/json" \
  -d '{"first_name": "Sarah", "last_name": "Klein", "email": "sarah@example.com", "role": "CTO", "company_id": 1}'
```

A contact's email and a company's domain are unique: a duplicate answers `409`. Company size
is one of `1-10`, `11-50`, `51-200`, `201-1000` or `1000+`.

Find them again:

| I want to | Call |
| --- | --- |
| Search contacts by name or email | `GET /contacts?q=klein` |
| Search companies by name or domain | `GET /companies?q=kibo` |
| See who works at a company | `GET /companies/1/contacts` |
| See my best leads first | `GET /contacts?sort=score` |
| Keep only hot leads | `GET /contacts?min_score=70` |

Lists come back as a page: `items`, `total`, `limit` (20 by default, 100 at most) and `offset`.

Deleting a company keeps its contacts and unlinks them. Deleting a contact also deletes their
deals and activities.

## Deals

A deal belongs to one contact and starts at the `lead` stage:

```bash
curl -X POST localhost:8000/deals -H "content-type: application/json" \
  -d '{"title": "Route planning pilot", "amount": 15000, "contact_id": 1, "expected_close": "2027-03-31"}'
```

Move it along the pipeline with its own endpoint:

```bash
curl -X POST localhost:8000/deals/1/stage -H "content-type: application/json" \
  -d '{"stage": "qualified"}'
```

The stages are `lead`, `qualified`, `proposal`, `negotiation`, then `won` or `lost`. The rules:

- A deal can skip stages: a warm referral can go straight to `proposal`.
- A deal can't go back.
- A deal can only be won from `negotiation`.
- Any open deal can be lost.
- A won or lost deal no longer moves.

A refused move answers `422` and says why, for example
`{"detail": "a deal can only be won from negotiation"}`.

`PUT /deals/{id}` changes the title, amount, contact and expected close date, never the stage.
`GET /deals?stage=proposal` filters the list and `GET /deals/pipeline` gives the number and
value of deals in each stage.

`GET /deals?overdue=true` keeps the open deals whose expected close date has passed: the ones
to update or chase. Deals without a date never count as overdue.

## The activity timeline

Log what happens with a contact. The kind is `note`, `call`, `email` or `meeting`:

```bash
curl -X POST localhost:8000/contacts/1/activities -H "content-type: application/json" \
  -d '{"kind": "call", "subject": "Budget check", "body": "Approval expected next quarter."}'
```

`GET /contacts/1/activities` returns the timeline, newest first.

To log something that happened earlier, add `occurred_at` with a timezone, such as
`"2026-11-02T14:30:00+01:00"`. The contact's `last_contacted_at` only moves forward, so
logging an old call doesn't make the contact look recently touched.

## The copilot

The copilot reads one contact at a time: their details, company, deals and activities.

**Who should I call first?**

```bash
curl -X POST localhost:8000/contacts/1/score
```

```json
{
  "lead": {
    "score": 90,
    "temperature": "hot",
    "reasons": ["Open deal 'Route planning pilot' in negotiation", "Contacted 2 days ago"],
    "risks": []
  },
  "model": "offline-rules"
}
```

Temperature is `hot` from 70, `warm` from 40 and `cold` below. The score is saved on the
contact, which is what `sort=score` and `min_score` use. `model` tells you what produced it.

**Where are we with this client?** `POST /contacts/1/insights` returns a short summary, the
open questions and one next action.

**What do I write?**

```bash
curl -X POST localhost:8000/contacts/1/follow-up -H "content-type: application/json" \
  -d '{"language": "en", "goal": "Get a date for the security review"}'
```

This returns a `subject` and a `body`, in `fr` (the default) or `en`. It is only a draft:
LeadPilot sends nothing and stores nothing, you stay in control.

**Offline or Claude?** Without `ANTHROPIC_API_KEY`, as on the public demo, a set of simple
rules answers and `model` is `offline-rules`. Those rules don't use the `goal`. With a key,
Claude answers from the same data.

## The sales overview

`GET /stats` gives the headline numbers:

```json
{
  "companies": 3,
  "contacts": 5,
  "open_deals": 3,
  "open_pipeline_amount": 65000,
  "won_deals": 1,
  "lost_deals": 1,
  "win_rate": 0.5
}
```

`win_rate` is won / (won + lost). It is `null` until a deal is closed.

## When something goes wrong

Errors are JSON with a `detail` field.

| Status | Meaning | What to do |
| --- | --- | --- |
| `404` | The record doesn't exist | Check the ID |
| `409` | The email or domain is already used | Find the existing record |
| `411` | The body was sent in chunks | Send a normal body with its length |
| `413` | The body is too large (1 MB by default) | Send less |
| `422` | Invalid data, a refused pipeline move, or the AI declined | Read `detail` |
| `429` | Too many requests | Wait for the seconds given in `Retry-After` |
| `500` | A bug on our side | Report the `request_id` from the answer |
| `503` | The AI provider is unavailable | Retry shortly; the rest of the API still works |

Every response has an `X-Request-ID` header. Include it when you report a problem: it points
to the matching line in the logs.
