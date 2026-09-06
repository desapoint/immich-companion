<script lang="ts">
  import V2Badge from './V2Badge.svelte';
  import V2Button from './V2Button.svelte';
  import V2Card from './V2Card.svelte';
  import V2ImageComparison, { type ComparisonMode } from './V2ImageComparison.svelte';
  import V2Inline from './V2Inline.svelte';
  import V2Section from './V2Section.svelte';
  import V2Stack from './V2Stack.svelte';
  import V2ViewerShell from './V2ViewerShell.svelte';
  import { demoCompareImage, demoDifferenceMask } from '../demo/duplicateVisuals';
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
  const selectedImage=$derived(demoCompareImage(group,member)),referenceImage=$derived(demoCompareImage(group,reference));
  const differenceImage=$derived(demoDifferenceMask(group,member,reference,diffHue,diffContrast,diffBinary));
  const decisionKey=$derived(assetIds[member]??'');
  const selectedSize=$derived((selectedAsset?.file_size_bytes??0)/1_048_576),referenceSize=$derived((referenceAsset?.file_size_bytes??0)/1_048_576);

  function prev(){if(activeCount)member=(member-1+activeCount)%activeCount}
  function next(){if(activeCount)member=(member+1)%activeCount}
  function setDecision(decision:string){if(decisionKey)decisions={...decisions,[decisionKey]:decision}}
</script>

<V2ViewerShell {open} title="Duplicate comparison" kind="compare" {onclose}>
  {#snippet header()}<V2Inline gap="sm" wrap={true}><V2Button onclick={onclose}>✕</V2Button><b>Duplicate comparison</b><V2Badge text={`Group ${group}`}/><V2Badge text={`${activeCount} images`}/></V2Inline><V2Inline gap="sm" wrap={true}><V2Button disabled={!activeCount} onclick={prev}>← Previous</V2Button><V2Button disabled={!activeCount} onclick={next}>Next →</V2Button><V2Button disabled={!selectedAsset} onclick={()=>reference=member}>Set as reference</V2Button></V2Inline>{/snippet}

  <div class="v2-compare-main"><section class="v2-compare-visual"><V2ImageComparison selectedSrc={selectedImage} referenceSrc={referenceImage} differenceSrc={differenceImage} selectedLabel={selectedAsset?.original_file_name??'Selected image'} referenceLabel={referenceAsset?.original_file_name??'Reference'} bind:mode bind:opacity bind:split bind:diffHue bind:diffContrast bind:diffBinary/>
    <div class="v2-filmstrip">{#each assetIds as assetId,index}{@const asset=demoAssetState.assets.find((candidate)=>candidate.id===assetId)}<button class="v2-thumb" class:active={index===member} class:reference={index===reference} onclick={()=>member=index}><img src={demoCompareImage(group,index)} alt={asset?.original_file_name??`Member ${index+1}`}><small>{asset?.original_file_name??`Member ${index+1}`}</small><small class="v2-muted">{asset?.file_size_bytes?`${(asset.file_size_bytes/1_048_576).toFixed(1)} MB`:'—'}</small></button>{/each}</div>
  </section><aside class="v2-compare-data">
    <V2Section title="Quick comparison"><V2Card><V2Stack gap="sm"><V2Inline justify="between"><span>File size difference</span><b>{selectedSize-referenceSize>=0?'+':''}{(selectedSize-referenceSize).toFixed(1)} MB</b></V2Inline><V2Inline justify="between"><span>Resolution</span><b>{selectedAsset?.width===referenceAsset?.width&&selectedAsset?.height===referenceAsset?.height?'Same':'Different'}</b></V2Inline><V2Inline justify="between"><span>Shared state</span><V2Badge tone="ok" text="Live demo assets"/></V2Inline></V2Stack></V2Card></V2Section>
    <V2Section title="Metadata side by side"><div class="v2-compare-grid"><b>Selected</b><b>Reference</b><span>{selectedAsset?.original_file_name??'—'}</span><span>{referenceAsset?.original_file_name??'—'}</span><span>{selectedAsset?.original_mime_type??'—'}</span><span>{referenceAsset?.original_mime_type??'—'}</span><span>{selectedAsset?.width??'—'} × {selectedAsset?.height??'—'}</span><span>{referenceAsset?.width??'—'} × {referenceAsset?.height??'—'}</span><span>{selectedAsset?new Date(selectedAsset.file_created_at).toLocaleString():'—'}</span><span>{referenceAsset?new Date(referenceAsset.file_created_at).toLocaleString():'—'}</span><span>{selectedAsset?.library_id?'External library':'Default library'}</span><span>{referenceAsset?.library_id?'External library':'Default library'}</span><span>{selectedAsset?.tags.length??0} tags</span><span>{referenceAsset?.tags.length??0} tags</span></div></V2Section>
    <V2Section title="Decision context"><V2Card><V2Stack gap="sm"><b>Decisions target real asset IDs.</b><span class="v2-small v2-muted">Review actions on the Duplicates page apply delete and stack changes to the same shared demo assets visible elsewhere.</span></V2Stack></V2Card></V2Section>
  </aside></div>

  {#snippet footer()}<span><b>{selectedAsset?.original_file_name??`Member ${member+1}`}</b> <span class="v2-small v2-muted">Choose disposition</span></span><V2Inline gap="sm" wrap={true}>{#each ['keep','delete','stack'] as decision}<V2Button active={decisions[decisionKey]===decision} onclick={()=>setDecision(decision)}>{decision[0].toUpperCase()+decision.slice(1)}</V2Button>{/each}</V2Inline>{/snippet}
</V2ViewerShell>
