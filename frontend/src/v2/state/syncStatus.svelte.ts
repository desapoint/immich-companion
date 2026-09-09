import { libraryData } from '../data/currentDataSource.svelte';
import type {
  SyncCoordinatorStatus,
  SyncDataRepository,
  SyncRun,
  SyncRunState,
  TaskConnectionState,
  TaskRecord,
  TaskRepository,
  TaskSubscription,
} from '../data/syncContracts';

const POLL_INTERVAL_MS = 30_000;

type SyncStatusSource = {
  sync: Pick<SyncDataRepository, 'status'>;
  tasks: Pick<TaskRepository, 'subscribe'>;
};

const TERMINAL_TASK_STATES = new Set<TaskRecord['status']>(['completed', 'failed', 'cancelled']);
const ACTIVE_TASK_STATES = new Set<TaskRecord['status']>(['running', 'retrying', 'recovering']);

function syncRunState(task: TaskRecord, fallback: SyncRunState): SyncRunState {
  switch (task.status) {
    case 'queued':
    case 'running':
    case 'retrying':
    case 'recovering':
    case 'completed':
    case 'failed':
      return task.status;
    default:
      return fallback;
  }
}

function progressString(progress: Record<string, unknown>, key: string, fallback: string | null): string | null {
  if (!(key in progress)) return fallback;
  const value = progress[key];
  if (value === null) return null;
  return typeof value === 'string' ? value : fallback;
}

function progressNumber(progress: Record<string, unknown>, key: string, fallback: number | null): number | null {
  if (!(key in progress)) return fallback;
  const value = progress[key];
  if (value === null) return null;
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

function applyTaskToRun(run: SyncRun, task: TaskRecord): SyncRun {
  const phase = progressString(task.progress, 'phase', run.phase) ?? run.phase;
  const completed = progressNumber(task.progress, 'completed', run.progress.completed) ?? run.progress.completed;
  const total = progressNumber(task.progress, 'total', run.progress.total);
  const percent = progressNumber(task.progress, 'percent', run.progress.percent);
  const detail = progressString(task.progress, 'detail', run.progress.detail);
  const checkpointCursor = task.checkpoint.cursor;

  return {
    ...run,
    status: syncRunState(task, run.status),
    phase,
    cursor: typeof checkpointCursor === 'string' ? checkpointCursor : run.cursor,
    counters: task.counters,
    attempts: task.attempt,
    error: task.error?.message ?? null,
    startedAt: task.startedAt ?? run.startedAt,
    completedAt: task.completedAt ?? run.completedAt,
    progress: {
      phase,
      completed,
      total,
      percent,
      detail,
    },
  };
}

export class SyncStatusController {
  status = $state<SyncCoordinatorStatus | null>(null);
  connectionState = $state<TaskConnectionState>('disconnected');
  loading = $state(false);
  error = $state('');
  lastUpdatedAt = $state<number | null>(null);

  private subscribers = 0;
  private taskSubscription: TaskSubscription | null = null;
  private pollTimer: ReturnType<typeof setInterval> | null = null;
  private refreshGeneration = 0;
  private refreshPromise: Promise<void> | null = null;
  private refreshQueued = false;

  constructor(
    private readonly source: SyncStatusSource = libraryData,
    private readonly pollIntervalMs = POLL_INTERVAL_MS,
  ) {}

  get stale(): boolean {
    return this.connectionState === 'reconnecting' || this.connectionState === 'disconnected' || Boolean(this.error);
  }

  acquire(): () => void {
    this.subscribers += 1;
    if (this.subscribers === 1) this.start();
    let released = false;
    return () => {
      if (released) return;
      released = true;
      this.subscribers = Math.max(0, this.subscribers - 1);
      if (this.subscribers === 0) this.stop();
    };
  }

  async refresh(): Promise<void> {
    if (this.refreshPromise) {
      this.refreshQueued = true;
      return this.refreshPromise;
    }

    const generation = ++this.refreshGeneration;
    this.loading = this.status === null;
    const request = (async () => {
      try {
        const next = await this.source.sync.status();
        if (generation !== this.refreshGeneration) return;
        this.status = next;
        this.error = '';
        this.lastUpdatedAt = Date.now();
      } catch (error) {
        if (generation !== this.refreshGeneration) return;
        this.error = error instanceof Error && error.message.trim()
          ? error.message
          : 'Synchronization status could not be loaded.';
      } finally {
        if (generation === this.refreshGeneration) this.loading = false;
      }
    })();

    this.refreshPromise = request;
    try {
      await request;
    } finally {
      if (this.refreshPromise === request) {
        this.refreshPromise = null;
        if (this.refreshQueued && this.subscribers > 0) {
          this.refreshQueued = false;
          void this.refresh();
        }
      }
    }
  }

  private applyTask(task: TaskRecord): boolean {
    if (!this.status) return false;

    let matched = false;
    let active = this.status.active;
    let pending = this.status.pending;

    if (active?.taskId === task.id) {
      active = applyTaskToRun(active, task);
      matched = true;
    }

    if (pending?.taskId === task.id) {
      const updated = applyTaskToRun(pending, task);
      if (ACTIVE_TASK_STATES.has(task.status)) {
        active = updated;
        pending = null;
      } else {
        pending = updated;
      }
      matched = true;
    }

    if (!matched) return false;

    this.status = { ...this.status, active, pending };
    this.error = '';
    this.lastUpdatedAt = Date.now();
    return true;
  }

  private start(): void {
    void this.refresh();
    this.taskSubscription = this.source.tasks.subscribe({
      onTask: (task) => {
        if (task.taskType !== 'asset_sync') return;
        const matched = this.applyTask(task);
        if (!matched || TERMINAL_TASK_STATES.has(task.status)) void this.refresh();
      },
      onConnectionState: (state) => {
        this.connectionState = state;
      },
      onRecovered: () => {
        void this.refresh();
      },
      onError: () => undefined,
    });
    this.pollTimer = setInterval(() => void this.refresh(), this.pollIntervalMs);
  }

  private stop(): void {
    if (this.pollTimer) clearInterval(this.pollTimer);
    this.pollTimer = null;
    this.taskSubscription?.close();
    this.taskSubscription = null;
    this.connectionState = 'disconnected';
    this.refreshGeneration += 1;
    this.refreshQueued = false;
    this.loading = false;
  }
}

export const syncStatus = new SyncStatusController();
