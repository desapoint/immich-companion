<script lang="ts">
  import ConfirmDialog from '../../../lib/components/ui/ConfirmDialog.svelte';
  import type { AssetSyncProgress } from '../types/assets';

  interface Props {
    total: number;
    shown: number;
    selected: number;
    syncing: boolean;
    syncMessage: string | null;
    syncProgress?: AssetSyncProgress | null;
    onsync: () => void;
    onfullsync: () => void;
  }

  let {
    total,
    shown,
    selected,
    syncing,
    syncMessage,
    syncProgress = null,
    onsync,
    onfullsync,
  }: Props = $props();
  let fullSyncConfirmation = $state(false);
  const phaseLabels: Record<string, string> = {
    queued: 'Queued',
    catalogs: 'Albums and tags',
    assets: 'Media',
    stacks: 'Stacks',
    relationships: 'Associations',
    finalizing: 'Finalizing',
  };
  const syncSteps = ['catalogs', 'assets', 'stacks', 'relationships', 'finalizing'];
  const currentStep = $derived(syncProgress ? Math.max(0, syncSteps.indexOf(syncProgress.phase)) : 0);
  const stepNumber = $derived(currentStep + 1);
  const stepPercent = $derived(syncProgress?.percent ?? null);
</script>

<div class="result-status">
  <div>
    <span>Search results</span>
    <strong>{total} matching assets</strong>
    <small>{shown} on this page · {selected} selected</small>
  </div>
  <div class="sync-area">
    {#if syncMessage && !syncing}<small role="status">{syncMessage}</small>{/if}
    {#if syncing && syncProgress}
      <div class="sync-progress" role="status" aria-label="Immich synchronization progress">
        <div class="progress-heading">
          <span>Step {stepNumber} of {syncSteps.length} · {phaseLabels[syncProgress.phase] ?? syncProgress.phase}</span>
        </div>
        <div class="progress-line">
          <div
            class:indeterminate={stepPercent === null}
            class="progress-track"
            role="progressbar"
            aria-valuemin="0"
            aria-valuemax="100"
            aria-valuenow={stepPercent ?? undefined}
            aria-valuetext={syncProgress.detail ?? phaseLabels[syncProgress.phase] ?? syncProgress.phase}
          >
            <div
              class="progress-value"
              style={stepPercent === null ? undefined : `width: ${stepPercent}%`}
            ></div>
          </div>
          {#if stepPercent !== null}
            <strong class="progress-percent">{stepPercent.toFixed(1)}%</strong>
          {:else}
            <strong class="progress-percent">Working…</strong>
          {/if}
        </div>
        <div class="progress-tooltip" role="tooltip">
          <strong>{phaseLabels[syncProgress.phase] ?? syncProgress.phase}</strong>
          {#if syncProgress.total !== null}
            <span>{syncProgress.completed.toLocaleString()} of {syncProgress.total.toLocaleString()} processed</span>
          {:else}
            <span>{syncProgress.completed.toLocaleString()} processed · total not available</span>
          {/if}
          {#if syncProgress.detail}<span>{syncProgress.detail}</span>{/if}
        </div>
      </div>
    {/if}
    <button type="button" onclick={onsync} disabled={syncing}>
      {syncing ? 'Syncing Immich…' : 'Incremental sync'}
    </button>
    <button
      class="full-sync"
      type="button"
      onclick={() => (fullSyncConfirmation = true)}
    >Full sync</button>
  </div>
</div>

{#if fullSyncConfirmation}
  <ConfirmDialog
    title="Force a global synchronization?"
    message="This checks every album, tag, image, stack, and membership before safely removing anything absent. It runs in bounded batches and cannot overlap another sync."
    confirmLabel="Start full sync"
    icon="info"
    onconfirm={() => {
      fullSyncConfirmation = false;
      onfullsync();
    }}
    onclose={() => (fullSyncConfirmation = false)}
  />
{/if}

<style>
  .result-status {
    display: flex;
    align-items: end;
    justify-content: space-between;
    gap: 1rem;
  }

  .result-status > div:first-child {
    display: grid;
    gap: 0.18rem;
  }

  span {
    color: var(--color-accent-strong);
    font-size: 0.65rem;
    font-weight: 800;
    letter-spacing: 0.07em;
    text-transform: uppercase;
  }

  strong {
    font-size: 1.1rem;
  }

  small {
    color: var(--color-ink-muted);
    font-size: 0.7rem;
  }

  .sync-area {
    display: flex;
    align-items: end;
    flex: 1 1 30rem;
    min-width: 0;
    flex-wrap: wrap;
    gap: 0.65rem;
  }

  .sync-progress {
    position: relative;
    display: grid;
    flex: 1 1 16rem;
    width: auto;
    min-width: 12rem;
    gap: 0.22rem;
    padding: 0.4rem 0.55rem;
    border: 1px solid color-mix(in srgb, var(--color-accent) 28%, var(--color-border));
    border-radius: var(--radius-md);
    background: color-mix(in srgb, var(--color-surface-raised) 92%, var(--color-accent));
    box-shadow: 0 0.45rem 1.4rem rgb(24 35 54 / 12%);
  }

  .progress-heading {
    display: flex;
    gap: 0.6rem;
    color: var(--color-ink);
    font-size: 0.62rem;
    font-weight: 760;
  }

  .progress-heading span {
    color: var(--color-ink-muted);
    font-size: 0.61rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  .progress-line {
    display: flex;
    align-items: center;
    min-width: 0;
    gap: 0.45rem;
  }

  .progress-track {
    flex: 1 1 auto;
    position: relative;
    overflow: hidden;
    height: 0.34rem;
    border-radius: 99px;
    background: color-mix(in srgb, var(--color-border) 72%, transparent);
  }

  .progress-percent {
    flex: 0 0 3.5rem;
    color: var(--color-ink-muted);
    font-size: 0.64rem;
    text-align: right;
    white-space: nowrap;
  }

  .progress-value {
    position: relative;
    overflow: hidden;
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(90deg, var(--color-accent-strong), var(--color-accent));
    transition: width 360ms ease;
  }

  .progress-value::after {
    position: absolute;
    inset: 0;
    content: '';
    background: linear-gradient(105deg, transparent 25%, rgb(255 255 255 / 42%) 50%, transparent 75%);
    background-size: 220% 100%;
    animation: progress-shimmer 1.5s linear infinite;
  }

  .progress-track.indeterminate .progress-value {
    width: 42%;
    animation: sync-progress 1.2s linear infinite;
  }

  .progress-tooltip {
    position: absolute;
    z-index: 2;
    right: 0.5rem;
    bottom: calc(100% + 0.45rem);
    display: grid;
    max-width: min(23rem, 80vw);
    min-width: min(13rem, 70vw);
    gap: 0.18rem;
    padding: 0.55rem 0.7rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-ink);
    background: var(--color-surface-raised);
    box-shadow: 0 0.5rem 1.25rem rgb(24 35 54 / 18%);
    font-size: 0.68rem;
    overflow-wrap: anywhere;
    opacity: 0;
    pointer-events: none;
    transform: translateY(0.25rem);
    transition: opacity 140ms ease, transform 140ms ease;
  }

  .progress-tooltip span {
    color: var(--color-ink-muted);
    font-size: 0.66rem;
    letter-spacing: normal;
    text-transform: none;
  }

  .sync-area > small {
    max-width: min(18rem, 38vw);
    overflow-wrap: anywhere;
  }

  .sync-progress:hover .progress-tooltip,
  .sync-progress:focus-within .progress-tooltip {
    opacity: 1;
    transform: translateY(0);
  }

  @keyframes sync-progress {
    from { transform: translateX(-110%); }
    to { transform: translateX(260%); }
  }

  @keyframes progress-shimmer {
    from { background-position: 120% 0; }
    to { background-position: -120% 0; }
  }

  button {
    min-height: 2.45rem;
    padding: 0.55rem 0.8rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-accent-strong);
    background: var(--color-surface-raised);
    cursor: pointer;
    font: inherit;
    font-size: 0.74rem;
    font-weight: 780;
  }

  button:disabled {
    cursor: wait;
    opacity: 0.58;
  }

  .full-sync { color: var(--color-ink-muted); }

  @media (max-width: 42rem) {
    .result-status,
    .sync-area {
      align-items: flex-start;
      flex-direction: column;
    }

    .sync-progress {
      width: 100%;
    }
  }
</style>
