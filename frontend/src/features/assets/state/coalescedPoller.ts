export type PollTask = (signal: AbortSignal) => Promise<void>;
export type PollDelay = () => number;

/**
 * Runs one poll request at a time and schedules the next run only after the
 * current request settles. This avoids overlapping requests when both timers
 * and push events ask for a refresh.
 */
export class CoalescedPoller {
  #timer: ReturnType<typeof setTimeout> | null = null;
  #request: Promise<void> | null = null;
  #controller: AbortController | null = null;
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
    if (
      !this.#running
      && this.#timer === null
      && this.#request === null
      && this.#controller === null
    ) return;
    this.#running = false;
    this.#generation += 1;
    this.#clearTimer();
    this.#controller?.abort();
    this.#controller = null;
    // Detach stale work immediately so a later start can issue a fresh poll.
    // The aborted request may settle afterward, but its generation can no
    // longer schedule another run.
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
      try {
        await activeRequest;
      } catch (error) {
        if (!this.#running || generation !== this.#generation) return;
        throw error;
      }
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
        try {
          await followUp;
        } catch (error) {
          if (!this.#running || generation !== this.#generation) return;
          throw error;
        }
        return;
      }
    }

    this.#clearTimer();
    const controller = new AbortController();
    this.#controller = controller;
    const request = this.task(controller.signal);
    this.#request = request;
    try {
      await request;
    } catch (error) {
      if (controller.signal.aborted) return;
      throw error;
    } finally {
      if (this.#request !== request) return;
      this.#request = null;
      if (this.#controller === controller) this.#controller = null;
      if (this.#running && generation === this.#generation) this.reschedule();
    }
  }

  #clearTimer(): void {
    if (this.#timer === null) return;
    clearTimeout(this.#timer);
    this.#timer = null;
  }
}
