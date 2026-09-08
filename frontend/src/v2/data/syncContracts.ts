export type SyncMode = 'incremental' | 'full';
export type SyncRunState = 'queued' | 'running' | 'completed' | 'failed' | 'recovering' | 'retrying';

export interface SyncProgress {
  phase: string;
  completed: number;
  total: number | null;
  percent: number | null;
  detail: string | null;
}

export interface SyncRun {
  id: string;
  taskId: string | null;
  mode: SyncMode;
  status: SyncRunState;
  phase: string;
  generation: number;
  windowStart: string | null;
  windowEnd: string;
  cursor: string | null;
  counters: Record<string, number>;
  attempts: number;
  error: string | null;
  createdAt: string;
  startedAt: string | null;
  heartbeatAt: string | null;
  completedAt: string | null;
  progress: SyncProgress;
}

export interface SyncCoordinatorStatus {
  active: SyncRun | null;
  pending: SyncRun | null;
  lastSuccess: SyncRun | null;
  lastFailure: SyncRun | null;
  successfulWatermark: string | null;
  authoritativeGeneration: number;
}

export interface SyncRuntimeSettings {
  fullBatchSize: number;
  fullMinBatchDelaySeconds: number;
  tagAssociationConcurrency: number;
}

export interface SyncSchedule {
  id: string;
  name: string;
  enabled: boolean;
  intervalSeconds: number;
  cronExpression: string | null;
  deduplicationPolicy: string;
  nextRunAt: string;
  taskType: string;
  payload: Record<string, unknown>;
  priority: number;
}

export type TaskState = 'queued' | 'running' | 'retrying' | 'recovering' | 'cancel_requested' | 'cancelled' | 'completed' | 'failed';
export type TaskConnectionState = 'connecting' | 'connected' | 'reconnecting' | 'disconnected';

export interface TaskRecord {
  id: string;
  taskType: string;
  status: TaskState;
  payload: Record<string, unknown>;
  checkpoint: Record<string, unknown>;
  counters: Record<string, number>;
  progress: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error: { type?: string; message?: string } | null;
  attempt: number;
  nextAttemptAt: string | null;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
}

export interface TaskSubscription {
  close(): void;
}

export interface TaskRepository {
  get(taskId: string, signal?: AbortSignal): Promise<TaskRecord>;
  cancel(taskId: string): Promise<TaskRecord>;
  list(taskType: string, limit?: number, signal?: AbortSignal): Promise<TaskRecord[]>;
  subscribe(handlers: {
    onTask: (task: TaskRecord) => void;
    onConnectionState: (state: TaskConnectionState) => void;
    onRecovered?: () => void;
    onError?: (error: Error) => void;
  }): TaskSubscription;
}

export interface SyncDataRepository {
  status(signal?: AbortSignal): Promise<SyncCoordinatorStatus>;
  start(mode: SyncMode): Promise<SyncRun>;
  runtimeSettings(signal?: AbortSignal): Promise<SyncRuntimeSettings>;
  saveRuntimeSettings(value: SyncRuntimeSettings): Promise<SyncRuntimeSettings>;
  schedules(signal?: AbortSignal): Promise<SyncSchedule[]>;
  saveSchedules(values: Array<Pick<SyncSchedule, 'name' | 'enabled' | 'cronExpression'>>): Promise<SyncSchedule[]>;
}
