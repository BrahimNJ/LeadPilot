# How LeadPilot works

For how to use the API, see the [user guide](user-guide.md).

## Architecture

LeadPilot is a single FastAPI service in front of a relational database, with an optional
call to Claude.

```mermaid
flowchart LR
    client[API client or browser] --> mw[Middleware]
    mw --> routers[Routers]
    routers --> domain[Pipeline rules]
    routers --> db[(PostgreSQL or SQLite)]
    routers --> port{{Copilot protocol}}
    port --> offline[Offline rules]
    port --> claude[Claude API]
```

| Folder | Role | Depends on |
| --- | --- | --- |
| `app/domain/` | Business rules | Nothing: plain Python |
| `app/ai/` | The copilot and what the model reads | Domain, models |
| `app/routers/` | HTTP endpoints | Everything above |
| `app/models.py` | Database tables | SQLAlchemy |
| `app/schemas.py` | What goes in and out of the API | Pydantic |
| `app/middleware.py` | Checks applied to every request | FastAPI |

## The life of a request

Take `POST /deals/1/stage`. Going through the layers from the outside in:

1. **CORS**, only if `CORS_ORIGINS` is set.
2. **Request ID**: reuses a harmless incoming `X-Request-ID` or creates one, then logs the
   method, path, status and duration.
3. **Security headers** are added to the response.
4. **Rate limit**, if enabled. Over the limit, the request stops here with a `429`.
5. **Body limit**: a body that is too large stops here with a `413`.
6. **FastAPI** matches the route and validates the input against a schema (`422` if invalid).
7. **The router** opens a database session for this request and loads the deal (`404` if missing).
8. **The domain** decides: `check_transition` accepts the move or raises an error with a reason.
9. **The router** commits and returns the deal as JSON.

Anything unexpected is caught at the very top: the traceback goes to the logs, and the client
gets a generic `500` with the request ID.

## Data model

```mermaid
erDiagram
    COMPANY |o--o{ CONTACT : employs
    CONTACT ||--o{ DEAL : has
    CONTACT ||--o{ ACTIVITY : has
    COMPANY {
        string name
        string domain UK
        string industry
        string size
    }
    CONTACT {
        string email UK
        string role
        datetime last_contacted_at
        int score
        json score_details
        string score_model
    }
    DEAL {
        string title
        int amount
        string stage
        date expected_close
        datetime closed_at
    }
    ACTIVITY {
        string kind
        string subject
        text body
        datetime occurred_at
    }
```

Foreign keys carry the delete rules: a company's contacts are unlinked (`SET NULL`), a contact's
deals and activities are removed (`CASCADE`). SQLite only applies these when asked to on each
connection, which `build_engine` does.

Amounts are whole euros: deal sizes are estimates, so cents would be false precision.

## Pipeline rules

```mermaid
stateDiagram-v2
    direction LR
    [*] --> lead
    lead --> qualified
    qualified --> proposal
    proposal --> negotiation
    negotiation --> won
    lead --> lost
    qualified --> lost
    proposal --> lost
    negotiation --> lost
    won --> [*]
    lost --> [*]
```

Stages can also be skipped going forward, except `won`, which needs `negotiation`. Going back
is refused because it would hide how long a deal really took. The rules live in
`app/domain/pipeline.py`, with no web or database code, so they are tested on their own.
