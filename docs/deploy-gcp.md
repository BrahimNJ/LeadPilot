# Deploying LeadPilot on Google Cloud Run

This guide deploys the API on **Cloud Run**, with **Cloud SQL for PostgreSQL** as the
database and **Secret Manager** for the credentials. It takes about twenty minutes the
first time.

```text
            HTTPS
  client ─────────▶ Cloud Run (leadpilot) ──▶ Cloud SQL (PostgreSQL 17)
                          │
                          ├──▶ Secret Manager (DATABASE_URL, ANTHROPIC_API_KEY)
                          └──▶ Claude API
```

## 0. Prerequisites

- A GCP project with billing enabled, and the `gcloud` CLI logged in
- An Anthropic API key (optional: without it the copilot runs on its offline rules)

```bash
export PROJECT_ID=my-project
export REGION=europe-west1
gcloud config set project "$PROJECT_ID"
gcloud services enable run.googleapis.com sqladmin.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com cloudbuild.googleapis.com
```

## 1. Database

```bash
gcloud sql instances create leadpilot-db \
  --database-version=POSTGRES_17 --edition=ENTERPRISE --tier=db-f1-micro --region="$REGION"
gcloud sql databases create leadpilot --instance=leadpilot-db
gcloud sql users create leadpilot --instance=leadpilot-db --password="$(openssl rand -base64 24)"
```

Keep the password you generated: it goes into the connection string below.

## 2. Secrets

Cloud Run reaches Cloud SQL through a Unix socket mounted under `/cloudsql`:

```bash
INSTANCE="$PROJECT_ID:$REGION:leadpilot-db"
printf 'postgresql+psycopg://leadpilot:PASSWORD@/leadpilot?host=/cloudsql/%s' "$INSTANCE" \
  | gcloud secrets create database-url --data-file=-
printf '%s' "$ANTHROPIC_API_KEY" | gcloud secrets create anthropic-api-key --data-file=-
```

Create a service account for the app, with access to these secrets and to Cloud SQL and
nothing else. Don't use the default Compute Engine account: it usually has the Editor role
on the whole project, so a flaw in the app would expose everything else in it.

```bash
gcloud iam service-accounts create leadpilot-runtime --display-name="LeadPilot runtime"
SA="leadpilot-runtime@$PROJECT_ID.iam.gserviceaccount.com"
for secret in database-url anthropic-api-key; do
  gcloud secrets add-iam-policy-binding "$secret" \
    --member="serviceAccount:$SA" --role=roles/secretmanager.secretAccessor
done
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$SA" --role=roles/cloudsql.client
```

## 3. Build and deploy

```bash
gcloud artifacts repositories create leadpilot --repository-format=docker --location="$REGION"
IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/leadpilot/api:$(git rev-parse --short HEAD)"
gcloud builds submit --tag "$IMAGE"

gcloud run deploy leadpilot \
  --image="$IMAGE" --region="$REGION" \
  --service-account="$SA" \
  --add-cloudsql-instances="$INSTANCE" \
  --set-secrets=DATABASE_URL=database-url:latest,ANTHROPIC_API_KEY=anthropic-api-key:latest \
  --set-env-vars=LLM_MODEL=claude-opus-5-5,LLM_EFFORT=medium \
  --min-instances=0 --max-instances=3 --memory=512Mi \
  --no-allow-unauthenticated
```

`--no-allow-unauthenticated` keeps the API private until authentication lands in the app:
call it with an identity token.

## 4. Check it

```bash
URL="$(gcloud run services describe leadpilot --region="$REGION" --format='value(status.url)')"
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" "$URL/health"
# {"status":"ok","version":"0.2.0","database":"ok"}
```

## Costs

With `min-instances=0` Cloud Run costs nothing while idle. The smallest Cloud SQL tier is
the main fixed cost; stop the instance (`gcloud sql instances patch leadpilot-db
--activation-policy=NEVER`) when you are not using it.

## Public demo, without a database server

For a demo that anyone can open and that costs nothing while idle, skip Cloud SQL and
Secret Manager: the app runs on SQLite inside the container, fills it with sample data
at startup, and the copilot uses its offline rules.

```bash
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com
gcloud artifacts repositories create leadpilot --repository-format=docker --location="$REGION"
IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/leadpilot/api:$(git rev-parse --short HEAD)"
gcloud builds submit --tag "$IMAGE"

# The demo needs no Google Cloud access at all, so this account gets no role.
gcloud iam service-accounts create leadpilot-demo-runtime --display-name="LeadPilot demo runtime"

gcloud run deploy leadpilot-demo \
  --image="$IMAGE" --region="$REGION" \
  --service-account="leadpilot-demo-runtime@$PROJECT_ID.iam.gserviceaccount.com" \
  --set-env-vars=DATABASE_URL=sqlite:////tmp/leadpilot.db,SEED_DEMO=true,RATE_LIMIT_PER_MINUTE=120,TRUST_FORWARDED_FOR=true \
  --min-instances=0 --max-instances=1 --memory=512Mi \
  --allow-unauthenticated
```

What to know about this mode:

- **Data is temporary.** `/tmp` lives in the instance's memory: when Cloud Run stops the
  instance after a few idle minutes, the next request starts again from the sample data.
- **One instance only.** Each instance would have its own SQLite file, so
  `--max-instances=1` keeps every visitor on the same data.
- **No API key, no AI bill.** Without `ANTHROPIC_API_KEY` the copilot answers with its
  offline rules, so a public URL can't run up a Claude bill.
- **Anyone can write.** There is no authentication yet: don't put real data in it.
- **Requests are limited.** 120 per minute and per client; beyond that the API answers `429`.
