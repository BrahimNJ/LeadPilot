# LeadPilot documentation

| I want to | Read |
| --- | --- |
| Use the API, step by step | [User guide](user-guide.md) |
| Understand how it is built | [How it works](how-it-works.md) |
| See every setting | [Configuration](configuration.md) |
| Deploy it | [Deployment on Cloud Run](deploy-gcp.md) |
| Report a security problem | [Security policy](../SECURITY.md) |
| Contribute | [Contributing guide](../CONTRIBUTING.md) |

## Architecture decisions

1. [A narrow boundary between the CRM and the language model](adr/0001-copilot-boundary.md)
2. [A public demo on SQLite, with no database server](adr/0002-public-demo-on-sqlite.md)
3. [An in-memory rate limiter](adr/0003-in-memory-rate-limit.md)
