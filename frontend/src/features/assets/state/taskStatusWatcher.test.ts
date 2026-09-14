import { afterEach, describe, expect, it, vi } from 'vitest';

import type { AssetTaskStatus } from '../types/assets';
import { TaskStatusWatcher, type TaskStatusSocket } from './taskStatusWatcher';

function task(status: AssetTaskStatus['status'] = 'running'): AssetTaskStatus {
  return {
    id: 'task-1',
    task_type: 'asset_integrity',
    status,
    payload: {},
    checkpoint: {},
    counters: {},
    progress: {},
    result: null,
    error: null,
    attempt: 1,
    next_attempt_at: null,
    created_at: '2026-09-14T00:00:00Z',
    started_at: null,
    completed_at: null,
  };
}

afterEach(() => vi.useRealTimers());

describe('TaskStatusWatcher', () => {
  it('falls back to one-at-a-time polling when the stream closes', async () => {
    vi.useFakeTimers();
    let closeStream = () => undefined;
    let activeLoads = 0;
    let maxActiveLoads = 0;
    let resolveLoad: ((value: AssetTaskStatus) => void) | null = null;
    const statuses: AssetTaskStatus[] = [];

    const watcher = new TaskStatusWatcher(
      (_taskId, _onstatus, _onerror, onclose): TaskStatusSocket => {
        closeStream = onclose;
        return { close: vi.fn() };
      },
      async () => {
        activeLoads += 1;
        maxActiveLoads = Math.max(maxActiveLoads, activeLoads);
        const value = await new Promise<AssetTaskStatus>((resolve) => { resolveLoad = resolve; });
        activeLoads -= 1;
        return value;
      },
      (next) => statuses.push(next),
      () => undefined,
      1000,
    );

    watcher.start('task-1');
    closeStream();
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(5000);
    expect(maxActiveLoads).toBe(1);

    resolveLoad?.(task());
    await Promise.resolve();
    await Promise.resolve();
    expect(statuses).toHaveLength(1);

    watcher.stop();
  });

  it('aborts fallback work when stopped', async () => {
    vi.useFakeTimers();
    let closeStream = () => undefined;
    let observedAbort = false;

    const watcher = new TaskStatusWatcher(
      (_taskId, _onstatus, _onerror, onclose): TaskStatusSocket => {
        closeStream = onclose;
        return { close: vi.fn() };
      },
      async (_taskId, signal) => new Promise<AssetTaskStatus>((_resolve, reject) => {
        signal.addEventListener('abort', () => {
          observedAbort = true;
          reject(new DOMException('Aborted', 'AbortError'));
        }, { once: true });
      }),
      () => undefined,
      () => undefined,
    );

    watcher.start('task-1');
    closeStream();
    await vi.advanceTimersByTimeAsync(0);
    watcher.stop();
    await Promise.resolve();

    expect(observedAbort).toBe(true);
  });
});
