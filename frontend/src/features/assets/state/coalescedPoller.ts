export type PollTask = () => Promise<void>;
export type PollDelay = () => number;

/**
 * Runs one poll request at a time and schedules the next run only after the
 * current request settles. This avoids overlapping requests when both timers
 * and push events ask for a refresh.
 */
export class CoalescedPoller {
  #timer: ReturnType<typeof setTimeout> | null = null;
  #request: Promise<void> | null = null;
  #generation = 0;
  #running = false;

  constructor(
    private readonly task: PollTask,
    private readonly delay: PollDelay,
  ) {}

  start(immediate = true): void {
    if (this.#running) return;
    this.#running = true;
    this.#generation += 1;
    if (immediate) void this.refresh();
    else this.reschedule();
  }

  stop(): void {
    if (!this.#running && this.#timer === null && this.#request === null) return;
    this.#running = false;
    this.#generation += 1;
    this.#clearTimer();
    // An in-flight promise cannot be cancelled generically. Detach it so a
    // future start does not wait for stale work and its completion cannot
    // schedule another poll for the stopped generation.
    this.#request = null;
  }

  reschedule(delay = this.delay()): void {
    if (!this.#running) return;
    this.#clearTimer();
    const generation = this.#generation;
    this.#timer = setTimeout(() => {
      this.#timer = null;
      if (!this.#running || generation !== this.#generation) return;
      void this.refresh();
    }, Math.max(0, delay));
  }

  async refresh(forceAfterCurrent = false): Promise<void> {
    if (!this.#running) return;
    const generation = this.#generation;
    const activeRequest = this.#request;
    if (activeRequest) {
      await activeRequest;
      if (
        !forceAfterCurrent
        || !this.#running
        || generation !== this.#generation
      ) return;

      // Another forced caller may already have started the shared follow-up
      // while this caller was waiting for the first request. Reuse it instead
      // of creating a second concurrent poll.
      const followUp = this.#request;
      if (followUp) {
        await followUp;
        return;
      }
    }

    this.#clearTimer();
    const request = this.task();
    this.#request = request;
    try {
      await request;
    } finally {
      if (this.#request !== request) return;
      this.#request = null;
      if (this.#running && generation === this.#generation) this.reschedule();
    }
  }

  #clearTimer(): void {
    if (this.#timer === null) return;
    clearTimeout(this.#timer);
    this.#timer = null;
  }
}
