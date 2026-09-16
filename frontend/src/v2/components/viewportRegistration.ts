import { untrack } from 'svelte';

export type ViewportRegistrationCallback = (node: HTMLElement | null) => void;
export type ResizeObserverFactory = (callback: ResizeObserverCallback) => ResizeObserver;

function browserResizeObserver(callback: ResizeObserverCallback): ResizeObserver {
  return new ResizeObserver(callback);
}

/**
 * Own the lifecycle boundary between comparison-mode DOM nodes and the reactive camera.
 *
 * Comparison modes report their viewport only from component mount/unmount lifecycle.
 * Camera registration is additionally executed inside untrack() so future callers cannot
 * accidentally make camera reads performed by the callback dependencies of a reactive
 * caller. Repeated reports of the same node are ignored, and resize observation is replaced
 * atomically with the node so mode changes cannot leave stale observers attached.
 */
export class ViewportRegistrationController {
  #node: HTMLElement | null = null;
  #observer: ResizeObserver | null = null;

  constructor(
    private readonly applyViewport: ViewportRegistrationCallback,
    private readonly remapViewport: () => void,
    private readonly createResizeObserver: ResizeObserverFactory | null =
      typeof ResizeObserver === 'undefined' ? null : browserResizeObserver,
  ) {}

  set(node: HTMLElement | null): void {
    if (node === this.#node) return;

    untrack(() => {
      this.#observer?.disconnect();
      this.#observer = null;
      this.#node = node;
      this.applyViewport(node);

      if (!node || !this.createResizeObserver) return;
      this.#observer = this.createResizeObserver(() => this.remapViewport());
      this.#observer.observe(node);
    });
  }

  destroy(): void {
    this.set(null);
  }
}
