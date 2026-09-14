interface RevisionedResult {
  revision: number;
}

interface PendingMutation<T extends RevisionedResult> {
  requestedRevision: number;
  sequence: number;
  run: (revision: number) => Promise<T>;
  resolve: (value: T) => void;
  reject: (reason: unknown) => void;
}

interface MutationQueueState<T extends RevisionedResult> {
  knownRevision: number | null;
  pending: PendingMutation<T>[];
  draining: boolean;
}

/**
 * Serializes optimistic, revisioned mutations per resource id.
 *
 * Callers may enqueue a follow-up mutation after awaiting the first result.
 * The queue yields one microtask after each completion and prioritizes the
 * highest requested revision, so that causal follow-ups run before older
 * operations that were queued concurrently with the same stale revision.
 * The backend remains the source of truth for revision conflicts caused by
 * other clients or processes.
 */
export class RevisionedMutationQueue<T extends RevisionedResult> {
  readonly #states = new Map<string, MutationQueueState<T>>();
  #sequence = 0;

  enqueue(
    resourceId: string,
    requestedRevision: number,
    run: (revision: number) => Promise<T>,
  ): Promise<T> {
    let state = this.#states.get(resourceId);
    if (!state) {
      state = { knownRevision: requestedRevision, pending: [], draining: false };
      this.#states.set(resourceId, state);
    } else if (state.knownRevision === null || requestedRevision > state.knownRevision) {
      state.knownRevision = requestedRevision;
    }

    const promise = new Promise<T>((resolve, reject) => {
      state!.pending.push({
        requestedRevision,
        sequence: this.#sequence++,
        run,
        resolve,
        reject,
      });
    });

    if (!state.draining) void this.#drain(resourceId, state);
    return promise;
  }

  clear(resourceId?: string): void {
    if (resourceId === undefined) {
      this.#states.clear();
      return;
    }
    this.#states.delete(resourceId);
  }

  async #drain(resourceId: string, state: MutationQueueState<T>): Promise<void> {
    if (state.draining) return;
    state.draining = true;
    try {
      while (state.pending.length > 0) {
        state.pending.sort((left, right) => (
          right.requestedRevision - left.requestedRevision
          || left.sequence - right.sequence
        ));
        const next = state.pending.shift();
        if (!next) continue;
        const revision = Math.max(state.knownRevision ?? next.requestedRevision, next.requestedRevision);
        try {
          const result = await next.run(revision);
          state.knownRevision = Math.max(state.knownRevision ?? result.revision, result.revision);
          next.resolve(result);
        } catch (error) {
          next.reject(error);
          for (const pending of state.pending.splice(0)) pending.reject(error);
          state.knownRevision = null;
          return;
        }

        // Let an awaiting caller enqueue its causal continuation before an
        // older concurrent mutation with the previous revision is selected.
        await Promise.resolve();
      }
    } finally {
      state.draining = false;
      if (state.pending.length === 0 && this.#states.get(resourceId) === state) {
        this.#states.delete(resourceId);
      } else if (state.pending.length > 0) {
        void this.#drain(resourceId, state);
      }
    }
  }
}
