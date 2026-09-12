import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { createTaskRepository, isApiTask, taskReconnectDelayMs } from './taskRepository';

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  closed = false;

  constructor(public readonly url: string) {
    FakeWebSocket.instances.push(this);
  }

  close(): void {
    this.closed = true;
    this.onclose?.();
  }

  open(): void {
    this.onopen?.();
  }

  message(value: unknown): void {
    this.onmessage?.({ data: JSON.stringify(value) });
  }

  disconnect(): void {
    this.onclose?.();
  }
}

beforeEach(() => {
  FakeWebSocket.instances = [];
  vi.stubGlobal('window', { location: { protocol: 'http:', host: 'localhost' } });
  vi.stubGlobal('WebSocket', FakeWebSocket);
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('V2 TaskRepository live stream', () => {
  it('shares one socket across subscribers and closes it after the last subscriber leaves', () => {
    const repository = createTaskRepository();
    const first = repository.subscribe({ onTask: () => undefined, onConnectionState: () => undefined });
    const second = repository.subscribe({ onTask: () => undefined, onConnectionState: () => undefined });

    expect(FakeWebSocket.instances).toHaveLength(1);
    first.close();
    expect(FakeWebSocket.instances[0].closed).toBe(false);
    second.close();
    expect(FakeWebSocket.instances[0].closed).toBe(true);
  });

  it('uses bounded backoff and publishes recovery after reconnect', () => {
    vi.useFakeTimers();
    vi.spyOn(Math, 'random').mockReturnValue(0.5);
    const recovered = vi.fn();
    const states: string[] = [];
    const repository = createTaskRepository();
    repository.subscribe({
      onTask: () => undefined,
      onConnectionState: (state) => states.push(state),
      onRecovered: recovered,
    });

    FakeWebSocket.instances[0].open();
    FakeWebSocket.instances[0].disconnect();
    expect(states).toContain('reconnecting');

    vi.advanceTimersByTime(1000);
    expect(FakeWebSocket.instances).toHaveLength(2);
    FakeWebSocket.instances[1].open();
    expect(recovered).toHaveBeenCalledTimes(1);
  });

  it('rejects malformed task messages without publishing them', () => {
    const tasks = vi.fn();
    const errors = vi.fn();
    const repository = createTaskRepository();
    repository.subscribe({ onTask: tasks, onConnectionState: () => undefined, onError: errors });

    FakeWebSocket.instances[0].message({ id: 'task-1', task_type: 'asset_sync', status: 'not-a-state' });

    expect(tasks).not.toHaveBeenCalled();
    expect(errors).toHaveBeenCalledTimes(1);
  });
});

describe('task stream validation helpers', () => {
  it('accepts the minimum valid task shape', () => {
    expect(isApiTask({ id: 'task-1', task_type: 'asset_sync', status: 'running' })).toBe(true);
    expect(isApiTask({ id: 'task-1', task_type: 'similarity_scan', status: 'paused' })).toBe(true);
  });

  it('bounds reconnect delay and applies jitter', () => {
    expect(taskReconnectDelayMs(0, () => 0.5)).toBe(1000);
    expect(taskReconnectDelayMs(1, () => 0.5)).toBe(2000);
    expect(taskReconnectDelayMs(20, () => 0.5)).toBe(30000);
    expect(taskReconnectDelayMs(20, () => 0)).toBe(24000);
    expect(taskReconnectDelayMs(20, () => 1)).toBe(30000);
  });
});
