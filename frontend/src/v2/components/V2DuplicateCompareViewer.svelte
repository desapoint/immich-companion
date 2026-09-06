<script lang="ts">
  import V2Badge from './V2Badge.svelte';
  import V2Button from './V2Button.svelte';
  import V2Card from './V2Card.svelte';
  import V2ImageComparison, { type ComparisonMode } from './V2ImageComparison.svelte';
  import V2Inline from './V2Inline.svelte';
  import V2Section from './V2Section.svelte';
  import V2Stack from './V2Stack.svelte';
  import V2ViewerShell from './V2ViewerShell.svelte';
  import { comparisonMemberData, demoDifferenceMask } from '../demo/duplicateVisuals';
  import { demoAssetFullSize, demoAssetPreview } from '../demo/demoAssetVisuals';
  import { demoAssetState } from '../demo/demoAssetState.svelte';

  let {
    open,
    group,
    assetIds = [],
    member = $bindable(0),
    reference = $bindable(0),
    decisions = $bindable<Record<string, string>>({}),
    onclose,
  }: {
    open: boolean;
    group: number;
    assetIds?: string[];
    member?: number;
    reference?: number;
    decisions?: Record<string, string>;
    onclose: () => void;
  } = $props();

  let mode=$state<ComparisonMode>('Side by side'),split=$state(50),opacity=$state(50),diffHue=$state(190),diffContrast=$state(180),diffBinary=$state(true);
  const activeCount=$derived(assetIds.length);
  const selectedAsset=$derived((demoAssetState.revision,demoAssetState.assets.find((asset)=>asset.id===assetIds[member])));
  const referenceAsset=$derived((demoAssetState.revision,demoAssetState.assets.find((asset)=>asset.id===assetIds[reference])));
  const selectedData=$derived((demoAssetState.revision,comparisonMemberData(assetIds[member]??'',group,member)));
  const referenceData=$derived((demoAssetState.revision,comparisonMemberData(assetIds[reference]??'',group,reference)));
  const selectedImage=$derived(selectedAsset?demoAssetFullSize(selectedAsset):'');
  const referenceImage=$derived(referenceAsset?demoAssetFullSize(referenceAsset):'');
  const differenceImage=$derived(demoDifferenceMask(group,member,reference,diffHue,diffContrast,diffBinary));
  const decisionKey=$derived(assetIds[member]??'');

  function prev(){if(activeCount)member=(member-1+activeCount)%activeCount}
  function next(){if(activeCount)member=(member+1)%activeCount}
  function setDecision(decision:string){if(decisionKey)decisions={...decisions,[decisionKey]:decision}}
</script>

<V2ViewerShell {open} title="Duplicate comparison" kind="compare" {onclose}>
  {#snippet header()}<V2Inline gap="sm" wrap={true}><V2Button onclick={onclose}>✕</V2Button><b>Duplicate comparison</b><V2Badge text={`Group ${group}`}/><V2Badge text={`${activeCount} images`}/></V2Inline><V2Inline gap="sm" wrap={true}><V2Button disabled={!activeCount} onclick={prev}>← Previous</V2Button><V2Button disabled={!activeCount} onclick={next}>Next →</V2Button><V2Button disabled={!selectedAsset} onclick={()=>reference=member}>Set as reference</V2Button></V2Inline>{/snippet}

  <div class="v2-compare-main"><section class="v2-compare-visual"><V2ImageComparison selectedSrc={selectedImage} referenceSrc={referenceImage} differenceSrc={differenceImage} selectedLabel={selectedData.name} referenceLabel={referenceData.name} bind:mode bind:opacity bind:split bind:diffHue bind:diffContrast bind:diffBinary/>
    <div class="v2-filmstrip">{#each assetIds as assetId,index}{@const asset=demoAssetState.assets.find((candidate)=>candidate.id===assetId)}{@const data=comparisonMemberData(assetId,group,index)}<button class="v2-thumb" class:active={index===member} class:reference={index===reference} onclick={()=>member=index}>{#if asset}<img src={demoAssetPreview(asset)} alt={data.name} loading="lazy" decoding="async">{/if}<small>{data.name}</small><small class="v2-muted">{data.size} · {data.similarity}%</small></button>{/each}</div>
  </section><aside class="v2-compare-data">
    <V2Section title="Quick comparison"><V2Card><V2Stack gap="sm"><V2Inline justify="between"><span>Visual similarity</span><b>{selectedData.similarity}%</b></V2Inline><V2Inline justify="between"><span>File size difference</span><b>{selectedData.sizeNum-referenceData.sizeNum>=0?'+':''}{(selectedData.sizeNum-referenceData.sizeNum).toFixed(1)} MB</b></V2Inline><V2Inline justify="between"><span>Resolution</span><b>{selectedData.dims===referenceData.dims?'Same':'Different'}</b></V2Inline><V2Inline justify="between"><span>Shared state</span><V2Badge tone="ok" text="Live demo assets"/></V2Inline></V2Stack></V2Card></V2Section>
    <V2Section title="Metadata side by side"><div class="v2-compare-grid"><b>Selected</b><b>Reference</b><span>{selectedData.name}</span><span>{referenceData.name}</span><span>{selectedData.codec}</span><span>{referenceData.codec}</span><span>{selectedData.size}</span><span>{referenceData.size}</span><span>{selectedData.dims}</span><span>{referenceData.dims}</span><span>{selectedData.taken}</span><span>{referenceData.taken}</span><span>{selectedData.library}</span><span>{referenceData.library}</span><span>{selectedData.uploaded}</span><span>{referenceData.uploaded}</span></div></V2Section>
    <V2Section title="Decision context"><V2Card><V2Stack gap="sm"><b>Decisions target real asset IDs.</b><span class="v2-small v2-muted">All duplicate metadata except similarity is derived from the shared demo asset record.</span></V2Stack></V2Card></V2Section>
  </aside></div>

  {#snippet footer()}<span><b>{selectedData.name}</b> <span class="v2-small v2-muted">Choose disposition</span></span><V2Inline gap="sm" wrap={true}>{#each ['keep','delete','stack'] as decision}<V2Button active={decisions[decisionKey]===decision} onclick={()=>setDecision(decision)}>{decision[0].toUpperCase()+decision.slice(1)}</V2Button>{/each}</V2Inline>{/snippet}
</V2ViewerShell>
