<script lang="ts">
  import { formatAssetDate } from '../state/assetViewModel';
  import type { AssetDetail } from '../types/assets';

  interface Props {
    detail: AssetDetail | null;
    loading: boolean;
    error: string | null;
  }

  let { detail, loading, error }: Props = $props();

  function displayValue(value: unknown): string {
    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
      return String(value);
    }
    return JSON.stringify(value);
  }
</script>

<aside class="info-panel" aria-label="Image details">
  <header>
    <span>More info</span>
    <strong>Immich metadata</strong>
  </header>

  {#if loading}
    <p role="status">Loading image details…</p>
  {:else if error}
    <p class="error" role="alert">{error}</p>
  {:else if detail}
    <dl>
      <div><dt>Immich ID</dt><dd title={detail.id}>{detail.id}</dd></div>
      <div><dt>Filename</dt><dd>{detail.original_file_name}</dd></div>
      {#if detail.original_path}<div><dt>Path</dt><dd title={detail.original_path}>{detail.original_path}</dd></div>{/if}
      {#if detail.original_mime_type}<div><dt>MIME type</dt><dd>{detail.original_mime_type}</dd></div>{/if}
      <div><dt>Taken</dt><dd>{formatAssetDate(detail.taken_at)}</dd></div>
      <div><dt>Modified</dt><dd>{formatAssetDate(detail.file_modified_at)}</dd></div>
      {#if detail.owner_id}<div><dt>Owner ID</dt><dd>{detail.owner_id}</dd></div>{/if}
      {#if detail.library_id}<div><dt>Library ID</dt><dd>{detail.library_id}</dd></div>{/if}
      {#if detail.visibility}<div><dt>Visibility</dt><dd>{detail.visibility}</dd></div>{/if}
    </dl>

    {#if detail.exif_info && Object.keys(detail.exif_info).length}
      <details open>
        <summary>EXIF information</summary>
        <dl>
          {#each Object.entries(detail.exif_info) as [key, value]}
            {#if value !== null && value !== ''}
              <div><dt>{key}</dt><dd>{displayValue(value)}</dd></div>
            {/if}
          {/each}
        </dl>
      </details>
    {/if}

    {#if detail.immich_url}
      <a href={detail.immich_url} target="_blank" rel="noopener noreferrer">Open this asset in Immich ↗</a>
    {/if}
  {:else}
    <p>No additional metadata is available.</p>
  {/if}
</aside>

<style>
  .info-panel {
    position: absolute;
    z-index: 4;
    top: 0.75rem;
    right: 0.75rem;
    width: min(26rem, calc(100% - 1.5rem));
    max-height: calc(100% - 1.5rem);
    padding: 0.9rem;
    overflow: auto;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-md);
    color: var(--color-ink-strong);
    background: color-mix(in srgb, var(--color-surface-raised) 96%, transparent);
    box-shadow: 0 1rem 3rem rgb(0 0 0 / 28%);
    backdrop-filter: blur(0.6rem);
  }

  header {
    display: grid;
    gap: 0.16rem;
    padding-bottom: 0.7rem;
    border-bottom: 1px solid var(--color-border-subtle);
  }

  header span {
    color: var(--color-accent-strong);
    font-size: 0.62rem;
    font-weight: 800;
    letter-spacing: 0.07em;
    text-transform: uppercase;
  }

  header strong {
    font-size: 0.9rem;
  }

  dl {
    display: grid;
    gap: 0.5rem;
    margin: 0.75rem 0;
  }

  dl div {
    display: grid;
    grid-template-columns: minmax(5rem, 0.38fr) minmax(0, 1fr);
    gap: 0.65rem;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid var(--color-border-subtle);
  }

  dt,
  dd,
  p,
  a,
  summary {
    font-size: 0.7rem;
  }

  dt {
    color: var(--color-ink-muted);
  }

  dd {
    min-width: 0;
    margin: 0;
    overflow-wrap: anywhere;
    font-family: var(--font-mono);
  }

  details {
    margin-top: 0.8rem;
  }

  summary {
    color: var(--color-accent-strong);
    cursor: pointer;
    font-weight: 760;
  }

  a {
    display: inline-block;
    margin-top: 0.5rem;
    color: var(--color-accent-strong);
    font-weight: 760;
    text-underline-offset: 0.2rem;
  }

  .error {
    color: var(--color-negative-ink);
  }
</style>
