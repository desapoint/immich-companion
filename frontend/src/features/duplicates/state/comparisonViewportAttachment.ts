import { untrack } from 'svelte';

export type ViewportRegistration = (node: HTMLElement | null) => void;

/**
 * Register a comparison viewport for the lifetime of its DOM node.
 *
 * Attachments are the lifecycle boundary here: registration happens after the
 * node exists, and cleanup always clears the callback and resize observer.
 */
export function createViewportAttachment(
  register: ViewportRegistration,
  onresize?: () => void,
  cleanup?: () => void,
): (node: HTMLElement) => void | (() => void) {
  return (node) => {
    // Attachments run in a reactive effect. Registration and initial measurement
    // may read or update component state, but neither should become a dependency
    // of the attachment itself or it can repeatedly detach and reattach.
    untrack(() => register(node));

    const observer = onresize && typeof ResizeObserver !== 'undefined'
      ? new ResizeObserver(onresize)
      : null;
    observer?.observe(node);
    if (onresize) untrack(onresize);

    return () => {
      observer?.disconnect();
      cleanup?.();
      untrack(() => register(null));
    };
  };
}
