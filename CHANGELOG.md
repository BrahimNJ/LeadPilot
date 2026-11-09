# Changelog

All notable changes to LeadPilot. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[semantic versioning](https://semver.org/).

## [0.3.0] - 2026-11-09

### Added

- `GET /contacts?sort=score` and `GET /stats`, a sales overview (#33)
- User guide, how-it-works, configuration reference and two ADRs (#34)
- `SECURITY.md` and a dependency audit in CI (#32)

### Security

- Security headers on every response (#32)
- Rate limit per client with `RATE_LIMIT_PER_MINUTE`, and request body limits (#32)
- Unexpected errors return a generic 500 with a request ID (#32)
- The deployment guide uses dedicated, least-privilege service accounts (#32)

### Fixed

- `%` and `_` in search terms no longer act as wildcards, and terms are capped at 100
  characters (#32)

## [0.2.0] - 2026-11-05

### Added

- Edit (`PUT /deals/{id}`) and delete (`DELETE /deals/{id}`) deals (#20)
- Search companies by name or domain with `GET /companies?q=` (#21)
- List a company's contacts with `GET /companies/{id}/contacts` (#21)
- Filter contacts by lead score with `GET /contacts?min_score=` (#21)
- `X-Request-ID` on every response, written in the request log (#22)
- `LOG_LEVEL` and `CORS_ORIGINS` settings (#22)
- Sample data at startup with `SEED_DEMO=true`, and `/` redirects to the docs (#22)
- Public demo on Cloud Run, documented in `docs/deploy-gcp.md` (#22)
- Dependabot, pre-commit hooks, a Makefile, coverage in CI and a contributing guide (#23)

### Fixed

- Foreign keys are now enforced on SQLite: deleting a contact also deletes its deals
  instead of leaving them behind (#19)

## [0.1.0] - 2026-11-04

First release: companies, contacts, a forward-only deals pipeline, an activity timeline,
and a Claude copilot for lead scoring, relationship summaries and follow-up drafts, with
an offline fallback. Container image and Cloud Run deployment guide.

[0.3.0]: https://github.com/BrahimNJ/LeadPilot/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/BrahimNJ/LeadPilot/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/BrahimNJ/LeadPilot/releases/tag/v0.1.0
