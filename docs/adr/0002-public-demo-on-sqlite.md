# 2. A public demo on SQLite, with no database server

- Status: accepted
- Date: 2026-11-05

## Context

Visitors should be able to try LeadPilot without installing anything. The demo must cost
nothing while idle and must not be able to run up a bill.

## Decision

The demo is a separate Cloud Run service that scales to zero, with at most one instance. It uses
SQLite in `/tmp`, is filled with sample data at startup, and has no Anthropic key, so the
copilot uses its offline rules. Its service account has no role on the project.

## Consequences

- No fixed cost: Cloud SQL would be billed even with no visitors.
- A public URL can't generate Claude API charges.
- Data disappears when the instance stops. For sample data, that is a feature.
- Everyone shares one instance, which is what makes a single SQLite file consistent.
- The demo doesn't exercise PostgreSQL. The production path remains the Cloud SQL guide.
