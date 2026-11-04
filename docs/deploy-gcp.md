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

Give the Cloud Run service account access to both secrets and to Cloud SQL:

```bash
SA="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')-compute@developer.gserviceaccount.com"
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
# {"status":"ok","version":"0.1.0","database":"ok"}
```

## Costs

With `min-instances=0` Cloud Run costs nothing while idle. The smallest Cloud SQL tier is
the main fixed cost; stop the instance (`gcloud sql instances patch leadpilot-db
--activation-policy=NEVER`) when you are not using it.
