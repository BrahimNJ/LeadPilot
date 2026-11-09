# Configuration

LeadPilot reads environment variables, and a `.env` file locally. Every variable is optional.

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./leadpilot.db` | SQLAlchemy URL of the database |
| `ANTHROPIC_API_KEY` | empty | Enables Claude. Empty: the copilot uses its offline rules |
| `LLM_MODEL` | `claude-opus-5-5` | Claude model |
| `LLM_EFFORT` | `medium` | `low`, `medium`, `high`, `xhigh` or `max` |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR` |
| `CORS_ORIGINS` | `[]` | Browser origins allowed to call the API, as a JSON list |
| `MAX_BODY_BYTES` | `1048576` | Largest request body accepted |
| `RATE_LIMIT_PER_MINUTE` | `0` | Requests per client and per minute. `0` turns it off |
| `TRUST_FORWARDED_FOR` | `false` | Identify clients by the last `X-Forwarded-For` entry |
| `SEED_DEMO` | `false` | Add sample records to an empty database at startup |

## Notes

- Keep `ANTHROPIC_API_KEY` and any database password in a secret manager in production.
- Set `TRUST_FORWARDED_FOR=true` only behind a proxy that appends the client address, as Cloud
  Run does. Otherwise a client could pick its own identity.
- `CORS_ORIGINS` takes full origins, for example `["https://app.example.com"]`.
