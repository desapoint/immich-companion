<script lang="ts">
  import SelectField from '../../../v2/components/SelectField.svelte';
  import V2Button from '../../../v2/components/V2Button.svelte';
  import V2Section from '../../../v2/components/V2Section.svelte';
  import V2Stack from '../../../v2/components/V2Stack.svelte';
  import type { DuplicateDecision, DuplicateSourceFilter } from '../../../v2/data/contracts';

  let { sourceFilter, reviewFilter, reviewFilterOptions, selectionScope, groupCount, mutating, keeperSummary, decisions, bulkPresetDisabled, onsourcefilter, onreviewfilter, onselectionchange, onopenkeeper, onpreset }: {
    sourceFilter: DuplicateSourceFilter;
    reviewFilter: string;
    reviewFilterOptions: string[];
    selectionScope: 'Current page' | 'All matching';
    groupCount: number;
    mutating: boolean;
    keeperSummary: string;
    decisions: DuplicateDecision[];
    bulkPresetDisabled: boolean;
    onsourcefilter: (value: string) => void;
    onreviewfilter: (value: string) => void;
    onselectionchange: (value: 'Current page' | 'All matching') => void;
    onopenkeeper: () => void;
    onpreset: (decision: DuplicateDecision) => void;
  } = $props();
</script>

<V2Section title="Review filter"><V2Stack gap="sm"><SelectField id="duplicate-source-filter" label="Discovery source" value={sourceFilter} options={[{value:'both',label:'Both sources'},{value:'immich',label:'Immich'},{value:'similarity',label:'Similarity engine'}]} onchange={onsourcefilter}/><SelectField id="duplicate-review-filter" label="Group state" value={reviewFilter} options={reviewFilterOptions} onchange={onreviewfilter}/></V2Stack></V2Section>
<V2Section title="Bulk choices"><V2Stack gap="sm"><span class="v2-small v2-muted">{selectionScope==='Current page'?`Current page only affects the ${groupCount.toLocaleString()} groups loaded below.`:'All matching filters affects every group matching the current discovery-source and group-state filters, including groups on other pages.'}</span><V2Button variant="primary" disabled={mutating||(selectionScope==='Current page'&&!groupCount)} onclick={onopenkeeper}>Automation rules…</V2Button>{#if keeperSummary}<span class="v2-small v2-muted">{keeperSummary}</span>{/if}{#if decisions.includes('keep')}<V2Button disabled={bulkPresetDisabled} onclick={()=>onpreset('keep')}>Keep all copies</V2Button>{/if}{#if decisions.includes('delete')}<V2Button disabled={bulkPresetDisabled} onclick={()=>onpreset('delete')}>Mark all for deletion</V2Button>{/if}{#if decisions.includes('stack')}<V2Button disabled={bulkPresetDisabled} onclick={()=>onpreset('stack')}>Stack each group</V2Button>{/if}</V2Stack></V2Section>
