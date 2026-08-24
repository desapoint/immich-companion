import type { Action } from 'svelte/action';

interface ClickOutsideParameters {
  enabled?: boolean;
  onoutside: (event: PointerEvent) => void;
}

export const clickOutside: Action<HTMLElement, ClickOutsideParameters> = (node, initial) => {
  let parameters = initial;

  function handlePointerDown(event: PointerEvent): void {
    if (
      parameters.enabled !== false
      && event.target instanceof Node
      && !node.contains(event.target)
    ) parameters.onoutside(event);
  }

  document.addEventListener('pointerdown', handlePointerDown);

  return {
    update(next) {
      parameters = next;
    },
    destroy() {
      document.removeEventListener('pointerdown', handlePointerDown);
    },
  };
};
