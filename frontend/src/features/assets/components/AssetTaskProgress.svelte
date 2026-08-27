<script lang="ts">
  import type { AssetTaskStatus } from '../types/assets';

  interface Props {
    task: AssetTaskStatus;
    overlay?: boolean;
    oncancel?: (() => void) | undefined;
  }

  let { task, overlay = false, oncancel }: Props = $props();
  const progress = $derived(task.progress ?? {});
  const percent = $derived(progress.percent ?? null);
  const completed = $derived(progress.completed ?? task.counters.processed ?? 0);
  const total = $derived(progress.total ?? task.counters.requested ?? null);
  const determinate = $derived(percent !== null && total !== null);
  const width = $derived(`${Math.max(0, Math.min(100, percent ?? 0))}%`);
  const terminal = $derived(['completed', 'failed', 'cancelled'].includes(task.status));
  const action = $derived(task.task_type === 'asset_action');
  const batch = $derived(progress.batch ?? null);
  const batches = $derived(progress.batches ?? null);
  const rate = $derived(progress.assets_per_second ?? null);
  const remaining = $derived(progress.estimated_remaining_seconds ?? null);
</script>

<div class:overlay role="presentation">
<div class="task-progress" class:terminal role="status" aria-live="polite">
  <span class="spinner" aria-hidden="true"></span>
  <div class="copy">
    <strong>{terminal ? (task.status === 'failed' ? `${action ? 'Action' : 'Sync'} failed` : `${action ? 'Action' : 'Sync'} complete`) : (action ? 'Applying selected action…' : 'Syncing selected assets…')}</strong>
    <small>
      {#if total !== null}{completed.toLocaleString()} of {total.toLocaleString()}{:else}Working…{/if}
      {#if percent !== null} · {percent.toFixed(0)}%{/if}
      {#if batch !== null && batches !== null} · Batch {batch}/{batches}{/if}
      {#if rate !== null} · {rate.toFixed(1)}/s{/if}
      {#if remaining !== null} · ~{Math.ceil(remaining)}s left{/if}
    </small>
  </div>
  {#if oncancel && !terminal}
    <button type="button" class="cancel" onclick={oncancel}>Cancel</button>
  {/if}
  <div class="progress-track" role="progressbar" aria-label="Task progress"
    aria-valuemin="0" aria-valuemax="100" aria-valuenow={determinate ? percent : undefined}>
    <span class:indeterminate={!determinate} class="progress-fill" style:width={determinate ? width : undefined}></span>
  </div>
</div>
</div>

<style>
  .task-progress {
    position: fixed;
    z-index: 120;
    right: 1rem;
    bottom: 1rem;
    display: flex;
    min-width: min(18rem, calc(100vw - 2rem));
    align-items: center;
    gap: 0.7rem;
    padding: 0.8rem 0.95rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-md);
    background: color-mix(in srgb, var(--color-surface-raised) 96%, transparent);
    box-shadow: 0 0.6rem 1.8rem rgb(17 24 19 / 18%);
    backdrop-filter: blur(0.75rem);
    flex-wrap: wrap;
  }

  .overlay {
    position: fixed;
    z-index: 119;
    inset: 0;
    display: grid;
    place-items: center;
    background: rgb(0 0 0 / 48%);
    backdrop-filter: blur(0.45rem);
  }

  .overlay:not(:global(.task-progress)) { pointer-events: auto; }

  :global(.overlay) .task-progress {
    position: relative;
    inset: auto;
    right: auto;
    bottom: auto;
    width: min(22rem, calc(100vw - 2rem));
    min-width: 0;
  }

  .spinner {
    width: 1.15rem;
    height: 1.15rem;
    flex: 0 0 auto;
    border: 0.16rem solid color-mix(in srgb, var(--color-accent) 25%, transparent);
    border-top-color: var(--color-accent-strong);
    border-radius: 50%;
    animation: spin 800ms linear infinite;
  }

  .terminal .spinner { animation: none; border-top-color: var(--color-accent-strong); }
  .copy { display: grid; min-width: 0; gap: 0.12rem; }
  strong { font-size: 0.74rem; }
  small { color: var(--color-ink-muted); font-size: 0.67rem; }
  .cancel { margin-left: auto; border: 1px solid var(--color-border-strong); border-radius: var(--radius-sm); padding: 0.35rem 0.5rem; color: var(--color-ink-muted); background: transparent; font: inherit; font-size: 0.68rem; cursor: pointer; }

  .progress-track {
    width: min(17rem, calc(100vw - 2rem));
    height: 0.28rem;
    overflow: hidden;
    flex: 0 0 100%;
    border-radius: 999px;
    background: color-mix(in srgb, var(--color-ink-muted) 18%, transparent);
  }

  .progress-fill {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: var(--color-accent-strong);
    transition: width 220ms ease;
  }

  .progress-fill.indeterminate {
    width: 38%;
    background: repeating-linear-gradient(
      135deg,
      var(--color-accent-strong) 0 0.35rem,
      var(--color-accent) 0.35rem 0.7rem
    );
    animation: progress-loop 1.1s linear infinite;
  }

  @keyframes spin { to { transform: rotate(360deg); } }
  @keyframes progress-loop { from { transform: translateX(-100%); } to { transform: translateX(270%); } }
</style>
