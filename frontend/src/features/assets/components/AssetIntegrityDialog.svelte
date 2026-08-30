<script lang="ts">
  import Dialog from '../../../lib/components/ui/Dialog.svelte';
  import Icon from '../../../lib/components/ui/Icon.svelte';
  import { formatAssetBytes, formatAssetDate } from '../state/assetViewModel';
  import type { AssetIntegrityReport, AssetTaskStatus } from '../types/assets';

  interface Props {
    filename: string;
    report: AssetIntegrityReport | null;
    task: AssetTaskStatus | null;
    error: string | null;
    onreanalyze: () => void;
    onclose: () => void;
  }

  let { filename, report, task, error, onreanalyze, onclose }: Props = $props();
  const running = $derived(
    task !== null && !['completed', 'failed', 'cancelled'].includes(task.status),
  );
  const completedBytes = $derived(task?.progress.completed ?? task?.counters.bytes_processed ?? 0);
  const totalBytes = $derived(task?.progress.total ?? null);
  const percent = $derived(task?.progress.percent ?? null);
  const progressWidth = $derived(`${Math.max(0, Math.min(100, percent ?? 0))}%`);
  const classificationLabel = $derived(({
    healthy: 'Healthy file structure',
    warning: 'Integrity warning',
    malformed: 'Malformed file structure',
    hash_only: 'Hashes calculated',
  } as const)[report?.classification ?? 'hash_only']);

  const issueLabels: Record<string, string> = {
    jpeg_missing_soi: 'The JPEG start marker is missing.',
    jpeg_missing_eoi: 'The JPEG end marker is missing.',
    jpeg_invalid_segment_length: 'A JPEG segment has an invalid length.',
    jpeg_truncated_segment: 'A JPEG segment ends before its declared length.',
    jpeg_invalid_marker: 'The JPEG contains an invalid marker.',
    jpeg_unexpected_soi: 'The JPEG contains an unexpected second start marker.',
    jpeg_unexpected_data_between_markers: 'Unexpected bytes occur between JPEG segments.',
    immich_checksum_mismatch: 'The calculated SHA-1 does not match Immich\'s checksum.',
    mime_format_mismatch: 'The detected file format does not match Immich\'s MIME type.',
  };

  const formatLabels = {
    jpeg: 'JPEG',
    heic: 'HEIC',
    heif: 'HEIF',
    avif: 'AVIF',
    png: 'PNG',
    webp: 'WebP',
    gif: 'GIF',
    tiff: 'TIFF',
    unknown: 'Unknown / hash only',
  } as const;
</script>

<Dialog
  title="File integrity"
  description={filename}
  size="small"
  closeOnBackdrop={true}
  closeOnEscape={true}
  {onclose}
>
  <div class="integrity-summary" class:negative={report?.classification === 'malformed' || error}>
    <span class="summary-icon"><Icon name="integrity" size="1.35rem" /></span>
    <div class="summary-copy" aria-live="polite">
      {#if running}
        <strong>{task?.status === 'retrying' ? 'Retrying integrity analysis…' : 'Analyzing original file…'}</strong>
        <p>{task?.progress.detail ?? 'Waiting for the integrity worker…'}</p>
      {:else if error}
        <strong>Integrity analysis failed</strong>
        <p role="alert">{error}</p>
      {:else if report}
        <strong>{classificationLabel}</strong>
        <p>The latest successful report is saved for duplicate analysis.</p>
      {:else}
        <strong>Preparing integrity analysis…</strong>
        <p>Connecting to the integrity worker.</p>
      {/if}
    </div>
  </div>

  {#if running}
    <div class="progress-copy">
      <span>{formatAssetBytes(completedBytes) ?? '0 B'} processed</span>
      {#if totalBytes !== null}<span>of {formatAssetBytes(totalBytes)}</span>{/if}
      {#if percent !== null}<span>{percent.toFixed(0)}%</span>{/if}
    </div>
    <div
      class="progress-track"
      role="progressbar"
      aria-label="File integrity analysis progress"
      aria-valuemin="0"
      aria-valuemax="100"
      aria-valuenow={percent ?? undefined}
    >
      <span class:indeterminate={percent === null} class="progress-fill" style:width={percent !== null ? progressWidth : undefined}></span>
    </div>
  {:else if report}
    <dl>
      <div><dt>Size</dt><dd>{formatAssetBytes(report.byte_size)}</dd></div>
      <div><dt>Detected format</dt><dd>{formatLabels[report.detected_format]}</dd></div>
      {#if report.format_matches_declared !== null}
        <div><dt>Declared format</dt><dd>{report.format_matches_declared ? 'Matches content' : 'Does not match content'}</dd></div>
      {/if}
      {#if report.structurally_valid !== null}
        <div><dt>JPEG structure</dt><dd>{report.structurally_valid ? 'Valid' : 'Malformed'}</dd></div>
      {/if}
      <div>
        <dt>Full decode</dt>
        <dd>
          {#if !report.decode_supported}
            Not supported by this analyzer
          {:else if report.decode_valid === null}
            Not attempted
          {:else}
            {report.decode_valid ? 'Successful' : 'Failed'}
          {/if}
        </dd>
      </div>
      {#if report.jpeg_eoi_offset !== null}
        <div><dt>JPEG end offset</dt><dd>{report.jpeg_eoi_offset.toLocaleString()} bytes</dd></div>
      {/if}
      <div><dt>Trailing bytes</dt><dd>{report.trailing_byte_count.toLocaleString()}</dd></div>
      {#if report.immich_checksum_match !== null}
        <div><dt>Immich checksum</dt><dd>{report.immich_checksum_match ? 'Matches' : 'Mismatch'}</dd></div>
      {/if}
      <div class="hash"><dt>SHA-1</dt><dd><code>{report.sha1_hex}</code></dd></div>
      <div class="hash"><dt>SHA-256</dt><dd><code>{report.sha256_hex}</code></dd></div>
      <div><dt>Analyzed</dt><dd>{formatAssetDate(report.analyzed_at)}</dd></div>
    </dl>
    {#if report.issues.length}
      <ul aria-label="Integrity findings">
        {#each report.issues as issue (issue)}
          <li>{issueLabels[issue] ?? issue}</li>
        {/each}
      </ul>
    {/if}
  {/if}

  {#snippet footer()}
    <div class="dialog-actions">
      <button type="button" onclick={onclose}>Close</button>
      {#if !running}
        <button type="button" class="reanalyze" onclick={onreanalyze}>
          {error ? 'Retry' : 'Re-analyze'}
        </button>
      {/if}
    </div>
  {/snippet}
</Dialog>

<style>
  .integrity-summary {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 0.8rem;
    align-items: start;
  }

  .summary-icon {
    display: grid;
    width: 2.6rem;
    height: 2.6rem;
    place-items: center;
    border-radius: 999px;
    color: var(--color-accent-strong);
    background: var(--color-surface-soft);
  }

  .negative .summary-icon { color: var(--color-negative-ink); }
  .summary-copy { display: grid; gap: 0.2rem; }
  strong, p { margin: 0; }
  strong { font-size: 0.82rem; }
  p { color: var(--color-ink-muted); font-size: 0.72rem; line-height: 1.45; }

  .progress-copy {
    display: flex;
    justify-content: space-between;
    gap: 0.5rem;
    margin-top: 1rem;
    color: var(--color-ink-muted);
    font-size: 0.68rem;
  }

  .progress-track {
    height: 0.34rem;
    margin-top: 0.4rem;
    overflow: hidden;
    border-radius: 999px;
    background: color-mix(in srgb, var(--color-ink-muted) 18%, transparent);
  }

  .progress-fill {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: var(--color-accent-strong);
    transition: width 180ms ease;
  }

  .progress-fill.indeterminate {
    width: 38%;
    animation: integrity-progress 1.1s linear infinite;
  }

  dl { display: grid; gap: 0.5rem; margin: 1rem 0 0; }
  dl div { display: grid; grid-template-columns: 8rem minmax(0, 1fr); gap: 0.7rem; }
  dt { color: var(--color-ink-muted); font-size: 0.68rem; }
  dd { min-width: 0; margin: 0; font-size: 0.72rem; }
  .hash dd { overflow-wrap: anywhere; }
  code { user-select: all; font-size: 0.66rem; }
  ul { margin: 0.9rem 0 0; padding-left: 1.2rem; color: var(--color-negative-ink); font-size: 0.7rem; }

  .dialog-actions { display: flex; width: 100%; justify-content: flex-end; gap: 0.55rem; }
  button {
    min-height: 2.4rem;
    padding: 0.5rem 0.8rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-ink-strong);
    background: var(--color-canvas);
    cursor: pointer;
    font: inherit;
    font-size: 0.72rem;
    font-weight: 780;
  }
  .reanalyze { border-color: var(--color-accent-strong); color: var(--color-accent-strong); }

  @keyframes integrity-progress {
    from { transform: translateX(-100%); }
    to { transform: translateX(270%); }
  }
</style>
