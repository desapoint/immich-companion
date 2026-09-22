import { afterEach, describe, expect, it, vi } from 'vitest';

import type { TaskRecord, TaskRepository } from '../../status/types/syncContracts';
import { waitForTask } from '../api/duplicateDiscovery';

const runningTask = {
  id: 'task-1',
  taskType: 'duplicate_resolution',
  status: 'running',
  payload: {},
  checkpoint: {},
  counters: {},
  progress: {},
  result: null,
  error: null,
  attempt: 1,
  nextAttemptAt: null,
  createdAt: '2026-09-21T00:00:00Z',
  startedAt: '2026-09-21T00:00:01Z',
  completedAt: null,
} satisfies TaskRecord;

const completedTask = {
  ...runningTask,
  status: 'completed',
  result: { summary: { failed_group_ids: [] } },
  completedAt: '2026-09-21T00:00:02Z',
} satisfies TaskRecord;

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('duplicate task waiting', () => {
  it('uses the task-specific WebSocket after the initial status read', async () => {
    let handlers!: Parameters<NonNullable<TaskRepository['subscribeTask']>>[1];
    const close = vi.fn();
    const source = {
      get: vi.fn(async () => runningTask),
      subscribeTask: vi.fn((_taskId: string, next: typeof handlers) => {
        handlers = next;
        next.onConnectionState('connected');
        return { close };
      }),
    } as unknown as TaskRepository;

    const pending = waitForTask(source, 'task-1');
    await Promise.resolve();
    await Promise.resolve();

    expect(source.subscribeTask).toHaveBeenCalledWith('task-1', expect.any(Object));
    expect(source.get).toHaveBeenCalledTimes(1);

    handlers.onTask(completedTask);

    await expect(pending).resolves.toEqual(completedTask);
    expect(source.get).toHaveBeenCalledTimes(1);
    expect(close).toHaveBeenCalledTimes(1);
  });

  it('falls back to REST polling when the task stream degrades', async () => {
    vi.useFakeTimers();
    let handlers!: Parameters<NonNullable<TaskRepository['subscribeTask']>>[1];
    const close = vi.fn();
    const source = {
      get: vi.fn()
        .mockResolvedValueOnce(runningTask)
        .mockResolvedValueOnce(completedTask),
      subscribeTask: vi.fn((_taskId: string, next: typeof handlers) => {
        handlers = next;
        next.onConnectionState('connected');
        return { close };
      }),
    } as unknown as TaskRepository;

    const pending = waitForTask(source, 'task-1');
    await Promise.resolve();
    await Promise.resolve();
    expect(source.get).toHaveBeenCalledTimes(1);

    handlers.onError?.(new Error('stream degraded'));
    await vi.advanceTimersByTimeAsync(0);

    await expect(pending).resolves.toEqual(completedTask);
    expect(source.get).toHaveBeenCalledTimes(2);
    expect(close).toHaveBeenCalledTimes(1);
  });
});
