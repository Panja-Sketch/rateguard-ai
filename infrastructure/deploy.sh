#!/usr/bin/env font
# Automated RateGuard Cloud Run Deployment & Pub/Sub Push Configuration Script

set -e

PROJECT_ID="rateguard-ai"
REGION="us-central1"
SERVICE_ACCOUNT="rateguard-runtime@rateguard-ai.iam.gserviceaccount.com"

echo "========================================================"
echo "   RateGuard AI -- Google Cloud Deployment Automation   "
echo "   Project: $PROJECT_ID | Region: $REGION"
echo "========================================================"

gcloud config set project "$PROJECT_ID"

# 1. Deploy RateGuard API Backend to Cloud Run
echo "\n1. Deploying Backend API to Cloud Run..."
gcloud run deploy rateguard-api \
  --source ./backend \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --service-account "$SERVICE_ACCOUNT" \
  --set-env-vars RATEGUARD_GOOGLE_CLOUD_PROJECT="$PROJECT_ID",RATEGUARD_GOOGLE_CLOUD_REGION="$REGION",RATEGUARD_GCS_BUCKET="rateguard-ai-artifacts",RATEGUARD_FIRESTORE_DATABASE="(default)",RATEGUARD_RUN_STORE="firestore",RATEGUARD_ARTIFACT_STORE="gcs",RATEGUARD_BIGQUERY_ENABLED="true",RATEGUARD_BIGQUERY_DATASET="rateguard",RATEGUARD_BIGQUERY_PORTFOLIO_TABLE="synthetic_policies",RATEGUARD_BIGQUERY_RESULTS_TABLE="portfolio_exposure_results",RATEGUARD_ASYNC_ENABLED="true",RATEGUARD_PUBSUB_TOPIC="assurance-runs",RATEGUARD_PUBSUB_SUBSCRIPTION="assurance-worker",RATEGUARD_GEMINI_MODEL="gemini-1.5-pro-002"

API_URL=$(gcloud run services describe rateguard-api --region "$REGION" --format "value(status.url)")
echo "   RateGuard API URL: $API_URL"

# 2. Configure Pub/Sub Push Subscription
echo "\n2. Configuring Pub/Sub Push Subscription ('assurance-worker')..."
gcloud pubsub subscriptions modify-push-config assurance-worker \
  --push-endpoint="${API_URL}/internal/pubsub/assurance" \
  --push-auth-service-account="$SERVICE_ACCOUNT"

# 3. Deploy RateGuard Frontend to Cloud Run
echo "\n3. Deploying Next.js Frontend to Cloud Run..."
gcloud run deploy rateguard-web \
  --source ./frontend \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars NEXT_PUBLIC_RATEGUARD_API_URL="$API_URL"

WEB_URL=$(gcloud run services describe rateguard-web --region "$REGION" --format "value(status.url)")
echo "   RateGuard Web Dashboard URL: $WEB_URL"

# 4. Update Backend CORS Config for Deployed Web Origin
echo "\n4. Updating Backend CORS for Deployed Web Origin..."
gcloud run services update rateguard-api \
  --region "$REGION" \
  --update-env-vars RATEGUARD_CORS_ORIGINS="[\"http://localhost:3000\",\"${WEB_URL}\"]"

echo "\n========================================================"
echo "DEPLOYMENT COMPLETE!"
echo "Public Web Dashboard: $WEB_URL"
echo "Public API URL:       $API_URL"
echo "========================================================"

