import { afterEach, describe, expect, it, vi } from 'vitest';

import { TaskUpdateConnection, type TaskUpdateSocket } from './taskUpdateConnection';

class FakeSocket implements TaskUpdateSocket {
  readyState = 0;
  private readonly listeners = new Map<string, Array<() => void>>();
  close = vi.fn(() => { this.readyState = 3; });

  addEventListener(type: 'open', listener: () => void): void {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }

  emitOpen(): void {
    this.readyState = 1;
    for (const listener of this.listeners.get('open') ?? []) listener();
  }
}

afterEach(() => vi.useRealTimers());

describe('task update connection', () => {
  it('keeps one stream, reconnects with bounded backoff, and resets after a successful connection', () => {
    vi.useFakeTimers();
    const sockets: FakeSocket[] = [];
    let close: (() => void) | undefined;
    const connection = new TaskUpdateConnection((_status, onclose) => {
      close = onclose;
      const socket = new FakeSocket();
      sockets.push(socket);
      return socket;
    }, vi.fn());

    connection.start();
    connection.start();
    expect(sockets).toHaveLength(1);

    close?.();
    vi.advanceTimersByTime(999);
    expect(sockets).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(sockets).toHaveLength(2);

    close?.();
    vi.advanceTimersByTime(2000);
    expect(sockets).toHaveLength(3);
    sockets[2].emitOpen();
    close?.();
    vi.advanceTimersByTime(1000);
    expect(sockets).toHaveLength(4);
  });

  it('reports unexpected connectivity transitions without treating explicit stop as a reconnectable loss', () => {
    vi.useFakeTimers();
    const sockets: FakeSocket[] = [];
    let close: (() => void) | undefined;
    const onconnectionchange = vi.fn();
    const connection = new TaskUpdateConnection((_status, onclose) => {
      close = onclose;
      const socket = new FakeSocket();
      sockets.push(socket);
      return socket;
    }, vi.fn(), onconnectionchange);

    connection.start();
    expect(connection.connected).toBe(false);
    sockets[0].emitOpen();
    expect(connection.connected).toBe(true);
    expect(onconnectionchange).toHaveBeenLastCalledWith(true);

    close?.();
    expect(connection.connected).toBe(false);
    expect(onconnectionchange).toHaveBeenLastCalledWith(false);

    vi.advanceTimersByTime(1000);
    sockets[1].emitOpen();
    expect(connection.connected).toBe(true);
    connection.stop();
    expect(connection.connected).toBe(false);
    expect(onconnectionchange.mock.calls).toEqual([[true], [false], [true]]);
  });

  it('recovers when the stream closes synchronously while opening', () => {
    vi.useFakeTimers();
    const sockets: FakeSocket[] = [];
    const open = vi.fn((_status, onclose) => {
      const socket = new FakeSocket();
      sockets.push(socket);
      if (sockets.length === 1) onclose();
      return socket;
    });
    const connection = new TaskUpdateConnection(open, vi.fn());

    connection.start();
    expect(sockets).toHaveLength(1);
    vi.advanceTimersByTime(1000);
    expect(sockets).toHaveLength(2);
  });

  it('closes a connecting stream after a workspace reload/unmount', () => {
    vi.useFakeTimers();
    const socket = new FakeSocket();
    const onconnectionchange = vi.fn();
    const open = vi.fn((_status, _onclose) => socket);
    const connection = new TaskUpdateConnection(open, vi.fn(), onconnectionchange);

    connection.start();
    connection.stop();
    vi.advanceTimersByTime(10000);

    expect(open).toHaveBeenCalledTimes(1);
    expect(connection.connected).toBe(false);
    expect(onconnectionchange).not.toHaveBeenCalled();
    expect(socket.close).not.toHaveBeenCalled();
    socket.emitOpen();
    expect(socket.close).toHaveBeenCalledTimes(1);
    expect(connection.connected).toBe(false);
  });
});
