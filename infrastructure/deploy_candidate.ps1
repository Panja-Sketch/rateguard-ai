# RateGuard AI -- Isolated Candidate/Staging Deployment (PowerShell mirror of deploy_candidate.sh)
#
# SAFETY: by default (no -DeployCandidate/-ResumeCandidate switch) this script
# performs ZERO gcloud/bq/gsutil/network calls. It only runs `git rev-parse`
# (local) and prints the full plan. Nothing here ever modifies production
# traffic or the production Pub/Sub push config. See deploy_candidate.sh for
# the full command-by-command rationale -- this file mirrors it.
#
# -DeployCandidate builds and deploys every candidate resource from scratch.
# -ResumeCandidate is for continuing a partially-completed candidate
# deployment: it discovers and verifies what already exists, skips backend
# rebuild/redeploy when the deployed image matches the current git commit,
# and provisions only what is still missing. The two switches are mutually
# exclusive.

param(
    [switch]$DeployCandidate,
    [switch]$ResumeCandidate
)

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "lib\CandidateDeployLib.ps1")

function Assert-MutuallyExclusiveModes {
    param([switch]$DeployCandidate, [switch]$ResumeCandidate)
    if ($DeployCandidate -and $ResumeCandidate) {
        throw "-DeployCandidate and -ResumeCandidate are mutually exclusive. Pass exactly one."
    }
}

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

$EXPECTED_STAGING_ENV = @{
    "RATEGUARD_PUBSUB_TOPIC"              = $STAGING_TOPIC
    "RATEGUARD_PUBSUB_SUBSCRIPTION"       = $STAGING_SUBSCRIPTION
    "RATEGUARD_FIRESTORE_COLLECTION"      = $STAGING_FIRESTORE_COLLECTION
    "RATEGUARD_BIGQUERY_DATASET"          = $STAGING_BIGQUERY_DATASET
    "RATEGUARD_BIGQUERY_PORTFOLIO_TABLE"  = $STAGING_BIGQUERY_PORTFOLIO_TABLE
    "RATEGUARD_BIGQUERY_RESULTS_TABLE"    = $STAGING_BIGQUERY_RESULTS_TABLE
    "RATEGUARD_GCS_BUCKET"                = $STAGING_GCS_BUCKET
}

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
    Write-Host "Exact commands that -DeployCandidate would run, in order:"
    Write-Host "  1) gcloud builds submit . --config=./backend/cloudbuild.yaml --substitutions=_IMAGE_TAG=$IMAGE_TAG"
    Write-Host "  2) gcloud run deploy rateguard-api / rateguard-worker --no-traffic --tag $CANDIDATE_TAG --env-vars-file=$CANDIDATE_ENV_FILE"
    Write-Host "  3) gcloud run services describe rateguard-api/rateguard-worker --format=json (reliable tagged + untagged URL discovery)"
    Write-Host "  4) Idempotent create/update: $STAGING_TOPIC, $STAGING_DLQ_TOPIC, $STAGING_SUBSCRIPTION"
    Write-Host "     (push -> <candidate-worker-tagged-url>/internal/pubsub/assurance, OIDC audience -> <untagged-worker-url>),"
    Write-Host "     $STAGING_DLQ_INSPECTION_SUBSCRIPTION, narrow DLQ IAM bindings"
    Write-Host "  5) Idempotently provision $STAGING_BIGQUERY_DATASET dataset/tables and load ONLY the synthetic demo portfolio; idempotently create gs://$STAGING_GCS_BUCKET"
    Write-Host "  6) gcloud builds submit ./frontend --config=./frontend/cloudbuild.yaml --substitutions=_IMAGE_TAG=$IMAGE_TAG,_NEXT_PUBLIC_RATEGUARD_API_URL=<candidate-api-tagged-url>"
    Write-Host "     gcloud run deploy rateguard-web --no-traffic --tag $CANDIDATE_TAG"
    Write-Host "  7) Full postcondition verification before the success banner is ever printed."
    Write-Host ""
    Write-Host "-ResumeCandidate additionally: discovers/verifies existing backend"
    Write-Host "image+revisions+URLs, skips backend/API/worker rebuild when the deployed"
    Write-Host "image already matches this git commit, and provisions only whatever"
    Write-Host "staging Pub/Sub/BigQuery/GCS/frontend resources are still missing."
    Write-Host ""
    Write-Host "NOT done by this script, ever: no production traffic change, no change"
    Write-Host "to the production Pub/Sub push config, no write to the production BigQuery"
    Write-Host "dataset ('rateguard') or bucket ('rateguard-ai-artifacts'), no API key, no promotion."
    Write-Host ""
    Write-Host "Re-run with no arguments to see this plan again. Pass -DeployCandidate to execute,"
    Write-Host "or -ResumeCandidate to continue a partially-completed candidate deployment."
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

function Get-CandidateServiceInfo {
    # Read-only `gcloud run services describe --format=json`, restricted to
    # only the fields this script needs (traffic/url/image/env) -- never the
    # full resource, and never parses human-formatted table output.
    param([Parameter(Mandatory = $true)][string]$ServiceName)
    $lines = Invoke-NativeCommand -Operation "Describe $ServiceName" -FilePath "gcloud" -CaptureOutput -ArgumentList @(
        "run", "services", "describe", $ServiceName,
        "--region", $REGION,
        "--format", "json(status.traffic,status.url,status.address,spec.template.spec.containers)"
    )
    return ConvertFrom-CloudRunServiceJson -JsonLines $lines -ServiceName $ServiceName
}

function Get-ValidatedCandidateBackendUrls {
    # Stops (throws) before any Pub/Sub or frontend operation if either
    # candidate tagged URL is missing or invalid -- this is the fix for the
    # original script silently falling back to a bare '/internal/pubsub/assurance'
    # push endpoint.
    $apiInfo = Get-CandidateServiceInfo -ServiceName "rateguard-api"
    $workerInfo = Get-CandidateServiceInfo -ServiceName "rateguard-worker"

    $apiTaggedUrl = Get-CandidateTaggedUrl -ServiceInfo $apiInfo -Tag $CANDIDATE_TAG
    $workerTaggedUrl = Get-CandidateTaggedUrl -ServiceInfo $workerInfo -Tag $CANDIDATE_TAG
    $workerUntaggedUrl = Get-UntaggedServiceUrl -ServiceInfo $workerInfo
    $apiUntaggedUrl = Get-UntaggedServiceUrl -ServiceInfo $apiInfo

    if (-not (Test-AbsoluteHttpsUrl -Url $apiTaggedUrl -RequiredHostFragment "rateguard-api" -RequireCandidateTagPrefix)) {
        throw "Candidate API tagged URL could not be discovered from 'gcloud run services describe rateguard-api --format=json' (traffic entry with tag='$CANDIDATE_TAG'). Refusing to continue."
    }
    if (-not (Test-AbsoluteHttpsUrl -Url $workerTaggedUrl -RequiredHostFragment "rateguard-worker" -RequireCandidateTagPrefix)) {
        throw "Candidate worker tagged URL could not be discovered from 'gcloud run services describe rateguard-worker --format=json' (traffic entry with tag='$CANDIDATE_TAG'). Refusing to continue."
    }
    if (-not (Test-AbsoluteHttpsUrl -Url $workerUntaggedUrl -RequiredHostFragment "rateguard-worker")) {
        throw "Untagged rateguard-worker service URL could not be discovered. Refusing to continue."
    }

    return [pscustomobject]@{
        ApiInfo           = $apiInfo
        WorkerInfo        = $workerInfo
        ApiTaggedUrl      = $apiTaggedUrl
        WorkerTaggedUrl   = $workerTaggedUrl
        ApiUntaggedUrl    = $apiUntaggedUrl
        WorkerUntaggedUrl = $workerUntaggedUrl
    }
}

function Resolve-PubSubServiceAgent {
    $lines = Invoke-NativeCommand -Operation "Resolving project number" -FilePath "gcloud" -CaptureOutput -ArgumentList @(
        "projects", "describe", $PROJECT_ID, "--format", "value(projectNumber)"
    )
    $projectNumber = (($lines -join "") ).Trim()
    if (-not $projectNumber) { throw "Could not resolve project number for '$PROJECT_ID'." }
    return "service-$projectNumber@gcp-sa-pubsub.iam.gserviceaccount.com"
}

function Initialize-StagingPubSub {
    # Idempotently creates/updates the isolated staging topic, DLQ topic,
    # push subscription (pointed at the candidate-tagged worker URL, OIDC
    # audience pinned to the untagged worker URL) and DLQ inspection
    # subscription. Every mutating call uses the checked execution pattern;
    # the IAM-binding calls only run after subscription create/update has
    # already succeeded (throw would have aborted the script otherwise).
    param(
        [Parameter(Mandatory = $true)][string]$WorkerTaggedUrl,
        [Parameter(Mandatory = $true)][string]$WorkerUntaggedUrl
    )

    $pushEndpoint = New-PubSubPushEndpoint -CandidateWorkerTaggedUrl $WorkerTaggedUrl
    $audience = Get-PubSubOidcAudience -UntaggedWorkerServiceUrl $WorkerUntaggedUrl

    $topicExists = $null
    try { $topicExists = gcloud pubsub topics describe "$STAGING_TOPIC" --format="value(name)" 2>$null } catch {}
    if (-not $topicExists) {
        Invoke-NativeCommand -Operation "Create topic $STAGING_TOPIC" -FilePath "gcloud" -ArgumentList @("pubsub", "topics", "create", $STAGING_TOPIC)
    }

    $dlqExists = $null
    try { $dlqExists = gcloud pubsub topics describe "$STAGING_DLQ_TOPIC" --format="value(name)" 2>$null } catch {}
    if (-not $dlqExists) {
        Invoke-NativeCommand -Operation "Create DLQ topic $STAGING_DLQ_TOPIC" -FilePath "gcloud" -ArgumentList @("pubsub", "topics", "create", $STAGING_DLQ_TOPIC)
    }

    $subExists = $null
    try { $subExists = gcloud pubsub subscriptions describe "$STAGING_SUBSCRIPTION" --format="value(name)" 2>$null } catch {}
    if (-not $subExists) {
        Invoke-NativeCommand -Operation "Create subscription $STAGING_SUBSCRIPTION" -FilePath "gcloud" -ArgumentList @(
            "pubsub", "subscriptions", "create", $STAGING_SUBSCRIPTION,
            "--topic=$STAGING_TOPIC",
            "--ack-deadline=$ACK_DEADLINE_SECONDS",
            "--min-retry-delay=${MIN_RETRY_BACKOFF_SECONDS}s",
            "--max-retry-delay=${MAX_RETRY_BACKOFF_SECONDS}s",
            "--dead-letter-topic=$STAGING_DLQ_TOPIC",
            "--max-delivery-attempts=$MAX_DELIVERY_ATTEMPTS",
            "--push-endpoint=$pushEndpoint",
            "--push-auth-service-account=$PUBSUB_PUSH_SA",
            "--push-auth-token-audience=$audience"
        )
    } else {
        Invoke-NativeCommand -Operation "Update subscription $STAGING_SUBSCRIPTION" -FilePath "gcloud" -ArgumentList @(
            "pubsub", "subscriptions", "update", $STAGING_SUBSCRIPTION,
            "--ack-deadline=$ACK_DEADLINE_SECONDS",
            "--min-retry-delay=${MIN_RETRY_BACKOFF_SECONDS}s",
            "--max-retry-delay=${MAX_RETRY_BACKOFF_SECONDS}s",
            "--dead-letter-topic=$STAGING_DLQ_TOPIC",
            "--max-delivery-attempts=$MAX_DELIVERY_ATTEMPTS"
        )
        Invoke-NativeCommand -Operation "Update push config for $STAGING_SUBSCRIPTION" -FilePath "gcloud" -ArgumentList @(
            "pubsub", "subscriptions", "modify-push-config", $STAGING_SUBSCRIPTION,
            "--push-endpoint=$pushEndpoint",
            "--push-auth-service-account=$PUBSUB_PUSH_SA",
            "--push-auth-token-audience=$audience"
        )
    }

    $dlqSubExists = $null
    try { $dlqSubExists = gcloud pubsub subscriptions describe "$STAGING_DLQ_INSPECTION_SUBSCRIPTION" --format="value(name)" 2>$null } catch {}
    if (-not $dlqSubExists) {
        Invoke-NativeCommand -Operation "Create DLQ inspection subscription" -FilePath "gcloud" -ArgumentList @(
            "pubsub", "subscriptions", "create", $STAGING_DLQ_INSPECTION_SUBSCRIPTION, "--topic=$STAGING_DLQ_TOPIC"
        )
    }

    $pubsubServiceAgent = Resolve-PubSubServiceAgent
    Invoke-NativeCommand -Operation "Grant publisher on DLQ topic" -FilePath "gcloud" -ArgumentList @(
        "pubsub", "topics", "add-iam-policy-binding", $STAGING_DLQ_TOPIC,
        "--member=serviceAccount:$pubsubServiceAgent", "--role=roles/pubsub.publisher"
    ) | Out-Null
    Invoke-NativeCommand -Operation "Grant subscriber on $STAGING_SUBSCRIPTION" -FilePath "gcloud" -ArgumentList @(
        "pubsub", "subscriptions", "add-iam-policy-binding", $STAGING_SUBSCRIPTION,
        "--member=serviceAccount:$pubsubServiceAgent", "--role=roles/pubsub.subscriber"
    ) | Out-Null
}

function Initialize-StagingDataResources {
    # Idempotently provisions the staging BigQuery dataset/tables and loads
    # ONLY the synthetic demo portfolio -- upload_synthetic_portfolio_bigquery.py
    # already skips the load itself when the table already holds 50,000 rows,
    # so calling it again here is always safe and never re-loads needlessly.
    # Idempotently creates the isolated staging GCS bucket.
    $env:RATEGUARD_BIGQUERY_DATASET = $STAGING_BIGQUERY_DATASET
    $env:RATEGUARD_BIGQUERY_PORTFOLIO_TABLE = $STAGING_BIGQUERY_PORTFOLIO_TABLE
    $env:RATEGUARD_BIGQUERY_RESULTS_TABLE = $STAGING_BIGQUERY_RESULTS_TABLE
    try {
        Invoke-NativeCommand -Operation "Provision staging BigQuery dataset/tables" -FilePath "python" -ArgumentList @("backend/scripts/setup_bigquery.py")
        Invoke-NativeCommand -Operation "Load synthetic portfolio into staging BigQuery" -FilePath "python" -ArgumentList @("backend/scripts/upload_synthetic_portfolio_bigquery.py")
    } finally {
        Remove-Item Env:\RATEGUARD_BIGQUERY_DATASET, Env:\RATEGUARD_BIGQUERY_PORTFOLIO_TABLE, Env:\RATEGUARD_BIGQUERY_RESULTS_TABLE -ErrorAction SilentlyContinue
    }

    $bucketExists = $null
    try { $bucketExists = gcloud storage buckets describe "gs://$STAGING_GCS_BUCKET" --format="value(name)" 2>$null } catch {}
    if (-not $bucketExists) {
        Invoke-NativeCommand -Operation "Create staging GCS bucket" -FilePath "gcloud" -ArgumentList @(
            "storage", "buckets", "create", "gs://$STAGING_GCS_BUCKET",
            "--project=$PROJECT_ID", "--location=$REGION", "--uniform-bucket-level-access"
        )
    } else {
        Write-Host "   Bucket gs://$STAGING_GCS_BUCKET already exists."
    }
}

function Deploy-CandidateFrontend {
    # Builds and deploys the candidate frontend using ONE comma-separated
    # --substitutions argument (never a space-separated array, never
    # concatenated into the image name), and verifies the built image
    # actually exists in Artifact Registry before attempting to deploy it.
    param([Parameter(Mandatory = $true)][string]$CandidateApiUrl)

    if (-not (Test-ImageReferenceNoSpaces -ImageReference $FRONTEND_IMAGE)) {
        throw "Frontend image reference contains whitespace: '$FRONTEND_IMAGE'"
    }
    $substitutions = New-FrontendSubstitutionsArg -ImageTag $IMAGE_TAG -CandidateApiUrl $CandidateApiUrl

    Invoke-NativeCommand -Operation "Frontend Cloud Build" -FilePath "gcloud" -ArgumentList @(
        "builds", "submit", "./frontend",
        "--config=./frontend/cloudbuild.yaml",
        "--substitutions=$substitutions"
    )

    Invoke-NativeCommand -Operation "Verify candidate frontend image exists" -FilePath "gcloud" -ArgumentList @(
        "artifacts", "docker", "images", "describe", $FRONTEND_IMAGE, "--format", "value(image_summary.digest)"
    ) | Out-Null

    Invoke-NativeCommand -Operation "rateguard-web candidate deployment" -FilePath "gcloud" -ArgumentList @(
        "run", "deploy", "rateguard-web",
        "--image", $FRONTEND_IMAGE, "--region", $REGION, "--platform", "managed",
        "--no-traffic", "--tag", $CANDIDATE_TAG, "--allow-unauthenticated"
    )

    $webInfo = Get-CandidateServiceInfo -ServiceName "rateguard-web"
    $webTaggedUrl = Get-CandidateTaggedUrl -ServiceInfo $webInfo -Tag $CANDIDATE_TAG
    if (-not (Test-AbsoluteHttpsUrl -Url $webTaggedUrl -RequiredHostFragment "rateguard-web" -RequireCandidateTagPrefix)) {
        throw "Candidate web tagged URL could not be discovered after deployment. Refusing to print success."
    }
    return $webTaggedUrl
}

function Confirm-CandidatePostconditions {
    # Verifies every postcondition required before the success banner may be
    # printed. Returns an array of failure reasons (empty = all satisfied).
    # Never throws on a missing resource -- collects every failure so the
    # caller can report a complete, concise picture in one pass.
    param([Parameter(Mandatory = $true)][string]$WorkerTaggedUrl, [Parameter(Mandatory = $true)][string]$WorkerUntaggedUrl)

    $failures = @()

    $apiInfo = $null; $workerInfo = $null; $webInfo = $null
    try { $apiInfo = Get-CandidateServiceInfo -ServiceName "rateguard-api" } catch { $failures += "rateguard-api describe failed: $($_.Exception.Message)" }
    try { $workerInfo = Get-CandidateServiceInfo -ServiceName "rateguard-worker" } catch { $failures += "rateguard-worker describe failed: $($_.Exception.Message)" }
    try { $webInfo = Get-CandidateServiceInfo -ServiceName "rateguard-web" } catch { $failures += "rateguard-web describe failed: $($_.Exception.Message)" }

    $apiImage = $null; $workerImage = $null

    if ($apiInfo) {
        $apiTaggedUrl = Get-CandidateTaggedUrl -ServiceInfo $apiInfo -Tag $CANDIDATE_TAG
        if (-not (Test-AbsoluteHttpsUrl -Url $apiTaggedUrl -RequiredHostFragment "rateguard-api" -RequireCandidateTagPrefix)) {
            $failures += "candidate API tagged URL missing or invalid"
        }
        if (-not (Test-ProductionTrafficUnchanged -ServiceInfo $apiInfo -CandidateTag $CANDIDATE_TAG)) {
            $failures += "rateguard-api production traffic allocation changed"
        }
        $apiImage = Get-DeployedImageReference -ServiceInfo $apiInfo
        if ($apiImage -ne $BACKEND_IMAGE) { $failures += "rateguard-api candidate revision does not run the expected backend image" }
        $failures += Test-CandidateEnvIsolation -ServiceInfo $apiInfo -ServiceLabel "rateguard-api" -ExpectedStagingValues $EXPECTED_STAGING_ENV
    }

    if ($workerInfo) {
        $workerTaggedUrl = Get-CandidateTaggedUrl -ServiceInfo $workerInfo -Tag $CANDIDATE_TAG
        if (-not (Test-AbsoluteHttpsUrl -Url $workerTaggedUrl -RequiredHostFragment "rateguard-worker" -RequireCandidateTagPrefix)) {
            $failures += "candidate worker tagged URL missing or invalid"
        }
        if (-not (Test-ProductionTrafficUnchanged -ServiceInfo $workerInfo -CandidateTag $CANDIDATE_TAG)) {
            $failures += "rateguard-worker production traffic allocation changed"
        }
        $workerImage = Get-DeployedImageReference -ServiceInfo $workerInfo
        if ($workerImage -ne $BACKEND_IMAGE) { $failures += "rateguard-worker candidate revision does not run the expected backend image" }
        $failures += Test-CandidateEnvIsolation -ServiceInfo $workerInfo -ServiceLabel "rateguard-worker" -ExpectedStagingValues $EXPECTED_STAGING_ENV
    }

    if ($apiImage -and $workerImage -and ($apiImage -ne $workerImage)) {
        $failures += "rateguard-api and rateguard-worker do not share the same backend image"
    }

    if ($webInfo) {
        $webTaggedUrl = Get-CandidateTaggedUrl -ServiceInfo $webInfo -Tag $CANDIDATE_TAG
        if (-not (Test-AbsoluteHttpsUrl -Url $webTaggedUrl -RequiredHostFragment "rateguard-web" -RequireCandidateTagPrefix)) {
            $failures += "candidate web tagged URL missing or invalid"
        }
        if (-not (Test-ProductionTrafficUnchanged -ServiceInfo $webInfo -CandidateTag $CANDIDATE_TAG)) {
            $failures += "rateguard-web production traffic allocation changed"
        }
    }

    try {
        $expectedEndpoint = New-PubSubPushEndpoint -CandidateWorkerTaggedUrl $WorkerTaggedUrl
        $expectedAudience = Get-PubSubOidcAudience -UntaggedWorkerServiceUrl $WorkerUntaggedUrl
        $subLines = Invoke-NativeCommand -Operation "Describe $STAGING_SUBSCRIPTION" -FilePath "gcloud" -CaptureOutput -ArgumentList @(
            "pubsub", "subscriptions", "describe", $STAGING_SUBSCRIPTION, "--format", "json"
        )
        $sub = ($subLines -join "`n") | ConvertFrom-Json
        if ($sub.pushConfig.pushEndpoint -ne $expectedEndpoint) { $failures += "$STAGING_SUBSCRIPTION push endpoint does not match the candidate worker tagged URL + path" }
        if ($sub.pushConfig.oidcToken.audience -ne $expectedAudience) { $failures += "$STAGING_SUBSCRIPTION OIDC audience does not match the untagged worker service URL" }
        $topicName = if ($sub.topic) { ($sub.topic -split '/')[-1] } else { $null }
        if ($topicName -ne $STAGING_TOPIC) { $failures += "$STAGING_SUBSCRIPTION source topic mismatch" }
        $dlqName = if ($sub.deadLetterPolicy -and $sub.deadLetterPolicy.deadLetterTopic) { ($sub.deadLetterPolicy.deadLetterTopic -split '/')[-1] } else { $null }
        if ($dlqName -ne $STAGING_DLQ_TOPIC) { $failures += "$STAGING_SUBSCRIPTION dead-letter topic mismatch" }
        if (-not $sub.ackDeadlineSeconds -or [int]$sub.ackDeadlineSeconds -ne $ACK_DEADLINE_SECONDS) { $failures += "$STAGING_SUBSCRIPTION ack deadline is not $ACK_DEADLINE_SECONDS" }
    } catch {
        $failures += "$STAGING_SUBSCRIPTION verification failed: $($_.Exception.Message)"
    }

    foreach ($table in @($STAGING_BIGQUERY_PORTFOLIO_TABLE, $STAGING_BIGQUERY_RESULTS_TABLE)) {
        try {
            Invoke-NativeCommand -Operation "bq show $STAGING_BIGQUERY_DATASET.$table" -FilePath "bq" -ArgumentList @(
                "show", "--format=none", "$($PROJECT_ID):$STAGING_BIGQUERY_DATASET.$table"
            ) | Out-Null
        } catch {
            $failures += "BigQuery table $STAGING_BIGQUERY_DATASET.$table missing or inaccessible"
        }
    }

    try {
        Invoke-NativeCommand -Operation "Describe staging bucket" -FilePath "gcloud" -ArgumentList @(
            "storage", "buckets", "describe", "gs://$STAGING_GCS_BUCKET", "--format", "value(name)"
        ) | Out-Null
    } catch {
        $failures += "GCS bucket $STAGING_GCS_BUCKET missing"
    }

    try {
        Invoke-NativeCommand -Operation "Describe backend candidate image" -FilePath "gcloud" -ArgumentList @(
            "artifacts", "docker", "images", "describe", $BACKEND_IMAGE, "--format", "value(image_summary.digest)"
        ) | Out-Null
    } catch {
        $failures += "backend candidate image $BACKEND_IMAGE not found in Artifact Registry"
    }

    try {
        Invoke-NativeCommand -Operation "Describe frontend candidate image" -FilePath "gcloud" -ArgumentList @(
            "artifacts", "docker", "images", "describe", $FRONTEND_IMAGE, "--format", "value(image_summary.digest)"
        ) | Out-Null
    } catch {
        $failures += "frontend candidate image $FRONTEND_IMAGE not found in Artifact Registry"
    }

    return $failures
}

function Write-SuccessBanner {
    # Reachable ONLY from the two call sites that already ran
    # Confirm-CandidatePostconditions and confirmed zero failures.
    param([string]$ApiUrl, [string]$WorkerUrl, [string]$WebUrl)
    Write-Host "========================================================"
    Write-Host "CANDIDATE DEPLOYMENT COMPLETE (0% production traffic)"
    Write-Host "Candidate API URL:      $ApiUrl"
    Write-Host "Candidate Worker URL:   $WorkerUrl"
    Write-Host "Candidate Web URL:      $WebUrl"
    Write-Host "Image tag:              $IMAGE_TAG"
    Write-Host "All postconditions verified."
    Write-Host "========================================================"
}

function Complete-CandidateDeployment {
    # Shared tail for both -DeployCandidate and -ResumeCandidate: runs
    # postcondition verification and either prints the success banner or
    # exits nonzero with a concise, safe failure summary. COMPLETE is never
    # printed unless every postcondition passed.
    param([Parameter(Mandatory = $true)]$Urls, [Parameter(Mandatory = $true)][string]$WebUrl)

    $failures = Confirm-CandidatePostconditions -WorkerTaggedUrl $Urls.WorkerTaggedUrl -WorkerUntaggedUrl $Urls.WorkerUntaggedUrl
    if ($failures.Count -gt 0) {
        $reasons = $failures -join "; "
        throw "candidate deployment postcondition verification failed: $reasons"
    }
    Write-SuccessBanner -ApiUrl $Urls.ApiTaggedUrl -WorkerUrl $Urls.WorkerTaggedUrl -WebUrl $WebUrl
}

function Deploy-Candidate {
    Write-Host "========================================================"
    Write-Host "   RateGuard AI -- Deploying Candidate (-DeployCandidate)"
    Write-Host "   Image tag: $IMAGE_TAG"
    Write-Host "========================================================"

    Invoke-NativeCommand -Operation "gcloud config set project" -FilePath "gcloud" -ArgumentList @("config", "set", "project", $PROJECT_ID) | Out-Null

    Write-CandidateEnvFile

    Write-Host "1. Building candidate backend image..."
    Invoke-NativeCommand -Operation "Backend Cloud Build" -FilePath "gcloud" -ArgumentList @(
        "builds", "submit", ".", "--config=./backend/cloudbuild.yaml", "--substitutions=_IMAGE_TAG=$IMAGE_TAG"
    )

    Write-Host "2. Deploying candidate API revision (--no-traffic --tag $CANDIDATE_TAG)..."
    Invoke-NativeCommand -Operation "rateguard-api candidate deployment" -FilePath "gcloud" -ArgumentList @(
        "run", "deploy", "rateguard-api",
        "--image", $BACKEND_IMAGE, "--region", $REGION, "--platform", "managed",
        "--no-traffic", "--tag", $CANDIDATE_TAG,
        "--allow-unauthenticated", "--service-account", $RUNTIME_SA,
        "--memory=512Mi", "--env-vars-file=$CANDIDATE_ENV_FILE"
    )

    Write-Host "3. Deploying candidate worker revision (--no-traffic --tag $CANDIDATE_TAG)..."
    Invoke-NativeCommand -Operation "rateguard-worker candidate deployment" -FilePath "gcloud" -ArgumentList @(
        "run", "deploy", "rateguard-worker",
        "--image", $BACKEND_IMAGE, "--region", $REGION, "--platform", "managed",
        "--no-traffic", "--tag", $CANDIDATE_TAG,
        "--no-allow-unauthenticated", "--service-account", $RUNTIME_SA,
        "--memory=1Gi", "--env-vars-file=$CANDIDATE_ENV_FILE"
    )

    Write-Host "4. Discovering and validating candidate tagged URLs (JSON describe)..."
    $urls = Get-ValidatedCandidateBackendUrls
    Write-Host "   Candidate API URL:    $($urls.ApiTaggedUrl)"
    Write-Host "   Candidate Worker URL: $($urls.WorkerTaggedUrl)"

    Write-Host "5. Idempotently configuring isolated staging Pub/Sub + DLQ..."
    Initialize-StagingPubSub -WorkerTaggedUrl $urls.WorkerTaggedUrl -WorkerUntaggedUrl $urls.WorkerUntaggedUrl

    Write-Host "6. Idempotently provisioning isolated staging BigQuery + GCS..."
    Initialize-StagingDataResources

    Write-Host "7. Building and deploying candidate frontend (--no-traffic --tag $CANDIDATE_TAG)..."
    $webUrl = Deploy-CandidateFrontend -CandidateApiUrl $urls.ApiTaggedUrl

    Remove-Item "$CANDIDATE_ENV_FILE" -Force -ErrorAction SilentlyContinue

    Write-Host "8. Verifying postconditions..."
    Complete-CandidateDeployment -Urls $urls -WebUrl $webUrl
}

function Resume-Candidate {
    Write-Host "========================================================"
    Write-Host "   RateGuard AI -- Resuming Candidate (-ResumeCandidate)"
    Write-Host "   Expected image tag: $IMAGE_TAG"
    Write-Host "========================================================"

    Invoke-NativeCommand -Operation "gcloud config set project" -FilePath "gcloud" -ArgumentList @("config", "set", "project", $PROJECT_ID) | Out-Null

    Write-Host "1. Discovering and verifying existing backend image/tag/digest..."
    $urls = Get-ValidatedCandidateBackendUrls
    $apiImage = Get-DeployedImageReference -ServiceInfo $urls.ApiInfo
    $workerImage = Get-DeployedImageReference -ServiceInfo $urls.WorkerInfo

    if ($apiImage -ne $workerImage) {
        throw "Mismatch: rateguard-api candidate image ('$apiImage') differs from rateguard-worker candidate image ('$workerImage'). Refusing to silently reconcile -- investigate before resuming."
    }
    if ($apiImage -ne $BACKEND_IMAGE) {
        throw "Mismatch: the deployed candidate image ('$apiImage') does not match the expected image for the current git commit ('$BACKEND_IMAGE'). Refusing to silently rebuild or redeploy. Either check out the commit that was actually built, or run -DeployCandidate to build the current commit from scratch."
    }
    Write-Host "   Existing candidate image confirmed: $apiImage"
    Write-Host "   Candidate API URL:    $($urls.ApiTaggedUrl)"
    Write-Host "   Candidate Worker URL: $($urls.WorkerTaggedUrl)"
    Write-Host "2. Backend image/API/worker already match the expected commit -- skipping rebuild and redeploy."

    Write-Host "3. Verifying/creating the missing staging push subscription (and re-verifying topics/DLQ)..."
    Initialize-StagingPubSub -WorkerTaggedUrl $urls.WorkerTaggedUrl -WorkerUntaggedUrl $urls.WorkerUntaggedUrl

    Write-Host "4. Verifying staging BigQuery dataset/tables and GCS bucket (reloading the portfolio only if missing)..."
    Initialize-StagingDataResources

    Write-Host "5. Checking for an existing candidate frontend revision..."
    $webInfo = Get-CandidateServiceInfo -ServiceName "rateguard-web"
    $existingWebUrl = Get-CandidateTaggedUrl -ServiceInfo $webInfo -Tag $CANDIDATE_TAG
    if (Test-AbsoluteHttpsUrl -Url $existingWebUrl -RequiredHostFragment "rateguard-web" -RequireCandidateTagPrefix) {
        Write-Host "   Candidate frontend revision already exists ($existingWebUrl) -- skipping frontend build/deploy."
        $webUrl = $existingWebUrl
    } else {
        Write-Host "   Candidate frontend revision missing -- building and deploying it now."
        $webUrl = Deploy-CandidateFrontend -CandidateApiUrl $urls.ApiTaggedUrl
    }

    Write-Host "6. Verifying postconditions..."
    Complete-CandidateDeployment -Urls $urls -WebUrl $webUrl
}

function Invoke-CandidateDeploymentEntryPoint {
    # The single point in this script that ever calls `exit`. Every failure
    # path above throws instead of exiting directly, which keeps
    # Deploy-Candidate/Resume-Candidate/Complete-CandidateDeployment safely
    # callable from tests without terminating the host process.
    param([switch]$DeployCandidate, [switch]$ResumeCandidate)
    try {
        Assert-MutuallyExclusiveModes -DeployCandidate:$DeployCandidate -ResumeCandidate:$ResumeCandidate
        if ($DeployCandidate) {
            Deploy-Candidate
        } elseif ($ResumeCandidate) {
            Resume-Candidate
        } else {
            Write-Plan
        }
    } catch {
        Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
        exit 1
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    Invoke-CandidateDeploymentEntryPoint -DeployCandidate:$DeployCandidate -ResumeCandidate:$ResumeCandidate
}
