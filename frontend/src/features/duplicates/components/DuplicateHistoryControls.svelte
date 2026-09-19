<script lang="ts">
  import SelectField from '../../../lib/components/ui/SelectField.svelte';
  import V2Button from '../../../lib/components/ui/Button.svelte';
  import V2Section from '../../../lib/components/layout/Section.svelte';
  import V2Stack from '../../../lib/components/layout/Stack.svelte';

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
