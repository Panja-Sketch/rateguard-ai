# RateGuard AI -- Candidate Deployment Helper Library
#
# Pure/testable helper functions used by infrastructure/deploy_candidate.ps1.
# Dot-sourced by the deploy script and by infrastructure/tests/*.Tests.ps1 so
# the parsing/validation/construction logic can be exercised offline, with no
# gcloud/bq/gsutil calls at all.
#
# Nothing in this file prints command output or environment-variable values.
# Callers are responsible for what (if anything) they choose to print.
#
# Deliberately no `Set-StrictMode`: Cloud Run traffic entries are
# heterogeneous JSON objects (the 100%-traffic entry has no .tag/.url, the
# candidate-tag entry has no .percent, etc.) -- PSCustomObject's default
# "missing property reads as $null" behavior is exactly what the parsing
# functions below rely on, and StrictMode -Version Latest would turn every
# normal, well-formed Cloud Run response into a PropertyNotFoundException.

function Invoke-NativeCommand {
    <#
    Runs a native executable and treats any nonzero exit code as fatal,
    regardless of $ErrorActionPreference (which native executables do not
    reliably honor). Always inspects $LASTEXITCODE immediately after the
    call, before any other statement can overwrite it.

    Never merges stderr into a captured output stream: in Windows
    PowerShell 5.1, `2>&1` on a native command wraps each stderr line in a
    NativeCommandError record and flips $?, even on a genuine exit code 0.
    stderr is left to stream directly to the console instead.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$Operation,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [switch]$CaptureOutput
    )

    if ($CaptureOutput) {
        $output = & $FilePath @ArgumentList
    } else {
        & $FilePath @ArgumentList
        $output = $null
    }

    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) { $exitCode = 0 }

    if ($exitCode -ne 0) {
        throw "Native command failed: $Operation (exit code $exitCode)"
    }

    return $output
}

function ConvertFrom-CloudRunServiceJson {
    <#
    Parses the JSON text produced by
    `gcloud run services describe SERVICE --format=json(...)`. Accepts
    either a single string or an array of lines (as returned by
    Invoke-NativeCommand -CaptureOutput) and raises a clear error if the
    text is not valid JSON, rather than letting a human-formatted-output
    regression fail silently downstream.
    #>
    param(
        [Parameter(Mandatory = $true)][AllowNull()]$JsonLines,
        [Parameter(Mandatory = $true)][string]$ServiceName
    )
    $text = if ($JsonLines -is [array]) { $JsonLines -join "`n" } else { [string]$JsonLines }
    if ([string]::IsNullOrWhiteSpace($text)) {
        throw "Empty response describing Cloud Run service '$ServiceName'; expected JSON."
    }
    try {
        return $text | ConvertFrom-Json
    } catch {
        throw "Failed to parse JSON describing Cloud Run service '$ServiceName': $($_.Exception.Message)"
    }
}

function Get-CandidateTaggedUrl {
    <#
    Finds the traffic/status entry whose .tag equals the given tag and
    returns its .url. Returns $null (never throws) when the tag is absent
    -- callers decide whether a missing candidate tag is fatal. Never
    parses human-formatted `gcloud ... ` table output.
    #>
    param(
        [Parameter(Mandatory = $true)]$ServiceInfo,
        [Parameter(Mandatory = $true)][string]$Tag
    )
    $traffic = $ServiceInfo.status.traffic
    if (-not $traffic) { return $null }
    $match = @($traffic) | Where-Object { $_.tag -eq $Tag } | Select-Object -First 1
    if (-not $match -or -not $match.url) { return $null }
    return [string]$match.url
}

function Get-UntaggedServiceUrl {
    <# The base (untagged) Cloud Run service URL -- required as the Pub/Sub
    OIDC audience even when the push endpoint targets a specific tag. #>
    param([Parameter(Mandatory = $true)]$ServiceInfo)
    if ($ServiceInfo.status.url) { return [string]$ServiceInfo.status.url }
    if ($ServiceInfo.status.address -and $ServiceInfo.status.address.url) {
        return [string]$ServiceInfo.status.address.url
    }
    return $null
}

function Get-DeployedImageReference {
    <# The image reference (registry/repo:tag) baked into the service's
    current revision template. Used for backend image parity checks. #>
    param([Parameter(Mandatory = $true)]$ServiceInfo)
    $containers = $ServiceInfo.spec.template.spec.containers
    if (-not $containers) { return $null }
    $first = @($containers) | Select-Object -First 1
    if (-not $first) { return $null }
    return [string]$first.image
}

function Get-ServiceEnvVar {
    <# Looks up one env var by name from a service's container env array,
    without ever printing its value. Returns $null if absent. #>
    param(
        [Parameter(Mandatory = $true)]$ServiceInfo,
        [Parameter(Mandatory = $true)][string]$Name
    )
    $containers = $ServiceInfo.spec.template.spec.containers
    if (-not $containers) { return $null }
    $first = @($containers) | Select-Object -First 1
    if (-not $first -or -not $first.env) { return $null }
    $entry = @($first.env) | Where-Object { $_.name -eq $Name } | Select-Object -First 1
    if (-not $entry) { return $null }
    return $entry.value
}

function Test-AbsoluteHttpsUrl {
    <#
    Validates a discovered URL is: nonempty, an absolute URI, HTTPS, and
    (optionally) has a host containing the expected service-name fragment
    and/or the "candidate---" tag prefix. Uses System.Uri, never a regex
    guess.
    #>
    param(
        [AllowEmptyString()][AllowNull()][string]$Url,
        [string]$RequiredHostFragment = $null,
        [switch]$RequireCandidateTagPrefix
    )
    if ([string]::IsNullOrWhiteSpace($Url)) { return $false }

    $uri = $null
    if (-not [System.Uri]::TryCreate($Url, [System.UriKind]::Absolute, [ref]$uri)) { return $false }
    if ($uri.Scheme -ne 'https') { return $false }
    if ([string]::IsNullOrWhiteSpace($uri.Host)) { return $false }
    if ($RequiredHostFragment -and ($uri.Host -notlike "*$RequiredHostFragment*")) { return $false }
    if ($RequireCandidateTagPrefix -and ($uri.Host -notlike 'candidate---*')) { return $false }
    return $true
}

function New-PubSubPushEndpoint {
    <# The push endpoint is always the candidate WORKER TAGGED URL plus the
    fixed internal path -- never the untagged worker URL, never the API
    URL. #>
    param([Parameter(Mandatory = $true)][string]$CandidateWorkerTaggedUrl)
    if (-not (Test-AbsoluteHttpsUrl -Url $CandidateWorkerTaggedUrl)) {
        throw "New-PubSubPushEndpoint: CandidateWorkerTaggedUrl is not an absolute https URL."
    }
    return "$($CandidateWorkerTaggedUrl.TrimEnd('/'))/internal/pubsub/assurance"
}

function Get-PubSubOidcAudience {
    <#
    Cloud Run requires the OIDC token audience to be the plain service URL,
    even when the push endpoint targets a specific traffic tag. Returning
    the tag URL, or the URL with the endpoint path appended, produces a
    token Cloud Run will reject. This function returns the untagged
    service URL, unmodified except for a trailing slash.
    #>
    param([Parameter(Mandatory = $true)][string]$UntaggedWorkerServiceUrl)
    if (-not (Test-AbsoluteHttpsUrl -Url $UntaggedWorkerServiceUrl)) {
        throw "Get-PubSubOidcAudience: UntaggedWorkerServiceUrl is not an absolute https URL."
    }
    if ($UntaggedWorkerServiceUrl -like '*---*') {
        throw "Get-PubSubOidcAudience: refusing to use a traffic-tag URL ('---') as the OIDC audience."
    }
    if ($UntaggedWorkerServiceUrl -like '*/internal/pubsub*') {
        throw "Get-PubSubOidcAudience: refusing to use a URL containing the endpoint path as the OIDC audience."
    }
    return $UntaggedWorkerServiceUrl.TrimEnd('/')
}

function New-FrontendSubstitutionsArg {
    <#
    Builds the single comma-separated --substitutions value Cloud Build
    expects. PowerShell has no bare-word array-splitting hazard here
    because this returns one scalar string; the caller must pass it as one
    argument (e.g. "--substitutions=$value"), never as several separate
    array elements.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$ImageTag,
        [Parameter(Mandatory = $true)][string]$CandidateApiUrl
    )
    if ([string]::IsNullOrWhiteSpace($ImageTag)) {
        throw "New-FrontendSubstitutionsArg: ImageTag must be nonempty."
    }
    if (-not (Test-AbsoluteHttpsUrl -Url $CandidateApiUrl)) {
        throw "New-FrontendSubstitutionsArg: CandidateApiUrl must be an absolute https URL."
    }
    $substitutions = "_IMAGE_TAG=$ImageTag,_NEXT_PUBLIC_RATEGUARD_API_URL=$CandidateApiUrl"
    if ($substitutions -match '\s') {
        throw "New-FrontendSubstitutionsArg: generated substitutions string contains whitespace."
    }
    if (-not (Test-FrontendSubstitutionsShape -Substitutions $substitutions)) {
        throw "New-FrontendSubstitutionsArg: generated substitutions string does not contain exactly the two expected keys."
    }
    return $substitutions
}

function Test-FrontendSubstitutionsShape {
    <# Exactly two comma-separated KEY=VALUE parts, the expected two keys,
    in the expected order. #>
    param([Parameter(Mandatory = $true)][string]$Substitutions)
    $parts = $Substitutions -split ','
    if ($parts.Count -ne 2) { return $false }
    if ($parts[0] -notmatch '^_IMAGE_TAG=.+$') { return $false }
    if ($parts[1] -notmatch '^_NEXT_PUBLIC_RATEGUARD_API_URL=.+$') { return $false }
    return $true
}

function Test-ImageReferenceNoSpaces {
    param([Parameter(Mandatory = $true)][string]$ImageReference)
    if ([string]::IsNullOrWhiteSpace($ImageReference)) { return $false }
    return ($ImageReference -notmatch '\s')
}

function Test-CandidateEnvIsolation {
    <#
    Compares a service's container env array against the expected staging
    key/value pairs. Returns an array of human-readable failure reasons
    (empty array = fully isolated). Failure messages name the KEY only,
    never the actual value on either side, so this is safe to print even
    though none of these particular keys are secret.
    #>
    param(
        [Parameter(Mandatory = $true)]$ServiceInfo,
        [Parameter(Mandatory = $true)][string]$ServiceLabel,
        [Parameter(Mandatory = $true)][hashtable]$ExpectedStagingValues
    )
    $failures = @()
    foreach ($key in $ExpectedStagingValues.Keys) {
        $actual = Get-ServiceEnvVar -ServiceInfo $ServiceInfo -Name $key
        if ($null -eq $actual) {
            $failures += "${ServiceLabel}: $key is not set"
        } elseif ($actual -ne $ExpectedStagingValues[$key]) {
            $failures += "${ServiceLabel}: $key does not reference the isolated staging resource"
        }
    }
    return $failures
}

function Test-ProductionTrafficUnchanged {
    <#
    Confirms the service's 100%-traffic entry (if any) is not the
    candidate tag -- i.e. the candidate revision is receiving 0% traffic.
    A service with no 100% entry yet (never deployed) is treated as
    "unchanged" (nothing to protect).
    #>
    param(
        [Parameter(Mandatory = $true)]$ServiceInfo,
        [Parameter(Mandatory = $true)][string]$CandidateTag
    )
    $traffic = $ServiceInfo.status.traffic
    if (-not $traffic) { return $true }
    $fullTraffic = @($traffic) | Where-Object { $_.percent -eq 100 }
    foreach ($entry in $fullTraffic) {
        if ($entry.tag -eq $CandidateTag) { return $false }
    }
    return $true
}
