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

<div class="v2-duplicate-decision-controls" class:has-primary={showPrimary}>
  <div>{#if decisions.includes('keep')}<V2Button {disabled} active={decision==='keep'} onclick={()=>ondecision('keep')}>Keep</V2Button>{/if}</div>
  <div>{#if decisions.includes('delete')}<V2Button {disabled} active={decision==='delete'} onclick={()=>ondecision('delete')}>Delete</V2Button>{/if}</div>
  <div class="stack-action">{#if decisions.includes('stack')}<V2Button {disabled} active={decision==='stack'} onclick={()=>ondecision('stack')}>{decision==='stack'?stackLabel:'Stack'}</V2Button>{/if}</div>
  {#if showPrimary}
    <div class="primary-slot">
      <V2Button iconOnly {disabled} active={isPrimary} title={isPrimary?'Stack primary':'Set as stack primary'} ariaLabel={isPrimary?'Stack primary':'Set as stack primary'} onclick={onprimary}>
        <Star size={16} fill={isPrimary?'currentColor':'none'} aria-hidden="true"/>
      </V2Button>
    </div>
  {/if}
</div>

<style>
  .v2-duplicate-decision-controls{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr) minmax(0,2fr) 38px;gap:5px;margin-top:6px;width:100%;align-items:stretch}
  .v2-duplicate-decision-controls>div{min-width:0}
  .v2-duplicate-decision-controls :global(.v2-button){width:100%;min-width:0;height:100%;padding:7px 5px;font-size:12px}
  .stack-action{grid-column:3/5}
  .has-primary .stack-action{grid-column:3}
  .primary-slot{grid-column:4;width:38px;min-width:38px;display:grid;place-items:stretch}
  .primary-slot :global(.v2-button){width:38px;min-width:38px;padding-inline:0}
</style>
