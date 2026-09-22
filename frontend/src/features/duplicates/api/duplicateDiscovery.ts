import type { DuplicateDiscoveryProgress } from '../types/contracts';
import type { TaskRecord, TaskRepository } from '../../status/types/syncContracts';

const TERMINAL_TASK_STATES = new Set(['completed', 'failed', 'cancelled']);
const FALLBACK_POLL_INTERVAL_MS = 1000;

function numericProgress(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

export function discoveryProgress(
  task: TaskRecord,
  similarity: boolean,
  rangeStart: number,
  rangeEnd: number,
): DuplicateDiscoveryProgress {
  const rawPhase = typeof task.progress.phase === 'string' ? task.progress.phase : '';
  const phases: Record<string, string> = {
    duplicate_fingerprints: 'Verifying file evidence',
    similarity_candidates: 'Indexing similarity candidates',
    similarity_scoring: 'Comparing candidate pairs',
    similarity_finalizing: 'Finalizing duplicate groups',
    duplicate_projection_publish: 'Publishing duplicate results',
    complete: 'Completing analysis',
  };
  const rawPercent = numericProgress(task.progress.percent);
  const overallPercent = rawPercent === null
    ? null
    : Math.min(rangeEnd, rangeStart + (rangeEnd - rangeStart) * rawPercent / 100);
  const matches = numericProgress(task.counters.matches_retained);
  const retainedLimit = similarity ? numericProgress(task.payload?.maximum_matches) : null;
  const retentionLimitReached = similarity && task.counters.result_limit_reached === 1;
  const queuedDetail = similarity
    ? 'Queued behind active asset-integrity work; the similarity phase will start automatically.'
    : 'Queued behind active asset-integrity work; exact duplicate analysis will start automatically.';
  const detail = typeof task.progress.detail === 'string'
    ? task.progress.detail
    : task.status === 'queued' ? queuedDetail : 'Preparing duplicate analysis…';
  const fallbackPhase = task.status === 'queued'
    ? (similarity ? 'Waiting for similarity scan' : 'Waiting for exact analysis')
    : (similarity ? 'Preparing similarity scan' : 'Preparing exact matches');
  const retentionDetail = matches === null
    ? ''
    : retainedLimit === null
      ? `${matches.toLocaleString()} matches retained`
      : `${matches.toLocaleString()} / ${retainedLimit.toLocaleString()} matches retained${retentionLimitReached ? ' · RETENTION LIMIT REACHED' : ''}`;
  return {
    label: `Duplicate discovery · ${phases[rawPhase] ?? fallbackPhase}`,
    detail: retentionDetail ? `${detail} · ${retentionDetail}` : detail,
    completed: numericProgress(task.progress.completed) ?? 0,
    total: numericProgress(task.progress.total),
    percent: overallPercent,
  };
}

export async function waitForTask(
  tasks: TaskRepository,
  taskId: string,
  similarity = false,
  rangeStart = 0,
  rangeEnd = 98,
  onprogress?: (progress: DuplicateDiscoveryProgress) => void,
): Promise<TaskRecord> {
  const subscribeTask = tasks.subscribeTask;
  if (!subscribeTask) {
    for (;;) {
      const task = await tasks.get(taskId);
      onprogress?.(discoveryProgress(task, similarity, rangeStart, rangeEnd));
      if (TERMINAL_TASK_STATES.has(task.status)) {
        if (task.status !== 'completed') throw new Error(task.error?.message ?? `Duplicate task ${task.status}.`);
        return task;
      }
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
  }

  return await new Promise<TaskRecord>((resolve, reject) => {
    let subscription: ReturnType<NonNullable<TaskRepository['subscribeTask']>> | null = null;
    let fallbackTimer: ReturnType<typeof setTimeout> | null = null;
    let pollInFlight = false;
    let settled = false;
    let streamHealthy = false;

    const clearFallback = (): void => {
      if (fallbackTimer) clearTimeout(fallbackTimer);
      fallbackTimer = null;
    };

    const cleanup = (): void => {
      clearFallback();
      subscription?.close();
      subscription = null;
    };

    const fail = (error: unknown): void => {
      if (settled) return;
      settled = true;
      cleanup();
      reject(error instanceof Error ? error : new Error('Duplicate task monitoring failed.'));
    };

    const acceptTask = (task: TaskRecord): boolean => {
      if (settled || task.id !== taskId) return false;
      onprogress?.(discoveryProgress(task, similarity, rangeStart, rangeEnd));
      if (!TERMINAL_TASK_STATES.has(task.status)) return false;
      settled = true;
      cleanup();
      if (task.status === 'completed') resolve(task);
      else reject(new Error(task.error?.message ?? `Duplicate task ${task.status}.`));
      return true;
    };

    const scheduleFallback = (delay = FALLBACK_POLL_INTERVAL_MS): void => {
      if (settled || streamHealthy || pollInFlight || fallbackTimer) return;
      fallbackTimer = setTimeout(() => {
        fallbackTimer = null;
        void poll();
      }, delay);
    };

    const poll = async (): Promise<void> => {
      if (settled || pollInFlight) return;
      pollInFlight = true;
      try {
        const task = await tasks.get(taskId);
        if (!settled) acceptTask(task);
      } catch (error) {
        if (!subscription) {
          fail(error);
          return;
        }
      } finally {
        pollInFlight = false;
        if (!settled && !streamHealthy) scheduleFallback();
      }
    };

    const created = subscribeTask(taskId, {
      onTask: (task) => {
        streamHealthy = true;
        clearFallback();
        acceptTask(task);
      },
      onConnectionState: (state) => {
        streamHealthy = state === 'connected';
        if (streamHealthy) clearFallback();
        else scheduleFallback(0);
      },
      onRecovered: () => {
        streamHealthy = true;
        clearFallback();
      },
      onError: () => {
        streamHealthy = false;
        scheduleFallback(0);
      },
    });
    subscription = created;
    if (settled) {
      created.close();
      return;
    }
    void poll();
  });
}
