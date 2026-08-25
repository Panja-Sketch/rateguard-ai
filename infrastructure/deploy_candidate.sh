#!/usr/bin/env bash
# RateGuard AI -- Isolated Candidate/Staging Deployment
#
# Builds ONE immutable backend image (tagged with the current git commit SHA,
# never `latest`) and deploys it to `rateguard-api` and `rateguard-worker` as
# a `--no-traffic --tag candidate` revision on each -- directly reachable via
# its own tagged URL, receiving ZERO normal production traffic. Candidate
# resources (Pub/Sub topic/subscription/DLQ, Firestore collection) are fully
# isolated from production while sharing the same GCP project and Firestore
# database.
#
# SAFETY: by default (no --deploy-candidate flag) this script performs ZERO
# gcloud/network calls. It only runs `git rev-parse` (local) and prints the
# full plan -- every resource name and every command it would run -- so the
# plan can be reviewed before anything touches Google Cloud. Nothing here
# ever modifies production traffic or the production Pub/Sub push config.

set -euo pipefail

PROJECT_ID="rateguard-ai"
REGION="us-central1"
RUNTIME_SA="rateguard-runtime@rateguard-ai.iam.gserviceaccount.com"
PUBSUB_PUSH_SA="rateguard-pubsub-push@rateguard-ai.iam.gserviceaccount.com"
CANDIDATE_TAG="candidate"

# Staging/candidate Pub/Sub + Firestore resource names -- fully isolated from
# production (assurance-runs / assurance-worker / assurance_runs).
STAGING_TOPIC="assurance-runs-staging"
STAGING_SUBSCRIPTION="assurance-worker-staging"
STAGING_DLQ_TOPIC="assurance-runs-staging-dlq"
STAGING_DLQ_INSPECTION_SUBSCRIPTION="assurance-runs-staging-dlq-inspect"
STAGING_FIRESTORE_COLLECTION="assurance_runs_staging"

# Same alignment rationale as production (see infrastructure/deploy.sh):
# 600s is Pub/Sub's hard ack-deadline maximum, giving a safe buffer over
# whatever the candidate worker's Cloud Run request timeout is configured to.
ACK_DEADLINE_SECONDS=600
MIN_RETRY_BACKOFF_SECONDS=10
MAX_RETRY_BACKOFF_SECONDS=600
MAX_DELIVERY_ATTEMPTS=5

# Immutable image identity: the git commit SHA, never `latest`. Both
# rateguard-api and rateguard-worker candidate revisions deploy this EXACT
# same image reference (by tag here; --deploy-candidate additionally resolves
# and logs the pushed digest so the two services can be verified to share the
# same digest, not just the same tag).
GIT_SHA="$(git rev-parse --short=12 HEAD 2>/dev/null || echo 'UNKNOWN_SHA')"
IMAGE_TAG="candidate-${GIT_SHA}"
BACKEND_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/rateguard/rateguard-api:${IMAGE_TAG}"
FRONTEND_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/rateguard/rateguard-web:${IMAGE_TAG}"

CANDIDATE_ENV_FILE="infrastructure/.candidate-env.yaml"

DEPLOY_CANDIDATE=false
for arg in "$@"; do
  case "$arg" in
    --deploy-candidate) DEPLOY_CANDIDATE=true ;;
    --help|-h)
      echo "Usage: $0 [--deploy-candidate]"
      echo "  (no flag)           Print the full candidate deployment plan. No GCP calls."
      echo "  --deploy-candidate  Actually build and deploy the candidate resources."
      exit 0
      ;;
  esac
done

print_plan() {
  cat <<PLAN
========================================================
   RateGuard AI -- Candidate/Staging Deployment PLAN
   (dry-run: no gcloud command below has been executed)
========================================================
Project:                       ${PROJECT_ID}
Region:                        ${REGION}
Git commit:                    ${GIT_SHA}
Immutable image tag:           ${IMAGE_TAG}
Backend image (api + worker):  ${BACKEND_IMAGE}
Frontend image:                ${FRONTEND_IMAGE}
Cloud Run candidate tag:       ${CANDIDATE_TAG} (--no-traffic)
Runtime service account:       ${RUNTIME_SA} (no API key)

Isolated staging resources (production is untouched):
  Pub/Sub topic:                 ${STAGING_TOPIC}
  Pub/Sub subscription:          ${STAGING_SUBSCRIPTION}
  Dead-letter topic:             ${STAGING_DLQ_TOPIC}
  Dead-letter inspection sub:    ${STAGING_DLQ_INSPECTION_SUBSCRIPTION}
  Firestore collection:          ${STAGING_FIRESTORE_COLLECTION}
  Ack deadline:                  ${ACK_DEADLINE_SECONDS}s
  Retry backoff:                 ${MIN_RETRY_BACKOFF_SECONDS}s - ${MAX_RETRY_BACKOFF_SECONDS}s
  Max delivery attempts:         ${MAX_DELIVERY_ATTEMPTS}

Candidate env vars (non-secret; no API key is ever set):
  RATEGUARD_AGENT_ENABLED=true
  GOOGLE_GENAI_USE_VERTEXAI=true
  GOOGLE_CLOUD_PROJECT=${PROJECT_ID}
  GOOGLE_CLOUD_LOCATION=global
  RATEGUARD_GEMINI_MODEL=gemini-3.7-flash
  RATEGUARD_RUN_STORE=firestore
  RATEGUARD_FIRESTORE_COLLECTION=${STAGING_FIRESTORE_COLLECTION}
  RATEGUARD_PUBSUB_TOPIC=${STAGING_TOPIC}
  RATEGUARD_PUBSUB_SUBSCRIPTION=${STAGING_SUBSCRIPTION}
  (all other values inherited from infrastructure/runtime-env.yaml: project,
   region, GCS bucket, Firestore database id, BigQuery dataset/tables, CORS)

Exact commands that --deploy-candidate would run, in order:

  1) Build the image ONCE:
     gcloud builds submit . --config=./backend/cloudbuild.yaml \\
       --substitutions=_IMAGE_TAG=${IMAGE_TAG}

  2) Deploy the SAME image digest to both candidate revisions, 0% traffic:
     gcloud run deploy rateguard-api \\
       --image ${BACKEND_IMAGE} --region ${REGION} --platform managed \\
       --no-traffic --tag ${CANDIDATE_TAG} \\
       --allow-unauthenticated --service-account ${RUNTIME_SA} \\
       --memory=512Mi --env-vars-file=${CANDIDATE_ENV_FILE}

     gcloud run deploy rateguard-worker \\
       --image ${BACKEND_IMAGE} --region ${REGION} --platform managed \\
       --no-traffic --tag ${CANDIDATE_TAG} \\
       --no-allow-unauthenticated --service-account ${RUNTIME_SA} \\
       --memory=1Gi --env-vars-file=${CANDIDATE_ENV_FILE}

  3) Idempotently create/update staging Pub/Sub topic + DLQ + subscription,
     pointed at the candidate-tagged worker URL only (never production):
     gcloud pubsub topics create ${STAGING_TOPIC}                 (if missing)
     gcloud pubsub topics create ${STAGING_DLQ_TOPIC}             (if missing)
     gcloud pubsub subscriptions create ${STAGING_SUBSCRIPTION} \\
       --topic=${STAGING_TOPIC} --ack-deadline=${ACK_DEADLINE_SECONDS} \\
       --min-retry-delay=${MIN_RETRY_BACKOFF_SECONDS}s --max-retry-delay=${MAX_RETRY_BACKOFF_SECONDS}s \\
       --dead-letter-topic=${STAGING_DLQ_TOPIC} --max-delivery-attempts=${MAX_DELIVERY_ATTEMPTS} \\
       --push-endpoint=<candidate-worker-tagged-url>/internal/pubsub/assurance \\
       --push-auth-service-account=${PUBSUB_PUSH_SA}
     gcloud pubsub subscriptions create ${STAGING_DLQ_INSPECTION_SUBSCRIPTION} \\
       --topic=${STAGING_DLQ_TOPIC}                               (if missing)
     gcloud pubsub topics add-iam-policy-binding ${STAGING_DLQ_TOPIC} \\
       --member=serviceAccount:<pubsub-service-agent> --role=roles/pubsub.publisher
     gcloud pubsub subscriptions add-iam-policy-binding ${STAGING_SUBSCRIPTION} \\
       --member=serviceAccount:<pubsub-service-agent> --role=roles/pubsub.subscriber

  4) Candidate frontend (API URL is baked in at build time -- see
     frontend/src/lib/api/client.ts's NEXT_PUBLIC_RATEGUARD_API_URL -- so a
     genuinely isolated candidate frontend needs its own build pointed only
     at the candidate-tagged API URL, never the production one):
     gcloud builds submit ./frontend --config=./frontend/cloudbuild.yaml \\
       --substitutions=_IMAGE_TAG=${IMAGE_TAG},_NEXT_PUBLIC_RATEGUARD_API_URL=<candidate-api-tagged-url>
     gcloud run deploy rateguard-web \\
       --image ${FRONTEND_IMAGE} --region ${REGION} --platform managed \\
       --no-traffic --tag ${CANDIDATE_TAG} --allow-unauthenticated

NOT done by this script, ever:
  - No production traffic change (no 'gcloud run services update-traffic').
  - No change to the production Pub/Sub subscription's push config.
  - No API key is added anywhere.
  - No production promotion (see infrastructure/promote_candidate.sh).

Re-run this plan any time with no arguments. Pass --deploy-candidate to
actually execute it.
PLAN
}

write_candidate_env_file() {
  cp infrastructure/runtime-env.yaml "$CANDIDATE_ENV_FILE"
  # Remove production-only Pub/Sub keys so the staging overrides below are
  # unambiguous (avoids two conflicting values for the same key in one file).
  grep -v -E '^(RATEGUARD_PUBSUB_TOPIC|RATEGUARD_PUBSUB_SUBSCRIPTION|RATEGUARD_FIRESTORE_COLLECTION|RATEGUARD_AGENT_ENABLED|GOOGLE_GENAI_USE_VERTEXAI|GOOGLE_CLOUD_PROJECT|GOOGLE_CLOUD_LOCATION|RATEGUARD_GEMINI_MODEL|RATEGUARD_RUN_STORE):' \
    infrastructure/runtime-env.yaml > "$CANDIDATE_ENV_FILE"
  cat >> "$CANDIDATE_ENV_FILE" <<ENV
RATEGUARD_AGENT_ENABLED: "true"
GOOGLE_GENAI_USE_VERTEXAI: "true"
GOOGLE_CLOUD_PROJECT: "${PROJECT_ID}"
GOOGLE_CLOUD_LOCATION: "global"
RATEGUARD_GEMINI_MODEL: "gemini-3.7-flash"
RATEGUARD_RUN_STORE: "firestore"
RATEGUARD_PUBSUB_TOPIC: "${STAGING_TOPIC}"
RATEGUARD_PUBSUB_SUBSCRIPTION: "${STAGING_SUBSCRIPTION}"
RATEGUARD_FIRESTORE_COLLECTION: "${STAGING_FIRESTORE_COLLECTION}"
ENV
}

deploy_candidate() {
  echo "========================================================"
  echo "   RateGuard AI -- Deploying Candidate (--deploy-candidate)"
  echo "   Image tag: ${IMAGE_TAG}"
  echo "========================================================"

  gcloud config set project "$PROJECT_ID"

  PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
  PUBSUB_SERVICE_AGENT="service-${PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com"

  write_candidate_env_file

  echo "1. Building candidate backend image (immutable tag, never latest)..."
  gcloud builds submit . --config=./backend/cloudbuild.yaml \
    --substitutions=_IMAGE_TAG="$IMAGE_TAG"

  echo "2. Deploying candidate API revision (--no-traffic --tag ${CANDIDATE_TAG})..."
  gcloud run deploy rateguard-api \
    --image "$BACKEND_IMAGE" --region "$REGION" --platform managed \
    --no-traffic --tag "$CANDIDATE_TAG" \
    --allow-unauthenticated --service-account "$RUNTIME_SA" \
    --memory=512Mi --env-vars-file="$CANDIDATE_ENV_FILE"

  CANDIDATE_API_URL=$(gcloud run services describe rateguard-api --region "$REGION" \
    --format "value(status.traffic[?tag==\"${CANDIDATE_TAG}\"].url)" 2>/dev/null || true)
  if [ -z "$CANDIDATE_API_URL" ]; then
    CANDIDATE_API_URL=$(gcloud run services describe rateguard-api --region "$REGION" \
      --format "value(status.address.url)" | sed "s#://#://${CANDIDATE_TAG}---#")
  fi
  echo "   Candidate API URL: ${CANDIDATE_API_URL}"

  echo "3. Deploying candidate worker revision (--no-traffic --tag ${CANDIDATE_TAG})..."
  gcloud run deploy rateguard-worker \
    --image "$BACKEND_IMAGE" --region "$REGION" --platform managed \
    --no-traffic --tag "$CANDIDATE_TAG" \
    --no-allow-unauthenticated --service-account "$RUNTIME_SA" \
    --memory=1Gi --env-vars-file="$CANDIDATE_ENV_FILE"

  CANDIDATE_WORKER_URL=$(gcloud run services describe rateguard-worker --region "$REGION" \
    --format "value(status.traffic[?tag==\"${CANDIDATE_TAG}\"].url)" 2>/dev/null || true)
  if [ -z "$CANDIDATE_WORKER_URL" ]; then
    CANDIDATE_WORKER_URL=$(gcloud run services describe rateguard-worker --region "$REGION" \
      --format "value(status.address.url)" | sed "s#://#://${CANDIDATE_TAG}---#")
  fi
  echo "   Candidate Worker URL: ${CANDIDATE_WORKER_URL}"

  echo "4. Idempotently configuring isolated staging Pub/Sub + DLQ..."
  if ! gcloud pubsub topics describe "$STAGING_TOPIC" >/dev/null 2>&1; then
    gcloud pubsub topics create "$STAGING_TOPIC"
  fi
  if ! gcloud pubsub topics describe "$STAGING_DLQ_TOPIC" >/dev/null 2>&1; then
    gcloud pubsub topics create "$STAGING_DLQ_TOPIC"
  fi
  if ! gcloud pubsub subscriptions describe "$STAGING_SUBSCRIPTION" >/dev/null 2>&1; then
    gcloud pubsub subscriptions create "$STAGING_SUBSCRIPTION" \
      --topic="$STAGING_TOPIC" \
      --ack-deadline="$ACK_DEADLINE_SECONDS" \
      --min-retry-delay="${MIN_RETRY_BACKOFF_SECONDS}s" \
      --max-retry-delay="${MAX_RETRY_BACKOFF_SECONDS}s" \
      --dead-letter-topic="$STAGING_DLQ_TOPIC" \
      --max-delivery-attempts="$MAX_DELIVERY_ATTEMPTS" \
      --push-endpoint="${CANDIDATE_WORKER_URL}/internal/pubsub/assurance" \
      --push-auth-service-account="$PUBSUB_PUSH_SA"
  else
    gcloud pubsub subscriptions update "$STAGING_SUBSCRIPTION" \
      --ack-deadline="$ACK_DEADLINE_SECONDS" \
      --min-retry-delay="${MIN_RETRY_BACKOFF_SECONDS}s" \
      --max-retry-delay="${MAX_RETRY_BACKOFF_SECONDS}s" \
      --dead-letter-topic="$STAGING_DLQ_TOPIC" \
      --max-delivery-attempts="$MAX_DELIVERY_ATTEMPTS"
    gcloud pubsub subscriptions modify-push-config "$STAGING_SUBSCRIPTION" \
      --push-endpoint="${CANDIDATE_WORKER_URL}/internal/pubsub/assurance" \
      --push-auth-service-account="$PUBSUB_PUSH_SA"
  fi
  if ! gcloud pubsub subscriptions describe "$STAGING_DLQ_INSPECTION_SUBSCRIPTION" >/dev/null 2>&1; then
    gcloud pubsub subscriptions create "$STAGING_DLQ_INSPECTION_SUBSCRIPTION" --topic="$STAGING_DLQ_TOPIC"
  fi
  gcloud pubsub topics add-iam-policy-binding "$STAGING_DLQ_TOPIC" \
    --member="serviceAccount:$PUBSUB_SERVICE_AGENT" --role="roles/pubsub.publisher" >/dev/null
  gcloud pubsub subscriptions add-iam-policy-binding "$STAGING_SUBSCRIPTION" \
    --member="serviceAccount:$PUBSUB_SERVICE_AGENT" --role="roles/pubsub.subscriber" >/dev/null

  echo "5. Building and deploying candidate frontend (--no-traffic --tag ${CANDIDATE_TAG})..."
  gcloud builds submit ./frontend --config=./frontend/cloudbuild.yaml \
    --substitutions=_IMAGE_TAG="$IMAGE_TAG",_NEXT_PUBLIC_RATEGUARD_API_URL="$CANDIDATE_API_URL"
  gcloud run deploy rateguard-web \
    --image "$FRONTEND_IMAGE" --region "$REGION" --platform managed \
    --no-traffic --tag "$CANDIDATE_TAG" --allow-unauthenticated

  CANDIDATE_WEB_URL=$(gcloud run services describe rateguard-web --region "$REGION" \
    --format "value(status.traffic[?tag==\"${CANDIDATE_TAG}\"].url)" 2>/dev/null || true)

  rm -f "$CANDIDATE_ENV_FILE"

  echo "========================================================"
  echo "CANDIDATE DEPLOYMENT COMPLETE (0% production traffic)"
  echo "Candidate API URL:      ${CANDIDATE_API_URL}"
  echo "Candidate Worker URL:   ${CANDIDATE_WORKER_URL}"
  echo "Candidate Web URL:      ${CANDIDATE_WEB_URL}"
  echo "Image tag:              ${IMAGE_TAG}"
  echo ""
  echo "Next step: python backend/scripts/verify_candidate.py --yes-test-candidate \\"
  echo "  --api-url ${CANDIDATE_API_URL} --frontend-url ${CANDIDATE_WEB_URL}"
  echo "========================================================"
}

if [ "$DEPLOY_CANDIDATE" = true ]; then
  deploy_candidate
else
  print_plan
fi
