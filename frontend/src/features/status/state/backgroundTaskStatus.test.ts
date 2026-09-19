import { afterEach, describe, expect, it, vi } from 'vitest';

import type { TaskRecord, TaskRepository } from '../types/syncContracts';
import {
  BackgroundTaskStatusController,
  backgroundTaskPresentation,
} from './backgroundTaskStatus.svelte';

const similarityTask: TaskRecord = {
  id: 'similarity-1',
  taskType: 'similarity_scan',
  status: 'running',
  payload: {},
  checkpoint: {},
  counters: { candidate_pairs: 500, matches_retained: 8 },
  progress: {
    phase: 'similarity_scoring',
    completed: 125,
    total: 500,
    percent: 35,
    detail: 'Scored 125 of 500 candidate pairs',
  },
  result: null,
  error: null,
  attempt: 1,
  nextAttemptAt: null,
  createdAt: '2026-09-10T12:00:00Z',
  startedAt: '2026-09-10T12:00:01Z',
  completedAt: null,
};

afterEach(() => vi.useRealTimers());

describe('background task status', () => {
  it('presents similarity phases and retained-match detail for the global tray', () => {
    expect(backgroundTaskPresentation(similarityTask)).toEqual({
      label: 'Similarity scan · Comparing pairs',
      detail: 'Scored 125 of 500 candidate pairs · 8 matches retained',
      completed: 125,
      total: 500,
      percent: 35,
    });
  });

  it('hydrates active tasks once and applies live terminal updates', async () => {
    let handlers!: Parameters<TaskRepository['subscribe']>[0];
    const close = vi.fn();
    const listActive = vi.fn(async () => [
      similarityTask,
      { ...similarityTask, id: 'sync', taskType: 'asset_sync' },
      { ...similarityTask, id: 'old', status: 'completed' as const },
    ]);
    const controller = new BackgroundTaskStatusController({
      listActive,
      subscribe: (next) => { handlers = next; return { close }; },
    }, 60_000);

    const release = controller.acquire();
    await Promise.resolve();
    await Promise.resolve();

    expect(listActive).toHaveBeenCalledTimes(1);
    expect(listActive).toHaveBeenCalledWith(200);
    expect(controller.tasks.map((task) => task.id)).toEqual(['similarity-1']);

    handlers.onTask({ ...similarityTask, progress: { ...similarityTask.progress, percent: 60 } });
    expect(controller.tasks[0]?.progress.percent).toBe(60);
    handlers.onTask({ ...similarityTask, status: 'completed', completedAt: '2026-09-10T12:01:00Z' });
    expect(controller.tasks).toEqual([]);

    release();
    expect(close).toHaveBeenCalledTimes(1);
  });

  it('uses the WebSocket while connected and polls only after a disconnect grace period', async () => {
    vi.useFakeTimers();
    let handlers!: Parameters<TaskRepository['subscribe']>[0];
    const listActive = vi.fn(async () => []);
    const controller = new BackgroundTaskStatusController({
      listActive,
      subscribe: (next) => { handlers = next; return { close: () => undefined }; },
    }, 30_000, 10_000);

    const release = controller.acquire();
    await Promise.resolve();
    await Promise.resolve();
    expect(listActive).toHaveBeenCalledTimes(1);

    handlers.onConnectionState('connected');
    await vi.advanceTimersByTimeAsync(180_000);
    expect(listActive).toHaveBeenCalledTimes(1);

    handlers.onConnectionState('reconnecting');
    await vi.advanceTimersByTimeAsync(9_999);
    expect(listActive).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(listActive).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(30_000);
    expect(listActive).toHaveBeenCalledTimes(3);

    handlers.onConnectionState('connected');
    handlers.onRecovered?.();
    await Promise.resolve();
    await Promise.resolve();
    expect(listActive).toHaveBeenCalledTimes(4);
    await vi.advanceTimersByTimeAsync(120_000);
    expect(listActive).toHaveBeenCalledTimes(4);

    release();
  });

  it('shares one task subscription across consumers', () => {
    const close = vi.fn();
    const subscribe = vi.fn(() => ({ close }));
    const controller = new BackgroundTaskStatusController({
      listActive: vi.fn(async () => []),
      subscribe,
    }, 60_000);

    const releaseFirst = controller.acquire();
    const releaseSecond = controller.acquire();
    expect(subscribe).toHaveBeenCalledTimes(1);
    releaseFirst();
    expect(close).not.toHaveBeenCalled();
    releaseSecond();
    expect(close).toHaveBeenCalledTimes(1);
  });

  it('keeps one stable workflow identity while backend scan stages change', () => {
    const controller = new BackgroundTaskStatusController({
      listActive: vi.fn(async () => []),
      subscribe: vi.fn(() => ({ close: () => undefined })),
    });

    controller.startDuplicateDiscovery();
    const workflowId = controller.workflow?.id;
    controller.updateDuplicateDiscovery({
      label: 'Duplicate discovery · Comparing candidate pairs',
      detail: 'Scored 40 of 100 candidate pairs',
      completed: 40,
      total: 100,
      percent: 54,
    });

    expect(controller.workflow?.id).toBe(workflowId);
    expect(controller.workflow?.presentation.percent).toBe(54);
    controller.finishDuplicateDiscovery();
    expect(controller.workflow).toBeNull();
  });
});
