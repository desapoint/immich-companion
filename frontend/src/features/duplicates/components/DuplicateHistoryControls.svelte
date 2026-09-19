<script lang="ts">
  import SelectField from '../../../v2/components/SelectField.svelte';
  import V2Button from '../../../v2/components/V2Button.svelte';
  import V2Section from '../../../v2/components/V2Section.svelte';
  import V2Stack from '../../../v2/components/V2Stack.svelte';

  let { historyRange, canViewHistory, mutating, reconciling, onrangechange, onrefresh, onclearall }: {
    historyRange: 'Last 30 days' | 'Last 90 days' | 'All history';
    canViewHistory: boolean;
    mutating: boolean;
    reconciling: boolean;
    onrangechange: (value: string) => void;
    onrefresh: () => void;
    onclearall: () => void;
  } = $props();
</script>

<V2Section title="History filter"><V2Stack gap="sm"><SelectField id="duplicate-history-range" label="Range" value={historyRange} options={['Last 30 days','Last 90 days','All history']} onchange={onrangechange}/><V2Button disabled={!canViewHistory||mutating||reconciling} onclick={onrefresh}>Refresh history</V2Button><V2Button variant="danger" disabled={!canViewHistory||mutating||reconciling} onclick={onclearall}>Clear all resolution history</V2Button></V2Stack></V2Section>
