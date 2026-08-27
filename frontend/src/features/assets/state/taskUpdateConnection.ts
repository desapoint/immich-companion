import type { AssetTaskStatus } from '../types/assets';

export interface TaskUpdateSocket {
  readyState: number;
  close(): void;
  addEventListener(type: 'open', listener: () => void, options?: { once?: boolean }): void;
}

export type OpenTaskUpdates = (
  onstatus: (task: AssetTaskStatus) => void,
  onclose: () => void,
) => TaskUpdateSocket;

const CONNECTING = 0;
const OPEN = 1;

/** Keeps the global task stream to one socket and reconnects it with a bounded backoff. */
export class TaskUpdateConnection {
  #socket: TaskUpdateSocket | null = null;
  #timer: ReturnType<typeof setTimeout> | null = null;
  #delay = 1000;
  #stopped = true;

  constructor(
    private readonly open: OpenTaskUpdates,
    private readonly onstatus: (task: AssetTaskStatus) => void,
  ) {}

  start(): void {
    this.#stopped = false;
    this.#connect();
  }

  stop(): void {
    this.#stopped = true;
    if (this.#timer !== null) {
      clearTimeout(this.#timer);
      this.#timer = null;
    }
    const socket = this.#socket;
    this.#socket = null;
    if (!socket) return;
    if (socket.readyState === CONNECTING) {
      socket.addEventListener('open', () => socket.close(), { once: true });
    } else {
      socket.close();
    }
  }

  #connect(): void {
    if (this.#stopped || this.#socket?.readyState === OPEN || this.#socket?.readyState === CONNECTING) return;
    this.#socket = this.open(this.onstatus, () => this.#scheduleReconnect());
    this.#socket.addEventListener('open', () => { this.#delay = 1000; }, { once: true });
  }

  #scheduleReconnect(): void {
    this.#socket = null;
    if (this.#stopped || this.#timer !== null) return;
    const delay = this.#delay;
    this.#timer = setTimeout(() => {
      this.#timer = null;
      this.#connect();
      this.#delay = Math.min(delay * 2, 10000);
    }, delay);
  }
}
