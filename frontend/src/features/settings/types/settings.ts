export interface SyncSchedule {
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
}

export interface SyncRuntimeSettings {
  full_batch_size: number;
  full_min_batch_delay_seconds: number;
  sync_trashed_album_context: boolean;
  sync_trashed_tag_context: boolean;
}
