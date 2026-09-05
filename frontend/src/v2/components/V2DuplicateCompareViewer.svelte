<script lang="ts">
  import V2Badge from './V2Badge.svelte';
  import V2Button from './V2Button.svelte';
  import V2Card from './V2Card.svelte';
  import V2ImageComparison, { type ComparisonMode } from './V2ImageComparison.svelte';
  import V2Inline from './V2Inline.svelte';
  import V2Section from './V2Section.svelte';
  import V2Stack from './V2Stack.svelte';
  import V2ViewerShell from './V2ViewerShell.svelte';
  import { comparisonMemberData, demoCompareImage, demoDifferenceMask } from '../demo/duplicateVisuals';

  let {
    open,
    group,
    member = $bindable(0),
    reference = $bindable(0),
    activeCount,
    decisions = $bindable<Record<string, string>>({}),
    onclose,
  }: {
    open: boolean;
    group: number;
    member?: number;
    reference?: number;
    activeCount: number;
    decisions?: Record<string, string>;
    onclose: () => void;
  } = $props();

  let mode = $state<ComparisonMode>('Side by side');
  let split = $state(50);
  let opacity = $state(50);
  let diffHue = $state(190);
  let diffContrast = $state(180);
  let diffBinary = $state(true);

  const selectedData = $derived(comparisonMemberData(group, member));
  const referenceData = $derived(comparisonMemberData(group, reference));
  const selectedImage = $derived(demoCompareImage(group, member));
  const referenceImage = $derived(demoCompareImage(group, reference));
  const differenceImage = $derived(demoDifferenceMask(group, member, reference, diffHue, diffContrast, diffBinary));
  const decisionKey = $derived(`${group}:${member}`);

  function prev(): void {
    member = (member - 1 + activeCount) % activeCount;
  }

  function next(): void {
    member = (member + 1) % activeCount;
  }

  function setDecision(decision: string): void {
    decisions = { ...decisions, [decisionKey]: decision };
  }
</script>

<V2ViewerShell {open} title="Duplicate comparison" kind="compare" {onclose}>
  {#snippet header()}
    <V2Inline gap="sm" wrap={true}>
      <V2Button onclick={onclose}>✕</V2Button>
      <b>Duplicate comparison</b>
      <V2Badge text={`Group ${group}`} />
      <V2Badge text={`${activeCount} images`} />
    </V2Inline>
    <V2Inline gap="sm" wrap={true}>
      <V2Button onclick={prev}>← Previous</V2Button>
      <V2Button onclick={next}>Next →</V2Button>
      <V2Button onclick={() => reference = member}>Set as reference</V2Button>
      <V2Button onclick={() => window.alert('Mock integrity analysis: current asset is healthy.')}>Analyze integrity</V2Button>
    </V2Inline>
  {/snippet}

  <div class="v2-compare-main">
    <section class="v2-compare-visual">
      <V2ImageComparison
        selectedSrc={selectedImage}
        referenceSrc={referenceImage}
        differenceSrc={differenceImage}
        selectedLabel="Selected image"
        referenceLabel="Reference"
        bind:mode
        bind:opacity
        bind:split
        bind:diffHue
        bind:diffContrast
        bind:diffBinary
      />

      <div class="v2-filmstrip">
        {#each Array.from({ length: activeCount }, (_, index) => index) as index}
          {@const data = comparisonMemberData(group, index)}
          <button class="v2-thumb" class:active={index === member} class:reference={index === reference} onclick={() => member = index}>
            <img src={demoCompareImage(group, index)} alt={`Member ${index + 1} example`}>
            <small>Member {index + 1}</small>
            <small class="v2-muted">{data.size} · {data.similarity}%</small>
          </button>
        {/each}
      </div>
    </section>

    <aside class="v2-compare-data">
      <V2Section title="Quick comparison">
        <V2Card>
          <V2Stack gap="sm">
            <V2Inline justify="between"><span>Visual similarity</span><b>{selectedData.similarity}%</b></V2Inline>
            <V2Inline justify="between"><span>File size difference</span><b>{selectedData.sizeNum - referenceData.sizeNum >= 0 ? '+' : ''}{(selectedData.sizeNum - referenceData.sizeNum).toFixed(1)} MB</b></V2Inline>
            <V2Inline justify="between"><span>Resolution</span><b>{selectedData.dims === referenceData.dims ? 'Same' : 'Different'}</b></V2Inline>
            <V2Inline justify="between"><span>Integrity</span><V2Badge tone="ok" text="Healthy" /></V2Inline>
          </V2Stack>
        </V2Card>
      </V2Section>
      <V2Section title="Metadata side by side">
        <div class="v2-compare-grid">
          <b>Selected</b><b>Reference</b>
          <span>{selectedData.name}</span><span>{referenceData.name}</span>
          <span>{selectedData.source}</span><span>{referenceData.source}</span>
          <span class:changed={selectedData.size !== referenceData.size}>{selectedData.size}</span><span class:changed={selectedData.size !== referenceData.size}>{referenceData.size}</span>
          <span class:changed={selectedData.dims !== referenceData.dims}>{selectedData.dims}</span><span class:changed={selectedData.dims !== referenceData.dims}>{referenceData.dims}</span>
          <span class:changed={selectedData.taken !== referenceData.taken}>{selectedData.taken}</span><span class:changed={selectedData.taken !== referenceData.taken}>{referenceData.taken}</span>
          <span>{selectedData.codec}</span><span>{referenceData.codec}</span>
          <span>{selectedData.library}</span><span>{referenceData.library}</span>
          <span class:changed={selectedData.uploaded !== referenceData.uploaded}>{selectedData.uploaded}</span><span class:changed={selectedData.uploaded !== referenceData.uploaded}>{referenceData.uploaded}</span>
        </div>
      </V2Section>
      <V2Section title="Decision context">
        <V2Card>
          <V2Stack gap="sm">
            <b>Highlighted cells differ.</b>
            <span class="v2-small v2-muted">Use image evidence and metadata together. Similarity alone does not authorize deletion.</span>
          </V2Stack>
        </V2Card>
      </V2Section>
    </aside>
  </div>

  {#snippet footer()}
    <span><b>Member {member + 1}</b> <span class="v2-small v2-muted">Choose disposition for this member</span></span>
    <V2Inline gap="sm" wrap={true}>
      {#each ['keep', 'delete', 'stack'] as decision}
        <V2Button active={decisions[decisionKey] === decision} onclick={() => setDecision(decision)}>{decision[0].toUpperCase() + decision.slice(1)}</V2Button>
      {/each}
      <V2Button disabled={decisions[decisionKey] !== 'stack'} onclick={() => window.alert(`Member ${member + 1} set as stack primary in this mockup.`)}>Set stack primary</V2Button>
    </V2Inline>
  {/snippet}
</V2ViewerShell>
