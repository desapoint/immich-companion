import type {
  DuplicateAnalysisOptions,
  DuplicateResolutionPlan,
  DuplicateResult,
  DuplicateTaskStatus,
} from '../types/duplicates';

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

function jsonBody(value: unknown): RequestInit {
  return {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(value),
  };
}

export function loadDuplicateGroups(options: DuplicateAnalysisOptions): Promise<DuplicateResult> {
  return requestJson('/api/assets/duplicates/cross-source/search', jsonBody(options));
}

export function analyzeDuplicateGroups(
  options: DuplicateAnalysisOptions,
): Promise<{ task_id: string }> {
  return requestJson('/api/assets/duplicates/cross-source/analyze', jsonBody(options));
}

export function loadDuplicateTask(taskId: string): Promise<DuplicateTaskStatus> {
  return requestJson(`/api/tasks/${encodeURIComponent(taskId)}`);
}

export function planDuplicateResolution(request: {
  options: DuplicateAnalysisOptions;
  duplicate_ids: string[];
  all_eligible: boolean;
  keeper_overrides: Record<string, string>;
}): Promise<DuplicateResolutionPlan> {
  return requestJson('/api/assets/duplicates/cross-source/plan', jsonBody(request));
}

export function executeDuplicateResolution(planId: string): Promise<{ task_id: string }> {
  return requestJson('/api/assets/duplicates/cross-source/execute', jsonBody({ plan_id: planId }));
}
