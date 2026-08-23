#!/usr/bin/env bash
# Automated RateGuard Cloud Deployment & Multi-Service Architecture Configuration Script

set -e

PROJECT_ID="rateguard-ai"
REGION="us-central1"
RUNTIME_SA="rateguard-runtime@rateguard-ai.iam.gserviceaccount.com"
PUBSUB_PUSH_SA="rateguard-pubsub-push@rateguard-ai.iam.gserviceaccount.com"

echo "========================================================"
echo "   RateGuard AI -- Production Cloud Deployment          "
echo "   Project: $PROJECT_ID | Region: $REGION"
echo "========================================================"

gcloud config set project "$PROJECT_ID"

# 0. Resolve Project Number & Pub/Sub Service Agent
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
PUBSUB_SERVICE_AGENT="service-${PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com"
echo "   Project Number: $PROJECT_NUMBER"
echo "   Pub/Sub Service Agent: $PUBSUB_SERVICE_AGENT"

# 1. Idempotent Service Account Setup & Least-Privilege IAM Roles
echo "\n1. Verifying and configuring Service Accounts..."

# Runtime SA
if ! gcloud iam service-accounts describe "$RUNTIME_SA" >/dev/null 2>&1; then
  echo "   Creating Runtime Service Account ($RUNTIME_SA)..."
  gcloud iam service-accounts create rateguard-runtime \
    --display-name="RateGuard Runtime Service Account"
else
  echo "   Runtime Service Account exists: $RUNTIME_SA"
fi

# Grant least-privilege roles to Runtime SA
RUNTIME_ROLES=(
  "roles/aiplatform.user"       # Vertex AI / Gemini 3.7 Flash invocation
  "roles/datastore.user"        # Firestore read/write
  "roles/bigquery.dataEditor"   # BigQuery results table write
  "roles/bigquery.jobUser"      # BigQuery query execution
  "roles/storage.objectUser"    # Cloud Storage artifact access
  "roles/pubsub.publisher"      # Pub/Sub message publishing
)

for role in "${RUNTIME_ROLES[@]}"; do
  echo "   Granting $role to Runtime SA..."
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$RUNTIME_SA" \
    --role="$role" >/dev/null
done

# Pub/Sub Push SA
if ! gcloud iam service-accounts describe "$PUBSUB_PUSH_SA" >/dev/null 2>&1; then
  echo "   Creating Pub/Sub Push Service Account ($PUBSUB_PUSH_SA)..."
  gcloud iam service-accounts create rateguard-pubsub-push \
    --display-name="RateGuard PubSub Push Invoker SA"
else
  echo "   Pub/Sub Push Service Account exists: $PUBSUB_PUSH_SA"
fi

# Grant roles/iam.serviceAccountTokenCreator to Google-managed Pub/Sub Service Agent on Push SA
echo "   Granting roles/iam.serviceAccountTokenCreator to Pub/Sub Service Agent on Push SA..."
gcloud iam service-accounts add-iam-policy-binding "$PUBSUB_PUSH_SA" \
  --member="serviceAccount:$PUBSUB_SERVICE_AGENT" \
  --role="roles/iam.serviceAccountTokenCreator" >/dev/null

# Note on actAs requirement for deployer
echo "   [IAM Verification] Deployer identity must hold roles/iam.serviceAccountUser on $PUBSUB_PUSH_SA to execute modify-push-config."

# 2. Deploy Public API Cloud Run Service (rateguard-api)
echo "\n2. Deploying Public API Service (rateguard-api)..."
gcloud run deploy rateguard-api \
  --source ./backend \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --service-account "$RUNTIME_SA" \
  --set-env-vars RATEGUARD_GOOGLE_CLOUD_PROJECT="$PROJECT_ID",RATEGUARD_GOOGLE_CLOUD_REGION="$REGION",RATEGUARD_GCS_BUCKET="rateguard-ai-artifacts",RATEGUARD_FIRESTORE_DATABASE="(default)",RATEGUARD_RUN_STORE="firestore",RATEGUARD_ARTIFACT_STORE="gcs",RATEGUARD_BIGQUERY_ENABLED="true",RATEGUARD_BIGQUERY_DATASET="rateguard",RATEGUARD_BIGQUERY_PORTFOLIO_TABLE="synthetic_policies",RATEGUARD_BIGQUERY_RESULTS_TABLE="portfolio_exposure_results",RATEGUARD_ASYNC_ENABLED="true",RATEGUARD_PUBSUB_TOPIC="assurance-runs",RATEGUARD_PUBSUB_SUBSCRIPTION="assurance-worker",RATEGUARD_GEMINI_MODEL="gemini-3.7-flash"

API_URL=$(gcloud run services describe rateguard-api --region "$REGION" --format "value(status.url)")
echo "   Public API URL: $API_URL"

# 3. Deploy Private Worker Cloud Run Service (rateguard-worker)
echo "\n3. Deploying Private Worker Service (rateguard-worker)..."
gcloud run deploy rateguard-worker \
  --source ./backend \
  --region "$REGION" \
  --platform managed \
  --no-allow-unauthenticated \
  --service-account "$RUNTIME_SA" \
  --set-env-vars RATEGUARD_GOOGLE_CLOUD_PROJECT="$PROJECT_ID",RATEGUARD_GOOGLE_CLOUD_REGION="$REGION",RATEGUARD_GCS_BUCKET="rateguard-ai-artifacts",RATEGUARD_FIRESTORE_DATABASE="(default)",RATEGUARD_RUN_STORE="firestore",RATEGUARD_ARTIFACT_STORE="gcs",RATEGUARD_BIGQUERY_ENABLED="true",RATEGUARD_BIGQUERY_DATASET="rateguard",RATEGUARD_BIGQUERY_PORTFOLIO_TABLE="synthetic_policies",RATEGUARD_BIGQUERY_RESULTS_TABLE="portfolio_exposure_results",RATEGUARD_ASYNC_ENABLED="true",RATEGUARD_PUBSUB_TOPIC="assurance-runs",RATEGUARD_PUBSUB_SUBSCRIPTION="assurance-worker",RATEGUARD_GEMINI_MODEL="gemini-3.7-flash"

WORKER_URL=$(gcloud run services describe rateguard-worker --region "$REGION" --format "value(status.url)")
echo "   Private Worker URL: $WORKER_URL"

# Grant roles/run.invoker to Pub/Sub Push SA on rateguard-worker
echo "   Granting roles/run.invoker to Pub/Sub Push SA on rateguard-worker..."
gcloud run services add-iam-policy-binding rateguard-worker \
  --region "$REGION" \
  --member="serviceAccount:$PUBSUB_PUSH_SA" \
  --role="roles/run.invoker" >/dev/null

# 4. Configure Pub/Sub Subscription Push to Private Worker Endpoint
echo "\n4. Configuring Pub/Sub Subscription ('assurance-worker') Push to Private Worker..."
gcloud pubsub subscriptions modify-push-config assurance-worker \
  --push-endpoint="${WORKER_URL}/internal/pubsub/assurance" \
  --push-auth-service-account="$PUBSUB_PUSH_SA"

# 5. Build and Deploy Next.js Frontend with Embedded Build-Time API URL (rateguard-web)
echo "\n5. Building and Deploying Frontend Web Dashboard (rateguard-web)..."
gcloud builds submit ./frontend \
  --config=./frontend/cloudbuild.yaml \
  --substitutions=_NEXT_PUBLIC_RATEGUARD_API_URL="$API_URL"

gcloud run deploy rateguard-web \
  --image "${REGION}-docker.pkg.dev/${PROJECT_ID}/rateguard/rateguard-web:latest" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated

WEB_URL=$(gcloud run services describe rateguard-web --region "$REGION" --format "value(status.url)")
echo "   Public Web Dashboard URL: $WEB_URL"

# 6. Update Backend CORS Config for Deployed Web Origin
echo "\n6. Updating Backend CORS for Deployed Web Origin..."
gcloud run services update rateguard-api \
  --region "$REGION" \
  --update-env-vars RATEGUARD_CORS_ORIGINS="[\"http://localhost:3000\",\"${WEB_URL}\"]"

echo "\n========================================================"
echo "DEPLOYMENT COMPLETED SUCCESSFULLY!"
echo "Public API Service:      $API_URL"
echo "Private Worker Service:  $WORKER_URL"
echo "Public Web Dashboard:    $WEB_URL"
echo "Pub/Sub Push Endpoint:   ${WORKER_URL}/internal/pubsub/assurance"
echo "Gemini Model:            gemini-3.7-flash"
echo "========================================================"
