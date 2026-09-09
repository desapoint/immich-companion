import { describe, expect, it, vi } from 'vitest';

import type { SyncCoordinatorStatus, SyncRun, TaskRecord, TaskRepository } from '../data/syncContracts';
import { SyncStatusController } from './syncStatus.svelte';

const run: SyncRun = {
  id: 'sync-1',
  taskId: 'task-1',
  mode: 'full',
  status: 'running',
  phase: 'assets',
  generation: 1,
  windowStart: null,
  windowEnd: '2026-09-09T00:00:00Z',
  cursor: null,
  counters: {},
  attempts: 0,
  error: null,
  createdAt: '2026-09-09T00:00:00Z',
  startedAt: '2026-09-09T00:00:01Z',
  heartbeatAt: null,
  completedAt: null,
  progress: {
    phase: 'assets',
    completed: 0,
    total: 100,
    percent: 0,
    detail: null,
  },
};

const emptyStatus: SyncCoordinatorStatus = {
  active: null,
  pending: null,
  lastSuccess: null,
  lastFailure: null,
  successfulWatermark: null,
  authoritativeGeneration: 0,
};

const activeStatus: SyncCoordinatorStatus = {
  ...emptyStatus,
  active: run,
  authoritativeGeneration: 1,
};

const task: TaskRecord = {
  id: 'task-1',
  taskType: 'asset_sync',
  status: 'running',
  payload: {},
  checkpoint: { cursor: 'cursor-25' },
  counters: { assets: 25 },
  progress: {
    phase: 'assets',
    completed: 25,
    total: 100,
    percent: 25,
    detail: '25 assets synchronized',
  },
  result: null,
  error: null,
  attempt: 1,
  nextAttemptAt: null,
  createdAt: '2026-09-09T00:00:00Z',
  startedAt: '2026-09-09T00:00:01Z',
  completedAt: null,
};

describe('SyncStatusController', () => {
  it('shares one task subscription until the last consumer releases it', async () => {
    let handlers!: Parameters<TaskRepository['subscribe']>[0];
    const close = vi.fn();
    const statusRequest = vi.fn(async () => emptyStatus);
    const subscribe = vi.fn((next: Parameters<TaskRepository['subscribe']>[0]) => {
      handlers = next;
      return { close };
    });
    const controller = new SyncStatusController({ sync: { status: statusRequest }, tasks: { subscribe } }, 60_000);

    const releaseFirst = controller.acquire();
    const releaseSecond = controller.acquire();
    await Promise.resolve();

    expect(subscribe).toHaveBeenCalledTimes(1);
    expect(statusRequest).toHaveBeenCalledTimes(1);
    releaseFirst();
    expect(close).not.toHaveBeenCalled();
    releaseSecond();
    expect(close).toHaveBeenCalledTimes(1);
    expect(controller.connectionState).toBe('disconnected');
    handlers.onConnectionState('connected');
  });

  it('applies live sync task progress without refetching coordinator status', async () => {
    let handlers!: Parameters<TaskRepository['subscribe']>[0];
    const statusRequest = vi.fn(async () => activeStatus);
    const controller = new SyncStatusController({
      sync: { status: statusRequest },
      tasks: { subscribe: (next) => { handlers = next; return { close: () => undefined }; } },
    }, 60_000);

    const release = controller.acquire();
    await Promise.resolve();
    handlers.onTask(task);
    await Promise.resolve();

    expect(statusRequest).toHaveBeenCalledTimes(1);
    expect(controller.status?.active?.progress.completed).toBe(25);
    expect(controller.status?.active?.progress.percent).toBe(25);
    expect(controller.status?.active?.counters).toEqual({ assets: 25 });
    expect(controller.status?.active?.cursor).toBe('cursor-25');
    expect(controller.status?.active?.attempts).toBe(1);
    release();
  });

  it('reconciles authoritative status after task-stream recovery and terminal events', async () => {
    let handlers!: Parameters<TaskRepository['subscribe']>[0];
    const statusRequest = vi.fn(async () => activeStatus);
    const controller = new SyncStatusController({
      sync: { status: statusRequest },
      tasks: { subscribe: (next) => { handlers = next; return { close: () => undefined }; } },
    }, 60_000);

    const release = controller.acquire();
    await Promise.resolve();
    handlers.onRecovered?.();
    await Promise.resolve();

    expect(statusRequest).toHaveBeenCalledTimes(2);

    handlers.onTask({ ...task, status: 'completed', completedAt: '2026-09-09T00:01:00Z' });
    await Promise.resolve();
    await Promise.resolve();

    expect(statusRequest).toHaveBeenCalledTimes(3);
    release();
  });

  it('refetches once when an asset sync task is not represented in current status', async () => {
    let handlers!: Parameters<TaskRepository['subscribe']>[0];
    const statusRequest = vi.fn(async () => emptyStatus);
    const controller = new SyncStatusController({
      sync: { status: statusRequest },
      tasks: { subscribe: (next) => { handlers = next; return { close: () => undefined }; } },
    }, 60_000);

    const release = controller.acquire();
    await Promise.resolve();
    handlers.onTask(task);
    handlers.onTask(task);
    await Promise.resolve();
    await Promise.resolve();

    expect(statusRequest).toHaveBeenCalledTimes(2);
    release();
  });
});
