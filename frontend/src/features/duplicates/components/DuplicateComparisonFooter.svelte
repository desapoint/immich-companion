<script lang="ts">
  import V2Button from '../../../lib/components/ui/Button.svelte';
  import V2DuplicateDecisionControls from './DuplicateDecisionControls.svelte';
  import type { DuplicateDecision } from '../types/contracts';

  let { assetName, decision, stackLabel, stackPrimary, decisions, disabled, ondecision, onprimary, onclear, }: {
    assetName: string; decision?: DuplicateDecision; stackLabel: string; stackPrimary: boolean; decisions: DuplicateDecision[]; disabled: boolean;
    ondecision: (decision: DuplicateDecision) => void; onprimary: () => void; onclear: () => void;
  } = $props();
</script>

<span class="v2-compare-footer-label"><b>{assetName}</b> <span class="v2-small v2-muted">Choose disposition</span></span><div class="v2-compare-footer-actions"><div class="v2-compare-footer-decisions"><V2DuplicateDecisionControls {decision} {stackLabel} isPrimary={stackPrimary} {decisions} {disabled} ondecision={ondecision} onprimary={onprimary}/></div><span class="v2-compare-clear-selection"><V2Button disabled={disabled||!decision} onclick={onclear}>Clear selection</V2Button></span></div>

<style>
  .v2-compare-footer-label{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.v2-compare-footer-actions{display:flex;align-items:center;justify-content:flex-end;gap:var(--v2-space-2);flex:0 1 auto;min-width:0;margin-left:auto}.v2-compare-footer-decisions{flex:0 1 25rem;width:min(25rem,100%);min-width:min(20rem,100%)}.v2-compare-footer-decisions :global(.v2-duplicate-decision-controls){margin-top:0}.v2-compare-clear-selection{display:inline-flex;flex:0 0 auto;align-self:center;white-space:nowrap}@media(max-width:720px){.v2-compare-footer-actions{flex:1 1 100%;width:100%}.v2-compare-footer-decisions{flex:1 1 18rem;min-width:0}}
</style>
