<script lang="ts">
  import { ViewerViewportController } from './viewerViewport.svelte';

  let {
    src,
    alt,
    controller = new ViewerViewportController(),
  }: {
    src: string;
    alt: string;
    controller?: ViewerViewportController;
  } = $props();

  let viewport = $state<HTMLElement | null>(null);
  let dragging = $state(false);
  let dragPointer = $state<number | null>(null);
  let lastX = $state(0);
  let lastY = $state(0);

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

  function keyboardZoom(event: KeyboardEvent): void {
    const target = event.target;
    if (target instanceof HTMLElement && (target.isContentEditable || !!target.closest('input,textarea,select'))) return;
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.key === '+' || event.key === '=') {
      event.preventDefault();
      controller.zoomFromCenter(1.25);
    } else if (event.key === '-' || event.key === '_') {
      event.preventDefault();
      controller.zoomFromCenter(1 / 1.25);
    }
  }

  function imageLoaded(event: Event): void {
    const image = event.currentTarget as HTMLImageElement;
    controller.setNaturalSize(image.naturalWidth, image.naturalHeight);
    requestAnimationFrame(() => controller.fit());
  }

  $effect(() => {
    controller.setViewport(viewport);
    return () => controller.setViewport(null);
  });
</script>

<svelte:window onkeydown={keyboardZoom} />

<div
  bind:this={viewport}
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
    <img {src} {alt} draggable="false" onload={imageLoaded}>
  </div>
</div>
