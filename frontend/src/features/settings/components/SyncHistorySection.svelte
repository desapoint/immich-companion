<script lang="ts">
  import { onMount } from 'svelte';
  import { libraryData } from '../../../app/data/currentDataSource.svelte';
  import V2Stack from '../../../lib/components/layout/Stack.svelte';
  import V2Badge from '../../../lib/components/ui/Badge.svelte';
  import V2Button from '../../../lib/components/ui/Button.svelte';
  import V2Card from '../../../lib/components/ui/Card.svelte';
  import LoadingSpinner from '../../../lib/components/ui/LoadingSpinner.svelte';
  import V2Notice from '../../../lib/components/ui/Notice.svelte';
  import V2Segmented from '../../../lib/components/ui/Segmented.svelte';
  import type { SyncHistoryFilter, SyncHistoryItem, SyncRuntimeSettings } from '../../status/types/syncContracts';

  const PAGE_SIZE = 25;
  let history = $state.raw<SyncHistoryItem[]>([]);
  let filter = $state<SyncHistoryFilter>('all');
  let total = $state(0);
  let loading = $state(true);
  let loadingMore = $state(false);
  let error = $state<string | null>(null);
  let active = true;
  const hasMore = $derived(history.length < total);

  function formatDuration(seconds: number | null): string {
    if (seconds == null) return '—';
    if (seconds < 1) return `${Math.round(seconds * 1000)} ms`;
    if (seconds < 60) return `${seconds.toFixed(seconds < 10 ? 2 : 1)} s`;
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const remainder = Math.round(seconds % 60);
    return hours ? `${hours}h ${minutes}m ${remainder}s` : `${minutes}m ${remainder}s`;
  }

  function formatDate(value: string | null): string {
    return value ? new Date(value).toLocaleString() : 'Not finished';
  }

  function formatNumber(value: number | null): string {
    return value == null ? '—' : value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }

  function label(value: string): string {
    return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  function statusTone(status: string): 'default' | 'ok' | 'warn' | 'bad' {
    if (status === 'completed') return 'ok';
    if (status === 'failed') return 'bad';
    if (status === 'cancelled' || status === 'retrying') return 'warn';
    return 'default';
  }

  function settingsRows(settings: SyncRuntimeSettings): Array<[string, string]> {
    return [
      ['Persistence batch size', settings.fullBatchSize.toLocaleString()],
      ['Minimum global batch duration', `${settings.fullMinBatchDelaySeconds} s`],
      ['Relationship concurrency', settings.tagAssociationConcurrency.toString()],
      ['Metadata request concurrency', settings.metadataRequestConcurrency.toString()],
      ['Pages prefetched', settings.pagePrefetch.toString()],
      ['Immich API page size', settings.apiPageSize.toLocaleString()],
      ['Incremental overlap', `${settings.incrementalOverlapSeconds} s`],
      ['Incremental strategy', label(settings.incrementalStrategy)],
      ['Adaptive throttling', settings.adaptiveThrottling ? 'Enabled' : 'Disabled'],
    ];
  }

  async function load(reset: boolean): Promise<void> {
    if (reset) loading = true;
    else loadingMore = true;
    error = null;
    try {
      const page = await libraryData.sync.history(filter, reset ? 0 : history.length, PAGE_SIZE);
      if (!active) return;
      history = reset ? page.items : [...history, ...page.items];
      total = page.total;
    } catch (value) {
      if (active) error = value instanceof Error ? value.message : 'Could not load synchronization history.';
    } finally {
      if (active) {
        loading = false;
        loadingMore = false;
      }
    }
  }

  function selectFilter(value: string): void {
    filter = value as SyncHistoryFilter;
    history = [];
    total = 0;
    void load(true);
  }

  onMount(() => {
    void load(true);
    return () => { active = false; };
  });
</script>

<V2Card title="Synchronization history">
  {#snippet actions()}
    <V2Button disabled={loading || loadingMore} onclick={() => void load(true)}>Refresh</V2Button>
  {/snippet}
  <V2Stack gap="md">
    <div class="history-toolbar">
      <V2Segmented
        items={[
          { value: 'all', label: 'All runs' },
          { value: 'incremental', label: 'Incremental' },
          { value: 'full', label: 'Global' },
        ]}
        active={filter}
        onselect={selectFilter}
        ariaLabel="Filter synchronization history"
      />
      <span class="v2-small v2-muted">{history.length} of {total} runs</span>
    </div>

    {#if error}<V2Notice tone="error" title="History unavailable">{error}</V2Notice>{/if}
    {#if loading}
      <div class="history-loading"><LoadingSpinner size="1rem" /> Loading synchronization history…</div>
    {:else if history.length === 0}
      <V2Notice tone="info">No {filter === 'all' ? '' : `${filter} `}synchronization runs have been recorded yet.</V2Notice>
    {:else}
      <div class="history-list">
        {#each history as run (run.id)}
          <article class="history-run">
            <header>
              <div>
                <strong>{run.mode === 'full' ? 'Global synchronization' : 'Incremental synchronization'}</strong>
                <span>{formatDate(run.startedAt)} · generation #{run.generation}</span>
              </div>
              <div class="history-badges">
                <V2Badge tone={run.mode === 'full' ? 'warn' : 'default'} text={run.mode === 'full' ? 'Global' : 'Incremental'} />
                <V2Badge tone={statusTone(run.status)} text={label(run.status)} />
              </div>
            </header>

            <div class="history-metrics">
              <div><span>Total duration</span><strong>{formatDuration(run.durationSeconds)}</strong></div>
              <div><span>Queue wait</span><strong>{formatDuration(run.queueSeconds)}</strong></div>
              <div><span>Assets / second</span><strong>{formatNumber(run.throughputPerSecond)}</strong></div>
              <div><span>Immich requests</span><strong>{formatNumber(run.apiRequests)}</strong></div>
              <div><span>Retries / limits</span><strong>{run.apiRetries} / {run.rateLimits}</strong></div>
              <div><span>Retry wait</span><strong>{formatDuration(run.waitSeconds)}</strong></div>
              <div><span>Checkpoints</span><strong>{formatNumber(run.checkpoints)}</strong></div>
              <div><span>Attempts</span><strong>{run.attempts}</strong></div>
            </div>

            {#if run.error}<V2Notice tone="error" title="Run error">{run.error}</V2Notice>{/if}
            {#if !run.telemetryAvailable}
              <V2Notice tone="info">This older run predates detailed telemetry. Its timestamps and available counters are still shown.</V2Notice>
            {/if}

            <details>
              <summary>View phase telemetry, counters and settings</summary>
              <V2Stack gap="md">
                <div class="phase-table-wrap">
                  <table class="phase-table">
                    <thead><tr><th>Phase</th><th>Duration</th><th>Processed</th><th>API requests</th><th>Retries</th><th>Rate limits</th><th>Wait</th><th>Checkpoints</th></tr></thead>
                    <tbody>
                      {#each run.phases as phase (phase.phase)}
                        <tr>
                          <th>{label(phase.phase)}</th>
                          <td>{formatDuration(phase.durationSeconds)}</td>
                          <td>{formatNumber(phase.processedItems)}</td>
                          <td>{formatNumber(phase.apiRequests)}</td>
                          <td>{formatNumber(phase.apiRetries)}</td>
                          <td>{formatNumber(phase.rateLimits)}</td>
                          <td>{formatDuration(phase.waitSeconds)}</td>
                          <td>{formatNumber(phase.checkpoints)}</td>
                        </tr>
                        {#if Object.keys(phase.counters).length}
                          <tr class="phase-counters"><td colspan="8">{Object.entries(phase.counters).map(([name, value]) => `${label(name)}: ${value.toLocaleString()}`).join(' · ')}</td></tr>
                        {/if}
                      {/each}
                    </tbody>
                  </table>
                </div>

                <section>
                  <h4>Settings used for this run</h4>
                  {#if run.settings}
                    <dl class="settings-snapshot">
                      {#each settingsRows(run.settings) as [name, value] (name)}
                        <div><dt>{name}</dt><dd>{value}</dd></div>
                      {/each}
                    </dl>
                  {:else}
                    <p class="v2-small v2-muted">The settings snapshot was not recorded for this older run.</p>
                  {/if}
                </section>

                <section>
                  <h4>Final counters</h4>
                  <div class="counter-list">
                    {#each Object.entries(run.counters) as [name, value] (name)}
                      <span><strong>{value.toLocaleString()}</strong> {label(name)}</span>
                    {/each}
                  </div>
                </section>
              </V2Stack>
            </details>
          </article>
        {/each}
      </div>
      {#if hasMore}
        <div class="load-more"><V2Button disabled={loadingMore} onclick={() => void load(false)}>{loadingMore ? 'Loading…' : 'Load 25 more'}</V2Button></div>
      {/if}
    {/if}
  </V2Stack>
</V2Card>

<style>
  .history-toolbar,.history-badges{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.65rem}.history-loading{display:flex;align-items:center;gap:.5rem;padding:1rem;color:var(--v2-muted)}.history-list{display:grid;gap:.85rem}.history-run{display:grid;gap:.8rem;padding:1rem;border:1px solid var(--v2-border,rgba(127,127,127,.22));border-radius:.8rem;background:var(--v2-surface-subtle,rgba(127,127,127,.035))}.history-run>header{display:flex;align-items:flex-start;justify-content:space-between;gap:1rem}.history-run>header>div:first-child{display:grid;gap:.2rem}.history-run>header span{font-size:.78rem;color:var(--v2-muted)}.history-metrics{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:.5rem}.history-metrics>div{display:grid;gap:.12rem;padding:.55rem;border-radius:.55rem;background:var(--v2-surface,rgba(127,127,127,.06))}.history-metrics span{font-size:.7rem;color:var(--v2-muted)}details{border-top:1px solid var(--v2-border,rgba(127,127,127,.2));padding-top:.7rem}summary{cursor:pointer;font-weight:650}details[open] summary{margin-bottom:1rem}.phase-table-wrap{overflow-x:auto}.phase-table{width:100%;min-width:780px;border-collapse:collapse;font-size:.78rem}.phase-table th,.phase-table td{padding:.55rem;text-align:right;border-bottom:1px solid var(--v2-border,rgba(127,127,127,.15));white-space:nowrap}.phase-table th:first-child{text-align:left}.phase-counters td{text-align:left;white-space:normal;color:var(--v2-muted);font-size:.72rem}section h4{margin:0 0 .6rem}.settings-snapshot{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.5rem;margin:0}.settings-snapshot>div{display:grid;gap:.12rem;padding:.55rem;border:1px solid var(--v2-border,rgba(127,127,127,.15));border-radius:.5rem}.settings-snapshot dt{font-size:.7rem;color:var(--v2-muted)}.settings-snapshot dd{margin:0;font-weight:650}.counter-list{display:flex;flex-wrap:wrap;gap:.45rem}.counter-list span{padding:.35rem .5rem;border-radius:.45rem;background:var(--v2-surface,rgba(127,127,127,.06));font-size:.74rem}.load-more{display:flex;justify-content:center}@media(max-width:1000px){.history-metrics{grid-template-columns:repeat(3,minmax(0,1fr))}.settings-snapshot{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:620px){.history-run>header{display:grid}.history-badges{justify-content:flex-start}.history-metrics,.settings-snapshot{grid-template-columns:1fr 1fr}}
</style>
