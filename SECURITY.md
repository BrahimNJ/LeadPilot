# Security policy

## Reporting a vulnerability

Please use GitHub's private reporting: **Security → Report a vulnerability** on this
repository. Please don't open a public issue for a security problem.

Only the latest release is supported.

## What the application does today

- Validates every request body and query parameter against a schema
- Uses parameterised queries through SQLAlchemy; `%` and `_` in search terms are plain text
- Sends security headers on every response, and returns a generic 500 with a request ID
- Limits request body size, and optionally requests per client (`RATE_LIMIT_PER_MINUTE`)
- Treats CRM content as data in copilot prompts (see [ADR 0001](docs/adr/0001-copilot-boundary.md))
- Runs in the container as a non-root user

## Known limits

- **There is no authentication yet.** Any client that can reach the API can read and change
  everything. A deployment holding real data must stay private
  (`--no-allow-unauthenticated`, as in the [deployment guide](docs/deploy-gcp.md)).
- The rate limiter counts per process, so with several instances the limit is per instance.
- The public demo holds sample data only. Anyone can edit it, and it resets regularly.
