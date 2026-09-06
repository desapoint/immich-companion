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
  import type { AssetRecord, DuplicateDecision } from '../data/contracts';

  let { open, group, assetIds=[], member=$bindable(0), reference=$bindable(0), decisions=$bindable<Record<string,DuplicateDecision>>({}), onclose }: { open:boolean; group:number; assetIds?:string[]; member?:number; reference?:number; decisions?:Record<string,DuplicateDecision>; onclose:()=>void }=$props();
  let mode=$state<ComparisonMode>('Side by side'),split=$state(50),opacity=$state(50),diffHue=$state(190),diffContrast=$state(180),diffBinary=$state(true),assets=$state<AssetRecord[]>([]),memberData=$state<ComparisonMemberData[]>([]),decisionOptions=$state<DuplicateDecision[]>([]),differenceImage=$state(''),differenceRequest=0;
  const emptyData:ComparisonMemberData={name:'Unknown asset',source:'—',size:'—',sizeNum:0,dims:'—',taken:'—',codec:'Unknown type',library:'—',uploaded:'—',similarity:'0.0'};
  const videoPlaceholder='data:image/svg+xml,'+encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="960" height="640" viewBox="0 0 960 640"><rect width="960" height="640" fill="#222831"/><circle cx="480" cy="320" r="82" fill="#ffffff22"/><path d="M455 270 545 320 455 370Z" fill="white"/><text x="480" y="450" text-anchor="middle" fill="white" font-family="sans-serif" font-size="34">Video asset</text></svg>`);
  function visualSource(asset:AssetRecord|undefined,full=true){if(!asset)return'';if(asset.asset_type==='VIDEO')return videoPlaceholder;return full?libraryData.media.view(asset).url:libraryData.media.thumbnail(asset).url}
  const activeCount=$derived(assetIds.length),selectedAsset=$derived(assets.find((asset)=>asset.id===assetIds[member])),referenceAsset=$derived(assets.find((asset)=>asset.id===assetIds[reference])),selectedData=$derived(memberData[member]??emptyData),referenceData=$derived(memberData[reference]??emptyData),selectedImage=$derived(visualSource(selectedAsset)),referenceImage=$derived(visualSource(referenceAsset)),decisionKey=$derived(assetIds[member]??'');
  $effect(()=>{const ids=[...assetIds],currentGroup=group;void(async()=>{assets=await libraryData.assets.getMany(ids);memberData=await Promise.all(ids.map((id,index)=>comparisonMemberData(id,currentGroup,index)))})()});
  $effect(()=>{if(open&&!decisionOptions.length)void(async()=>decisionOptions=(await libraryData.duplicates.capabilities()).decisions)()});
  $effect(()=>{
    const selected=selectedAsset,referenceValue=referenceAsset,hue=diffHue,contrast=diffContrast,binary=diffBinary;
    const request=++differenceRequest;
    if(!selected||!referenceValue||selected.asset_type!=='IMAGE'||referenceValue.asset_type!=='IMAGE'){differenceImage=videoPlaceholder;return}
    void(async()=>{try{const resource=await libraryData.media.difference(selected,referenceValue,{hue,contrast,binary});if(request===differenceRequest)differenceImage=resource.url}catch{if(request===differenceRequest)differenceImage=selectedImage}})();
  });
  function prev(){if(activeCount)member=(member-1+activeCount)%activeCount}
  function next(){if(activeCount)member=(member+1)%activeCount}
  function setDecision(decision:DuplicateDecision){if(decisionKey&&decisionOptions.includes(decision))decisions={...decisions,[decisionKey]:decision}}
</script>

<V2ViewerShell {open} title="Duplicate comparison" kind="compare" {onclose}>
  {#snippet header()}<V2Inline gap="sm" wrap={true}><V2Button onclick={onclose}>✕</V2Button><b>Duplicate comparison</b><V2Badge text={`Group ${group}`}/><V2Badge text={`${activeCount} images`}/></V2Inline><V2Inline gap="sm" wrap={true}><V2Button disabled={!activeCount} onclick={prev}>← Previous</V2Button><V2Button disabled={!activeCount} onclick={next}>Next →</V2Button><V2Button disabled={!selectedAsset} onclick={()=>reference=member}>Set as reference</V2Button></V2Inline>{/snippet}
  <div class="v2-compare-main"><section class="v2-compare-visual"><V2ImageComparison selectedSrc={selectedImage} referenceSrc={referenceImage} differenceSrc={differenceImage||selectedImage} selectedLabel={selectedData.name} referenceLabel={referenceData.name} bind:mode bind:opacity bind:split bind:diffHue bind:diffContrast bind:diffBinary/>
    <div class="v2-filmstrip">{#each assetIds as assetId,index}{@const asset=assets.find((candidate)=>candidate.id===assetId)}{@const data=memberData[index]??emptyData}<button class="v2-thumb" class:active={index===member} class:reference={index===reference} onclick={()=>member=index}>{#if asset}<img src={visualSource(asset,false)} alt={data.name} loading="lazy" decoding="async">{/if}<small>{data.name}</small><small class="v2-muted">{data.size} · {data.similarity}%</small></button>{/each}</div>
  </section><aside class="v2-compare-data"><V2Section title="Quick comparison"><V2Card><V2Stack gap="sm"><V2Inline justify="between"><span>Visual similarity</span><b>{selectedData.similarity}%</b></V2Inline><V2Inline justify="between"><span>File size difference</span><b>{selectedData.sizeNum-referenceData.sizeNum>=0?'+':''}{(selectedData.sizeNum-referenceData.sizeNum).toFixed(1)} MB</b></V2Inline><V2Inline justify="between"><span>Resolution</span><b>{selectedData.dims===referenceData.dims?'Same':'Different'}</b></V2Inline><V2Inline justify="between"><span>Difference source</span><V2Badge tone="ok" text="Displayed pixels"/></V2Inline></V2Stack></V2Card></V2Section><V2Section title="Metadata side by side"><div class="v2-compare-grid"><b>Selected</b><b>Reference</b><span>{selectedData.name}</span><span>{referenceData.name}</span><span>{selectedData.codec}</span><span>{referenceData.codec}</span><span>{selectedData.size}</span><span>{referenceData.size}</span><span>{selectedData.dims}</span><span>{referenceData.dims}</span><span>{selectedData.taken}</span><span>{referenceData.taken}</span><span>{selectedData.library}</span><span>{referenceData.library}</span><span>{selectedData.uploaded}</span><span>{referenceData.uploaded}</span></div></V2Section></aside></div>
  {#snippet footer()}<span><b>{selectedData.name}</b> <span class="v2-small v2-muted">Choose disposition</span></span><V2Inline gap="sm" wrap={true}>{#each decisionOptions as decision}<V2Button active={decisions[decisionKey]===decision} onclick={()=>setDecision(decision)}>{decision[0].toUpperCase()+decision.slice(1)}</V2Button>{/each}</V2Inline>{/snippet}
</V2ViewerShell>
