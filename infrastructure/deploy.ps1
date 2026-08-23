# RateGuard AI -- Production Cloud Deployment Automation Script (PowerShell)

$ErrorActionPreference = "Stop"

$PROJECT_ID = "rateguard-ai"
$REGION = "us-central1"
$RUNTIME_SA = "rateguard-runtime@rateguard-ai.iam.gserviceaccount.com"
$PUBSUB_PUSH_SA = "rateguard-pubsub-push@rateguard-ai.iam.gserviceaccount.com"
$BACKEND_IMAGE = "$REGION-docker.pkg.dev/$PROJECT_ID/rateguard/rateguard-api:latest"
$FRONTEND_IMAGE = "$REGION-docker.pkg.dev/$PROJECT_ID/rateguard/rateguard-web:latest"

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory=$true)][string]$StageName,
        [Parameter(Mandatory=$true)][scriptblock]$ScriptBlock
    )
    & $ScriptBlock
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`nError: $StageName failed (exit code $LASTEXITCODE). Deployment stopped." -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

Write-Host "========================================================"
Write-Host "   RateGuard AI -- Production Cloud Deployment          "
Write-Host "   Project: $PROJECT_ID | Region: $REGION"
Write-Host "========================================================"

Invoke-CheckedCommand -StageName "gcloud config" -ScriptBlock {
    gcloud config set project "$PROJECT_ID"
}

# 0. Resolve Project Number & Pub/Sub Service Agent
$PROJECT_NUMBER = ""
Invoke-CheckedCommand -StageName "Resolving project number" -ScriptBlock {
    $global:PROJECT_NUMBER_VAL = (gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)").Trim()
}
$PROJECT_NUMBER = $global:PROJECT_NUMBER_VAL
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
  Invoke-CheckedCommand -StageName "Creating Runtime SA" -ScriptBlock {
    gcloud iam service-accounts create rateguard-runtime `
      --display-name="RateGuard Runtime Service Account"
  }
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
  Invoke-CheckedCommand -StageName "Granting $role to Runtime SA" -ScriptBlock {
    gcloud projects add-iam-policy-binding "$PROJECT_ID" `
      --member="serviceAccount:$RUNTIME_SA" `
      --role="$role" | Out-Null
  }
}

# Pub/Sub Push SA
$pushSaExists = $null
try {
  $pushSaExists = gcloud iam service-accounts describe "$PUBSUB_PUSH_SA" --format="value(email)" 2>$null
} catch {}

if (-not $pushSaExists) {
  Write-Host "   Creating Pub/Sub Push Service Account ($PUBSUB_PUSH_SA)..."
  Invoke-CheckedCommand -StageName "Creating Pub/Sub Push SA" -ScriptBlock {
    gcloud iam service-accounts create rateguard-pubsub-push `
      --display-name="RateGuard PubSub Push Invoker SA"
  }
} else {
  Write-Host "   Pub/Sub Push Service Account exists: $PUBSUB_PUSH_SA"
}

# Grant roles/iam.serviceAccountTokenCreator to Google-managed Pub/Sub Service Agent on Push SA
Write-Host "   Granting roles/iam.serviceAccountTokenCreator to Pub/Sub Service Agent on Push SA..."
Invoke-CheckedCommand -StageName "Granting Token Creator to Pub/Sub Service Agent" -ScriptBlock {
  gcloud iam service-accounts add-iam-policy-binding "$PUBSUB_PUSH_SA" `
    --member="serviceAccount:$PUBSUB_SERVICE_AGENT" `
    --role="roles/iam.serviceAccountTokenCreator" | Out-Null
}

# Note on actAs requirement for deployer
Write-Host "   [IAM Verification] Deployer identity must hold roles/iam.serviceAccountUser on $PUBSUB_PUSH_SA to execute modify-push-config."

# 2. Build Backend Docker Container via Cloud Build (Repository Root Context)
Write-Host "`n2. Building Backend Docker Container via Cloud Build..."
Invoke-CheckedCommand -StageName "Backend Cloud Build" -ScriptBlock {
  gcloud builds submit . `
    --config=./backend/cloudbuild.yaml
}

# 3. Deploy Public API Cloud Run Service (rateguard-api)
Write-Host "`n3. Deploying Public API Service (rateguard-api)..."
Invoke-CheckedCommand -StageName "rateguard-api deployment" -ScriptBlock {
  gcloud run deploy rateguard-api `
    --image "$BACKEND_IMAGE" `
    --region "$REGION" `
    --platform managed `
    --allow-unauthenticated `
    --service-account "$RUNTIME_SA" `
    --set-env-vars RATEGUARD_GOOGLE_CLOUD_PROJECT="$PROJECT_ID",RATEGUARD_GOOGLE_CLOUD_REGION="$REGION",RATEGUARD_GCS_BUCKET="rateguard-ai-artifacts",RATEGUARD_FIRESTORE_DATABASE="(default)",RATEGUARD_RUN_STORE="firestore",RATEGUARD_ARTIFACT_STORE="gcs",RATEGUARD_BIGQUERY_ENABLED="true",RATEGUARD_BIGQUERY_DATASET="rateguard",RATEGUARD_BIGQUERY_PORTFOLIO_TABLE="synthetic_policies",RATEGUARD_BIGQUERY_RESULTS_TABLE="portfolio_exposure_results",RATEGUARD_ASYNC_ENABLED="true",RATEGUARD_PUBSUB_TOPIC="assurance-runs",RATEGUARD_PUBSUB_SUBSCRIPTION="assurance-worker",RATEGUARD_GEMINI_MODEL="gemini-3.7-flash",RATEGUARD_DATA_DIR="/app/data"
}

$API_URL = ""
Invoke-CheckedCommand -StageName "Describing rateguard-api URL" -ScriptBlock {
  $global:API_URL_VAL = (gcloud run services describe rateguard-api --region "$REGION" --format "value(status.url)").Trim()
}
$API_URL = $global:API_URL_VAL
Write-Host "   Public API URL: $API_URL"

# 4. Deploy Private Worker Cloud Run Service (rateguard-worker) using SAME Backend Image
Write-Host "`n4. Deploying Private Worker Service (rateguard-worker)..."
Invoke-CheckedCommand -StageName "rateguard-worker deployment" -ScriptBlock {
  gcloud run deploy rateguard-worker `
    --image "$BACKEND_IMAGE" `
    --region "$REGION" `
    --platform managed `
    --no-allow-unauthenticated `
    --service-account "$RUNTIME_SA" `
    --set-env-vars RATEGUARD_GOOGLE_CLOUD_PROJECT="$PROJECT_ID",RATEGUARD_GOOGLE_CLOUD_REGION="$REGION",RATEGUARD_GCS_BUCKET="rateguard-ai-artifacts",RATEGUARD_FIRESTORE_DATABASE="(default)",RATEGUARD_RUN_STORE="firestore",RATEGUARD_ARTIFACT_STORE="gcs",RATEGUARD_BIGQUERY_ENABLED="true",RATEGUARD_BIGQUERY_DATASET="rateguard",RATEGUARD_BIGQUERY_PORTFOLIO_TABLE="synthetic_policies",RATEGUARD_BIGQUERY_RESULTS_TABLE="portfolio_exposure_results",RATEGUARD_ASYNC_ENABLED="true",RATEGUARD_PUBSUB_TOPIC="assurance-runs",RATEGUARD_PUBSUB_SUBSCRIPTION="assurance-worker",RATEGUARD_GEMINI_MODEL="gemini-3.7-flash",RATEGUARD_DATA_DIR="/app/data"
}

$WORKER_URL = ""
Invoke-CheckedCommand -StageName "Describing rateguard-worker URL" -ScriptBlock {
  $global:WORKER_URL_VAL = (gcloud run services describe rateguard-worker --region "$REGION" --format "value(status.url)").Trim()
}
$WORKER_URL = $global:WORKER_URL_VAL
Write-Host "   Private Worker URL: $WORKER_URL"

# Grant roles/run.invoker to Pub/Sub Push SA on rateguard-worker
Write-Host "   Granting roles/run.invoker to Pub/Sub Push SA on rateguard-worker..."
Invoke-CheckedCommand -StageName "Granting run.invoker on rateguard-worker" -ScriptBlock {
  gcloud run services add-iam-policy-binding rateguard-worker `
    --region "$REGION" `
    --member="serviceAccount:$PUBSUB_PUSH_SA" `
    --role="roles/run.invoker" | Out-Null
}

# 5. Configure Pub/Sub Subscription Push to Private Worker Endpoint
Write-Host "`n5. Configuring Pub/Sub Subscription ('assurance-worker') Push to Private Worker..."
Invoke-CheckedCommand -StageName "Pub/Sub push configuration" -ScriptBlock {
  gcloud pubsub subscriptions modify-push-config assurance-worker `
    --push-endpoint="${WORKER_URL}/internal/pubsub/assurance" `
    --push-auth-service-account="$PUBSUB_PUSH_SA"
}

# 6. Build and Deploy Next.js Frontend with Embedded Build-Time API URL (rateguard-web)
Write-Host "`n6. Building and Deploying Frontend Web Dashboard (rateguard-web)..."
Invoke-CheckedCommand -StageName "Frontend Cloud Build" -ScriptBlock {
  gcloud builds submit ./frontend `
    --config=./frontend/cloudbuild.yaml `
    --substitutions=_NEXT_PUBLIC_RATEGUARD_API_URL="$API_URL"
}

Invoke-CheckedCommand -StageName "rateguard-web deployment" -ScriptBlock {
  gcloud run deploy rateguard-web `
    --image "$FRONTEND_IMAGE" `
    --region "$REGION" `
    --platform managed `
    --allow-unauthenticated
}

$WEB_URL = ""
Invoke-CheckedCommand -StageName "Describing rateguard-web URL" -ScriptBlock {
  $global:WEB_URL_VAL = (gcloud run services describe rateguard-web --region "$REGION" --format "value(status.url)").Trim()
}
$WEB_URL = $global:WEB_URL_VAL
Write-Host "   Public Web Dashboard URL: $WEB_URL"

# 7. Update Backend CORS Config for Deployed Web Origin
Write-Host "`n7. Updating Backend CORS for Deployed Web Origin..."
$CORS_JSON = "[`"http://localhost:3000`",`"$WEB_URL`"]"
Invoke-CheckedCommand -StageName "CORS update" -ScriptBlock {
  gcloud run services update rateguard-api `
    --region "$REGION" `
    --update-env-vars RATEGUARD_CORS_ORIGINS=$CORS_JSON
}

Write-Host "`n========================================================"
Write-Host "DEPLOYMENT COMPLETED SUCCESSFULLY!"
Write-Host "Public API Service:      $API_URL"
Write-Host "Private Worker Service:  $WORKER_URL"
Write-Host "Public Web Dashboard:    $WEB_URL"
Write-Host "Pub/Sub Push Endpoint:   ${WORKER_URL}/internal/pubsub/assurance"
Write-Host "Backend Image:           $BACKEND_IMAGE"
Write-Host "Frontend Image:          $FRONTEND_IMAGE"
Write-Host "Gemini Model:            gemini-3.7-flash"
Write-Host "========================================================"
