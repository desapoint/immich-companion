import { jsonRequest, requestJson } from '../../../lib/api/http';
import type { SyncCoordinatorStatus, SyncDataRepository, SyncMode, SyncRun, SyncRunState, SyncRuntimeSettings, SyncSchedule } from '../syncContracts';

type ApiSyncProgress = {
  phase: string;
  completed: number;
  total: number | null;
  percent: number | null;
  detail: string | null;
};

type ApiSyncRun = {
  id: string;
  task_id?: string | null;
  mode: SyncMode;
  status: SyncRunState;
  phase: string;
  generation: number;
  window_start: string | null;
  window_end: string;
  cursor: string | null;
  counters: Record<string, number>;
  attempts: number;
  error: string | null;
  created_at: string;
  started_at: string | null;
  heartbeat_at: string | null;
  completed_at: string | null;
  progress: ApiSyncProgress;
};

type ApiCoordinatorStatus = {
  active: ApiSyncRun | null;
  pending: ApiSyncRun | null;
  last_success: ApiSyncRun | null;
  last_failure: ApiSyncRun | null;
  successful_watermark: string | null;
  authoritative_generation: number;
};

type ApiRuntimeSettings = {
  full_batch_size: number;
  full_min_batch_delay_seconds: number;
  tag_association_concurrency: number;
};

type ApiSchedule = {
  id: string;
  name: string;
  enabled: boolean;
  interval_seconds: number;
  cron_expression: string | null;
  deduplication_policy: string;
  next_run_at: string;
  task_type: string;
  payload: Record<string, unknown>;
  priority: number;
};

function normalizeRun(run: ApiSyncRun | null): SyncRun | null {
  if (!run) return null;
  return {
    id: run.id,
    taskId: run.task_id ?? null,
    mode: run.mode,
    status: run.status,
    phase: run.phase,
    generation: run.generation,
    windowStart: run.window_start,
    windowEnd: run.window_end,
    cursor: run.cursor,
    counters: run.counters ?? {},
    attempts: run.attempts,
    error: run.error,
    createdAt: run.created_at,
    startedAt: run.started_at,
    heartbeatAt: run.heartbeat_at,
    completedAt: run.completed_at,
    progress: {
      phase: run.progress?.phase ?? run.phase,
      completed: run.progress?.completed ?? 0,
      total: run.progress?.total ?? null,
      percent: run.progress?.percent ?? null,
      detail: run.progress?.detail ?? null,
    },
  };
}

function normalizeStatus(status: ApiCoordinatorStatus): SyncCoordinatorStatus {
  return {
    active: normalizeRun(status.active),
    pending: normalizeRun(status.pending),
    lastSuccess: normalizeRun(status.last_success),
    lastFailure: normalizeRun(status.last_failure),
    successfulWatermark: status.successful_watermark,
    authoritativeGeneration: status.authoritative_generation,
  };
}

function normalizeRuntime(value: ApiRuntimeSettings): SyncRuntimeSettings {
  return {
    fullBatchSize: value.full_batch_size,
    fullMinBatchDelaySeconds: value.full_min_batch_delay_seconds,
    tagAssociationConcurrency: value.tag_association_concurrency,
  };
}

function runtimePayload(value: SyncRuntimeSettings): ApiRuntimeSettings {
  return {
    full_batch_size: value.fullBatchSize,
    full_min_batch_delay_seconds: value.fullMinBatchDelaySeconds,
    tag_association_concurrency: value.tagAssociationConcurrency,
  };
}

function normalizeSchedule(value: ApiSchedule): SyncSchedule {
  return {
    id: value.id,
    name: value.name,
    enabled: value.enabled,
    intervalSeconds: value.interval_seconds,
    cronExpression: value.cron_expression,
    deduplicationPolicy: value.deduplication_policy,
    nextRunAt: value.next_run_at,
    taskType: value.task_type,
    payload: value.payload ?? {},
    priority: value.priority,
  };
}

export function createSyncRepository(): SyncDataRepository {
  return {
    status: async (signal) => normalizeStatus(await requestJson<ApiCoordinatorStatus>('/api/assets/sync/status', { signal })),
    start: async (mode) => normalizeRun(await requestJson<ApiSyncRun>('/api/assets/sync/start', jsonRequest('POST', { mode })))!,
    runtimeSettings: async (signal) => normalizeRuntime(await requestJson<ApiRuntimeSettings>('/api/settings/sync/runtime', { signal })),
    saveRuntimeSettings: async (value) => normalizeRuntime(await requestJson<ApiRuntimeSettings>('/api/settings/sync/runtime', jsonRequest('PUT', runtimePayload(value)))),
    schedules: async (signal) => (await requestJson<ApiSchedule[]>('/api/settings/sync', { signal })).map(normalizeSchedule),
    saveSchedules: async (values) => {
      const saved: SyncSchedule[] = [];
      const failures: string[] = [];
      for (const value of values) {
        try {
          const schedule = await requestJson<ApiSchedule>(`/api/settings/sync/${encodeURIComponent(value.name)}`, jsonRequest('PUT', {
            enabled: value.enabled,
            cron_expression: value.cronExpression,
          }));
          saved.push(normalizeSchedule(schedule));
        } catch (error) {
          failures.push(`${value.name}: ${error instanceof Error ? error.message : 'save failed'}`);
        }
      }
      if (failures.length) throw new Error(`Some synchronization schedules could not be saved. ${failures.join(' ')}`);
      return saved;
    },
  };
}
