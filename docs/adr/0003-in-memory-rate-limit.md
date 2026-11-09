# 3. An in-memory rate limiter

- Status: accepted
- Date: 2026-11-09

## Context

The demo is public and has no authentication, so one client shouldn't be able to monopolise
its single instance.

## Decision

A fixed one-minute window per client, counted in the process (`app/ratelimit.py`). Beyond the
limit the API answers `429` with `Retry-After`. `/health` is exempt.

On Cloud Run, the client is the last entry of `X-Forwarded-For`, the only one added by the
platform. Earlier entries are whatever the caller sent, so they are ignored. The table of
counters is capped: when it is full, new clients share one bucket.

## Consequences

- No extra service to run or pay for, and the limit is exact with one instance.
- With several instances the limit is per instance. A shared store such as Redis would be
  needed before relying on it at scale.
- A fixed window allows a short burst across two windows, which is acceptable here.
- This limits abuse. It does not replace authentication.
