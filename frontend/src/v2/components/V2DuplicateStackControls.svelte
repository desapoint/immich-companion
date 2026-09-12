<script lang="ts">
  import { Layers3, Plus } from '@lucide/svelte';
  import V2Button from './V2Button.svelte';
  import V2Inline from './V2Inline.svelte';
  import type { DuplicatePendingStack } from '../data/contracts';

  let {
    stacks = [],
    activeStackId = null,
    disabled = false,
    onselect,
    oncreate,
  }: {
    stacks?: DuplicatePendingStack[];
    activeStackId?: string | null;
    disabled?: boolean;
    onselect: (stackId: string) => void;
    oncreate: () => void;
  } = $props();
</script>

<V2Inline gap="sm" wrap={true}>
  <span class="v2-small v2-muted stack-label"><Layers3 size={14} aria-hidden="true"/> Pending stacks</span>
  {#each stacks as stack}
    <V2Button {disabled} active={activeStackId===stack.id} onclick={()=>onselect(stack.id)}>
      {stack.label} · {stack.assetIds.length}
    </V2Button>
  {/each}
  <V2Button {disabled} onclick={oncreate}><Plus size={14} aria-hidden="true"/> New stack</V2Button>
</V2Inline>

<style>
  .stack-label{display:inline-flex;align-items:center;gap:5px;white-space:nowrap}
</style>
