function createSessionId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

/**
 * Gives each user-visible selection state a page-session-scoped identity.
 * Async operations capture the current token when they start and may only
 * clear the selection if that exact token is still current when they finish.
 */
export class SelectionOwnership {
  readonly #sessionId: string;
  #generation = 0;

  constructor(sessionId = createSessionId()) {
    this.#sessionId = sessionId;
  }

  current(): string {
    return `${this.#sessionId}:${this.#generation}`;
  }

  changed(): void {
    this.#generation += 1;
  }

  owns(owner: string | null | undefined): boolean {
    return owner !== null && owner !== undefined && owner === this.current();
  }
}
