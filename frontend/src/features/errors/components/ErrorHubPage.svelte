<script lang="ts">
  import { onMount } from 'svelte';

  import V2PageLayout from '../../../lib/components/layout/PageLayout.svelte';
  import V2Section from '../../../lib/components/layout/Section.svelte';
  import V2Badge from '../../../lib/components/ui/Badge.svelte';
  import V2Button from '../../../lib/components/ui/Button.svelte';
  import V2Card from '../../../lib/components/ui/Card.svelte';
  import V2ErrorState from '../../../lib/components/ui/ErrorState.svelte';
  import V2Table from '../../../lib/components/ui/Table.svelte';
  import { loadTaskErrors } from '../api/errorRepository';
  import type { TaskErrorEvent } from '../types/errorContracts';

  type Filter = 'all' | 'failed' | 'retrying';

  let errors = $state.raw<TaskErrorEvent[]>([]);
  let loading = $state(true);
  let loadError = $state('');
  let filter = $state<Filter>('all');
  let active = true;

  const visibleErrors = $derived(filter === 'all' ? errors : errors.filter((error) => error.outcome === filter));
  const failedCount = $derived(errors.filter((error) => error.outcome === 'failed').length);
  const retryCount = $derived(errors.filter((error) => error.outcome === 'retrying').length);

  function operationLabel(value: string): string {
    return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  function occurredLabel(value: string): string {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
  }

  function attemptLabel(error: TaskErrorEvent): string {
    return error.maxAttempts === null ? `${error.attempt}` : `${error.attempt} / ${error.maxAttempts}`;
  }

  function classificationLabel(error: TaskErrorEvent): string {
    if (error.retryable === null) return 'Historical · unknown';
    return error.retryable ? 'Transient' : 'Permanent';
  }

  async function refresh(): Promise<void> {
    loading = true;
    loadError = '';
    try {
      const nextErrors = await loadTaskErrors();
      if (active) errors = nextErrors;
    } catch (error) {
      if (active) loadError = error instanceof Error ? error.message : 'The error history could not be loaded.';
    } finally {
      if (active) loading = false;
    }
  }

  onMount(() => {
    active = true;
    void refresh();
    return () => { active = false; };
  });
</script>

<V2PageLayout
  title="Error Hub"
  description="Inspect durable background-task failures and retry decisions without exposing task payloads."
>
  {#snippet headerActions()}
    <V2Button disabled={loading} onclick={() => void refresh()}>{loading ? 'Refreshing…' : 'Refresh'}</V2Button>
  {/snippet}

  {#snippet context()}
    <div class="error-hub-summary" aria-label="Error summary">
      <div><span class="v2-muted">Recorded</span><b>{errors.length}</b></div>
      <div><span class="v2-muted">Stopped</span><b>{failedCount}</b></div>
      <div><span class="v2-muted">Retried</span><b>{retryCount}</b></div>
    </div>
  {/snippet}

  <V2Section title="Background operation errors">
    {#snippet actions()}
      <div class="error-hub-filters" aria-label="Filter errors">
        <V2Button active={filter === 'all'} ariaPressed={filter === 'all'} onclick={() => filter = 'all'}>All</V2Button>
        <V2Button active={filter === 'failed'} ariaPressed={filter === 'failed'} onclick={() => filter = 'failed'}>Stopped</V2Button>
        <V2Button active={filter === 'retrying'} ariaPressed={filter === 'retrying'} onclick={() => filter = 'retrying'}>Retried</V2Button>
      </div>
    {/snippet}

    {#if loadError}
      <V2ErrorState title="Error history unavailable" message={loadError} onretry={() => void refresh()} />
    {:else}
      <V2Card>
        <V2Table compact={true} class="error-hub-table">
          <thead><tr><th>When</th><th>Operation</th><th>Cause</th><th>Decision</th><th>Attempt</th></tr></thead>
          <tbody>
            {#each visibleErrors as error (error.id)}
              <tr>
                <td data-label="When"><time datetime={error.occurredAt}>{occurredLabel(error.occurredAt)}</time></td>
                <td data-label="Operation"><b>{operationLabel(error.taskType)}</b><small class="error-hub-task-id v2-muted" title={error.taskId}>{error.taskId}</small></td>
                <td data-label="Cause"><b>{error.errorType}</b><span class="error-hub-message">{error.message}</span></td>
                <td data-label="Decision"><V2Badge tone={error.willRetry ? 'warn' : 'bad'} text={error.willRetry ? 'Retry scheduled' : 'Stopped'} /><small class="v2-muted">{classificationLabel(error)}</small></td>
                <td data-label="Attempt">{attemptLabel(error)}</td>
              </tr>
            {:else}
              <tr><td colspan="5" class="error-hub-empty v2-muted">{loading ? 'Loading error history…' : errors.length ? 'No errors match this filter.' : 'No background-task errors have been recorded.'}</td></tr>
            {/each}
          </tbody>
        </V2Table>
      </V2Card>
    {/if}
  </V2Section>
</V2PageLayout>

<style>
  .error-hub-summary { display: grid; gap: 0.75rem; }
  .error-hub-summary > div { display: flex; align-items: baseline; justify-content: space-between; gap: 1rem; }
  .error-hub-summary b { font-size: 1.15rem; color: var(--v2-text); }
  .error-hub-filters { display: flex; flex-wrap: wrap; gap: 0.4rem; }
  .error-hub-task-id, .error-hub-message, td small { display: block; margin-top: 0.25rem; }
  .error-hub-task-id { max-width: 15rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .error-hub-message { max-width: 42rem; overflow-wrap: anywhere; }
  .error-hub-empty { padding-block: 2rem; text-align: center; }
  time { white-space: nowrap; }

  @media (max-width: 760px) {
    :global(.error-hub-table thead) { display: none; }
    :global(.error-hub-table tbody), :global(.error-hub-table tr), :global(.error-hub-table td) { display: block; }
    :global(.error-hub-table tr) { padding: 0.65rem 0; border-bottom: 1px solid var(--v2-line); }
    :global(.error-hub-table tr:last-child) { border-bottom: 0; }
    :global(.error-hub-table td) { display: grid; grid-template-columns: 5rem minmax(0, 1fr); gap: 0.6rem; border: 0; padding: 0.35rem 0; }
    :global(.error-hub-table td::before) { content: attr(data-label); color: var(--v2-muted); font-size: 0.68rem; font-weight: 800; letter-spacing: 0.06em; text-transform: uppercase; }
    :global(.error-hub-table td[colspan]) { display: block; }
  }
</style>
