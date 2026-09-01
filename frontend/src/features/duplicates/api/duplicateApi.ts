import type {
  DuplicateAnalysisOptions,
  DuplicateResolutionPlan,
  DuplicateResult,
  DuplicateTaskStatus,
  DuplicatePlanAction,
  DuplicateGroupDraft,
  DuplicateMemberDraftDecision,
  DuplicateWorkspaceState,
  ExactDuplicateGroup,
  SimilarityScanSummary,
} from '../types/duplicates';

let suppressNextAutomaticDuplicateAnalysis = false;

async function requestJson<T>(input: string, init?: RequestInit): Promise<T> {
  const response = await fetch(input, {
    ...init,
    headers: { Accept: 'application/json', ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Companion request failed with HTTP ${response.status}.`);
  }
  return await response.json() as T;
}

function jsonBody(value: unknown, method = 'POST'): RequestInit {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(value),
  };
}

export function saveDuplicateReview(request: {
  group_id: string;
  options: DuplicateAnalysisOptions;
  manual_action: DuplicatePlanAction | null;
  manual_primary_asset_id: string | null;
}): Promise<ExactDuplicateGroup> {
  return requestJson(
    '/api/assets/duplicates/cross-source/review',
    jsonBody(request, 'PUT'),
  );
}

export function loadDuplicateWorkspace(): Promise<DuplicateWorkspaceState> {
  return requestJson('/api/assets/duplicates/workspace');
}

export function saveDuplicateWorkspaceSelection(request: {
  options: DuplicateAnalysisOptions;
  selected_group_ids: string[];
  active_group_id: string | null;
}): Promise<DuplicateWorkspaceState> {
  return requestJson('/api/assets/duplicates/workspace/selection', jsonBody(request, 'PUT'));
}

export function saveDuplicateGroupDraft(request: {
  group_id: string;
  member_fingerprint: string;
  options: DuplicateAnalysisOptions;
  decisions: DuplicateMemberDraftDecision[];
  stack_primary_asset_id: string | null;
  metadata_keeper_asset_id: string | null;
  status: 'pending' | 'completed';
}): Promise<DuplicateGroupDraft> {
  return requestJson('/api/assets/duplicates/workspace/group', jsonBody(request, 'PUT'));
}

export function switchDuplicateSimilarityReference(
  duplicateId: string,
  referenceAssetId: string,
): Promise<ExactDuplicateGroup> {
  return requestJson(
    `/api/assets/duplicates/cross-source/${encodeURIComponent(duplicateId)}/similarity-reference`,
    jsonBody({ reference_asset_id: referenceAssetId }),
  );
}

export function loadDuplicateGroups(options: DuplicateAnalysisOptions): Promise<DuplicateResult> {
  const suppressAutomaticAnalysis = suppressNextAutomaticDuplicateAnalysis;
  suppressNextAutomaticDuplicateAnalysis = false;
  const requestOptions = suppressAutomaticAnalysis
    ? { ...options, analyze_automatically: false }
    : options;
  return requestJson('/api/assets/duplicates/cross-source/search', jsonBody(requestOptions));
}

export function analyzeDuplicateGroups(
  options: DuplicateAnalysisOptions,
): Promise<{ task_id: string }> {
  suppressNextAutomaticDuplicateAnalysis = false;
  return requestJson('/api/assets/duplicates/cross-source/analyze', jsonBody(options));
}

export function startDuplicateSimilarityScan(
  similarityThreshold: number,
): Promise<{ task_id: string }> {
  return requestJson('/api/assets/duplicates/similarity-scan', jsonBody({
    similarity_threshold: similarityThreshold,
    scope: 'all_eligible_assets',
    maximum_perceptual_distance: 12,
    maximum_aspect_difference: 0.05,
    maximum_neighbors_per_asset: 8,
    maximum_matches: 5000,
  }));
}

export function loadLatestSimilarityScan(): Promise<SimilarityScanSummary | null> {
  return requestJson('/api/assets/duplicates/similarity-scan/latest');
}

export function loadSimilarityScanTasks(): Promise<DuplicateTaskStatus[]> {
  return requestJson('/api/tasks?task_type=similarity_scan&limit=1');
}

export function cancelDuplicateTask(taskId: string): Promise<DuplicateTaskStatus> {
  return requestJson(`/api/tasks/${encodeURIComponent(taskId)}/cancel`, { method: 'POST' });
}

export async function loadDuplicateTask(taskId: string): Promise<DuplicateTaskStatus> {
  const loaded = await requestJson<DuplicateTaskStatus>(`/api/tasks/${encodeURIComponent(taskId)}`);
  if (loaded.task_type === 'cross_source_duplicates' && loaded.status === 'completed') {
    suppressNextAutomaticDuplicateAnalysis = true;
  }
  return loaded;
}

export function planDuplicateResolution(request: {
  options: DuplicateAnalysisOptions;
  group_ids: string[];
  all_eligible: boolean;
  keeper_overrides: Record<string, string>;
  action_overrides: Record<string, Exclude<DuplicatePlanAction, 'none'>>;
}): Promise<DuplicateResolutionPlan> {
  return requestJson('/api/assets/duplicates/cross-source/plan', jsonBody(request));
}

export function executeDuplicateResolution(planId: string): Promise<{ task_id: string }> {
  return requestJson('/api/assets/duplicates/cross-source/execute', jsonBody({ plan_id: planId }));
}
