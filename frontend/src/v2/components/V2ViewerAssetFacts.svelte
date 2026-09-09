<script lang="ts">
  import type { MediaDelivery } from '../data/contracts';
  import V2Card from './V2Card.svelte';
  import V2Section from './V2Section.svelte';

  let {
    filename,
    width = null,
    height = null,
    mimeType = null,
    fileSizeBytes = null,
    path = null,
    offline = false,
    takenAt,
    libraryId = null,
    delivery,
  }: {
    filename: string;
    width?: number | null;
    height?: number | null;
    mimeType?: string | null;
    fileSizeBytes?: number | null;
    path?: string | null;
    offline?: boolean;
    takenAt: string;
    libraryId?: string | null;
    delivery?: MediaDelivery;
  } = $props();

  const sizeLabel = $derived(formatFileSize(fileSizeBytes));

  function formatFileSize(bytes: number | null | undefined): string {
    if (bytes === null || bytes === undefined) return 'Unknown size';
    if (bytes < 1024) return `${bytes} B`;
    const units = ['KB', 'MB', 'GB', 'TB'];
    let value = bytes / 1024;
    let index = 0;
    while (value >= 1024 && index < units.length - 1) {
      value /= 1024;
      index += 1;
    }
    return `${value.toFixed(value >= 10 ? 1 : 2)} ${units[index]}`;
  }
</script>

<V2Section title="Details">
  <V2Card>
    <b>{filename}</b>
    <p class="v2-small v2-muted">{width ?? '—'} × {height ?? '—'} · {mimeType ?? 'Unknown type'} · {sizeLabel}</p>
    {#if path}<p class="viewer-path v2-small v2-muted" title={path}>{path}</p>{/if}
    {#if offline}<p class="v2-small v2-muted">The original source is currently offline. A cached or generated derivative may still be viewable.</p>{/if}
    {#if delivery === 'transcoded'}<p class="v2-small v2-muted">Original format is preserved in metadata; playback uses a browser-compatible derivative.</p>
    {:else if delivery === 'decoded'}<p class="v2-small v2-muted">Original format is preserved; viewing uses a decoded browser-compatible derivative.</p>{/if}
  </V2Card>
</V2Section>
<V2Section title="Metadata">
  <V2Card>
    <dl class="viewer-facts">
      <div><dt>Taken</dt><dd>{new Date(takenAt).toLocaleString()}</dd></div>
      <div><dt>Source</dt><dd>{libraryId ? `External library · ${libraryId}` : 'Immich upload'}</dd></div>
      <div><dt>File size</dt><dd>{sizeLabel}</dd></div>
    </dl>
  </V2Card>
</V2Section>

<style>
  .viewer-path{overflow-wrap:anywhere;word-break:break-word}.viewer-facts{display:grid;gap:.5rem;margin:0}.viewer-facts div{display:grid;grid-template-columns:4.5rem minmax(0,1fr);gap:.65rem}.viewer-facts dt{color:var(--v2-muted);font-size:.7rem;text-transform:uppercase;letter-spacing:.05em}.viewer-facts dd{margin:0;font-size:.75rem;overflow-wrap:anywhere}
</style>
