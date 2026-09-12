import { libraryData } from '../data/currentDataSource.svelte';
import type {
  TaskConnectionState,
  TaskRecord,
  TaskRepository,
  TaskSubscription,
} from '../data/syncContracts';

const POLL_INTERVAL_MS = 30_000;
const BACKGROUND_TASK_TYPES = ['cross_source_duplicates', 'similarity_scan'] as const;
const ACTIVE_TASK_STATES = new Set<TaskRecord['status']>([
  'queued',
  'running',
  'retrying',
  'recovering',
  'pause_requested',
  'paused',
  'cancel_requested',
]);

type BackgroundTaskSource = Pick<TaskRepository, 'list' | 'subscribe'>;

export type BackgroundTaskPresentation = {
  label: string;
  detail: string;
  completed: number;
  total: number | null;
  percent: number | null;
};

function progressNumber(progress: Record<string, unknown>, key: string): number | null {
  const value = progress[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

export function backgroundTaskPresentation(task: TaskRecord): BackgroundTaskPresentation {
  const rawPhase = typeof task.progress.phase === 'string' ? task.progress.phase : '';
  const phases: Record<string, string> = {
    duplicate_fingerprints: 'Verifying file evidence',
    similarity_candidates: 'Indexing candidates',
    similarity_scoring: 'Comparing pairs',
    similarity_finalizing: 'Finalizing groups',
    complete: 'Completing',
  };
  const title = task.taskType === 'similarity_scan' ? 'Similarity scan' : 'Duplicate analysis';
  const phase = phases[rawPhase] ?? (task.status === 'queued' ? 'Queued' : 'Preparing');
  const matches = progressNumber(task.counters, 'matches_retained');
  const fallbackDetail = task.status === 'queued'
    ? 'Waiting for the background worker…'
    : 'Preparing duplicate analysis…';
  const progressDetail = typeof task.progress.detail === 'string'
    ? task.progress.detail
    : fallbackDetail;
  return {
    label: `${title} · ${phase}`,
    detail: matches === null ? progressDetail : `${progressDetail} · ${matches.toLocaleString()} matches retained`,
    completed: progressNumber(task.progress, 'completed') ?? 0,
    total: progressNumber(task.progress, 'total'),
    percent: progressNumber(task.progress, 'percent'),
  };
}

function newestFirst(left: TaskRecord, right: TaskRecord): number {
  return right.createdAt.localeCompare(left.createdAt);
}

export class BackgroundTaskStatusController {
  tasks = $state.raw<TaskRecord[]>([]);
  workflow = $state.raw<{ id: string; presentation: BackgroundTaskPresentation } | null>(null);
  connectionState = $state<TaskConnectionState>('disconnected');
  error = $state('');

  private subscribers = 0;
  private taskSubscription: TaskSubscription | null = null;
  private pollTimer: ReturnType<typeof setInterval> | null = null;
  private refreshGeneration = 0;

  constructor(
    private readonly source: BackgroundTaskSource = libraryData.tasks,
    private readonly pollIntervalMs = POLL_INTERVAL_MS,
  ) {}

  startDuplicateDiscovery(): void {
    this.workflow = {
      id: 'duplicate-discovery',
      presentation: {
        label: 'Duplicate discovery · Preparing',
        detail: 'Submitting background analysis…',
        completed: 0,
        total: null,
        percent: null,
      },
    };
  }

  updateDuplicateDiscovery(presentation: BackgroundTaskPresentation): void {
    this.workflow = { id: 'duplicate-discovery', presentation };
  }

  finishDuplicateDiscovery(): void {
    this.workflow = null;
    this.tasks = [];
    if (this.subscribers > 0) void this.refresh();
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
    const generation = ++this.refreshGeneration;
    try {
      const results = await Promise.all(
        BACKGROUND_TASK_TYPES.map((taskType) => this.source.list(taskType, 10)),
      );
      if (generation !== this.refreshGeneration) return;
      this.tasks = results
        .flat()
        .filter((task) => ACTIVE_TASK_STATES.has(task.status))
        .sort(newestFirst);
      this.error = '';
    } catch (error) {
      if (generation !== this.refreshGeneration) return;
      this.error = error instanceof Error && error.message.trim()
        ? error.message
        : 'Background task status could not be loaded.';
    }
  }

  private applyTask(task: TaskRecord): void {
    if (!BACKGROUND_TASK_TYPES.includes(task.taskType as typeof BACKGROUND_TASK_TYPES[number])) return;
    if (!ACTIVE_TASK_STATES.has(task.status)) {
      this.tasks = this.tasks.filter((candidate) => candidate.id !== task.id);
      return;
    }
    this.tasks = [task, ...this.tasks.filter((candidate) => candidate.id !== task.id)]
      .sort(newestFirst);
    this.error = '';
  }

  private start(): void {
    void this.refresh();
    this.taskSubscription = this.source.subscribe({
      onTask: (task) => this.applyTask(task),
      onConnectionState: (state) => this.connectionState = state,
      onRecovered: () => void this.refresh(),
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
  }
}

export const backgroundTaskStatus = new BackgroundTaskStatusController();
