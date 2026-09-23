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
    register(node);

    const observer = onresize && typeof ResizeObserver !== 'undefined'
      ? new ResizeObserver(onresize)
      : null;
    observer?.observe(node);
    onresize?.();

    return () => {
      observer?.disconnect();
      cleanup?.();
      register(null);
    };
  };
}
