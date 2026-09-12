<script lang="ts">
  import { Star } from '@lucide/svelte';
  import V2Button from './V2Button.svelte';
  import type { DuplicateDecision } from '../data/contracts';

  let {
    decision,
    stackLabel = 'Stack',
    isPrimary = false,
    stackEnabled = true,
    disabled = false,
    decisions = ['keep', 'delete', 'stack'],
    ondecision,
    onprimary,
  }: {
    decision?: DuplicateDecision;
    stackLabel?: string;
    isPrimary?: boolean;
    stackEnabled?: boolean;
    disabled?: boolean;
    decisions?: DuplicateDecision[];
    ondecision: (decision: DuplicateDecision) => void;
    onprimary: () => void;
  } = $props();

  const showPrimary=$derived(decisions.includes('stack')&&stackEnabled&&decision==='stack');
</script>

<div class="v2-duplicate-decision-controls" class:has-primary={showPrimary} data-decision={decision}>
  <div class="decision-keep">{#if decisions.includes('keep')}<V2Button {disabled} active={decision==='keep'} ariaPressed={decision==='keep'} onclick={()=>ondecision('keep')}>Keep</V2Button>{/if}</div>
  <div class="decision-delete">{#if decisions.includes('delete')}<V2Button {disabled} active={decision==='delete'} ariaPressed={decision==='delete'} onclick={()=>ondecision('delete')}>Delete</V2Button>{/if}</div>
  <div class="stack-action decision-stack">{#if decisions.includes('stack')}<V2Button {disabled} active={decision==='stack'} ariaPressed={decision==='stack'} onclick={()=>ondecision('stack')}>{decision==='stack'?stackLabel:'Stack'}</V2Button>{/if}</div>
  {#if showPrimary}
    <div class="primary-slot">
      <V2Button iconOnly {disabled} active={isPrimary} title={isPrimary?'Stack primary':'Set as stack primary'} ariaLabel={isPrimary?'Stack primary':'Set as stack primary'} onclick={onprimary}>
        <Star size={16} fill={isPrimary?'currentColor':'none'} aria-hidden="true"/>
      </V2Button>
    </div>
  {/if}
</div>

<style>
  .v2-duplicate-decision-controls{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr) minmax(0,2fr) 38px;gap:5px;margin-top:6px;width:100%;padding:4px;align-items:stretch;border:1px solid var(--v2-line);border-radius:9px;background:var(--v2-bg);box-sizing:border-box}
  .v2-duplicate-decision-controls>div{min-width:0}
  .v2-duplicate-decision-controls :global(.v2-button){width:100%;min-width:0;height:100%;padding:7px 5px;font-size:12px}
  .stack-action{grid-column:3/5}
  .has-primary .stack-action{grid-column:3}
  .primary-slot{grid-column:4;width:38px;min-width:38px;display:grid;place-items:stretch}
  .primary-slot :global(.v2-button){width:38px;min-width:38px;padding-inline:0}

  .decision-keep :global(.v2-button){border-color:#2f8f5b;background:var(--v2-bg);color:#8be0ad}
  .decision-keep :global(.v2-button:hover:not(:disabled)){background:rgba(47,143,91,.16)}
  .decision-keep :global(.v2-button[data-active="true"]){border-color:#66dda0;background:color-mix(in srgb,#2f8f5b 58%,var(--v2-bg));color:#f0fff5;font-weight:750;box-shadow:inset 0 0 0 2px rgba(135,238,179,.34),0 0 0 1px rgba(79,201,133,.25)}

  .decision-delete :global(.v2-button){border-color:#a64545;background:var(--v2-bg);color:#ff9e9e}
  .decision-delete :global(.v2-button:hover:not(:disabled)){background:rgba(166,69,69,.16)}
  .decision-delete :global(.v2-button[data-active="true"]){border-color:#ff7373;background:color-mix(in srgb,#a64545 58%,var(--v2-bg));color:#fff2f2;font-weight:750;box-shadow:inset 0 0 0 2px rgba(255,142,142,.3),0 0 0 1px rgba(224,91,91,.25)}

  .decision-stack :global(.v2-button){border-color:#536fbe;background:var(--v2-bg);color:#aebfff}
  .decision-stack :global(.v2-button:hover:not(:disabled)){background:rgba(83,111,190,.16)}
  .decision-stack :global(.v2-button[data-active="true"]){border-color:#91a7ff;background:color-mix(in srgb,#536fbe 62%,var(--v2-bg));color:#f5f7ff;font-weight:750;box-shadow:inset 0 0 0 2px rgba(164,181,255,.3),0 0 0 1px rgba(124,148,232,.25)}
</style>
