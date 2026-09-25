import { jsonRequest, requestJson } from '../../../lib/api/http';
import type { SyncCoordinatorStatus, SyncDataRepository, SyncHistoryItem, SyncHistoryPage, SyncMode, SyncRun, SyncRunState, SyncRuntimeSettings, SyncSchedule } from '../types/syncContracts';

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
  metadata_request_concurrency: number;
  page_prefetch: number;
  api_page_size: number;
  incremental_overlap_seconds: number;
  incremental_strategy: 'automatic' | 'asset' | 'relation';
  adaptive_throttling: boolean;
};

type ApiSchedule = {
  id: string;
  name: string;
  enabled: boolean;
  interval_seconds: number;
  cron_expression: string | null;
  deduplication_policy: string;
  next_run_at: string;
  last_run_at: string | null;
  task_type: string;
  payload: Record<string, unknown>;
  priority: number;
};

type ApiPhaseTelemetry = {
  phase: string;
  duration_seconds: number;
  processed_items: number;
  api_requests: number;
  api_retries: number;
  rate_limits: number;
  wait_seconds: number;
  checkpoints: number;
  counters: Record<string, number>;
};

type ApiHistoryItem = {
  id: string;
  mode: SyncMode;
  status: string;
  generation: number;
  attempts: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  queue_seconds: number | null;
  duration_seconds: number | null;
  throughput_per_second: number | null;
  api_requests: number;
  api_retries: number;
  rate_limits: number;
  wait_seconds: number;
  checkpoints: number;
  counters: Record<string, number>;
  settings: ApiRuntimeSettings | null;
  phases: ApiPhaseTelemetry[];
  error: string | null;
  telemetry_available: boolean;
};

type ApiHistoryPage = {
  items: ApiHistoryItem[];
  total: number;
  offset: number;
  limit: number;
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
    metadataRequestConcurrency: value.metadata_request_concurrency,
    pagePrefetch: value.page_prefetch,
    apiPageSize: value.api_page_size,
    incrementalOverlapSeconds: value.incremental_overlap_seconds,
    incrementalStrategy: value.incremental_strategy,
    adaptiveThrottling: value.adaptive_throttling,
  };
}

function runtimePayload(value: SyncRuntimeSettings): ApiRuntimeSettings {
  return {
    full_batch_size: value.fullBatchSize,
    full_min_batch_delay_seconds: value.fullMinBatchDelaySeconds,
    tag_association_concurrency: value.tagAssociationConcurrency,
    metadata_request_concurrency: value.metadataRequestConcurrency,
    page_prefetch: value.pagePrefetch,
    api_page_size: value.apiPageSize,
    incremental_overlap_seconds: value.incrementalOverlapSeconds,
    incremental_strategy: value.incrementalStrategy,
    adaptive_throttling: value.adaptiveThrottling,
  };
}

function normalizeHistoryItem(value: ApiHistoryItem): SyncHistoryItem {
  return {
    id: value.id,
    mode: value.mode,
    status: value.status,
    generation: value.generation,
    attempts: value.attempts,
    createdAt: value.created_at,
    startedAt: value.started_at,
    completedAt: value.completed_at,
    queueSeconds: value.queue_seconds,
    durationSeconds: value.duration_seconds,
    throughputPerSecond: value.throughput_per_second,
    apiRequests: value.api_requests,
    apiRetries: value.api_retries,
    rateLimits: value.rate_limits,
    waitSeconds: value.wait_seconds,
    checkpoints: value.checkpoints,
    counters: value.counters ?? {},
    settings: value.settings ? normalizeRuntime(value.settings) : null,
    phases: (value.phases ?? []).map((phase) => ({
      phase: phase.phase,
      durationSeconds: phase.duration_seconds,
      processedItems: phase.processed_items,
      apiRequests: phase.api_requests,
      apiRetries: phase.api_retries,
      rateLimits: phase.rate_limits,
      waitSeconds: phase.wait_seconds,
      checkpoints: phase.checkpoints,
      counters: phase.counters ?? {},
    })),
    error: value.error,
    telemetryAvailable: value.telemetry_available,
  };
}

function normalizeHistory(value: ApiHistoryPage): SyncHistoryPage {
  return {
    items: value.items.map(normalizeHistoryItem),
    total: value.total,
    offset: value.offset,
    limit: value.limit,
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
    lastRunAt: value.last_run_at ?? null,
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
    history: async (mode, offset = 0, limit = 25, signal) => normalizeHistory(await requestJson<ApiHistoryPage>(`/api/settings/sync/history?mode=${encodeURIComponent(mode)}&offset=${offset}&limit=${limit}`, { signal })),
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
