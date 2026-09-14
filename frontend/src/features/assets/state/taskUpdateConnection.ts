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
  #connected = false;

  constructor(
    private readonly open: OpenTaskUpdates,
    private readonly onstatus: (task: AssetTaskStatus) => void,
    private readonly onconnectionchange?: (connected: boolean) => void,
  ) {}

  get connected(): boolean {
    return this.#connected;
  }

  start(): void {
    if (!this.#stopped) return;
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
    // Explicit teardown is owned by the caller and must not look like a
    // recoverable connection loss; otherwise consumers may restart fallback
    // polling while they are unmounting.
    this.#connected = false;
    if (!socket) return;
    if (socket.readyState === CONNECTING) {
      socket.addEventListener('open', () => socket.close(), { once: true });
    } else {
      socket.close();
    }
  }

  #connect(): void {
    if (
      this.#stopped
      || this.#socket?.readyState === OPEN
      || this.#socket?.readyState === CONNECTING
    ) return;

    let socket: TaskUpdateSocket | null = null;
    let closedBeforeAssignment = false;
    socket = this.open(this.onstatus, () => {
      if (socket) this.#scheduleReconnect(socket);
      else closedBeforeAssignment = true;
    });
    this.#socket = socket;
    socket.addEventListener('open', () => {
      if (this.#stopped || this.#socket !== socket) return;
      this.#delay = 1000;
      this.#setConnected(true);
    }, { once: true });
    if (closedBeforeAssignment) this.#scheduleReconnect(socket);
  }

  #scheduleReconnect(socket: TaskUpdateSocket): void {
    if (this.#socket !== socket) return;
    this.#socket = null;
    this.#setConnected(false);
    if (this.#stopped || this.#timer !== null) return;
    const delay = this.#delay;
    this.#timer = setTimeout(() => {
      this.#timer = null;
      this.#connect();
      this.#delay = Math.min(delay * 2, 10000);
    }, delay);
  }

  #setConnected(connected: boolean): void {
    if (this.#connected === connected) return;
    this.#connected = connected;
    this.onconnectionchange?.(connected);
  }
}
