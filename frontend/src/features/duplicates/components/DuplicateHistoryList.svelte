<script lang="ts">
  import V2Badge from '../../../v2/components/V2Badge.svelte';
  import V2Button from '../../../v2/components/V2Button.svelte';
  import V2Card from '../../../v2/components/V2Card.svelte';
  import V2Stack from '../../../v2/components/V2Stack.svelte';
  import V2Toolbar from '../../../v2/components/V2Toolbar.svelte';
  import type { DuplicateHistoryRecord } from '../../../v2/data/contracts';

  let { history, mutating, reconciling, onselect, onclear }: { history: DuplicateHistoryRecord[]; mutating: boolean; reconciling: boolean; onselect: (id: string) => void; onclear: (row: DuplicateHistoryRecord) => void } = $props();
</script>

<V2Toolbar sticky={false}><V2Badge text="Resolution history" /></V2Toolbar>
<V2Stack gap="sm">{#each history as row (row.id)}<V2Card><div class="v2-history-row"><button class="v2-history-resolution" type="button" disabled={mutating||reconciling} onclick={() => onselect(row.id)}><span class="v2-history-identity"><b>{row.groupLabel}</b><small>{new Date(row.occurredAt).toLocaleString()}</small></span><span class="v2-history-summary">{row.summary}</span></button><V2Button variant="danger" disabled={mutating||reconciling} onclick={() => onclear(row)}>Clear resolution</V2Button></div></V2Card>{:else}<V2Card><span class="v2-muted">No resolution history in this range.</span></V2Card>{/each}</V2Stack>

<style>
  .v2-history-row{display:flex;align-items:center;gap:10px;justify-content:space-between;min-width:0}.v2-history-resolution{display:flex;align-items:center;justify-content:space-between;gap:18px;flex:1;min-width:0;border:0;padding:4px;background:transparent;color:inherit;font:inherit;text-align:left;cursor:pointer}.v2-history-resolution:focus-visible{outline:2px solid var(--v2-accent);outline-offset:2px;border-radius:6px}.v2-history-resolution:disabled{cursor:default;opacity:.55}.v2-history-identity{display:grid;gap:3px;min-width:0}.v2-history-identity b,.v2-history-identity small,.v2-history-summary{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.v2-history-identity small{color:var(--v2-muted);font-size:11px}@media(max-width:720px){.v2-history-row,.v2-history-resolution{align-items:stretch;flex-direction:column}.v2-history-resolution{gap:6px}}
</style>
