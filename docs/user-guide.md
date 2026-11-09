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
