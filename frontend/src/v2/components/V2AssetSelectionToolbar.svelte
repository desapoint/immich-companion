<script lang="ts">
  import { CheckCheck, ListChecks, Shuffle, X } from '@lucide/svelte';
  import V2Badge from './V2Badge.svelte';
  import V2Button from './V2Button.svelte';
  import V2Toolbar from './V2Toolbar.svelte';

  let { selectedCount, total, noun = 'matching assets', allMatchingSelected = false, allVisibleSelected = false, onselectvisible, onselectall, oninvert, onclear, actions: actionContent }: {
    selectedCount: number; total: number; noun?: string; allMatchingSelected?: boolean; allVisibleSelected?: boolean;
    onselectvisible: () => void; onselectall: () => void; oninvert: () => void; onclear: () => void; actions?: import('svelte').Snippet;
  } = $props();
</script>

<V2Toolbar class="v2-selection-toolbar">
  <V2Badge text={allMatchingSelected ? `All ${selectedCount.toLocaleString()} selected` : `${selectedCount.toLocaleString()} selected`} />
  <V2Button iconOnly title="Select visible" ariaLabel="Select visible" active={allVisibleSelected} onclick={onselectvisible}><ListChecks size={18}/></V2Button>
  <V2Button iconOnly title={`Select all ${total.toLocaleString()} ${noun}`} ariaLabel={`Select all ${total.toLocaleString()} ${noun}`} active={allMatchingSelected} onclick={onselectall}><CheckCheck size={18}/></V2Button>
  <V2Button iconOnly title="Invert selection" ariaLabel="Invert selection" onclick={oninvert}><Shuffle size={18}/></V2Button>
  <V2Button iconOnly title="Clear selection" ariaLabel="Clear selection" onclick={onclear}><X size={18}/></V2Button>
  {#if actionContent}{#snippet actions()}{@render actionContent()}{/snippet}{/if}
</V2Toolbar>
