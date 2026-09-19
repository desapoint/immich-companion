import type { DuplicateDiscoveryProgress } from '../types/contracts';
import type { TaskRecord, TaskRepository } from '../../status/types/syncContracts';

const TERMINAL_TASK_STATES = new Set(['completed', 'failed', 'cancelled']);

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
  const queuedDetail = similarity
    ? 'Queued behind active asset-integrity work; the similarity phase will start automatically.'
    : 'Queued behind active asset-integrity work; exact duplicate analysis will start automatically.';
  const detail = typeof task.progress.detail === 'string'
    ? task.progress.detail
    : task.status === 'queued' ? queuedDetail : 'Preparing duplicate analysis…';
  const fallbackPhase = task.status === 'queued'
    ? (similarity ? 'Waiting for similarity scan' : 'Waiting for exact analysis')
    : (similarity ? 'Preparing similarity scan' : 'Preparing exact matches');
  return {
    label: `Duplicate discovery · ${phases[rawPhase] ?? fallbackPhase}`,
    detail: matches === null ? detail : `${detail} · ${matches.toLocaleString()} matches retained`,
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
