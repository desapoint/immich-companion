<script lang="ts">
  import V2Badge from '../../../lib/components/ui/Badge.svelte';
  import V2Button from '../../../lib/components/ui/Button.svelte';
  import V2KeyboardShortcuts, { type KeyboardShortcut } from '../../../lib/components/ui/KeyboardShortcuts.svelte';

  let { groupTitle, matchLabel, activeCount, selectedForReview, boundedValidation, canPreviousGroup, canNextGroup, groupNavigationLoading, disabled, hasSelectedAsset, hasReference, onclose, onpreviousgroup, onprevious, onnext, onnextgroup, onreference, onrevalidate, ondebug, }: {
    groupTitle: string; matchLabel: string; activeCount: number; selectedForReview: boolean; boundedValidation: boolean;
    canPreviousGroup: boolean; canNextGroup: boolean; groupNavigationLoading: boolean; disabled: boolean; hasSelectedAsset: boolean; hasReference: boolean;
    onclose: () => void; onpreviousgroup: () => void; onprevious: () => void; onnext: () => void; onnextgroup: () => void; onreference: () => void; onrevalidate?: () => void; ondebug?: () => void;
  } = $props();

  const shortcuts: KeyboardShortcut[] = [
    { keys: 'Esc', description: 'Close comparison' }, { keys: '←', description: 'Previous image in group' }, { keys: '→', description: 'Next image in group' },
    { keys: ['Shift', '←'], description: 'Previous duplicate group' }, { keys: ['Shift', '→'], description: 'Next duplicate group' }, { keys: 'R', description: 'Set current asset as reference' },
    { keys: '1', description: 'Side by side' }, { keys: '2', description: 'Swipe' }, { keys: '3', description: 'Transparency' }, { keys: '4', description: 'Difference' }, { keys: '5', description: 'Local changes' }, { keys: '6', description: 'Flicker' },
  ];
</script>

<div class="v2-compare-header-identity"><V2Button onclick={onclose}>✕</V2Button><b class="v2-compare-group-title" title={groupTitle}>{groupTitle}</b><V2Badge text={matchLabel}/><V2Badge text={`${activeCount} images`}/>{#if selectedForReview}<V2Badge tone="ok" text="Selected for review"/>{/if}{#if boundedValidation}<V2Badge tone="warn" text="Bounded validation"/>{/if}</div><div class="v2-compare-header-actions"><V2Button disabled={!canPreviousGroup||groupNavigationLoading} title="Previous duplicate group (Shift+Left)" onclick={onpreviousgroup}>⇤ Previous group</V2Button><V2Button disabled={!activeCount} onclick={onprevious}>← Previous image</V2Button><V2Button disabled={!activeCount} onclick={onnext}>Next image →</V2Button><V2Button disabled={!canNextGroup||groupNavigationLoading} title="Next duplicate group (Shift+Right)" onclick={onnextgroup}>Next group ⇥</V2Button><V2Button disabled={disabled||!hasSelectedAsset} onclick={onreference}>Set as reference</V2Button>{#if ondebug}<V2Button disabled={!hasSelectedAsset} onclick={ondebug}>Add image to debug</V2Button>{/if}{#if onrevalidate}<V2Button disabled={disabled||!hasReference} onclick={onrevalidate}>Revalidate from reference</V2Button>{/if}<V2KeyboardShortcuts {shortcuts}/></div>

<style>
  .v2-compare-header-identity,.v2-compare-header-actions{display:flex;align-items:center;gap:var(--v2-space-2);flex-wrap:wrap;min-width:0;max-width:100%}.v2-compare-header-identity{flex:1 1 360px}.v2-compare-header-actions{flex:0 1 auto;justify-content:flex-end}.v2-compare-group-title{display:block;min-width:0;max-width:min(34rem,42vw);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}@media(max-width:720px){.v2-compare-group-title{max-width:calc(100vw - 8rem)}.v2-compare-header-actions{justify-content:flex-start}}
</style>
