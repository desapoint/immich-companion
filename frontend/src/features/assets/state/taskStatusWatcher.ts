import type { AssetTaskStatus } from '../types/assets';
import { CoalescedPoller } from './coalescedPoller';
import { isAbortError } from './latestRequest';

export interface TaskStatusSocket {
  close(): void;
}

export type OpenTaskStatusStream = (
  taskId: string,
  onstatus: (task: AssetTaskStatus) => void,
  onerror: () => void,
  onclose: () => void,
) => TaskStatusSocket;

export type LoadTaskStatus = (
  taskId: string,
  signal: AbortSignal,
) => Promise<AssetTaskStatus>;

/**
 * Watches one task with push-first delivery and a single abortable fallback
 * poll request at a time. Socket errors and closes converge on the same
 * polling path; stop() tears both transports down.
 */
export class TaskStatusWatcher {
  #taskId: string | null = null;
  #socket: TaskStatusSocket | null = null;
  #poller: CoalescedPoller | null = null;

  constructor(
    private readonly open: OpenTaskStatusStream,
    private readonly load: LoadTaskStatus,
    private readonly onstatus: (task: AssetTaskStatus) => void,
    private readonly onerror: (error: unknown) => void,
    private readonly pollDelayMs = 1000,
  ) {}

  start(taskId: string): void {
    this.stop();
    this.#taskId = taskId;
    this.#poller = new CoalescedPoller(
      (signal) => this.#poll(taskId, signal),
      () => this.pollDelayMs,
    );
    this.#socket = this.open(
      taskId,
      (task) => {
        if (this.#taskId === taskId) this.onstatus(task);
      },
      () => this.#switchToPolling(taskId),
      () => this.#switchToPolling(taskId),
    );
  }

  stop(): void {
    this.#taskId = null;
    const socket = this.#socket;
    this.#socket = null;
    socket?.close();
    this.#poller?.stop();
    this.#poller = null;
  }

  #switchToPolling(taskId: string): void {
    if (this.#taskId !== taskId) return;
    const socket = this.#socket;
    this.#socket = null;
    socket?.close();
    this.#poller?.start();
  }

  async #poll(taskId: string, signal: AbortSignal): Promise<void> {
    try {
      const task = await this.load(taskId, signal);
      if (!signal.aborted && this.#taskId === taskId) this.onstatus(task);
    } catch (error) {
      if (signal.aborted || isAbortError(error) || this.#taskId !== taskId) return;
      this.onerror(error);
    }
  }
}
