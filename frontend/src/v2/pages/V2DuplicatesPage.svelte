<script lang="ts">
  import SelectField from '../components/SelectField.svelte';
  import V2Badge from '../components/V2Badge.svelte';
  import V2Button from '../components/V2Button.svelte';
  import V2Card from '../components/V2Card.svelte';
  import V2Checkbox from '../components/V2Checkbox.svelte';
  import V2DuplicateCompareViewer from '../components/V2DuplicateCompareViewer.svelte';
  import V2Field from '../components/V2Field.svelte';
  import V2Inline from '../components/V2Inline.svelte';
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2Section from '../components/V2Section.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import V2Tabs from '../components/V2Tabs.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';
  import V2Zone from '../components/V2Zone.svelte';
  import { demoCompareImage } from '../demo/duplicateVisuals';

  type DuplicateTab = 'Review' | 'Rules & discovery' | 'Resolution history';

  let tab = $state<DuplicateTab>('Review');
  let compare = $state(false);
  let group = $state(1);
  let member = $state(0);
  let reference = $state(0);
  let decisions = $state<Record<string, string>>({});

  const groups = [
    { id: 1, count: 2, state: 'Actionable', tone: 'ok', kind: 'Exact pair' },
    { id: 2, count: 2, state: 'Needs review', tone: 'warn', kind: 'Similar pair' },
    { id: 3, count: 3, state: 'Actionable', tone: 'ok', kind: 'Exact group' },
    { id: 4, count: 5, state: 'Needs decisions', tone: 'warn', kind: 'Mixed group' },
    { id: 5, count: 6, state: 'Actionable', tone: 'ok', kind: 'Similarity cluster' },
    { id: 6, count: 9, state: 'Blocked', tone: 'bad', kind: 'Large cluster' },
    { id: 7, count: 10, state: 'Needs review', tone: 'warn', kind: 'Large similarity cluster' },
  ] as const;

  const activeCount = $derived(groups.find((item) => item.id === group)?.count ?? 2);

  function openCompare(nextGroup: number, index: number): void {
    group = nextGroup;
    member = index;
    reference = 0;
    compare = true;
  }
</script>

<V2PageLayout title="Duplicates" description="Review exact and similarity duplicate groups, tune discovery rules, and inspect resolution history.">
  {#snippet headerActions()}
    <V2Inline gap="sm"><V2Button>Scan similar</V2Button><V2Button variant="primary">Review actions</V2Button></V2Inline>
  {/snippet}
  {#snippet tabs()}
    <V2Tabs items={['Review', 'Rules & discovery', 'Resolution history']} active={tab} ariaLabel="Duplicate sections" onselect={(value) => tab = value as DuplicateTab} />
  {/snippet}

  {#snippet context()}
    <V2Zone>
      {#if tab === 'Review'}
        <V2Section title="Review filter"><V2Stack gap="sm"><SelectField id="duplicate-review-filter" label="Group state" options={['All groups', 'Needs review', 'Auto-ready', 'Blocked']} /><V2Button>Select auto-ready</V2Button></V2Stack></V2Section>
        <V2Section title="Similarity"><V2Field label="Threshold" value="82" /><V2Inline gap="sm"><V2Button>Scan again</V2Button><V2Button>Cancel scan</V2Button></V2Inline><span class="v2-small v2-muted">Similarity is review evidence only.</span></V2Section>
        <V2Section title="Bulk preset"><V2Stack gap="sm"><V2Button>Keep all copies</V2Button><V2Button>Mark all for deletion</V2Button><V2Button>Stack each group</V2Button></V2Stack></V2Section>
      {:else if tab === 'Rules & discovery'}
        <V2Section title="Discovery"><V2Stack gap="sm"><V2Field label="Similarity threshold" value="82" /><V2Checkbox label="Include visually similar assets" checked={true} /><V2Checkbox label="Include exact file matches" checked={true} /><V2Button variant="primary">Run discovery</V2Button></V2Stack></V2Section>
      {:else}
        <V2Section title="History filter"><V2Stack gap="sm"><SelectField id="duplicate-history-range" label="Range" options={['Last 30 days', 'Last 90 days', 'All history']} /><V2Button>Export history</V2Button></V2Stack></V2Section>
      {/if}
    </V2Zone>
  {/snippet}

  <V2Zone>
    {#if tab === 'Review'}
      <V2Toolbar><V2Badge text="18 groups" /><V2Badge tone="ok" text="7 ready" /><V2Badge tone="warn" text="3 blocked" />{#snippet actions()}<V2Button onclick={() => decisions = {}}>Clear decisions</V2Button>{/snippet}</V2Toolbar>
      {#each groups as item}
        <V2Card class="v2-duplicate-group">
          <V2Stack gap="md">
            <V2Inline justify="between" align="start" wrap={true}>
              <V2Inline gap="sm" wrap={true}><input type="checkbox"><b>Group {item.id}</b><V2Badge text={`${item.count} images`} /><V2Badge text={item.kind} /><V2Badge tone={item.tone} text={item.state} /></V2Inline>
              <V2Inline gap="sm" wrap={true}><V2Button>Apply preset</V2Button><V2Button onclick={() => openCompare(item.id, 0)}>Compare</V2Button></V2Inline>
            </V2Inline>
            <div class="v2-duplicate-members">
              {#each Array.from({ length: item.count }, (_, index) => index) as index}
                <div class="v2-duplicate-member">
                  <button class="v2-duplicate-image" onclick={() => openCompare(item.id, index)}>
                    <img src={demoCompareImage(item.id, index)} alt={`Duplicate member ${index + 1}`}>
                    <span class="v2-duplicate-image-meta"><b>Member {index + 1}</b><small>{index === 0 ? 'Suggested keeper' : index % 3 === 0 ? 'External' : 'Immich'}</small></span>
                  </button>
                  <div class="v2-duplicate-actions"><V2Button variant={index === 0 ? 'primary' : 'default'}>Keep</V2Button><V2Button>Delete</V2Button><V2Button>Stack</V2Button></div>
                </div>
              {/each}
            </div>
          </V2Stack>
        </V2Card>
      {/each}
    {:else if tab === 'Rules & discovery'}
      <V2Toolbar sticky={false}><b>Rules & discovery</b><V2Badge tone="ok" text="Demo configuration" /></V2Toolbar>
      <div class="v2-setting-grid">
        <V2Card title="Exact matches"><V2Stack gap="sm"><V2Checkbox label="Detect identical file hashes" checked={true} /><V2Checkbox label="Group exact copies automatically" checked={true} /><V2Button>Save exact-match rules</V2Button></V2Stack></V2Card>
        <V2Card title="Similarity discovery"><V2Stack gap="sm"><V2Field label="Minimum similarity" value="82" /><V2Field label="Maximum candidates per asset" value="20" /><V2Button variant="primary">Save discovery rules</V2Button></V2Stack></V2Card>
      </div>
    {:else}
      <V2Toolbar sticky={false}><V2Badge text="12 resolutions" />{#snippet actions()}<V2Button>Export</V2Button>{/snippet}</V2Toolbar>
      <V2Stack gap="sm">
        {#each [['Today 09:42', 'Group 1', 'Kept 1 · deleted 1'], ['Yesterday 18:10', 'Group 3', 'Stacked 3 assets'], ['Aug 30 14:22', 'Group 5', 'Reviewed · no action']] as row}
          <V2Card><V2Inline justify="between" wrap={true}><V2Stack gap="xs"><b>{row[1]}</b><span class="v2-small v2-muted">{row[0]}</span></V2Stack><span>{row[2]}</span></V2Inline></V2Card>
        {/each}
      </V2Stack>
    {/if}
  </V2Zone>

  {#snippet inspector()}
    <V2Zone>
      {#if tab === 'Review'}
        <V2Section title="Batch readiness"><V2Card><V2Stack gap="sm"><b>2 selected groups</b><span class="v2-small v2-muted">All selected groups must pass actionability guards before execution.</span><V2Inline gap="sm"><V2Badge tone="ok" text="2 ready" /><V2Badge text="0 blocked" /></V2Inline></V2Stack></V2Card></V2Section>
        <V2Section title="Current group"><V2Card><span class="v2-small">Keeper: Member 1<br>Delete: 1<br>Stack: 0<br>Online: all</span></V2Card></V2Section>
      {:else if tab === 'Rules & discovery'}
        <V2Section title="Discovery status"><V2Card><V2Stack gap="sm"><V2Badge tone="ok" text="Rules valid" /><span class="v2-small v2-muted">These controls are demo-only until discovery settings are integrated.</span></V2Stack></V2Card></V2Section>
      {:else}
        <V2Section title="History summary"><V2Card><V2Stack gap="sm"><b>12 resolved groups</b><span class="v2-small v2-muted">8 deletions · 3 stacks · 1 no-action review</span></V2Stack></V2Card></V2Section>
      {/if}
    </V2Zone>
  {/snippet}
</V2PageLayout>

<V2DuplicateCompareViewer
  open={compare}
  {group}
  {activeCount}
  bind:member
  bind:reference
  bind:decisions
  onclose={() => compare = false}
/>
