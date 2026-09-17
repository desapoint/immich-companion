import { untrack } from 'svelte';

export type ViewportRegistrationCallback = (node: HTMLElement | null) => void;
export type ResizeObserverFactory = (callback: ResizeObserverCallback) => ResizeObserver;

function browserResizeObserver(callback: ResizeObserverCallback): ResizeObserver {
  return new ResizeObserver(callback);
}

/**
 * Own the lifecycle boundary between viewer DOM nodes and the reactive camera.
 *
 * Viewer surfaces should report their viewport from mount/unmount or action lifecycle,
 * not by calling reactive camera methods directly from a $effect. Svelte tracks reactive
 * reads performed by synchronous callees, so a camera method invoked from an effect can
 * accidentally make camera $state a dependency of that effect and invalidate the same
 * effect while it is registering. That feedback loop can end in
 * effect_update_depth_exceeded.
 *
 * Registration is additionally executed inside untrack() so callers remain safe even when
 * they originate from a reactive context. Repeated reports of the same node are ignored,
 * and resize observation is replaced atomically with the node so mode or viewer changes
 * cannot leave stale observers attached.
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
