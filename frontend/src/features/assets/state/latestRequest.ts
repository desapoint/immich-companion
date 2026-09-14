export type LatestRequestResult<T> =
  | { status: 'success'; value: T; version: number }
  | { status: 'error'; error: unknown; version: number }
  | { status: 'aborted'; version: number };

export function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === 'AbortError';
}

export function requestErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message.trim() ? error.message : fallback;
}

/**
 * Owns a single replaceable AbortController. Starting new work aborts the
 * previous request, stale completions are reported as aborted, and completed
 * controllers are released immediately.
 */
export class LatestRequest {
  #controller: AbortController | null = null;
  #version = 0;

  get active(): boolean {
    return this.#controller !== null;
  }

  isCurrent(version: number): boolean {
    return version === this.#version;
  }

  abort(): void {
    this.#version += 1;
    this.#controller?.abort();
    this.#controller = null;
  }

  async run<T>(load: (signal: AbortSignal) => Promise<T>): Promise<LatestRequestResult<T>> {
    this.#controller?.abort();
    const controller = new AbortController();
    const version = ++this.#version;
    this.#controller = controller;

    try {
      const value = await load(controller.signal);
      if (!this.isCurrent(version) || controller.signal.aborted) {
        return { status: 'aborted', version };
      }
      return { status: 'success', value, version };
    } catch (error) {
      if (!this.isCurrent(version) || controller.signal.aborted || isAbortError(error)) {
        return { status: 'aborted', version };
      }
      return { status: 'error', error, version };
    } finally {
      if (this.#controller === controller) this.#controller = null;
    }
  }
}
