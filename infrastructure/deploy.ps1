# RateGuard AI -- Production Cloud Deployment Automation Script (PowerShell)

$ErrorActionPreference = "Stop"

$PROJECT_ID = "rateguard-ai"
$REGION = "us-central1"
$RUNTIME_SA = "rateguard-runtime@rateguard-ai.iam.gserviceaccount.com"
$PUBSUB_PUSH_SA = "rateguard-pubsub-push@rateguard-ai.iam.gserviceaccount.com"

Write-Host "========================================================"
Write-Host "   RateGuard AI -- Production Cloud Deployment          "
Write-Host "   Project: $PROJECT_ID | Region: $REGION"
Write-Host "========================================================"

gcloud config set project "$PROJECT_ID"

# 0. Resolve Project Number & Pub/Sub Service Agent
$PROJECT_NUMBER = (gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)").Trim()
$PUBSUB_SERVICE_AGENT = "service-${PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com"
Write-Host "   Project Number: $PROJECT_NUMBER"
Write-Host "   Pub/Sub Service Agent: $PUBSUB_SERVICE_AGENT"

# 1. Idempotent Service Account Setup & Least-Privilege IAM Roles
Write-Host "`n1. Verifying and configuring Service Accounts..."

# Runtime SA
$saExists = $null
try {
  $saExists = gcloud iam service-accounts describe "$RUNTIME_SA" --format="value(email)" 2>$null
} catch {}

if (-not $saExists) {
  Write-Host "   Creating Runtime Service Account ($RUNTIME_SA)..."
  gcloud iam service-accounts create rateguard-runtime `
    --display-name="RateGuard Runtime Service Account"
} else {
  Write-Host "   Runtime Service Account exists: $RUNTIME_SA"
}

# Grant least-privilege roles to Runtime SA
$RUNTIME_ROLES = @(
  "roles/aiplatform.user",       # Vertex AI / Gemini 3.7 Flash invocation
  "roles/datastore.user",        # Firestore read/write
  "roles/bigquery.dataEditor",   # BigQuery results table write
  "roles/bigquery.jobUser",      # BigQuery query execution
  "roles/storage.objectUser",    # Cloud Storage artifact access
  "roles/pubsub.publisher"      # Pub/Sub message publishing
)

foreach ($role in $RUNTIME_ROLES) {
  Write-Host "   Granting $role to Runtime SA..."
  gcloud projects add-iam-policy-binding "$PROJECT_ID" `
    --member="serviceAccount:$RUNTIME_SA" `
    --role="$role" | Out-Null
}

# Pub/Sub Push SA
$pushSaExists = $null
try {
  $pushSaExists = gcloud iam service-accounts describe "$PUBSUB_PUSH_SA" --format="value(email)" 2>$null
} catch {}

if (-not $pushSaExists) {
  Write-Host "   Creating Pub/Sub Push Service Account ($PUBSUB_PUSH_SA)..."
  gcloud iam service-accounts create rateguard-pubsub-push `
    --display-name="RateGuard PubSub Push Invoker SA"
} else {
  Write-Host "   Pub/Sub Push Service Account exists: $PUBSUB_PUSH_SA"
}

# Grant roles/iam.serviceAccountTokenCreator to Google-managed Pub/Sub Service Agent on Push SA
Write-Host "   Granting roles/iam.serviceAccountTokenCreator to Pub/Sub Service Agent on Push SA..."
gcloud iam service-accounts add-iam-policy-binding "$PUBSUB_PUSH_SA" `
  --member="serviceAccount:$PUBSUB_SERVICE_AGENT" `
  --role="roles/iam.serviceAccountTokenCreator" | Out-Null

# Note on actAs requirement for deployer
Write-Host "   [IAM Verification] Deployer identity must hold roles/iam.serviceAccountUser on $PUBSUB_PUSH_SA to execute modify-push-config."

# 2. Deploy Public API Cloud Run Service (rateguard-api)
Write-Host "`n2. Deploying Public API Service (rateguard-api)..."
gcloud run deploy rateguard-api `
  --source ./backend `
  --region "$REGION" `
  --platform managed `
  --allow-unauthenticated `
  --service-account "$RUNTIME_SA" `
  --set-env-vars RATEGUARD_GOOGLE_CLOUD_PROJECT="$PROJECT_ID",RATEGUARD_GOOGLE_CLOUD_REGION="$REGION",RATEGUARD_GCS_BUCKET="rateguard-ai-artifacts",RATEGUARD_FIRESTORE_DATABASE="(default)",RATEGUARD_RUN_STORE="firestore",RATEGUARD_ARTIFACT_STORE="gcs",RATEGUARD_BIGQUERY_ENABLED="true",RATEGUARD_BIGQUERY_DATASET="rateguard",RATEGUARD_BIGQUERY_PORTFOLIO_TABLE="synthetic_policies",RATEGUARD_BIGQUERY_RESULTS_TABLE="portfolio_exposure_results",RATEGUARD_ASYNC_ENABLED="true",RATEGUARD_PUBSUB_TOPIC="assurance-runs",RATEGUARD_PUBSUB_SUBSCRIPTION="assurance-worker",RATEGUARD_GEMINI_MODEL="gemini-3.7-flash"

$API_URL = (gcloud run services describe rateguard-api --region "$REGION" --format "value(status.url)").Trim()
Write-Host "   Public API URL: $API_URL"

# 3. Deploy Private Worker Cloud Run Service (rateguard-worker)
Write-Host "`n3. Deploying Private Worker Service (rateguard-worker)..."
gcloud run deploy rateguard-worker `
  --source ./backend `
  --region "$REGION" `
  --platform managed `
  --no-allow-unauthenticated `
  --service-account "$RUNTIME_SA" `
  --set-env-vars RATEGUARD_GOOGLE_CLOUD_PROJECT="$PROJECT_ID",RATEGUARD_GOOGLE_CLOUD_REGION="$REGION",RATEGUARD_GCS_BUCKET="rateguard-ai-artifacts",RATEGUARD_FIRESTORE_DATABASE="(default)",RATEGUARD_RUN_STORE="firestore",RATEGUARD_ARTIFACT_STORE="gcs",RATEGUARD_BIGQUERY_ENABLED="true",RATEGUARD_BIGQUERY_DATASET="rateguard",RATEGUARD_BIGQUERY_PORTFOLIO_TABLE="synthetic_policies",RATEGUARD_BIGQUERY_RESULTS_TABLE="portfolio_exposure_results",RATEGUARD_ASYNC_ENABLED="true",RATEGUARD_PUBSUB_TOPIC="assurance-runs",RATEGUARD_PUBSUB_SUBSCRIPTION="assurance-worker",RATEGUARD_GEMINI_MODEL="gemini-3.7-flash"

$WORKER_URL = (gcloud run services describe rateguard-worker --region "$REGION" --format "value(status.url)").Trim()
Write-Host "   Private Worker URL: $WORKER_URL"

# Grant roles/run.invoker to Pub/Sub Push SA on rateguard-worker
Write-Host "   Granting roles/run.invoker to Pub/Sub Push SA on rateguard-worker..."
gcloud run services add-iam-policy-binding rateguard-worker `
  --region "$REGION" `
  --member="serviceAccount:$PUBSUB_PUSH_SA" `
  --role="roles/run.invoker" | Out-Null

# 4. Configure Pub/Sub Subscription Push to Private Worker Endpoint
Write-Host "`n4. Configuring Pub/Sub Subscription ('assurance-worker') Push to Private Worker..."
gcloud pubsub subscriptions modify-push-config assurance-worker `
  --push-endpoint="${WORKER_URL}/internal/pubsub/assurance" `
  --push-auth-service-account="$PUBSUB_PUSH_SA"

# 5. Build and Deploy Next.js Frontend with Embedded Build-Time API URL (rateguard-web)
Write-Host "`n5. Building and Deploying Frontend Web Dashboard (rateguard-web)..."
gcloud builds submit ./frontend `
  --config=./frontend/cloudbuild.yaml `
  --substitutions=_NEXT_PUBLIC_RATEGUARD_API_URL="$API_URL"

gcloud run deploy rateguard-web `
  --image "$REGION-docker.pkg.dev/$PROJECT_ID/rateguard/rateguard-web:latest" `
  --region "$REGION" `
  --platform managed `
  --allow-unauthenticated

$WEB_URL = (gcloud run services describe rateguard-web --region "$REGION" --format "value(status.url)").Trim()
Write-Host "   Public Web Dashboard URL: $WEB_URL"

# 6. Update Backend CORS Config for Deployed Web Origin
Write-Host "`n6. Updating Backend CORS for Deployed Web Origin..."
$CORS_JSON = "[`"http://localhost:3000`",`"$WEB_URL`"]"
gcloud run services update rateguard-api `
  --region "$REGION" `
  --update-env-vars RATEGUARD_CORS_ORIGINS=$CORS_JSON

Write-Host "`n========================================================"
Write-Host "DEPLOYMENT COMPLETED SUCCESSFULLY!"
Write-Host "Public API Service:      $API_URL"
Write-Host "Private Worker Service:  $WORKER_URL"
Write-Host "Public Web Dashboard:    $WEB_URL"
Write-Host "Pub/Sub Push Endpoint:   ${WORKER_URL}/internal/pubsub/assurance"
Write-Host "Gemini Model:            gemini-3.7-flash"
Write-Host "========================================================"
