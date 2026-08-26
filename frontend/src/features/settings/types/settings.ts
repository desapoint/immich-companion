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
