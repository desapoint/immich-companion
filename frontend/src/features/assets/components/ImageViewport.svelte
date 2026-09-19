<script lang="ts">
  import { ViewerViewportController } from '../state/viewportController.svelte';
  import { ViewportRegistrationController } from '../state/viewportRegistration';

  let {
    src,
    alt,
    controller = new ViewerViewportController(),
    onerror,
  }: {
    src: string;
    alt: string;
    controller?: ViewerViewportController;
    onerror?: () => void;
  } = $props();

  let dragging = $state(false);
  let dragPointer = $state<number | null>(null);
  let lastX = $state(0);
  let lastY = $state(0);

  function createViewportRegistration(activeController: ViewerViewportController): ViewportRegistrationController {
    return new ViewportRegistrationController(
      (node) => activeController.setViewport(node),
      () => activeController.remapViewport(),
    );
  }

  // Keep DOM registration lifecycle-owned. Calling ViewerViewportController.setViewport()
  // directly from a $effect can subscribe that effect to camera $state read inside the
  // method, then invalidate the same effect while it registers and recurse until Svelte
  // throws effect_update_depth_exceeded.
  function registerViewport(node: HTMLElement, initialController: ViewerViewportController) {
    let activeController = initialController;
    let registration = createViewportRegistration(activeController);
    registration.set(node);

    return {
      update(nextController: ViewerViewportController) {
        if (nextController === activeController) return;
        registration.destroy();
        activeController = nextController;
        registration = createViewportRegistration(activeController);
        registration.set(node);
      },
      destroy() {
        registration.destroy();
      },
    };
  }

  function pointerDown(event: PointerEvent): void {
    if (event.button !== 0) return;
    event.preventDefault();
    dragging = true;
    dragPointer = event.pointerId;
    lastX = event.clientX;
    lastY = event.clientY;
    (event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId);
  }

  function pointerMove(event: PointerEvent): void {
    if (!dragging || dragPointer !== event.pointerId) return;
    event.preventDefault();
    controller.panBy(event.clientX - lastX, event.clientY - lastY);
    lastX = event.clientX;
    lastY = event.clientY;
  }

  function pointerEnd(event: PointerEvent): void {
    if (!dragging || dragPointer !== event.pointerId) return;
    dragging = false;
    dragPointer = null;
    try { (event.currentTarget as HTMLElement).releasePointerCapture?.(event.pointerId); } catch {}
  }

  function wheel(event: WheelEvent): void {
    event.preventDefault();
    controller.wheel(event);
  }

  function imageLoaded(event: Event): void {
    const image = event.currentTarget as HTMLImageElement;
    controller.setNaturalSize(image.naturalWidth, image.naturalHeight);
    requestAnimationFrame(() => controller.fit());
  }
</script>

<div
  use:registerViewport={controller}
  class="v2-image-viewport"
  class:panning={dragging}
  role="region"
  aria-label="Image viewport"
  onpointerdown={pointerDown}
  onpointermove={pointerMove}
  onpointerup={pointerEnd}
  onpointercancel={pointerEnd}
  onwheel={wheel}
>
  <div class="v2-image-viewport-transform" style={`transform:${controller.transform}`}>
    <img {src} {alt} draggable="false" onload={imageLoaded} onerror={onerror}>
  </div>
</div>
