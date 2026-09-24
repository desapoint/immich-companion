<script lang="ts">
  import { Check, LoaderCircle } from '@lucide/svelte';
  import type { DuplicateReviewProgressPhase } from '../types/reviewProgress';

  let {
    phase,
    overlay = false,
  }: {
    phase: DuplicateReviewProgressPhase;
    overlay?: boolean;
  } = $props();

  const steps: Array<{ phase: DuplicateReviewProgressPhase; label: string }> = [
    { phase: 'saving', label: 'Save choices' },
    { phase: 'planning', label: 'Validate plan' },
    { phase: 'ready', label: 'Confirm' },
    { phase: 'applying', label: 'Apply actions' },
    { phase: 'refreshing', label: 'Refresh results' },
  ];
  const currentIndex = $derived(steps.findIndex((step) => step.phase === phase));
  const title = $derived(phase === 'saving'
    ? 'Saving review choices'
    : phase === 'planning'
      ? 'Checking duplicate action plan'
      : phase === 'ready'
        ? 'Action plan ready'
        : phase === 'applying'
          ? 'Applying duplicate actions'
          : 'Refreshing duplicate results');
  const detail = $derived(phase === 'saving'
    ? 'Waiting for pending decisions and selections to finish saving…'
    : phase === 'planning'
      ? 'Validating current groups, stack membership, and action-plan safety…'
      : phase === 'ready'
        ? 'Review the frozen plan, then confirm when you are ready.'
        : phase === 'applying'
          ? 'Companion is applying the confirmed plan. Keep this page open.'
          : 'The actions were applied. Loading the latest groups and selections…');
</script>

<div class:progress-overlay={overlay} class:progress-inline={!overlay} role="status" aria-live="polite" aria-busy={phase !== 'ready'}>
  <div class="progress-panel">
    <div class="progress-heading">
      {#if phase === 'ready'}<Check size={19} aria-hidden="true" />{:else}<span class="spinner"><LoaderCircle size={19} aria-hidden="true" /></span>{/if}
      <div><b>{title}</b><span>{detail}</span></div>
    </div>
    <ol aria-label="Review action progress">
      {#each steps as step, index (step.phase)}
        <li data-state={index < currentIndex ? 'complete' : index === currentIndex ? 'current' : 'upcoming'}>
          <span aria-hidden="true">{index < currentIndex ? '✓' : index + 1}</span>{step.label}
        </li>
      {/each}
    </ol>
  </div>
</div>

<style>
  .progress-overlay { position: fixed; z-index: 90; inset: var(--v2-topbar-height) 0 0 var(--v2-sidebar-width); display: grid; place-items: center; padding: 16px; background: color-mix(in srgb, var(--v2-bg) 72%, transparent); backdrop-filter: blur(3px); }
  .progress-panel { width: min(620px, 100%); display: grid; gap: 14px; padding: 16px 18px; border: 1px solid color-mix(in srgb, var(--v2-accent) 45%, var(--v2-line)); border-radius: var(--v2-radius); background: var(--v2-surface-2); box-shadow: 0 18px 48px rgb(0 0 0 / 42%); }
  .progress-inline .progress-panel { width: auto; padding: 0; border: 0; background: transparent; box-shadow: none; }
  .progress-heading { display: flex; align-items: center; gap: 10px; }
  .progress-heading > div { display: grid; gap: 3px; min-width: 0; }
  .progress-heading span { color: var(--v2-muted); font-size: 12px; line-height: 1.4; }
  .spinner { display: grid; animation: review-progress-spin .9s linear infinite; color: var(--v2-accent); }
  ol { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 6px; margin: 0; padding: 0; list-style: none; }
  li { display: flex; align-items: center; gap: 5px; min-width: 0; color: var(--v2-muted); font-size: 10px; }
  li > span { display: grid; width: 19px; height: 19px; flex: 0 0 19px; place-items: center; border: 1px solid var(--v2-line); border-radius: 999px; font-size: 10px; }
  li[data-state='current'] { color: var(--v2-text); font-weight: 750; }
  li[data-state='current'] > span { border-color: var(--v2-accent); background: var(--v2-accent-2); }
  li[data-state='complete'] { color: var(--v2-ok, #69d69a); }
  @keyframes review-progress-spin { to { transform: rotate(360deg); } }
  @media(max-width: 620px) {
    .progress-overlay { inset: var(--v2-topbar-height) 0 58px; }
    ol { grid-template-columns: 1fr; }
  }
  @media(prefers-reduced-motion: reduce) { .spinner { animation: none; } }
</style>
