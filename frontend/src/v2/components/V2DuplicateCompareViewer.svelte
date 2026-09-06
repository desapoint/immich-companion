<script lang="ts">
  import V2Badge from './V2Badge.svelte';
  import V2Button from './V2Button.svelte';
  import V2Card from './V2Card.svelte';
  import V2ImageComparison, { type ComparisonMode } from './V2ImageComparison.svelte';
  import V2Inline from './V2Inline.svelte';
  import V2Section from './V2Section.svelte';
  import V2Stack from './V2Stack.svelte';
  import V2ViewerShell from './V2ViewerShell.svelte';
  import { comparisonMemberData, type ComparisonMemberData } from '../data/duplicateMember';
  import { libraryData } from '../data/currentDataSource.svelte';
  import type { AssetRecord } from '../data/contracts';

  let { open, group, assetIds=[], member=$bindable(0), reference=$bindable(0), decisions=$bindable<Record<string,string>>({}), onclose }: { open:boolean; group:number; assetIds?:string[]; member?:number; reference?:number; decisions?:Record<string,string>; onclose:()=>void }=$props();
  let mode=$state<ComparisonMode>('Side by side'),split=$state(50),opacity=$state(50),diffHue=$state(190),diffContrast=$state(180),diffBinary=$state(true),assets=$state<AssetRecord[]>([]),memberData=$state<ComparisonMemberData[]>([]);
  const emptyData:ComparisonMemberData={name:'Unknown asset',source:'—',size:'—',sizeNum:0,dims:'—',taken:'—',codec:'Unknown type',library:'—',uploaded:'—',similarity:'0.0'};
  const activeCount=$derived(assetIds.length),selectedAsset=$derived(assets.find((asset)=>asset.id===assetIds[member])),referenceAsset=$derived(assets.find((asset)=>asset.id===assetIds[reference])),selectedData=$derived(memberData[member]??emptyData),referenceData=$derived(memberData[reference]??emptyData),selectedImage=$derived(selectedAsset?libraryData.media.fullSize(selectedAsset):''),referenceImage=$derived(referenceAsset?libraryData.media.fullSize(referenceAsset):''),differenceImage=$derived(selectedAsset&&referenceAsset?libraryData.media.difference(selectedAsset,referenceAsset,{hue:diffHue,contrast:diffContrast,binary:diffBinary}):''),decisionKey=$derived(assetIds[member]??'');
  $effect(()=>{const ids=[...assetIds],currentGroup=group;void(async()=>{assets=await libraryData.assets.getMany(ids);memberData=await Promise.all(ids.map((id,index)=>comparisonMemberData(id,currentGroup,index)))})()});
  function prev(){if(activeCount)member=(member-1+activeCount)%activeCount}
  function next(){if(activeCount)member=(member+1)%activeCount}
  function setDecision(decision:string){if(decisionKey)decisions={...decisions,[decisionKey]:decision}}
</script>

<V2ViewerShell {open} title="Duplicate comparison" kind="compare" {onclose}>
  {#snippet header()}<V2Inline gap="sm" wrap={true}><V2Button onclick={onclose}>✕</V2Button><b>Duplicate comparison</b><V2Badge text={`Group ${group}`}/><V2Badge text={`${activeCount} images`}/></V2Inline><V2Inline gap="sm" wrap={true}><V2Button disabled={!activeCount} onclick={prev}>← Previous</V2Button><V2Button disabled={!activeCount} onclick={next}>Next →</V2Button><V2Button disabled={!selectedAsset} onclick={()=>reference=member}>Set as reference</V2Button></V2Inline>{/snippet}
  <div class="v2-compare-main"><section class="v2-compare-visual"><V2ImageComparison selectedSrc={selectedImage} referenceSrc={referenceImage} differenceSrc={differenceImage} selectedLabel={selectedData.name} referenceLabel={referenceData.name} bind:mode bind:opacity bind:split bind:diffHue bind:diffContrast bind:diffBinary/>
    <div class="v2-filmstrip">{#each assetIds as assetId,index}{@const asset=assets.find((candidate)=>candidate.id===assetId)}{@const data=memberData[index]??emptyData}<button class="v2-thumb" class:active={index===member} class:reference={index===reference} onclick={()=>member=index}>{#if asset}<img src={libraryData.media.thumbnail(asset)} alt={data.name} loading="lazy" decoding="async">{/if}<small>{data.name}</small><small class="v2-muted">{data.size} · {data.similarity}%</small></button>{/each}</div>
  </section><aside class="v2-compare-data"><V2Section title="Quick comparison"><V2Card><V2Stack gap="sm"><V2Inline justify="between"><span>Visual similarity</span><b>{selectedData.similarity}%</b></V2Inline><V2Inline justify="between"><span>File size difference</span><b>{selectedData.sizeNum-referenceData.sizeNum>=0?'+':''}{(selectedData.sizeNum-referenceData.sizeNum).toFixed(1)} MB</b></V2Inline><V2Inline justify="between"><span>Resolution</span><b>{selectedData.dims===referenceData.dims?'Same':'Different'}</b></V2Inline><V2Inline justify="between"><span>Data source</span><V2Badge tone="ok" text="Repository records"/></V2Inline></V2Stack></V2Card></V2Section><V2Section title="Metadata side by side"><div class="v2-compare-grid"><b>Selected</b><b>Reference</b><span>{selectedData.name}</span><span>{referenceData.name}</span><span>{selectedData.codec}</span><span>{referenceData.codec}</span><span>{selectedData.size}</span><span>{referenceData.size}</span><span>{selectedData.dims}</span><span>{referenceData.dims}</span><span>{selectedData.taken}</span><span>{referenceData.taken}</span><span>{selectedData.library}</span><span>{referenceData.library}</span><span>{selectedData.uploaded}</span><span>{referenceData.uploaded}</span></div></V2Section></aside></div>
  {#snippet footer()}<span><b>{selectedData.name}</b> <span class="v2-small v2-muted">Choose disposition</span></span><V2Inline gap="sm" wrap={true}>{#each ['keep','delete','stack'] as decision}<V2Button active={decisions[decisionKey]===decision} onclick={()=>setDecision(decision)}>{decision[0].toUpperCase()+decision.slice(1)}</V2Button>{/each}</V2Inline>{/snippet}
</V2ViewerShell>
