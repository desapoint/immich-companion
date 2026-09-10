<script lang="ts">
  import V2Badge from './V2Badge.svelte';
  import V2Button from './V2Button.svelte';
  import V2Card from './V2Card.svelte';
  import V2ImageComparison, { type ComparisonMode } from './V2ImageComparison.svelte';
  import V2Inline from './V2Inline.svelte';
  import V2KeyboardShortcuts, { type KeyboardShortcut } from './V2KeyboardShortcuts.svelte';
  import V2Section from './V2Section.svelte';
  import V2Stack from './V2Stack.svelte';
  import V2ViewerShell from './V2ViewerShell.svelte';
  import { comparisonMemberData, type ComparisonMemberData } from '../data/duplicateMember';
  import { duplicateKindLabel } from '../data/duplicatePresentation';
  import { libraryData } from '../data/currentDataSource.svelte';
  import type { AssetRecord, DuplicateDecision } from '../data/contracts';

  let { open, groupId, groupTitle, groupKind, assetIds=[], similarities={}, member=$bindable(0), reference=$bindable(0), decisions=$bindable<Record<string,DuplicateDecision>>({}), ondecisionchange, onreferencechange, onclose }: { open:boolean; groupId:string; groupTitle:string; groupKind:string; assetIds?:string[]; similarities?:Record<string,number>; member?:number; reference?:number; decisions?:Record<string,DuplicateDecision>; ondecisionchange?:(assetId:string,decision:DuplicateDecision)=>void; onreferencechange?:(assetId:string)=>Promise<void>; onclose:()=>void }=$props();
  const shortcuts:KeyboardShortcut[]=[
    {keys:'Esc',description:'Close comparison'},
    {keys:'←',description:'Previous group member'},
    {keys:'→',description:'Next group member'},
    {keys:'R',description:'Set current asset as reference'},
    {keys:'1',description:'Side by side'},
    {keys:'2',description:'Swipe'},
    {keys:'3',description:'Transparency'},
    {keys:'4',description:'Difference'},
  ];
  let mode=$state<ComparisonMode>('Side by side'),split=$state(50),opacity=$state(50),diffHue=$state(190),diffContrast=$state(180),diffBinary=$state(true),diffTolerance=$state(8),assets=$state<AssetRecord[]>([]),memberData=$state<ComparisonMemberData[]>([]),decisionOptions=$state<DuplicateDecision[]>([]),copiedGroupId=$state(false);
  const emptyData:ComparisonMemberData={name:'Unknown asset',source:'—',size:'—',sizeNum:0,dims:'—',taken:'—',codec:'Unknown type',library:'—',uploaded:'—',similarity:'0.0'};
  const videoPlaceholder='data:image/svg+xml,'+encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="960" height="640" viewBox="0 0 960 640"><rect width="960" height="640" fill="#222831"/><circle cx="480" cy="320" r="82" fill="#ffffff22"/><path d="M455 270 545 320 455 370Z" fill="white"/><text x="480" y="450" text-anchor="middle" fill="white" font-family="sans-serif" font-size="34">Video asset</text></svg>`);
  function visualSource(asset:AssetRecord|undefined,full=true){if(!asset)return'';if(asset.asset_type==='VIDEO')return videoPlaceholder;return full?libraryData.media.view(asset).url:libraryData.media.thumbnail(asset).url}
  const activeCount=$derived(assetIds.length),selectedAsset=$derived(assets.find((asset)=>asset.id===assetIds[member])),referenceAsset=$derived(assets.find((asset)=>asset.id===assetIds[reference])),selectedData=$derived(memberData[member]??emptyData),referenceData=$derived(memberData[reference]??emptyData),selectedImage=$derived(visualSource(selectedAsset)),referenceImage=$derived(visualSource(referenceAsset)),decisionKey=$derived(assetIds[member]??''),matchLabel=$derived(duplicateKindLabel(groupKind));
  $effect(()=>{const ids=[...assetIds],scores={...similarities};void(async()=>{assets=await libraryData.assets.getMany(ids);memberData=await Promise.all(ids.map((id)=>comparisonMemberData(id,scores[id]??0)))})()});
  $effect(()=>{if(open&&!decisionOptions.length)void(async()=>decisionOptions=(await libraryData.duplicates.capabilities()).decisions)()});
  function prev(){if(activeCount)member=(member-1+activeCount)%activeCount}
  function next(){if(activeCount)member=(member+1)%activeCount}
  function setDecision(decision:DuplicateDecision){if(decisionKey&&decisionOptions.includes(decision)){decisions={...decisions,[decisionKey]:decision};ondecisionchange?.(decisionKey,decision)}}
  async function setReference(){if(!selectedAsset)return;await onreferencechange?.(selectedAsset.id);reference=member}
  async function copyGroupId(){if(!groupId)return;try{await navigator.clipboard.writeText(groupId);copiedGroupId=true;setTimeout(()=>copiedGroupId=false,1200)}catch{copiedGroupId=false}}
  function editableTarget(target:EventTarget|null):boolean{return target instanceof Element&&Boolean(target.closest('input,textarea,select,[contenteditable="true"]'))}
  function handleShortcut(event:KeyboardEvent){
    if(!open||event.defaultPrevented||event.ctrlKey||event.metaKey||event.altKey||editableTarget(event.target))return;
    if(event.key==='ArrowLeft'&&activeCount){event.preventDefault();prev();return}
    if(event.key==='ArrowRight'&&activeCount){event.preventDefault();next();return}
    if((event.key==='r'||event.key==='R')&&selectedAsset){event.preventDefault();void setReference();return}
    const modes:Record<string,ComparisonMode>={'1':'Side by side','2':'Swipe','3':'Transparency','4':'Difference'};
    const nextMode=modes[event.key];
    if(nextMode){event.preventDefault();mode=nextMode}
  }
</script>

<svelte:window onkeydown={handleShortcut}/>

<V2ViewerShell {open} title="Duplicate comparison" kind="compare" {onclose}>
  {#snippet header()}<div class="v2-compare-header-identity"><V2Button onclick={onclose}>✕</V2Button><b class="v2-compare-group-title" title={groupTitle}>{groupTitle}</b><V2Badge text={matchLabel}/><V2Badge text={`${activeCount} images`}/></div><div class="v2-compare-header-actions"><V2Button disabled={!activeCount} onclick={prev}>← Previous</V2Button><V2Button disabled={!activeCount} onclick={next}>Next →</V2Button><V2Button disabled={!selectedAsset} onclick={()=>void setReference()}>Set as reference</V2Button><V2KeyboardShortcuts {shortcuts}/></div>{/snippet}
  <div class="v2-compare-main"><section class="v2-compare-visual"><V2ImageComparison selectedSrc={selectedImage} referenceSrc={referenceImage} selectedLabel={selectedData.name} referenceLabel={referenceData.name} bind:mode bind:opacity bind:split bind:diffHue bind:diffContrast bind:diffBinary bind:diffTolerance/>
    <div class="v2-filmstrip">{#each assetIds as assetId,index (assetId)}{@const asset=assets.find((candidate)=>candidate.id===assetId)}{@const data=memberData[index]??emptyData}<button class="v2-thumb" class:active={index===member} class:reference={index===reference} onclick={()=>member=index}>{#if asset}<img src={visualSource(asset,false)} alt={data.name} loading="lazy" decoding="async">{/if}<small>{data.name}</small><small class="v2-muted">{data.size} · {data.similarity}%</small></button>{/each}</div>
  </section><aside class="v2-compare-data"><V2Section title="Quick comparison"><V2Card><V2Stack gap="sm"><V2Inline justify="between"><span>Visual similarity</span><b>{selectedData.similarity}%</b></V2Inline><V2Inline justify="between"><span>File size difference</span><b>{selectedData.sizeNum-referenceData.sizeNum>=0?'+':''}{(selectedData.sizeNum-referenceData.sizeNum).toFixed(1)} MB</b></V2Inline><V2Inline justify="between"><span>Resolution</span><b>{selectedData.dims===referenceData.dims?'Same':'Different'}</b></V2Inline><V2Inline justify="between"><span>Difference source</span><V2Badge tone="ok" text="Layered displayed pixels"/></V2Inline></V2Stack></V2Card></V2Section><V2Section title="Group details"><V2Card><V2Stack gap="sm"><V2Inline justify="between"><span>Match type</span><b>{matchLabel}</b></V2Inline><div class="v2-technical-group"><span class="v2-small v2-muted">Technical group ID</span><code title={groupId}>{groupId}</code><V2Button disabled={!groupId} onclick={()=>void copyGroupId()}>{copiedGroupId?'Copied':'Copy ID'}</V2Button></div></V2Stack></V2Card></V2Section><V2Section title="Metadata side by side"><div class="v2-compare-grid"><b>Selected</b><b>Reference</b><span class:changed={selectedData.name!==referenceData.name}>{selectedData.name}</span><span class:changed={selectedData.name!==referenceData.name}>{referenceData.name}</span><span class:changed={selectedData.codec!==referenceData.codec}>{selectedData.codec}</span><span class:changed={selectedData.codec!==referenceData.codec}>{referenceData.codec}</span><span class:changed={selectedData.size!==referenceData.size}>{selectedData.size}</span><span class:changed={selectedData.size!==referenceData.size}>{referenceData.size}</span><span class:changed={selectedData.dims!==referenceData.dims}>{selectedData.dims}</span><span class:changed={selectedData.dims!==referenceData.dims}>{referenceData.dims}</span><span class:changed={selectedData.taken!==referenceData.taken}>{selectedData.taken}</span><span class:changed={selectedData.taken!==referenceData.taken}>{referenceData.taken}</span><span class:changed={selectedData.library!==referenceData.library}>{selectedData.library}</span><span class:changed={selectedData.library!==referenceData.library}>{referenceData.library}</span><span class:changed={selectedData.uploaded!==referenceData.uploaded}>{selectedData.uploaded}</span><span class:changed={selectedData.uploaded!==referenceData.uploaded}>{referenceData.uploaded}</span></div></V2Section></aside></div>
  {#snippet footer()}<span><b>{selectedData.name}</b> <span class="v2-small v2-muted">Choose disposition</span></span><V2Inline gap="sm" wrap={true}>{#each decisionOptions as decision (decision)}<V2Button active={decisions[decisionKey]===decision} onclick={()=>setDecision(decision)}>{decision[0].toUpperCase()+decision.slice(1)}</V2Button>{/each}</V2Inline>{/snippet}
</V2ViewerShell>

<style>
  .v2-compare-header-identity,.v2-compare-header-actions{display:flex;align-items:center;gap:var(--v2-space-2);flex-wrap:wrap;min-width:0;max-width:100%}
  .v2-compare-header-identity{flex:1 1 360px}
  .v2-compare-header-actions{flex:0 1 auto;justify-content:flex-end}
  .v2-compare-group-title{display:block;min-width:0;max-width:min(34rem,42vw);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .v2-technical-group{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:6px;align-items:center;min-width:0}
  .v2-technical-group>span{grid-column:1/-1}
  .v2-technical-group code{display:block;min-width:0;max-width:100%;padding:7px;border:1px solid var(--v2-line);border-radius:6px;background:var(--v2-bg);overflow-wrap:anywhere;font-size:10px;color:var(--v2-muted)}
  @media(max-width:720px){.v2-compare-group-title{max-width:calc(100vw - 8rem)}.v2-compare-header-actions{justify-content:flex-start}}
</style>
