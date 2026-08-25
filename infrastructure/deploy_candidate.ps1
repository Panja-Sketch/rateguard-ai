# RateGuard AI -- Isolated Candidate/Staging Deployment (PowerShell mirror of deploy_candidate.sh)
#
# SAFETY: by default (no -DeployCandidate switch) this script performs ZERO
# gcloud/network calls. It only runs `git rev-parse` (local) and prints the
# full plan. Nothing here ever modifies production traffic or the production
# Pub/Sub push config. See deploy_candidate.sh for the full command-by-command
# rationale -- this file mirrors it.

param(
    [switch]$DeployCandidate
)

$ErrorActionPreference = "Stop"

$PROJECT_ID = "rateguard-ai"
$REGION = "us-central1"
$RUNTIME_SA = "rateguard-runtime@rateguard-ai.iam.gserviceaccount.com"
$PUBSUB_PUSH_SA = "rateguard-pubsub-push@rateguard-ai.iam.gserviceaccount.com"
$CANDIDATE_TAG = "candidate"

$STAGING_TOPIC = "assurance-runs-staging"
$STAGING_SUBSCRIPTION = "assurance-worker-staging"
$STAGING_DLQ_TOPIC = "assurance-runs-staging-dlq"
$STAGING_DLQ_INSPECTION_SUBSCRIPTION = "assurance-runs-staging-dlq-inspect"
$STAGING_FIRESTORE_COLLECTION = "assurance_runs_staging"

# Separate dataset (not just separate tables in the production dataset) and a
# separate bucket -- see deploy_candidate.sh for the full rationale. Same
# table names as production, isolated by living in a different dataset.
$STAGING_BIGQUERY_DATASET = "rateguard_staging"
$STAGING_BIGQUERY_PORTFOLIO_TABLE = "synthetic_policies"
$STAGING_BIGQUERY_RESULTS_TABLE = "portfolio_exposure_results"
$STAGING_GCS_BUCKET = "rateguard-ai-artifacts-staging"

$ACK_DEADLINE_SECONDS = 600
$MIN_RETRY_BACKOFF_SECONDS = 10
$MAX_RETRY_BACKOFF_SECONDS = 600
$MAX_DELIVERY_ATTEMPTS = 5

try {
    $GIT_SHA = (git rev-parse --short=12 HEAD 2>$null).Trim()
    if (-not $GIT_SHA) { $GIT_SHA = "UNKNOWN_SHA" }
} catch {
    $GIT_SHA = "UNKNOWN_SHA"
}
$IMAGE_TAG = "candidate-$GIT_SHA"
$BACKEND_IMAGE = "$REGION-docker.pkg.dev/$PROJECT_ID/rateguard/rateguard-api:$IMAGE_TAG"
$FRONTEND_IMAGE = "$REGION-docker.pkg.dev/$PROJECT_ID/rateguard/rateguard-web:$IMAGE_TAG"
$CANDIDATE_ENV_FILE = "infrastructure/.candidate-env.yaml"

function Write-Plan {
    Write-Host "========================================================"
    Write-Host "   RateGuard AI -- Candidate/Staging Deployment PLAN"
    Write-Host "   (dry-run: no gcloud command below has been executed)"
    Write-Host "========================================================"
    Write-Host "Project:                       $PROJECT_ID"
    Write-Host "Region:                        $REGION"
    Write-Host "Git commit:                    $GIT_SHA"
    Write-Host "Immutable image tag:           $IMAGE_TAG"
    Write-Host "Backend image (api + worker):  $BACKEND_IMAGE"
    Write-Host "Frontend image:                $FRONTEND_IMAGE"
    Write-Host "Cloud Run candidate tag:       $CANDIDATE_TAG (--no-traffic)"
    Write-Host "Runtime service account:       $RUNTIME_SA (no API key)"
    Write-Host ""
    Write-Host "Isolated staging resources (production is untouched):"
    Write-Host "  Pub/Sub topic:                 $STAGING_TOPIC"
    Write-Host "  Pub/Sub subscription:          $STAGING_SUBSCRIPTION"
    Write-Host "  Dead-letter topic:             $STAGING_DLQ_TOPIC"
    Write-Host "  Dead-letter inspection sub:    $STAGING_DLQ_INSPECTION_SUBSCRIPTION"
    Write-Host "  Firestore collection:          $STAGING_FIRESTORE_COLLECTION"
    Write-Host "  BigQuery dataset:              $STAGING_BIGQUERY_DATASET"
    Write-Host "  BigQuery portfolio table:      $STAGING_BIGQUERY_DATASET.$STAGING_BIGQUERY_PORTFOLIO_TABLE"
    Write-Host "  BigQuery results table:        $STAGING_BIGQUERY_DATASET.$STAGING_BIGQUERY_RESULTS_TABLE"
    Write-Host "  GCS artifact bucket:           $STAGING_GCS_BUCKET"
    Write-Host "  Ack deadline:                  ${ACK_DEADLINE_SECONDS}s"
    Write-Host "  Retry backoff:                 ${MIN_RETRY_BACKOFF_SECONDS}s - ${MAX_RETRY_BACKOFF_SECONDS}s"
    Write-Host "  Max delivery attempts:         $MAX_DELIVERY_ATTEMPTS"
    Write-Host ""
    Write-Host "Candidate env vars (non-secret; no API key is ever set):"
    Write-Host "  RATEGUARD_AGENT_ENABLED=true"
    Write-Host "  GOOGLE_GENAI_USE_VERTEXAI=true"
    Write-Host "  GOOGLE_CLOUD_PROJECT=$PROJECT_ID"
    Write-Host "  GOOGLE_CLOUD_LOCATION=global"
    Write-Host "  RATEGUARD_GEMINI_MODEL=gemini-3.7-flash"
    Write-Host "  RATEGUARD_RUN_STORE=firestore"
    Write-Host "  RATEGUARD_FIRESTORE_COLLECTION=$STAGING_FIRESTORE_COLLECTION"
    Write-Host "  RATEGUARD_PUBSUB_TOPIC=$STAGING_TOPIC"
    Write-Host "  RATEGUARD_PUBSUB_SUBSCRIPTION=$STAGING_SUBSCRIPTION"
    Write-Host "  RATEGUARD_BIGQUERY_DATASET=$STAGING_BIGQUERY_DATASET"
    Write-Host "  RATEGUARD_BIGQUERY_PORTFOLIO_TABLE=$STAGING_BIGQUERY_PORTFOLIO_TABLE"
    Write-Host "  RATEGUARD_BIGQUERY_RESULTS_TABLE=$STAGING_BIGQUERY_RESULTS_TABLE"
    Write-Host "  RATEGUARD_GCS_BUCKET=$STAGING_GCS_BUCKET"
    Write-Host "  (all other values inherited from infrastructure/runtime-env.yaml)"
    Write-Host ""
    Write-Host "Exact commands that -DeployCandidate would run, in order:"
    Write-Host "  1) gcloud builds submit . --config=./backend/cloudbuild.yaml --substitutions=_IMAGE_TAG=$IMAGE_TAG"
    Write-Host "  2) gcloud run deploy rateguard-api --image $BACKEND_IMAGE --region $REGION --no-traffic --tag $CANDIDATE_TAG --service-account $RUNTIME_SA --env-vars-file=$CANDIDATE_ENV_FILE"
    Write-Host "     gcloud run deploy rateguard-worker --image $BACKEND_IMAGE --region $REGION --no-traffic --tag $CANDIDATE_TAG --service-account $RUNTIME_SA --env-vars-file=$CANDIDATE_ENV_FILE"
    Write-Host "  3) Idempotent create/update: $STAGING_TOPIC, $STAGING_DLQ_TOPIC, $STAGING_SUBSCRIPTION (push -> candidate-tagged worker URL only), $STAGING_DLQ_INSPECTION_SUBSCRIPTION, narrow DLQ IAM bindings"
    Write-Host "  4) Idempotently provision $STAGING_BIGQUERY_DATASET dataset/tables (python backend/scripts/setup_bigquery.py) and load ONLY the synthetic demo portfolio (python backend/scripts/upload_synthetic_portfolio_bigquery.py); idempotently create gs://$STAGING_GCS_BUCKET"
    Write-Host "  5) gcloud builds submit ./frontend --config=./frontend/cloudbuild.yaml --substitutions=_IMAGE_TAG=$IMAGE_TAG,_NEXT_PUBLIC_RATEGUARD_API_URL=<candidate-api-tagged-url>"
    Write-Host "     gcloud run deploy rateguard-web --image $FRONTEND_IMAGE --region $REGION --no-traffic --tag $CANDIDATE_TAG"
    Write-Host ""
    Write-Host "NOT done by this script, ever: no production traffic change, no change"
    Write-Host "to the production Pub/Sub push config, no write to the production BigQuery"
    Write-Host "dataset ('rateguard') or bucket ('rateguard-ai-artifacts'), no API key, no promotion."
    Write-Host ""
    Write-Host "Re-run with no arguments to see this plan again. Pass -DeployCandidate to execute."
}

function Write-CandidateEnvFile {
    $lines = Get-Content infrastructure/runtime-env.yaml | Where-Object {
        $_ -notmatch '^(RATEGUARD_PUBSUB_TOPIC|RATEGUARD_PUBSUB_SUBSCRIPTION|RATEGUARD_FIRESTORE_COLLECTION|RATEGUARD_AGENT_ENABLED|GOOGLE_GENAI_USE_VERTEXAI|GOOGLE_CLOUD_PROJECT|GOOGLE_CLOUD_LOCATION|RATEGUARD_GEMINI_MODEL|RATEGUARD_RUN_STORE|RATEGUARD_BIGQUERY_DATASET|RATEGUARD_BIGQUERY_PORTFOLIO_TABLE|RATEGUARD_BIGQUERY_RESULTS_TABLE|RATEGUARD_GCS_BUCKET):'
    }
    $lines | Set-Content -Encoding utf8 $CANDIDATE_ENV_FILE
    Add-Content -Encoding utf8 $CANDIDATE_ENV_FILE @"
RATEGUARD_AGENT_ENABLED: "true"
GOOGLE_GENAI_USE_VERTEXAI: "true"
GOOGLE_CLOUD_PROJECT: "$PROJECT_ID"
GOOGLE_CLOUD_LOCATION: "global"
RATEGUARD_GEMINI_MODEL: "gemini-3.7-flash"
RATEGUARD_RUN_STORE: "firestore"
RATEGUARD_PUBSUB_TOPIC: "$STAGING_TOPIC"
RATEGUARD_PUBSUB_SUBSCRIPTION: "$STAGING_SUBSCRIPTION"
RATEGUARD_FIRESTORE_COLLECTION: "$STAGING_FIRESTORE_COLLECTION"
RATEGUARD_BIGQUERY_DATASET: "$STAGING_BIGQUERY_DATASET"
RATEGUARD_BIGQUERY_PORTFOLIO_TABLE: "$STAGING_BIGQUERY_PORTFOLIO_TABLE"
RATEGUARD_BIGQUERY_RESULTS_TABLE: "$STAGING_BIGQUERY_RESULTS_TABLE"
RATEGUARD_GCS_BUCKET: "$STAGING_GCS_BUCKET"
"@
}

function Deploy-Candidate {
    Write-Host "========================================================"
    Write-Host "   RateGuard AI -- Deploying Candidate (-DeployCandidate)"
    Write-Host "   Image tag: $IMAGE_TAG"
    Write-Host "========================================================"

    gcloud config set project "$PROJECT_ID"
    $PROJECT_NUMBER = (gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)").Trim()
    $PUBSUB_SERVICE_AGENT = "service-$PROJECT_NUMBER@gcp-sa-pubsub.iam.gserviceaccount.com"

    Write-CandidateEnvFile

    Write-Host "1. Building candidate backend image..."
    gcloud builds submit . --config=./backend/cloudbuild.yaml --substitutions=_IMAGE_TAG="$IMAGE_TAG"

    Write-Host "2. Deploying candidate API revision (--no-traffic --tag $CANDIDATE_TAG)..."
    gcloud run deploy rateguard-api `
        --image "$BACKEND_IMAGE" --region "$REGION" --platform managed `
        --no-traffic --tag "$CANDIDATE_TAG" `
        --allow-unauthenticated --service-account "$RUNTIME_SA" `
        --memory=512Mi --env-vars-file="$CANDIDATE_ENV_FILE"

    $CANDIDATE_API_URL = (gcloud run services describe rateguard-api --region "$REGION" `
        --format "value(status.traffic[?tag=='$CANDIDATE_TAG'].url)").Trim()
    Write-Host "   Candidate API URL: $CANDIDATE_API_URL"

    Write-Host "3. Deploying candidate worker revision (--no-traffic --tag $CANDIDATE_TAG)..."
    gcloud run deploy rateguard-worker `
        --image "$BACKEND_IMAGE" --region "$REGION" --platform managed `
        --no-traffic --tag "$CANDIDATE_TAG" `
        --no-allow-unauthenticated --service-account "$RUNTIME_SA" `
        --memory=1Gi --env-vars-file="$CANDIDATE_ENV_FILE"

    $CANDIDATE_WORKER_URL = (gcloud run services describe rateguard-worker --region "$REGION" `
        --format "value(status.traffic[?tag=='$CANDIDATE_TAG'].url)").Trim()
    Write-Host "   Candidate Worker URL: $CANDIDATE_WORKER_URL"

    Write-Host "4. Idempotently configuring isolated staging Pub/Sub + DLQ..."
    $topicExists = $null
    try { $topicExists = gcloud pubsub topics describe "$STAGING_TOPIC" --format="value(name)" 2>$null } catch {}
    if (-not $topicExists) { gcloud pubsub topics create "$STAGING_TOPIC" }

    $dlqExists = $null
    try { $dlqExists = gcloud pubsub topics describe "$STAGING_DLQ_TOPIC" --format="value(name)" 2>$null } catch {}
    if (-not $dlqExists) { gcloud pubsub topics create "$STAGING_DLQ_TOPIC" }

    $subExists = $null
    try { $subExists = gcloud pubsub subscriptions describe "$STAGING_SUBSCRIPTION" --format="value(name)" 2>$null } catch {}
    if (-not $subExists) {
        gcloud pubsub subscriptions create "$STAGING_SUBSCRIPTION" `
            --topic="$STAGING_TOPIC" --ack-deadline="$ACK_DEADLINE_SECONDS" `
            --min-retry-delay="${MIN_RETRY_BACKOFF_SECONDS}s" --max-retry-delay="${MAX_RETRY_BACKOFF_SECONDS}s" `
            --dead-letter-topic="$STAGING_DLQ_TOPIC" --max-delivery-attempts="$MAX_DELIVERY_ATTEMPTS" `
            --push-endpoint="$CANDIDATE_WORKER_URL/internal/pubsub/assurance" `
            --push-auth-service-account="$PUBSUB_PUSH_SA"
    } else {
        gcloud pubsub subscriptions update "$STAGING_SUBSCRIPTION" `
            --ack-deadline="$ACK_DEADLINE_SECONDS" `
            --min-retry-delay="${MIN_RETRY_BACKOFF_SECONDS}s" --max-retry-delay="${MAX_RETRY_BACKOFF_SECONDS}s" `
            --dead-letter-topic="$STAGING_DLQ_TOPIC" --max-delivery-attempts="$MAX_DELIVERY_ATTEMPTS"
        gcloud pubsub subscriptions modify-push-config "$STAGING_SUBSCRIPTION" `
            --push-endpoint="$CANDIDATE_WORKER_URL/internal/pubsub/assurance" `
            --push-auth-service-account="$PUBSUB_PUSH_SA"
    }

    $dlqSubExists = $null
    try { $dlqSubExists = gcloud pubsub subscriptions describe "$STAGING_DLQ_INSPECTION_SUBSCRIPTION" --format="value(name)" 2>$null } catch {}
    if (-not $dlqSubExists) {
        gcloud pubsub subscriptions create "$STAGING_DLQ_INSPECTION_SUBSCRIPTION" --topic="$STAGING_DLQ_TOPIC"
    }

    gcloud pubsub topics add-iam-policy-binding "$STAGING_DLQ_TOPIC" `
        --member="serviceAccount:$PUBSUB_SERVICE_AGENT" --role="roles/pubsub.publisher" | Out-Null
    gcloud pubsub subscriptions add-iam-policy-binding "$STAGING_SUBSCRIPTION" `
        --member="serviceAccount:$PUBSUB_SERVICE_AGENT" --role="roles/pubsub.subscriber" | Out-Null

    Write-Host "5. Idempotently provisioning isolated staging BigQuery dataset/tables and"
    Write-Host "   loading ONLY the synthetic demonstration portfolio (never production data)..."
    $env:RATEGUARD_BIGQUERY_DATASET = $STAGING_BIGQUERY_DATASET
    $env:RATEGUARD_BIGQUERY_PORTFOLIO_TABLE = $STAGING_BIGQUERY_PORTFOLIO_TABLE
    $env:RATEGUARD_BIGQUERY_RESULTS_TABLE = $STAGING_BIGQUERY_RESULTS_TABLE
    python backend/scripts/setup_bigquery.py
    python backend/scripts/upload_synthetic_portfolio_bigquery.py
    Remove-Item Env:\RATEGUARD_BIGQUERY_DATASET, Env:\RATEGUARD_BIGQUERY_PORTFOLIO_TABLE, Env:\RATEGUARD_BIGQUERY_RESULTS_TABLE -ErrorAction SilentlyContinue

    Write-Host "6. Idempotently creating isolated staging GCS artifact bucket..."
    $bucketExists = $null
    try { $bucketExists = gcloud storage buckets describe "gs://$STAGING_GCS_BUCKET" --format="value(name)" 2>$null } catch {}
    if (-not $bucketExists) {
        gcloud storage buckets create "gs://$STAGING_GCS_BUCKET" `
            --project="$PROJECT_ID" --location="$REGION" --uniform-bucket-level-access
    } else {
        Write-Host "   Bucket gs://$STAGING_GCS_BUCKET already exists."
    }

    Write-Host "7. Building and deploying candidate frontend (--no-traffic --tag $CANDIDATE_TAG)..."
    gcloud builds submit ./frontend --config=./frontend/cloudbuild.yaml `
        --substitutions=_IMAGE_TAG="$IMAGE_TAG",_NEXT_PUBLIC_RATEGUARD_API_URL="$CANDIDATE_API_URL"
    gcloud run deploy rateguard-web `
        --image "$FRONTEND_IMAGE" --region "$REGION" --platform managed `
        --no-traffic --tag "$CANDIDATE_TAG" --allow-unauthenticated

    $CANDIDATE_WEB_URL = (gcloud run services describe rateguard-web --region "$REGION" `
        --format "value(status.traffic[?tag=='$CANDIDATE_TAG'].url)").Trim()

    Remove-Item "$CANDIDATE_ENV_FILE" -Force -ErrorAction SilentlyContinue

    Write-Host "========================================================"
    Write-Host "CANDIDATE DEPLOYMENT COMPLETE (0% production traffic)"
    Write-Host "Candidate API URL:      $CANDIDATE_API_URL"
    Write-Host "Candidate Worker URL:   $CANDIDATE_WORKER_URL"
    Write-Host "Candidate Web URL:      $CANDIDATE_WEB_URL"
    Write-Host "Image tag:              $IMAGE_TAG"
    Write-Host "========================================================"
}

if ($DeployCandidate) {
    Deploy-Candidate
} else {
    Write-Plan
}
