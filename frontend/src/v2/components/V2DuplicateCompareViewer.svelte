<script lang="ts">
  import V2Badge from './V2Badge.svelte';
  import V2Button from './V2Button.svelte';
  import V2Card from './V2Card.svelte';
  import V2DuplicateDecisionControls from './V2DuplicateDecisionControls.svelte';
  import V2ImageComparison, { type ComparisonMode } from './V2ImageComparison.svelte';
  import V2Inline from './V2Inline.svelte';
  import V2KeyboardShortcuts, { type KeyboardShortcut } from './V2KeyboardShortcuts.svelte';
  import V2LazyAssetMedia from './V2LazyAssetMedia.svelte';
  import V2Section from './V2Section.svelte';
  import V2Stack from './V2Stack.svelte';
  import V2ViewerShell from './V2ViewerShell.svelte';
  import { comparisonMemberData, type ComparisonMemberData } from '../data/duplicateMember';
  import { duplicateKindLabel } from '../data/duplicatePresentation';
  import { libraryData } from '../data/currentDataSource.svelte';
  import type { AssetRecord, DuplicateDecision, MediaResource } from '../data/contracts';
  import { loadImmichLibraries } from '../../lib/api/duplicatePolicyApi';

  let { open, groupTitle, groupKind, assetIds=[], similarities={}, member=$bindable(0), reference=$bindable(0), decisions=$bindable<Record<string,DuplicateDecision>>({}), decisionOptions=[], stackLabel='Stack', stackPrimary=false, disabled=false, ondecisionchange, ondecisionclear, onstackprimary, onreferencechange, onclose }: { open:boolean; groupTitle:string; groupKind:string; assetIds?:string[]; similarities?:Record<string,number|null>; member?:number; reference?:number; decisions?:Record<string,DuplicateDecision>; decisionOptions?:DuplicateDecision[]; stackLabel?:string; stackPrimary?:boolean; disabled?:boolean; ondecisionchange?:(assetId:string,decision:DuplicateDecision)=>void; ondecisionclear?:(assetId:string)=>void; onstackprimary?:(assetId:string)=>void; onreferencechange?:(assetId:string)=>Promise<void>; onclose:()=>void }=$props();
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
  let mode=$state<ComparisonMode>('Side by side'),split=$state(50),opacity=$state(50),diffHue=$state(190),diffContrast=$state(180),diffBinary=$state(true),diffTolerance=$state(8),assets=$state<AssetRecord[]>([]),libraryNames=$state<Map<string,string>>(new Map()),loading=$state(false),loadError=$state(''),loadGeneration=0,libraryNamesPromise:Promise<Map<string,string>>|null=null;
  const emptyData:ComparisonMemberData={name:'Unknown asset',source:'—',size:'—',sizeNum:0,dims:'—',taken:'—',codec:'Unknown type',library:'—',libraryId:null,folder:'—',uploaded:'—',similarity:'Not calculated'};
  const emptyResource:MediaResource={url:'',fallbackUrls:[],mimeType:null,posterUrl:null,delivery:'preview',originalMimeType:null,expiresAt:null};
  const videoPlaceholder='data:image/svg+xml,'+encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="960" height="640" viewBox="0 0 960 640"><rect width="960" height="640" fill="#222831"/><circle cx="480" cy="320" r="82" fill="#ffffff22"/><path d="M455 270 545 320 455 370Z" fill="white"/><text x="480" y="450" text-anchor="middle" fill="white" font-family="sans-serif" font-size="34">Video asset</text></svg>`);
  function comparisonResource(asset:AssetRecord|undefined):MediaResource{if(!asset)return emptyResource;if(asset.asset_type==='VIDEO')return{...emptyResource,url:videoPlaceholder,mimeType:'image/svg+xml'};return libraryData.media.view(asset)}
  function getLibraryNames():Promise<Map<string,string>>{libraryNamesPromise??=loadImmichLibraries().then((libraries)=>new Map(libraries.map((library)=>[library.id,library.name]))).catch(()=>new Map());return libraryNamesPromise}
  const activeCount=$derived(assetIds.length),assetById=$derived(new Map(assets.map((asset)=>[asset.id,asset]))),memberData=$derived(assetIds.map((id)=>comparisonMemberData(assetById.get(id),similarities[id]??null,libraryNames))),selectedAsset=$derived(assetById.get(assetIds[member])),referenceAsset=$derived(assetById.get(assetIds[reference])),selectedData=$derived(memberData[member]??emptyData),referenceData=$derived(memberData[reference]??emptyData),selectedResource=$derived(comparisonResource(selectedAsset)),referenceResource=$derived(comparisonResource(referenceAsset)),decisionKey=$derived(assetIds[member]??''),matchLabel=$derived(duplicateKindLabel(groupKind)),sameExternalLibrary=$derived(Boolean(selectedData.libraryId&&selectedData.libraryId===referenceData.libraryId)),foldersComparable=$derived(sameExternalLibrary&&selectedData.folder!=='Unavailable'&&referenceData.folder!=='Unavailable'),sameFolder=$derived(foldersComparable&&selectedData.folder===referenceData.folder);
  $effect(()=>{if(!open)return;const generation=++loadGeneration,ids=[...assetIds];loading=true;loadError='';void(async()=>{try{const [nextAssets,nextLibraryNames]=await Promise.all([libraryData.assets.getMany(ids),getLibraryNames()]);if(generation!==loadGeneration)return;assets=nextAssets;libraryNames=nextLibraryNames}catch(error){if(generation===loadGeneration)loadError=error instanceof Error?error.message:'Could not load comparison assets.'}finally{if(generation===loadGeneration)loading=false}})();return()=>{loadGeneration+=1}});
  function prev(){if(activeCount)member=(member-1+activeCount)%activeCount}
  function next(){if(activeCount)member=(member+1)%activeCount}
  function setDecision(decision:DuplicateDecision){if(decisionKey&&decisionOptions.includes(decision)){decisions={...decisions,[decisionKey]:decision};ondecisionchange?.(decisionKey,decision)}}
  function clearDecision(){if(decisionKey&&decisions[decisionKey])ondecisionclear?.(decisionKey)}
  function setStackPrimary(){if(decisionKey)onstackprimary?.(decisionKey)}
  async function setReference(){if(!selectedAsset)return;await onreferencechange?.(selectedAsset.id);reference=member}
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
  <div class="v2-compare-main"><section class="v2-compare-visual">
    {#if loading}<div class="v2-compare-media-status" role="status">Loading comparison media…</div>{:else if loadError}<div class="v2-compare-media-status" role="alert">{loadError}</div>{:else}<V2ImageComparison {selectedResource} {referenceResource} selectedLabel={selectedData.name} referenceLabel={referenceData.name} bind:mode bind:opacity bind:split bind:diffHue bind:diffContrast bind:diffBinary bind:diffTolerance/>{/if}
    <div class="v2-filmstrip">{#each assetIds as assetId,index (assetId)}{@const asset=assetById.get(assetId)}{@const data=memberData[index]??emptyData}<button class="v2-thumb" class:active={index===member} class:reference={index===reference} onclick={()=>member=index}>{#if asset}<span class="v2-thumb-media"><V2LazyAssetMedia cacheKey={`duplicate-compare-thumbnail:${asset.id}`} resolve={()=>libraryData.media.thumbnail(asset)} alt={data.name}/></span>{/if}<small>{data.name}</small><small class="v2-muted">{data.size} · {data.similarity}</small></button>{/each}</div>
  </section><aside class="v2-compare-data"><V2Section title="Quick comparison"><V2Card><V2Stack gap="sm"><V2Inline justify="between"><span>Match type</span><b>{matchLabel}</b></V2Inline><V2Inline justify="between"><span>Visual similarity</span><b>{selectedData.similarity}</b></V2Inline><V2Inline justify="between"><span>File size difference</span><b>{selectedData.sizeNum-referenceData.sizeNum>=0?'+':''}{(selectedData.sizeNum-referenceData.sizeNum).toFixed(1)} MB</b></V2Inline><V2Inline justify="between"><span>Resolution</span><b>{selectedData.dims===referenceData.dims?'Same':'Different'}</b></V2Inline>{#if sameExternalLibrary}<V2Inline justify="between"><span>External folder</span><V2Badge tone={!foldersComparable?'warn':sameFolder?'ok':'warn'} text={!foldersComparable?'Unavailable':sameFolder?'Same':'Different'}/></V2Inline>{/if}<V2Inline justify="between"><span>Difference source</span><V2Badge tone="ok" text="Layered displayed pixels"/></V2Inline></V2Stack></V2Card></V2Section><V2Section title="Metadata side by side"><div class="v2-compare-grid"><b></b><b>Selected</b><b>Reference</b><b>File name</b><span class:changed={selectedData.name!==referenceData.name}>{selectedData.name}</span><span class:changed={selectedData.name!==referenceData.name}>{referenceData.name}</span><b>Source</b><span class:changed={selectedData.source!==referenceData.source}>{selectedData.source}</span><span class:changed={selectedData.source!==referenceData.source}>{referenceData.source}</span><b>Folder</b><span class:changed={foldersComparable&&!sameFolder}>{selectedData.folder}</span><span class:changed={foldersComparable&&!sameFolder}>{referenceData.folder}</span><b>Format</b><span class:changed={selectedData.codec!==referenceData.codec}>{selectedData.codec}</span><span class:changed={selectedData.codec!==referenceData.codec}>{referenceData.codec}</span><b>File size</b><span class:changed={selectedData.size!==referenceData.size}>{selectedData.size}</span><span class:changed={selectedData.size!==referenceData.size}>{referenceData.size}</span><b>Dimensions</b><span class:changed={selectedData.dims!==referenceData.dims}>{selectedData.dims}</span><span class:changed={selectedData.dims!==referenceData.dims}>{referenceData.dims}</span><b>Taken</b><span class:changed={selectedData.taken!==referenceData.taken}>{selectedData.taken}</span><span class:changed={selectedData.taken!==referenceData.taken}>{referenceData.taken}</span><b>Added to Immich</b><span class:changed={selectedData.uploaded!==referenceData.uploaded}>{selectedData.uploaded}</span><span class:changed={selectedData.uploaded!==referenceData.uploaded}>{referenceData.uploaded}</span></div></V2Section></aside></div>
  {#snippet footer()}<span class="v2-compare-footer-label"><b>{selectedData.name}</b> <span class="v2-small v2-muted">Choose disposition</span></span><div class="v2-compare-footer-actions"><div class="v2-compare-footer-decisions"><V2DuplicateDecisionControls decision={decisions[decisionKey]} {stackLabel} isPrimary={stackPrimary} decisions={decisionOptions} {disabled} ondecision={setDecision} onprimary={setStackPrimary}/></div><span class="v2-compare-clear-selection"><V2Button disabled={disabled||!decisions[decisionKey]} onclick={clearDecision}>Clear selection</V2Button></span></div>{/snippet}
</V2ViewerShell>

<style>
  .v2-compare-header-identity,.v2-compare-header-actions{display:flex;align-items:center;gap:var(--v2-space-2);flex-wrap:wrap;min-width:0;max-width:100%}
  .v2-compare-header-identity{flex:1 1 360px}
  .v2-compare-header-actions{flex:0 1 auto;justify-content:flex-end}
  .v2-compare-group-title{display:block;min-width:0;max-width:min(34rem,42vw);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .v2-compare-footer-label{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .v2-compare-footer-actions{display:flex;align-items:center;justify-content:flex-end;gap:var(--v2-space-2);flex:0 1 auto;min-width:0;margin-left:auto}
  .v2-compare-footer-decisions{flex:0 1 25rem;width:min(25rem,100%);min-width:min(20rem,100%)}
  .v2-compare-footer-decisions :global(.v2-duplicate-decision-controls){margin-top:0}
  .v2-compare-clear-selection{display:inline-flex;flex:0 0 auto;align-self:center;white-space:nowrap}
  .v2-thumb-media{position:relative;display:block;width:92px;height:92px;overflow:hidden;border-radius:5px}
  .v2-compare-media-status{display:grid;place-items:center;width:100%;height:100%;padding:var(--v2-space-4);color:var(--v2-muted);background:var(--v2-image-workzone);text-align:center}
  @media(max-width:720px){.v2-compare-group-title{max-width:calc(100vw - 8rem)}.v2-compare-header-actions{justify-content:flex-start}.v2-compare-footer-actions{flex:1 1 100%;width:100%}.v2-compare-footer-decisions{flex:1 1 18rem;min-width:0}}
</style>
