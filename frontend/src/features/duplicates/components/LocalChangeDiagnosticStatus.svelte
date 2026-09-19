<script lang="ts">
  import type { LocalChangeDiagnostics } from '../utils/localChangeDiagnostics';

  let {
    diagnostics,
    loading = false,
    error = '',
  }: {
    diagnostics: LocalChangeDiagnostics | null;
    loading?: boolean;
    error?: string;
  } = $props();

  function sourceLabel(source: LocalChangeDiagnostics['source']): string {
    if (source === 'original') return 'Original detail sample';
    if (source === 'transcoded') return 'Full-size conversion detail sample';
    if (source === 'preview') return 'Preview fallback detail sample';
    return 'Detail sample';
  }

  function diagnosticSummary(value: LocalChangeDiagnostics): string {
    const changed = value.changedPercent?.toFixed(2) ?? '—';
    const coherent = value.coherentChangedPercent?.toFixed(2) ?? '—';
    const largest = value.largestChangedRegionPercent?.toFixed(2) ?? '—';
    const regions = value.substantialRegionCount ?? '—';
    return `Changed ${changed}% · coherent ${coherent}% · largest region ${largest}% · ${regions} regions`;
  }
</script>

{#if loading}
  <div class="local-change-status" role="status">Calculating localized changes…</div>
{:else if error}
  <div class="local-change-status" role="alert">{error}</div>
{:else if diagnostics?.available}
  <div class="local-change-note">
    {diagnosticSummary(diagnostics)} · {sourceLabel(diagnostics.source)} · validator evidence
  </div>
{:else}
  <div class="local-change-status">Localized detail evidence is unavailable for this pair.</div>
{/if}

<style>
  .local-change-note,
  .local-change-status {
    position:absolute;
    left:50%;
    bottom:14px;
    z-index:8;
    transform:translateX(-50%);
    max-width:calc(100% - 24px);
    border:1px solid #385467;
    border-radius:999px;
    padding:6px 10px;
    background:rgba(0,0,0,.84);
    color:#e8f8ff;
    font-size:11px;
    text-align:center;
    pointer-events:none;
  }
</style>
