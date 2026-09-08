import { describe, expect, it, vi } from 'vitest';

import type { SyncCoordinatorStatus, TaskRecord, TaskRepository } from '../data/syncContracts';
import { SyncStatusController } from './syncStatus.svelte';

const status: SyncCoordinatorStatus = {
  active: null,
  pending: null,
  lastSuccess: null,
  lastFailure: null,
  successfulWatermark: null,
  authoritativeGeneration: 0,
};

const task: TaskRecord = {
  id: 'task-1',
  taskType: 'asset_sync',
  status: 'running',
  payload: {},
  checkpoint: {},
  counters: {},
  progress: {},
  result: null,
  error: null,
  attempt: 0,
  nextAttemptAt: null,
  createdAt: '',
  startedAt: null,
  completedAt: null,
};

describe('SyncStatusController', () => {
  it('shares one task subscription until the last consumer releases it', async () => {
    let handlers!: Parameters<TaskRepository['subscribe']>[0];
    const close = vi.fn();
    const statusRequest = vi.fn(async () => status);
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

  it('reconciles authoritative status after task-stream recovery', async () => {
    let handlers!: Parameters<TaskRepository['subscribe']>[0];
    const statusRequest = vi.fn(async () => status);
    const controller = new SyncStatusController({
      sync: { status: statusRequest },
      tasks: { subscribe: (next) => { handlers = next; return { close: () => undefined }; } },
    }, 60_000);

    const release = controller.acquire();
    await Promise.resolve();
    handlers.onRecovered?.();
    await Promise.resolve();

    expect(statusRequest).toHaveBeenCalledTimes(2);
    handlers.onTask(task);
    await Promise.resolve();
    expect(statusRequest).toHaveBeenCalledTimes(3);
    release();
  });
});
