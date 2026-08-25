# Focused, offline tests for infrastructure/lib/CandidateDeployLib.ps1 and the
# orchestration functions in infrastructure/deploy_candidate.ps1.
#
# No gcloud/bq/gsutil/network calls anywhere in this file. Cloud Run JSON
# fixtures below mirror the exact shape returned by a real
# `gcloud run services describe --format=json(...)` against this project's
# rateguard-api / rateguard-worker / rateguard-web services (captured
# read-only while diagnosing the partial candidate deployment).
#
# Run with: Invoke-Pester infrastructure/tests/CandidateDeployLib.Tests.ps1

$libPath = Join-Path $PSScriptRoot "..\lib\CandidateDeployLib.ps1"
. $libPath

$deployScriptPath = Join-Path $PSScriptRoot "..\deploy_candidate.ps1"

function New-ApiServiceInfoWithCandidateTag {
    '{
      "status": {
        "url": "https://rateguard-api-iqofutwtva-uc.a.run.app",
        "traffic": [
          { "percent": 100, "revisionName": "rateguard-api-00015-4tt" },
          { "revisionName": "rateguard-api-00016-vov", "tag": "candidate", "url": "https://candidate---rateguard-api-iqofutwtva-uc.a.run.app" }
        ]
      },
      "spec": { "template": { "spec": { "containers": [ { "image": "us-central1-docker.pkg.dev/rateguard-ai/rateguard/rateguard-api:candidate-23cfc95b5949", "env": [ { "name": "RATEGUARD_PUBSUB_TOPIC", "value": "assurance-runs-staging" } ] } ] } } }
    }' | ConvertFrom-Json
}

function New-WorkerServiceInfoWithCandidateTag {
    '{
      "status": {
        "url": "https://rateguard-worker-iqofutwtva-uc.a.run.app",
        "traffic": [
          { "percent": 100, "revisionName": "rateguard-worker-00008-w2p" },
          { "revisionName": "rateguard-worker-00009-luq", "tag": "candidate", "url": "https://candidate---rateguard-worker-iqofutwtva-uc.a.run.app" }
        ]
      },
      "spec": { "template": { "spec": { "containers": [ { "image": "us-central1-docker.pkg.dev/rateguard-ai/rateguard/rateguard-api:candidate-23cfc95b5949" } ] } } }
    }' | ConvertFrom-Json
}

function New-WebServiceInfoNoCandidateTag {
    '{
      "status": {
        "url": "https://rateguard-web-iqofutwtva-uc.a.run.app",
        "traffic": [
          { "latestRevision": true, "percent": 100, "revisionName": "rateguard-web-00008-9v2" }
        ]
      }
    }' | ConvertFrom-Json
}

function New-WebServiceInfoWithCandidateTag {
    '{
      "status": {
        "url": "https://rateguard-web-iqofutwtva-uc.a.run.app",
        "traffic": [
          { "percent": 100, "revisionName": "rateguard-web-00008-9v2" },
          { "revisionName": "rateguard-web-00009-abc", "tag": "candidate", "url": "https://candidate---rateguard-web-iqofutwtva-uc.a.run.app" }
        ]
      }
    }' | ConvertFrom-Json
}

Describe "Get-CandidateTaggedUrl" {

    It "extracts the tagged URL from a realistic Cloud Run JSON describe" {
        $info = New-ApiServiceInfoWithCandidateTag
        $url = Get-CandidateTaggedUrl -ServiceInfo $info -Tag "candidate"
        $url | Should Be "https://candidate---rateguard-api-iqofutwtva-uc.a.run.app"
    }

    It "returns null when no traffic entry carries the requested tag (missing tag)" {
        $info = New-WebServiceInfoNoCandidateTag
        $url = Get-CandidateTaggedUrl -ServiceInfo $info -Tag "candidate"
        $url | Should Be $null
    }

    It "a missing tag URL fails absolute-https validation" {
        $info = New-WebServiceInfoNoCandidateTag
        $url = Get-CandidateTaggedUrl -ServiceInfo $info -Tag "candidate"
        (Test-AbsoluteHttpsUrl -Url $url -RequiredHostFragment "rateguard-web" -RequireCandidateTagPrefix) | Should Be $false
    }

    It "extracts the untagged base URL separately from the tagged URL" {
        $info = New-WorkerServiceInfoWithCandidateTag
        (Get-UntaggedServiceUrl -ServiceInfo $info) | Should Be "https://rateguard-worker-iqofutwtva-uc.a.run.app"
    }
}

Describe "Test-AbsoluteHttpsUrl" {

    It "rejects an empty URL" { Test-AbsoluteHttpsUrl -Url "" | Should Be $false }
    It "rejects a null URL" { Test-AbsoluteHttpsUrl -Url $null | Should Be $false }
    It "rejects a relative path" { Test-AbsoluteHttpsUrl -Url "/internal/pubsub/assurance" | Should Be $false }
    It "rejects a plain http URL" { Test-AbsoluteHttpsUrl -Url "http://candidate---rateguard-api-iqofutwtva-uc.a.run.app" | Should Be $false }
    It "accepts a well-formed https candidate URL" {
        Test-AbsoluteHttpsUrl -Url "https://candidate---rateguard-api-iqofutwtva-uc.a.run.app" -RequiredHostFragment "rateguard-api" -RequireCandidateTagPrefix | Should Be $true
    }
    It "rejects a URL missing the required candidate tag prefix" {
        Test-AbsoluteHttpsUrl -Url "https://rateguard-api-iqofutwtva-uc.a.run.app" -RequireCandidateTagPrefix | Should Be $false
    }
    It "rejects a URL whose host does not contain the required service fragment" {
        Test-AbsoluteHttpsUrl -Url "https://candidate---rateguard-worker-iqofutwtva-uc.a.run.app" -RequiredHostFragment "rateguard-api" | Should Be $false
    }
}

Describe "Pub/Sub endpoint + OIDC audience construction" {

    It "builds the push endpoint from the candidate worker TAGGED url plus the fixed path" {
        $endpoint = New-PubSubPushEndpoint -CandidateWorkerTaggedUrl "https://candidate---rateguard-worker-iqofutwtva-uc.a.run.app"
        $endpoint | Should Be "https://candidate---rateguard-worker-iqofutwtva-uc.a.run.app/internal/pubsub/assurance"
    }

    It "throws when building a push endpoint from an invalid worker URL" {
        { New-PubSubPushEndpoint -CandidateWorkerTaggedUrl "" } | Should Throw
    }

    It "uses the UNTAGGED worker service URL as the OIDC audience" {
        $audience = Get-PubSubOidcAudience -UntaggedWorkerServiceUrl "https://rateguard-worker-iqofutwtva-uc.a.run.app"
        $audience | Should Be "https://rateguard-worker-iqofutwtva-uc.a.run.app"
    }

    It "refuses a traffic-TAG url as the OIDC audience" {
        { Get-PubSubOidcAudience -UntaggedWorkerServiceUrl "https://candidate---rateguard-worker-iqofutwtva-uc.a.run.app" } | Should Throw
    }

    It "refuses a url containing the endpoint path as the OIDC audience" {
        { Get-PubSubOidcAudience -UntaggedWorkerServiceUrl "https://rateguard-worker-iqofutwtva-uc.a.run.app/internal/pubsub/assurance" } | Should Throw
    }
}

Describe "Frontend Cloud Build substitutions" {

    It "builds one comma-separated substitutions string with exactly the two expected keys" {
        $subs = New-FrontendSubstitutionsArg -ImageTag "candidate-23cfc95b5949" -CandidateApiUrl "https://candidate---rateguard-api-iqofutwtva-uc.a.run.app"
        $subs | Should Be "_IMAGE_TAG=candidate-23cfc95b5949,_NEXT_PUBLIC_RATEGUARD_API_URL=https://candidate---rateguard-api-iqofutwtva-uc.a.run.app"
        (Test-FrontendSubstitutionsShape -Substitutions $subs) | Should Be $true
    }

    It "throws on an empty image tag" {
        { New-FrontendSubstitutionsArg -ImageTag "" -CandidateApiUrl "https://candidate---rateguard-api-iqofutwtva-uc.a.run.app" } | Should Throw
    }

    It "throws when the candidate API URL is not an absolute https URL" {
        { New-FrontendSubstitutionsArg -ImageTag "candidate-23cfc95b5949" -CandidateApiUrl "not-a-url" } | Should Throw
    }

    It "rejects a substitutions string that is not exactly the two expected keys" {
        (Test-FrontendSubstitutionsShape -Substitutions "_IMAGE_TAG=x") | Should Be $false
        (Test-FrontendSubstitutionsShape -Substitutions "_IMAGE_TAG=x,_NEXT_PUBLIC_RATEGUARD_API_URL=y,_EXTRA=z") | Should Be $false
        (Test-FrontendSubstitutionsShape -Substitutions "_WRONG_KEY=x,_NEXT_PUBLIC_RATEGUARD_API_URL=y") | Should Be $false
    }

    It "the generated image reference contains no spaces" {
        $image = "us-central1-docker.pkg.dev/rateguard-ai/rateguard/rateguard-web:candidate-23cfc95b5949"
        (Test-ImageReferenceNoSpaces -ImageReference $image) | Should Be $true
    }

    It "detects a space-corrupted image reference" {
        (Test-ImageReferenceNoSpaces -ImageReference "us-central1-docker.pkg.dev/rateguard-ai/rateguard/rateguard-web candidate-23cfc95b5949") | Should Be $false
    }
}

Describe "Test-ProductionTrafficUnchanged" {

    It "passes when the candidate tag carries 0% traffic" {
        $info = New-ApiServiceInfoWithCandidateTag
        (Test-ProductionTrafficUnchanged -ServiceInfo $info -CandidateTag "candidate") | Should Be $true
    }

    It "fails when the candidate tag somehow carries 100% traffic" {
        $info = '{ "status": { "traffic": [ { "percent": 100, "tag": "candidate", "revisionName": "x" } ] } }' | ConvertFrom-Json
        (Test-ProductionTrafficUnchanged -ServiceInfo $info -CandidateTag "candidate") | Should Be $false
    }
}

Describe "Test-CandidateEnvIsolation" {

    It "reports no failures when the expected staging key/value is present" {
        $info = New-ApiServiceInfoWithCandidateTag
        $failures = @(Test-CandidateEnvIsolation -ServiceInfo $info -ServiceLabel "rateguard-api" -ExpectedStagingValues @{ "RATEGUARD_PUBSUB_TOPIC" = "assurance-runs-staging" })
        $failures.Count | Should Be 0
    }

    It "reports a failure (naming only the key, never the value) when a key is missing" {
        $info = New-WebServiceInfoNoCandidateTag
        $failures = @(Test-CandidateEnvIsolation -ServiceInfo $info -ServiceLabel "rateguard-web" -ExpectedStagingValues @{ "RATEGUARD_GCS_BUCKET" = "rateguard-ai-artifacts-staging" })
        $failures.Count | Should Be 1
        $failures[0] | Should Match "RATEGUARD_GCS_BUCKET"
        $failures[0] | Should Not Match "rateguard-ai-artifacts-staging"
    }

    It "reports a failure when a key points at the wrong (e.g. production) value" {
        $info = New-ApiServiceInfoWithCandidateTag
        $failures = @(Test-CandidateEnvIsolation -ServiceInfo $info -ServiceLabel "rateguard-api" -ExpectedStagingValues @{ "RATEGUARD_PUBSUB_TOPIC" = "assurance-runs" })
        $failures.Count | Should Be 1
    }
}

Describe "Invoke-NativeCommand fail-fast" {

    It "returns normally and captures output on a zero exit code" {
        $out = Invoke-NativeCommand -Operation "cmd echo" -FilePath "cmd.exe" -ArgumentList @("/c", "echo", "hello") -CaptureOutput
        ($out -join "") | Should Match "hello"
    }

    It "throws immediately on a nonzero exit code, naming the operation" {
        { Invoke-NativeCommand -Operation "deliberate failure" -FilePath "cmd.exe" -ArgumentList @("/c", "exit", "7") } | Should Throw "deliberate failure"
    }

    It "a nonzero native command aborts a calling script block before later statements run" {
        $script = {
            Invoke-NativeCommand -Operation "step one" -FilePath "cmd.exe" -ArgumentList @("/c", "exit", "3")
            $global:__reached_after_failure = $true
        }
        $global:__reached_after_failure = $false
        try { & $script } catch { }
        $global:__reached_after_failure | Should Be $false
        Remove-Variable -Name __reached_after_failure -Scope Global -ErrorAction SilentlyContinue
    }
}

Describe "ConvertFrom-CloudRunServiceJson" {

    It "throws a clear error on empty/human-formatted (non-JSON) input instead of silently returning nothing" {
        { ConvertFrom-CloudRunServiceJson -JsonLines @() -ServiceName "rateguard-api" } | Should Throw
        { ConvertFrom-CloudRunServiceJson -JsonLines @("NAME    REGION    URL", "rateguard-api  us-central1  https://x") -ServiceName "rateguard-api" } | Should Throw
    }
}

Describe "deploy_candidate.ps1 orchestration" {

    # Dot-sourcing runs the module-load path only: $MyInvocation.InvocationName
    # is '.' when dot-sourced, so Invoke-CandidateDeploymentEntryPoint is never
    # auto-invoked and no gcloud/git side effects beyond `git rev-parse` occur.
    . $deployScriptPath

    It "-DeployCandidate and -ResumeCandidate are mutually exclusive" {
        { Assert-MutuallyExclusiveModes -DeployCandidate -ResumeCandidate } | Should Throw "mutually exclusive"
    }

    It "does not throw when only -DeployCandidate is set" {
        { Assert-MutuallyExclusiveModes -DeployCandidate } | Should Not Throw
    }

    It "does not throw when only -ResumeCandidate is set" {
        { Assert-MutuallyExclusiveModes -ResumeCandidate } | Should Not Throw
    }

    It "the success banner cannot be reached when postconditions fail" {
        Mock Confirm-CandidatePostconditions { return @("simulated postcondition failure") }
        Mock Write-SuccessBanner { $global:__banner_printed = $true }
        $global:__banner_printed = $false

        $urls = [pscustomobject]@{
            ApiTaggedUrl      = "https://candidate---rateguard-api-iqofutwtva-uc.a.run.app"
            WorkerTaggedUrl   = "https://candidate---rateguard-worker-iqofutwtva-uc.a.run.app"
            WorkerUntaggedUrl = "https://rateguard-worker-iqofutwtva-uc.a.run.app"
        }

        { Complete-CandidateDeployment -Urls $urls -WebUrl "https://candidate---rateguard-web-iqofutwtva-uc.a.run.app" } | Should Throw

        $global:__banner_printed | Should Be $false
        Remove-Variable -Name __banner_printed -Scope Global -ErrorAction SilentlyContinue
    }

    It "the success banner IS reached when every postcondition passes" {
        Mock Confirm-CandidatePostconditions { return @() }
        Mock Write-SuccessBanner { $global:__banner_printed = $true }
        $global:__banner_printed = $false

        $urls = [pscustomobject]@{
            ApiTaggedUrl      = "https://candidate---rateguard-api-iqofutwtva-uc.a.run.app"
            WorkerTaggedUrl   = "https://candidate---rateguard-worker-iqofutwtva-uc.a.run.app"
            WorkerUntaggedUrl = "https://rateguard-worker-iqofutwtva-uc.a.run.app"
        }

        { Complete-CandidateDeployment -Urls $urls -WebUrl "https://candidate---rateguard-web-iqofutwtva-uc.a.run.app" } | Should Not Throw
        $global:__banner_printed | Should Be $true
        Remove-Variable -Name __banner_printed -Scope Global -ErrorAction SilentlyContinue
    }

    It "-ResumeCandidate stops on a backend image mismatch instead of silently rebuilding" {
        Mock Get-ValidatedCandidateBackendUrls {
            $apiInfo = New-ApiServiceInfoWithCandidateTag
            $apiInfo.spec.template.spec.containers[0].image = "us-central1-docker.pkg.dev/rateguard-ai/rateguard/rateguard-api:candidate-DIFFERENT_SHA"
            $workerInfo = New-WorkerServiceInfoWithCandidateTag
            $workerInfo.spec.template.spec.containers[0].image = "us-central1-docker.pkg.dev/rateguard-ai/rateguard/rateguard-api:candidate-DIFFERENT_SHA"
            [pscustomobject]@{
                ApiInfo           = $apiInfo
                WorkerInfo        = $workerInfo
                ApiTaggedUrl      = "https://candidate---rateguard-api-iqofutwtva-uc.a.run.app"
                WorkerTaggedUrl   = "https://candidate---rateguard-worker-iqofutwtva-uc.a.run.app"
                ApiUntaggedUrl    = "https://rateguard-api-iqofutwtva-uc.a.run.app"
                WorkerUntaggedUrl = "https://rateguard-worker-iqofutwtva-uc.a.run.app"
            }
        }
        Mock Invoke-NativeCommand { }

        { Resume-Candidate } | Should Throw "Mismatch"
    }

    It "-ResumeCandidate skips backend rebuild and frontend redeploy when everything already matches" {
        # Build the API/worker fixtures against whatever $BACKEND_IMAGE the
        # dot-sourced script actually computed for the current git HEAD
        # (rather than a hardcoded value), so this test is independent of
        # which commit it happens to run against.
        Mock Get-ValidatedCandidateBackendUrls {
            $apiInfo = New-ApiServiceInfoWithCandidateTag
            $apiInfo.spec.template.spec.containers[0].image = $BACKEND_IMAGE
            $workerInfo = New-WorkerServiceInfoWithCandidateTag
            $workerInfo.spec.template.spec.containers[0].image = $BACKEND_IMAGE
            [pscustomobject]@{
                ApiInfo           = $apiInfo
                WorkerInfo        = $workerInfo
                ApiTaggedUrl      = "https://candidate---rateguard-api-iqofutwtva-uc.a.run.app"
                WorkerTaggedUrl   = "https://candidate---rateguard-worker-iqofutwtva-uc.a.run.app"
                ApiUntaggedUrl    = "https://rateguard-api-iqofutwtva-uc.a.run.app"
                WorkerUntaggedUrl = "https://rateguard-worker-iqofutwtva-uc.a.run.app"
            }
        }
        Mock Initialize-StagingPubSub { }
        Mock Initialize-StagingDataResources { }
        Mock Get-CandidateServiceInfo {
            param($ServiceName)
            if ($ServiceName -eq "rateguard-web") { return New-WebServiceInfoWithCandidateTag }
            return New-ApiServiceInfoWithCandidateTag
        }
        Mock Deploy-CandidateFrontend { $global:__frontend_deployed = $true; return "https://candidate---rateguard-web-iqofutwtva-uc.a.run.app" }
        Mock Confirm-CandidatePostconditions { return @() }
        Mock Write-SuccessBanner { }
        Mock Invoke-NativeCommand { }
        $global:__frontend_deployed = $false

        { Resume-Candidate } | Should Not Throw

        # The candidate web tag already exists in the fixture returned by the
        # mocked Get-CandidateServiceInfo, so the frontend must NOT be rebuilt.
        $global:__frontend_deployed | Should Be $false
        Remove-Variable -Name __frontend_deployed -Scope Global -ErrorAction SilentlyContinue
    }
}
