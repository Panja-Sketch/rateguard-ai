import {
  AssuranceMissionDetail,
  AssuranceMissionSummary,
  AssuranceReport,
  AssuranceRunRecord,
  EvidenceRecord,
  SourceDescriptor,
  ValidationIssue,
  WorkflowEvent,
} from '../types/assurance';

const BASE_URL =
  process.env.NEXT_PUBLIC_RATEGUARD_API_URL || 'http://localhost:8000';

export class ApiError extends Error {
  status: number;
  code?: string;
  issues?: ValidationIssue[];

  constructor(message: string, status: number, code?: string, issues?: ValidationIssue[]) {
    super(message);
    this.status = status;
    this.name = 'ApiError';
    this.code = code;
    this.issues = issues;
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
    let code: string | undefined;
    let issues: ValidationIssue[] | undefined;
    try {
      const data = await res.json();
      if (data.detail) {
        if (typeof data.detail === 'string') {
          errorDetail = data.detail;
        } else {
          errorDetail = data.detail.message || JSON.stringify(data.detail);
          code = data.detail.code;
          if (Array.isArray(data.detail.issues)) {
            issues = data.detail.issues as ValidationIssue[];
          }
        }
      } else if (data.message) {
        errorDetail = data.message;
      }
    } catch {
      // Ignore non-JSON body errors
    }
    throw new ApiError(errorDetail, res.status, code, issues);
  }
  return res.json() as Promise<T>;
}

export async function fetchHealth(): Promise<{ status: string; service: string }> {
  const res = await fetch(`${BASE_URL}/health`, { cache: 'no-store' });
  return handleResponse<{ status: string; service: string }>(res);
}

/**
 * True when `err` is the browser's own transport-level failure (DNS
 * failure, connection refused, or a CORS-blocked response) rather than a
 * structured API error. `fetch()` rejects with a bare `TypeError` in this
 * case — never an ApiError, since no HTTP response was ever received to
 * parse a body from. Distinguishing this is what lets callers show
 * "RateGuard API is currently unreachable" instead of the browser's raw
 * "Failed to fetch" message.
 */
export function isNetworkUnreachableError(err: unknown): boolean {
  return err instanceof TypeError;
}

/** Renders `err` as user-facing text, replacing a raw transport failure
 * with an actionable, non-technical message instead of the browser's
 * "Failed to fetch". `context` names what didn't happen (e.g. "No mission
 * was created.") so the message tells the user exactly what state they're
 * left in. */
export function describeFetchError(err: unknown, context: string): string {
  if (isNetworkUnreachableError(err)) {
    return `RateGuard API is currently unreachable. ${context}`;
  }
  return err instanceof Error ? err.message : String(err);
}

export async function createAssuranceMission(params: {
  name: string;
  mode: string;
  product: string;
  jurisdiction: string;
  effective_period_start: string;
  portfolio_dataset: string;
  gating_policy: string;
  source_a: Record<string, unknown> | null;
  source_b?: Record<string, unknown> | null;
  runtime_connector?: Record<string, unknown> | null;
  disposable_sample_run?: boolean;
  is_demo_sample?: boolean;
}): Promise<{
  mission_id: string;
  status: string;
  mode: string;
  decision: string;
  result: Record<string, unknown>;
}> {
  const res = await fetch(`${BASE_URL}/api/v1/missions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
    cache: 'no-store',
  });
  return handleResponse(res);
}

export async function testRatingApiConnector(config: Record<string, unknown>): Promise<{
  status: string;
  http_status: number;
  parsed_premium: string;
  response_sample: Record<string, unknown>;
}> {
  const res = await fetch(`${BASE_URL}/api/v1/connectors/test`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
    cache: 'no-store',
  });
  return handleResponse(res);
}

export async function listAssuranceMissions(
  limit: number = 50,
  offset: number = 0,
  filters?: { status?: string; mode?: string; decision?: string }
): Promise<{
  missions: AssuranceMissionSummary[];
  total_count: number;
  limit: number;
  offset: number;
}> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (filters?.status) params.append('status', filters.status);
  if (filters?.mode) params.append('mode', filters.mode);
  if (filters?.decision) params.append('decision', filters.decision);

  const res = await fetch(`${BASE_URL}/api/v1/missions?${params.toString()}`, {
    cache: 'no-store',
  });
  return handleResponse(res);
}

export async function getAssuranceMission(missionId: string): Promise<AssuranceMissionDetail> {
  const res = await fetch(`${BASE_URL}/api/v1/missions/${missionId}`, {
    cache: 'no-store',
  });
  return handleResponse<AssuranceMissionDetail>(res);
}

export async function archiveAssuranceMission(missionId: string): Promise<{
  mission_id: string;
  status: string;
  message: string;
}> {
  const res = await fetch(`${BASE_URL}/api/v1/missions/${missionId}/archive`, {
    method: 'POST',
    cache: 'no-store',
  });
  return handleResponse(res);
}

export async function deleteAssuranceMission(missionId: string): Promise<{
  mission_id: string;
  status: string;
  message: string;
}> {
  const res = await fetch(`${BASE_URL}/api/v1/missions/${missionId}`, {
    method: 'DELETE',
    cache: 'no-store',
  });
  return handleResponse(res);
}

export async function cancelAssuranceMission(missionId: string): Promise<{
  mission_id: string;
  status: string;
  cancellation_requested?: boolean;
  message: string;
}> {
  const res = await fetch(`${BASE_URL}/api/v1/missions/${missionId}/cancel`, {
    method: 'POST',
    cache: 'no-store',
  });
  return handleResponse(res);
}

export async function retryAssuranceMission(missionId: string): Promise<{
  mission_id: string;
  status: string;
  attempt_number: number;
  message: string;
}> {
  const res = await fetch(`${BASE_URL}/api/v1/missions/${missionId}/retry`, {
    method: 'POST',
    cache: 'no-store',
  });
  return handleResponse(res);
}

export async function fetchSystemInfo(): Promise<{
  gemini_model: string;
  gemini_model_display: string;
  agent_framework: string;
  agent_provider: string;
  agent_supervisor: string;
  ipir_version: string;
  cloud_project: string;
}> {
  const res = await fetch(`${BASE_URL}/api/v1/system/info`, { cache: 'no-store' });
  return handleResponse(res);
}

export async function fetchDemoScenarios(): Promise<{
  scenarios: Array<{
    id: string;
    name: string;
    description: string;
    left_package_id: string;
    right_package_id: string;
    expected_decision: string;
    tags: string[];
    category: string;
  }>;
  count: number;
}> {
  const res = await fetch(`${BASE_URL}/api/v1/demo/scenarios`, { cache: 'no-store' });
  return handleResponse(res);
}

export async function launchScenarioLabRun(params: {
  name?: string;
  roof_age_21_30_factor?: number | null;
  deductible_1000_factor?: number | null;
  territory_t05_factor?: number | null;
  claims_free_discount_pct?: number | null;
  claims_free_effective_date?: string | null;
  minimum_premium?: number | null;
  policy_fee?: number | null;
  async_execution?: boolean;
}): Promise<{
  run_id: string;
  status: string;
  lab_package_id?: string;
  parameter_changes?: Record<string, unknown>;
}> {
  const res = await fetch(`${BASE_URL}/api/v1/assurance/scenario-lab`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
    cache: 'no-store',
  });
  return handleResponse(res);
}

export async function listAssuranceRuns(limit: number = 50): Promise<{
  runs: Array<{
    run_id: string;
    created_at: string;
    updated_at: string;
    status: string;
    workflow_stage?: string;
    left_package_id?: string;
    right_package_id?: string;
    decision?: string;
    summary?: string;
  }>;
  count: number;
}> {
  const res = await fetch(`${BASE_URL}/api/v1/assurance/runs?limit=${limit}`, {
    cache: 'no-store',
  });
  return handleResponse(res);
}

export async function startAssuranceRun(params: {
  leftPackageId?: string;
  rightPackageId?: string;
  leftSourceId?: string;
  rightSourceId?: string;
  asyncExecution?: boolean;
}): Promise<{
  run_id: string;
  status: string;
  job_id?: string;
  executive_summary?: string;
  recommendation?: string;
  result?: AssuranceReport;
}> {
  // No hidden demo fallback: callers must explicitly resolve a package or source id
  // (see sources/page.tsx and missions/new/page.tsx) before invoking this.
  if (!params.leftPackageId && !params.leftSourceId) {
    throw new ApiError('Source A must be selected before executing an assurance run.', 400);
  }
  if (!params.rightPackageId && !params.rightSourceId) {
    throw new ApiError('Source B must be selected before executing an assurance run.', 400);
  }

  // Values are passed through as-is (no `|| 'AZ_HO3_...'` fallback) — callers are
  // responsible for only invoking this once a real package/source id is resolved.
  const payload = {
    left_package_id: params.leftPackageId,
    right_package_id: params.rightPackageId,
    left_source_id: params.leftSourceId || null,
    right_source_id: params.rightSourceId || null,
    include_portfolio_analysis: true,
    async_execution: params.asyncExecution,
  };

  const res = await fetch(`${BASE_URL}/api/v1/assurance/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    cache: 'no-store',
  });

  return handleResponse(res);
}

export async function getAssuranceRun(runId: string): Promise<AssuranceRunRecord> {
  const res = await fetch(`${BASE_URL}/api/v1/assurance/runs/${runId}`, {
    cache: 'no-store',
  });
  return handleResponse<AssuranceRunRecord>(res);
}

export async function getAssuranceRunEvents(runId: string): Promise<{
  run_id: string;
  event_count: number;
  events: WorkflowEvent[];
}> {
  const res = await fetch(`${BASE_URL}/api/v1/assurance/runs/${runId}/events`, {
    cache: 'no-store',
  });
  return handleResponse<{ run_id: string; event_count: number; events: WorkflowEvent[] }>(res);
}

export async function getAssuranceRunResult(runId: string): Promise<AssuranceReport> {
  const res = await fetch(`${BASE_URL}/api/v1/assurance/runs/${runId}/result`, {
    cache: 'no-store',
  });
  return handleResponse<AssuranceReport>(res);
}

export async function getAssuranceRunEvidence(runId: string): Promise<{
  run_id: string;
  evidence_count: number;
  evidence: EvidenceRecord[];
}> {
  const res = await fetch(`${BASE_URL}/api/v1/assurance/runs/${runId}/evidence`, {
    cache: 'no-store',
  });
  return handleResponse<{ run_id: string; evidence_count: number; evidence: EvidenceRecord[] }>(res);
}

export async function uploadSourceFile(file: File): Promise<SourceDescriptor> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${BASE_URL}/api/v1/sources`, {
    method: 'POST',
    body: formData,
    cache: 'no-store',
  });

  return handleResponse<SourceDescriptor>(res);
}

export async function compileSource(sourceId: string): Promise<{
  source_id: string;
  adapter_id: string;
  ipir_package_id: string;
  mapping_coverage: number;
  confidence: number;
  warnings: string[];
  requires_human_review: boolean;
  ipir_package: unknown;
}> {
  const res = await fetch(`${BASE_URL}/api/v1/sources/${sourceId}/compile`, {
    method: 'POST',
    cache: 'no-store',
  });
  return handleResponse(res);
}
