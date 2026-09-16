import { requestJson } from '../../../lib/api/http';

export type ImmichDuplicateSyncState =
  | 'never_synced'
  | 'idle'
  | 'queued'
  | 'running'
  | 'retrying'
  | 'recovering'
  | 'pause_requested'
  | 'paused'
  | 'cancel_requested'
  | 'failed';

export type ImmichDuplicateSyncStatus = {
  state: ImmichDuplicateSyncState;
  authoritativeGeneration: number;
  groupCount: number;
  memberCount: number;
  lastSuccessAt: string | null;
  lastAttemptAt: string | null;
  taskId: string | null;
  taskStatus: string | null;
  error: string | null;
};

type ApiStatus = {
  state: ImmichDuplicateSyncState;
  authoritative_generation: number;
  group_count: number;
  member_count: number;
  last_success_at: string | null;
  last_attempt_at: string | null;
  task_id: string | null;
  task_status: string | null;
  error: string | null;
};

type ApiTaskStart = { task_id: string };

function normalize(value: ApiStatus): ImmichDuplicateSyncStatus {
  return {
    state: value.state,
    authoritativeGeneration: value.authoritative_generation,
    groupCount: value.group_count,
    memberCount: value.member_count,
    lastSuccessAt: value.last_success_at,
    lastAttemptAt: value.last_attempt_at,
    taskId: value.task_id,
    taskStatus: value.task_status,
    error: value.error,
  };
}

export const immichDuplicateSyncRepository = {
  async status(signal?: AbortSignal): Promise<ImmichDuplicateSyncStatus> {
    return normalize(
      await requestJson<ApiStatus>('/api/settings/duplicates/immich-sync', { signal }),
    );
  },

  async start(): Promise<string> {
    const result = await requestJson<ApiTaskStart>(
      '/api/settings/duplicates/immich-sync',
      { method: 'POST' },
    );
    return result.task_id;
  },
};
