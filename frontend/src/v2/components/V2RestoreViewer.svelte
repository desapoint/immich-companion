<script lang="ts">
  import V2Badge from './V2Badge.svelte';
  import V2Button from './V2Button.svelte';
  import V2Card from './V2Card.svelte';
  import V2ImageViewport from './V2ImageViewport.svelte';
  import V2Inline from './V2Inline.svelte';
  import V2Section from './V2Section.svelte';
  import V2ViewerShell from './V2ViewerShell.svelte';
  import V2ZoomControl from './V2ZoomControl.svelte';
  import { ViewerViewportController } from './viewerViewport.svelte';
  import { demoCompareImage } from '../demo/duplicateVisuals';

  let { open = false, onclose }: { open?: boolean; onclose: () => void } = $props();
  const camera = new ViewerViewportController();
  const imageSrc = demoCompareImage(9, 1);

  $effect(() => {
    if (open) requestAnimationFrame(() => camera.fit());
  });
</script>

<V2ViewerShell {open} title="Restore Viewer" {onclose}>
  {#snippet header()}
    <V2Inline gap="sm"><V2Button onclick={onclose}>✕</V2Button><b>Restore Viewer</b><V2Badge text="3 / 48" /></V2Inline>
    <V2Inline gap="sm">
      <V2ZoomControl
        value={camera.zoom}
        onzoomout={() => camera.setZoom(camera.zoom / 1.25)}
        onzoomin={() => camera.setZoom(camera.zoom * 1.25)}
      />
      <V2Button onclick={() => camera.fit()} title="Fit image">Fit</V2Button>
      <V2Button onclick={() => camera.actual()} title="Actual pixel size">1:1</V2Button>
      <V2Button title="Asset information">ⓘ</V2Button>
      <V2Button title="Viewer help">?</V2Button>
    </V2Inline>
  {/snippet}

  <div class="v2-viewer-stage">
    <div class="v2-image-stage"><V2ImageViewport src={imageSrc} alt="Trashed asset preview" controller={camera} /></div>
    <aside class="v2-viewer-info">
      <V2Section title="Details"><V2Card><b>IMG_20260821_174512.jpg</b><p class="v2-small v2-muted">4032 × 3024 · JPEG · 4.8 MB</p></V2Card></V2Section>
      <V2Section title="Metadata"><V2Card><span class="v2-small">Taken Aug 21, 2026<br>Samsung device<br>External library</span></V2Card></V2Section>
      <V2Section title="Restore boundary"><V2Card><span class="v2-small">Only restore, selection and shared viewing controls are exposed.</span></V2Card></V2Section>
    </aside>
  </div>

  {#snippet footer()}
    <V2Button>← Previous</V2Button>
    <V2Inline gap="sm"><V2Button variant="primary">Restore visible</V2Button></V2Inline>
    <V2Button>Next →</V2Button>
  {/snippet}
</V2ViewerShell>
