<script lang="ts">
  import { onMount } from 'svelte';
  import ConfirmDialog from '../components/V2ConfirmDialog.svelte';
  import SelectField from '../components/SelectField.svelte';
  import V2Badge from '../components/V2Badge.svelte';
  import V2Button from '../components/V2Button.svelte';
  import V2Card from '../components/V2Card.svelte';
  import V2Checkbox from '../components/V2Checkbox.svelte';
  import V2CollectionControls, { type ResultMode } from '../components/V2CollectionControls.svelte';
  import V2CollectionFooter from '../components/V2CollectionFooter.svelte';
  import V2DuplicateCompareViewer from '../components/V2DuplicateCompareViewer.svelte';
  import V2DuplicateDecisionControls from '../components/V2DuplicateDecisionControls.svelte';
  import V2DuplicateStackControls from '../components/V2DuplicateStackControls.svelte';
  import V2ErrorState from '../components/V2ErrorState.svelte';
  import V2Field from '../components/V2Field.svelte';
  import V2Inline from '../components/V2Inline.svelte';
  import V2LazyAssetMedia from '../components/V2LazyAssetMedia.svelte';
  import V2OperationToast from '../components/V2OperationToast.svelte';
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2RoundCheckbox from '../components/V2RoundCheckbox.svelte';
  import V2Section from '../components/V2Section.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import V2Tabs from '../components/V2Tabs.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';
  import V2Zone from '../components/V2Zone.svelte';
  import { createCollectionView } from '../state/collectionView.svelte';
  import { CollectionRequestController } from '../state/collectionRequest.svelte';
  import { OperationController } from '../state/operationController.svelte';
  import {
    assignAssetToActiveStack,
    assignGroupToSingleStack,
    clearGroupStacks,
    createDuplicateStackWorkspace,
    createPendingStack,
    invalidPendingStacks,
    removeAssetFromPendingStack,
    resolutionStacks,
    selectPendingStack,
    setPendingStackPrimary,
    stackForAsset,
    stacksForGroup,
  } from '../state/duplicateStackResolution';
  import { libraryData } from '../data/currentDataSource.svelte';
  import { duplicateGroupTitle, duplicateKindLabel } from '../data/duplicatePresentation';
  import { errorMessage, mutationFeedback, pendingOperationFeedback } from '../data/mutationFeedback';
  import type { DuplicateCapabilities, DuplicateDecision, DuplicateGroupRecord, DuplicateHistoryRecord, DuplicatePreparedPlan, DuplicateResolutionPlan, DuplicateState } from '../data/contracts';

  type DuplicateTab='Review'|'Rules & discovery'|'Resolution history';
  type PendingReview={scope:'all'|'group';groupId:string|null;plan:DuplicatePreparedPlan};
  const collection=createCollectionView({pageSize:6,resultModeStorageKey:'immichCompanionDuplicateResultMode'});
  let tab=$state<DuplicateTab>('Review'),compare=$state(false),group=$state(''),member=$state(0),reference=$state(0);
  let decisions=$state<Record<string,DuplicateDecision>>({}),stackWorkspace=$state(createDuplicateStackWorkspace()),selectedGroups=$state<string[]>([]),reviewFilter=$state<DuplicateState|'All groups'|'Auto-ready'>('All groups');
  let groups=$state<DuplicateGroupRecord[]>([]),total=$state(0),nextCursor=$state<string|null>(null),retryResolution=$state<DuplicateResolutionPlan|null>(null),pendingReview=$state<PendingReview|null>(null),interactionError=$state('');
  let capabilities=$state<DuplicateCapabilities>({canRunDiscovery:false,canApplyDecisions:false,canViewHistory:false,reviewFilters:['All groups'],decisions:[]});
  let similarityThreshold=$state('82'),includeSimilar=$state(true),includeExact=$state(true),maxCandidates=$state('20'),discoverySummary=$state('');
  let historyRange=$state<'Last 30 days'|'Last 90 days'|'All history'>('Last 30 days'),history=$state<DuplicateHistoryRecord[]>([]);
  let planPreparing=$state(false);
  const groupRequests=new CollectionRequestController(),historyRequests=new CollectionRequestController(),operations=new OperationController();
  const loading=$derived(groupRequests.loading||historyRequests.loading),loadError=$derived(groupRequests.error||historyRequests.error),mutating=$derived(operations.busy||planPreparing),operationError=$derived(operations.error),feedback=$derived(operations.feedback);

  const activeGroup=$derived(groups.find((item)=>item.id===group)),activeAssetIds=$derived(activeGroup?.members.map((item)=>item.asset.id)??[]),activeCompareStack=$derived(stackForAsset(stackWorkspace,activeAssetIds[member]??'')),decisionCount=$derived(Object.keys(decisions).length);
  const activeSimilarities=$derived(Object.fromEntries(activeGroup?.members.map((item)=>[item.asset.id,item.similarity])??[]));
  const reviewFilterOptions=$derived(capabilities.reviewFilters.map(String));
  const invalidStackCount=$derived(invalidPendingStacks(stackWorkspace).length);
  const draftTimers=new Map<string,ReturnType<typeof setTimeout>>();
  let selectionSave=Promise.resolve();
  let workspaceHydrated=false;

  function hydrateWorkspace(items:DuplicateGroupRecord[],replace:boolean){
    if(!replace)return;
    let nextDecisions:Record<string,DuplicateDecision>={};
    let nextStacks=createDuplicateStackWorkspace();
    const selected:string[]=[];
    for(const item of items){
      nextDecisions={...nextDecisions,...item.savedDecisions};
      if(item.selected)selected.push(item.id);
      const stackIds=item.members.filter((entry)=>item.savedDecisions[entry.asset.id]==='stack').map((entry)=>entry.asset.id);
      if(stackIds.length){nextStacks=createPendingStack(nextStacks,item.id);for(const id of stackIds)nextStacks=assignAssetToActiveStack(nextStacks,item.id,id);if(item.stackPrimaryAssetId)nextStacks=setPendingStackPrimary(nextStacks,item.stackPrimaryAssetId)}
    }
    decisions=nextDecisions;stackWorkspace=nextStacks;selectedGroups=selected;workspaceHydrated=true;
  }

  function scheduleDraft(item:DuplicateGroupRecord){
    const previous=draftTimers.get(item.id);if(previous)clearTimeout(previous);
    draftTimers.set(item.id,setTimeout(()=>{draftTimers.delete(item.id);const resolution=groupResolution(item);if(!Object.keys(resolution.decisions).length)return;void libraryData.duplicates.saveDraft(item.id,resolution).catch((error)=>interactionError=errorMessage(error,'Duplicate choices could not be saved.'))},250));
  }

  function persistSelection(){
    if(!workspaceHydrated)return;
    const ids=[...selectedGroups],active=compare?group:null;
    selectionSave=selectionSave.catch(()=>undefined).then(()=>libraryData.duplicates.saveSelection(ids,active)).catch((error)=>{interactionError=errorMessage(error,'Duplicate group selection could not be saved.')});
  }

  $effect(()=>{
    let next=stackWorkspace;
    for(const item of groups){
      for(const member of item.members){
        const id=member.asset.id;
        if(decisions[id]==='stack'&&!next.assetToStack[id])next=assignAssetToActiveStack(next,item.id,id);
        if(decisions[id]!=='stack'&&next.assetToStack[id])next=removeAssetFromPendingStack(next,id);
      }
    }
    if(next!==stackWorkspace)stackWorkspace=next;
  });

  async function refreshGroups(reset=true):Promise<boolean>{
    if(groupRequests.loading&&!reset)return false;
    if(reset){nextCursor=null;if(collection.resultMode==='Infinite')collection.reset()}
    const query=collection.resultMode==='Pagination'?{state:reviewFilter,page:collection.page,pageSize:collection.pageSize}:{state:reviewFilter,pageSize:collection.pageSize,cursor:reset?null:nextCursor};
    const result=await groupRequests.run((signal)=>libraryData.duplicates.search({...query,signal}),{
      fallbackError:'Duplicate groups could not be loaded.',
      mode:collection.resultMode==='Infinite'&&!reset?'append':'replace',
      apply:(response,mode)=>{
        groups=mode==='append'?[...groups,...response.items]:response.items;
        hydrateWorkspace(response.items,mode==='replace');
        total=response.total;
        nextCursor=response.nextCursor;
        collection.clampPage(total);
      },
    });
    return result!==null;
  }
  async function reconcileGroups(action:string):Promise<void>{if(!await refreshGroups())throw new Error(groupRequests.error||`${action} was applied, but duplicate groups could not be refreshed.`)}
  function pending(action:string){return(phase:'applying'|'reconciling')=>pendingOperationFeedback(action,phase==='applying'?'applying':'refreshing')}
  async function loadMore(){if(!nextCursor||groupRequests.loading)return;collection.loadMore(total);await refreshGroups(false)}
  function setPage(value:number){collection.setPage(value);void refreshGroups()}
  function setPageSize(value:number){collection.setPageSize(value,total);void refreshGroups()}
  function setMode(value:ResultMode){collection.setMode(value);void refreshGroups()}
  function setReviewFilter(value:string){reviewFilter=value as typeof reviewFilter;collection.reset();selectedGroups=[];interactionError='';void refreshGroups()}
  function openCompare(nextGroup:string,index:number){group=nextGroup;member=index;reference=0;compare=true;persistSelection()}
  async function switchReference(assetId:string){if(!activeGroup)return;const updated=await libraryData.duplicates.switchReference(activeGroup.id,assetId);groups=groups.map((item)=>item.id===updated.id?updated:item)}
  function setDecision(groupId:string,assetId:string,decision:DuplicateDecision){if(!capabilities.decisions.includes(decision))return;const item=groups.find((entry)=>entry.id===groupId),wasComplete=item?groupComplete(item):false;const next={...decisions,[assetId]:decision};decisions=next;stackWorkspace=decision==='stack'?assignAssetToActiveStack(stackWorkspace,groupId,assetId):removeAssetFromPendingStack(stackWorkspace,assetId);if(item){if(!wasComplete&&groupComplete(item,next)&&!selectedGroups.includes(item.id)){selectedGroups=[...selectedGroups,item.id];persistSelection()}scheduleDraft(item)}}
  function clearDecision(groupId:string,assetId:string){if(!decisions[assetId])return;const next={...decisions};delete next[assetId];decisions=next;stackWorkspace=removeAssetFromPendingStack(stackWorkspace,assetId);selectedGroups=selectedGroups.filter((id)=>id!==groupId);persistSelection();const item=groups.find((entry)=>entry.id===groupId);if(!item)return;const resolution=groupResolution(item);if(Object.keys(resolution.decisions).length){scheduleDraft(item);return}const timer=draftTimers.get(item.id);if(timer)clearTimeout(timer);draftTimers.delete(item.id);void libraryData.duplicates.saveDraft(item.id,{decisions:{},stacks:[]}).catch((error)=>interactionError=errorMessage(error,'Duplicate choice could not be cleared.'))}
  function setStackPrimary(assetId:string){if(decisions[assetId]!=='stack')return;stackWorkspace=setPendingStackPrimary(stackWorkspace,assetId);const item=groups.find((entry)=>entry.members.some((entry)=>entry.asset.id===assetId));if(item)scheduleDraft(item)}
  function newStack(groupId:string){stackWorkspace=createPendingStack(stackWorkspace,groupId)}
  function chooseStack(groupId:string,stackId:string){stackWorkspace=selectPendingStack(stackWorkspace,groupId,stackId)}
  function presetGroup(item:DuplicateGroupRecord,decision:DuplicateDecision){if(!capabilities.decisions.includes(decision))return;const next={...decisions};for(const member of item.members)next[member.asset.id]=decision;decisions=next;stackWorkspace=decision==='stack'?assignGroupToSingleStack(stackWorkspace,item):clearGroupStacks(stackWorkspace,item.id);if(!selectedGroups.includes(item.id)){selectedGroups=[...selectedGroups,item.id];persistSelection()}scheduleDraft(item)}
  function clearGroupChoices(item:DuplicateGroupRecord){const groupIds=new Set(item.members.map((member)=>member.asset.id));decisions=Object.fromEntries(Object.entries(decisions).filter(([id])=>!groupIds.has(id))) as Record<string,DuplicateDecision>;stackWorkspace=clearGroupStacks(stackWorkspace,item.id);selectedGroups=selectedGroups.filter((id)=>id!==item.id);persistSelection();void libraryData.duplicates.saveDraft(item.id,{decisions:{},stacks:[]}).catch((error)=>interactionError=errorMessage(error,'Duplicate choices could not be cleared.'))}
  async function clearAllDecisions():Promise<void>{
    if(mutating)return;
    for(const timer of draftTimers.values())clearTimeout(timer);
    draftTimers.clear();
    await selectionSave.catch(()=>undefined);
    const cleared=await operations.run('Clear duplicate decisions',()=>libraryData.duplicates.clearDecisions(),{
      pending:pending('Clear duplicate decisions'),
      outcome:(count)=>({tone:'ok',title:'Duplicate decisions cleared',detail:`Cleared saved decisions for ${count.toLocaleString()} ${count===1?'group':'groups'}.`,failures:[]}),
      onOutcome:()=>{decisions={};stackWorkspace=createDuplicateStackWorkspace();selectedGroups=[];compare=false;interactionError=''},
      reconcile:()=>reconcileGroups('Duplicate decisions'),
      reconcileError:'Duplicate decisions were cleared, but the latest groups could not be loaded.',
    });
    if(cleared===null)for(const item of groups)if(Object.keys(groupResolution(item).decisions).length)scheduleDraft(item);
  }
  function applyBulkPreset(decision:DuplicateDecision){if(!capabilities.decisions.includes(decision))return;const next={...decisions};let workspace=stackWorkspace;for(const item of groups)if(selectedGroups.includes(item.id)){for(const member of item.members)next[member.asset.id]=decision;workspace=decision==='stack'?assignGroupToSingleStack(workspace,item):clearGroupStacks(workspace,item.id)}decisions=next;stackWorkspace=workspace;for(const item of groups)if(selectedGroups.includes(item.id))scheduleDraft(item)}
  function toggleGroup(id:string,checked:boolean){selectedGroups=checked?[...new Set([...selectedGroups,id])]:selectedGroups.filter((value)=>value!==id);persistSelection()}
  function currentResolution(nextDecisions=decisions):DuplicateResolutionPlan{return{decisions:{...nextDecisions},stacks:resolutionStacks(stackWorkspace).filter((stack)=>stack.assetIds.every((id)=>nextDecisions[id]==='stack'))}}
  function groupResolution(item:DuplicateGroupRecord):DuplicateResolutionPlan{const ids=new Set(item.members.map((entry)=>entry.asset.id));const groupDecisions=Object.fromEntries(Object.entries(decisions).filter(([id])=>ids.has(id))) as Record<string,DuplicateDecision>;return{decisions:groupDecisions,stacks:resolutionStacks(stackWorkspace).filter((stack)=>stack.groupId===item.id&&stack.assetIds.every((id)=>groupDecisions[id]==='stack'))}}
  function groupDisplayName(groupId:string|null):string{const item=groups.find((entry)=>entry.id===groupId);return item?duplicateGroupTitle(item):'duplicate group'}
  function groupComplete(item:DuplicateGroupRecord,source:Readonly<Record<string,DuplicateDecision>>=decisions){return item.members.length>0&&item.members.every((entry)=>Boolean(source[entry.asset.id]))}
  function groupHasInvalidStack(item:DuplicateGroupRecord){return stacksForGroup(stackWorkspace,item.id).some((stack)=>stack.assetIds.length===1)}
  async function prepareReview(scope:'all'|'group',groupId:string|null,resolution:DuplicateResolutionPlan){planPreparing=true;try{const plan=await libraryData.duplicates.prepareDecisions(resolution);pendingReview={scope,groupId,plan}}catch(error){interactionError=errorMessage(error,'Duplicate actions could not be prepared.')}finally{planPreparing=false}}
  function requestReviewAll(resolution=currentResolution()){interactionError='';const selected=groups.filter((item)=>selectedGroups.includes(item.id));if(!selected.length||selected.some((item)=>!groupComplete(item))){interactionError='Every selected duplicate group needs a decision for every image.';return}if(invalidStackCount){interactionError=`${invalidStackCount} pending stack${invalidStackCount===1?' has':'s have'} only one asset. Add another asset or choose Keep/Delete before applying.`;return}const selectedResolution={decisions:Object.fromEntries(Object.entries(resolution.decisions).filter(([id])=>selected.some((item)=>item.members.some((member)=>member.asset.id===id)))) as Record<string,DuplicateDecision>,stacks:resolution.stacks.filter((stack)=>selectedGroups.includes(stack.groupId))};void prepareReview('all',null,selectedResolution)}
  function requestReviewGroup(item:DuplicateGroupRecord){interactionError='';const label=duplicateGroupTitle(item);if(!groupComplete(item)){interactionError=`${label} still has assets without a decision.`;return}if(groupHasInvalidStack(item)){interactionError=`${label} has an incomplete one-asset stack.`;return}void prepareReview('group',item.id,groupResolution(item))}
  async function refillAfterGroupReview(groupId:string,label:string):Promise<void>{
    const remaining=groups.filter((item)=>item.id!==groupId);
    const query=collection.resultMode==='Pagination'?{state:reviewFilter,page:collection.page,pageSize:collection.pageSize}:{state:reviewFilter,pageSize:collection.pageSize,cursor:null};
    const result=await groupRequests.run((signal)=>libraryData.duplicates.search({...query,signal}),{
      fallbackError:`${label} was reviewed, but duplicate groups could not be refreshed.`,
      apply:(response)=>{
        const preserved=new Map(remaining.map((item)=>[item.id,item]));
        if(collection.resultMode==='Pagination')groups=response.items.map((item)=>preserved.get(item.id)??item);
        else{const existingIds=new Set(remaining.map((item)=>item.id));groups=[...remaining,...response.items.filter((item)=>!existingIds.has(item.id))]}
        total=response.total;nextCursor=response.nextCursor;collection.clampPage(total);
      },
    });
    if(!result)throw new Error(groupRequests.error||`${label} was reviewed, but duplicate groups could not be refreshed.`);
  }
  function clearAppliedGroupState(item:DuplicateGroupRecord){const ids=new Set(item.members.map((entry)=>entry.asset.id));decisions=Object.fromEntries(Object.entries(decisions).filter(([id])=>!ids.has(id))) as Record<string,DuplicateDecision>;stackWorkspace=clearGroupStacks(stackWorkspace,item.id);selectedGroups=selectedGroups.filter((id)=>id!==item.id)}
  async function applyDecisionSet(plan:DuplicatePreparedPlan){
    const resolution=plan.resolution;if(!capabilities.canApplyDecisions||Object.keys(resolution.decisions).length===0||mutating)return;
    operations.clearOutcome();interactionError='';
    await operations.run('Duplicate decisions',()=>libraryData.duplicates.executePlan(plan),{
      pending:pending('Duplicate decisions'),
      outcome:(result)=>mutationFeedback('Duplicate decisions',result),
      onOutcome:(_feedback,result)=>{const failedIds=new Set(result.failed.map((failure)=>failure.id));const failedDecisions=Object.fromEntries(Object.entries(resolution.decisions).filter(([id])=>failedIds.has(id))) as Record<string,DuplicateDecision>;retryResolution=result.failed.length?{decisions:failedDecisions,stacks:resolution.stacks.filter((stack)=>stack.assetIds.some((id)=>failedIds.has(id)))}:null;decisions={...failedDecisions};stackWorkspace=createDuplicateStackWorkspace();selectedGroups=[];compare=false},
      reconcile:()=>reconcileGroups('Duplicate decisions'),
      reconcileError:'Duplicate decisions were applied, but the latest groups could not be loaded.',
    });
  }
  async function applyGroupDecisionSet(groupId:string,plan:DuplicatePreparedPlan){
    const resolution=plan.resolution;
    if(!capabilities.canApplyDecisions||mutating)return;
    const item=groups.find((entry)=>entry.id===groupId);if(!item)return;
    const label=duplicateGroupTitle(item);
    operations.clearOutcome();interactionError='';
    await operations.run(`Review ${label}`,()=>libraryData.duplicates.executePlan(plan),{
      pending:pending(`Review ${label}`),
      outcome:(result)=>mutationFeedback(`Review ${label}`,result),
      onOutcome:(_feedback,result)=>{const failedIds=new Set(result.failed.map((failure)=>failure.id));if(result.failed.length){const failedDecisions=Object.fromEntries(Object.entries(resolution.decisions).filter(([id])=>failedIds.has(id))) as Record<string,DuplicateDecision>;retryResolution={decisions:failedDecisions,stacks:resolution.stacks.filter((stack)=>stack.assetIds.some((id)=>failedIds.has(id)))};return}retryResolution=null;clearAppliedGroupState(item);if(compare&&group===groupId)compare=false},
      reconcile:async(result)=>{if(!result.failed.length)await refillAfterGroupReview(groupId,label)},
      reconcileError:`${label} was reviewed, but the latest groups could not be loaded.`,
    });
  }
  async function confirmPendingReview(){const review=pendingReview;if(!review||mutating)return;if(review.scope==='group'&&review.groupId!==null)await applyGroupDecisionSet(review.groupId,review.plan);else await applyDecisionSet(review.plan);pendingReview=null}
  async function runDiscovery(){
    if(!capabilities.canRunDiscovery||mutating)return;
    operations.clearOutcome();interactionError='';
    await operations.run('Duplicate discovery',()=>libraryData.duplicates.runDiscovery({similarityThreshold:Number(similarityThreshold)||0,includeSimilar,includeExact,maxCandidates:Math.max(1,Number(maxCandidates)||20)}),{
      pending:pending('Duplicate discovery'),
      outcome:(result)=>({tone:'ok',title:'Discovery completed',detail:`${result.groupCount} groups · ${result.candidateCount} candidates`,failures:[]}),
      onOutcome:(outcome)=>{discoverySummary=outcome.detail;stackWorkspace=createDuplicateStackWorkspace()},
      reconcile:()=>reconcileGroups('Duplicate discovery'),
      reconcileError:'Duplicate discovery completed, but the latest groups could not be loaded.',
    });
  }
  async function refreshHistory():Promise<boolean>{
    if(!capabilities.canViewHistory){history=[];return true}
    const result=await historyRequests.run((signal)=>libraryData.duplicates.history({range:historyRange,page:1,pageSize:50,signal}),{
      fallbackError:'Resolution history could not be loaded.',
      apply:(response)=>{history=response.items},
    });
    return result!==null;
  }

  onMount(()=>{void(async()=>{try{await libraryData.initialize();collection.hydrate();capabilities=await libraryData.duplicates.capabilities();if(!capabilities.reviewFilters.includes(reviewFilter))reviewFilter=capabilities.reviewFilters[0]??'All groups';await Promise.all([refreshGroups(),refreshHistory()])}catch(error){groupRequests.setError(errorMessage(error,'The duplicate data source could not be initialized.'))}})();return()=>{groupRequests.cancel();historyRequests.cancel();for(const timer of draftTimers.values())clearTimeout(timer)}});
</script>

<V2PageLayout title="Duplicates" description="Review duplicate groups supplied by the active data source, with provider-backed discovery and decisions.">
  {#snippet headerActions()}<V2Inline gap="sm"><V2Button disabled={!capabilities.canRunDiscovery||loading||mutating} onclick={runDiscovery}>{mutating?(operations.phase==='reconciling'?'Refreshing…':'Working…'):'Scan similar'}</V2Button><V2Button variant="primary" disabled={!capabilities.canApplyDecisions||decisionCount===0||mutating} onclick={()=>requestReviewAll()}>Review actions{decisionCount?` (${decisionCount})`:''}</V2Button></V2Inline>{/snippet}
  {#snippet tabs()}<V2Tabs items={['Review','Rules & discovery','Resolution history']} active={tab} ariaLabel="Duplicate sections" onselect={(value)=>{tab=value as DuplicateTab;if(tab==='Resolution history')void refreshHistory()}}/>{/snippet}
  {#snippet context()}<V2Zone>{#if tab==='Review'}<V2Section title="Review filter"><V2Stack gap="sm"><SelectField id="duplicate-review-filter" label="Group state" value={reviewFilter} options={reviewFilterOptions} onchange={setReviewFilter}/><V2Button disabled={mutating||!groups.some((item)=>item.state==='Actionable')} onclick={()=>{selectedGroups=groups.filter((item)=>item.state==='Actionable').map((item)=>item.id);persistSelection()}}>Select auto-ready</V2Button></V2Stack></V2Section><V2Section title="Similarity"><V2Field label="Threshold" value={similarityThreshold} onchange={(value)=>similarityThreshold=value}/><span class="v2-small v2-muted">Similarity remains review evidence only.</span></V2Section><V2Section title="Bulk preset"><V2Stack gap="sm">{#if capabilities.decisions.includes('keep')}<V2Button disabled={mutating||!selectedGroups.length} onclick={()=>applyBulkPreset('keep')}>Keep all copies</V2Button>{/if}{#if capabilities.decisions.includes('delete')}<V2Button disabled={mutating||!selectedGroups.length} onclick={()=>applyBulkPreset('delete')}>Mark all for deletion</V2Button>{/if}{#if capabilities.decisions.includes('stack')}<V2Button disabled={mutating||!selectedGroups.length} onclick={()=>applyBulkPreset('stack')}>Stack each group</V2Button>{/if}</V2Stack></V2Section>{:else if tab==='Rules & discovery'}<V2Section title="Discovery"><V2Stack gap="sm"><V2Field label="Similarity threshold" value={similarityThreshold} onchange={(value)=>similarityThreshold=value}/><V2Checkbox label="Include visually similar assets" checked={includeSimilar} onchange={(checked)=>includeSimilar=checked}/><V2Checkbox label="Include exact file matches" checked={includeExact} onchange={(checked)=>includeExact=checked}/><V2Field label="Maximum candidates per asset" value={maxCandidates} onchange={(value)=>maxCandidates=value}/><V2Button variant="primary" disabled={!capabilities.canRunDiscovery||mutating} onclick={runDiscovery}>{mutating?(operations.phase==='reconciling'?'Refreshing…':'Scanning…'):'Run discovery'}</V2Button>{#if discoverySummary}<span class="v2-small v2-muted">{discoverySummary}</span>{/if}</V2Stack></V2Section>{:else}<V2Section title="History filter"><V2Stack gap="sm"><SelectField id="duplicate-history-range" label="Range" value={historyRange} options={['Last 30 days','Last 90 days','All history']} onchange={(value)=>{historyRange=value as typeof historyRange;void refreshHistory()}}/><V2Button disabled={!capabilities.canViewHistory||mutating} onclick={refreshHistory}>Refresh history</V2Button></V2Stack></V2Section>{/if}</V2Zone>{/snippet}

  <V2Zone>
    {#if loadError}<V2ErrorState title="Duplicate data unavailable" message={loadError} onretry={()=>void (tab==='Resolution history'?refreshHistory():refreshGroups())}/>{/if}
    {#if interactionError}<V2ErrorState title="Duplicate review needs attention" message={interactionError}/>{/if}
    <V2OperationToast {feedback} error={operationError} failureTitle="Duplicate operation failed" retryLabel={retryResolution?'Retry failed':''} onretry={retryResolution?()=>requestReviewAll(retryResolution!):undefined}/>
    {#if tab==='Review'}<V2Toolbar><V2Badge text={`${total} groups`}/><V2Badge tone="ok" text={`${groups.filter((item)=>item.state==='Actionable').length} loaded ready`}/><V2Badge text={`${decisionCount} decisions`}/>{#if invalidStackCount}<V2Badge tone="warn" text={`${invalidStackCount} incomplete stack${invalidStackCount===1?'':'s'}`}/>{/if}{#snippet actions()}<V2CollectionControls id="duplicate-results" sort="state:asc" sortFields={[]} pageSize={collection.pageSize} pageSizes={[6,12,24]} resultMode={collection.resultMode} onsort={()=>{}} onpagesize={setPageSize} onmode={setMode}/><V2Button disabled={mutating} onclick={()=>void clearAllDecisions()}>Clear decisions</V2Button>{/snippet}</V2Toolbar>
    {#each groups as item (item.id)}
      {@const groupStacks=stacksForGroup(stackWorkspace,item.id)}
      <V2Card class="v2-duplicate-group"><V2Stack gap="md"><V2Inline justify="between" align="start" wrap={true}><V2Inline gap="sm" wrap={true}><span class="v2-duplicate-group-selector"><V2RoundCheckbox checked={selectedGroups.includes(item.id)} disabled={mutating} ariaLabel={`${selectedGroups.includes(item.id)?'Deselect':'Select'} ${duplicateGroupTitle(item)}`} onclick={()=>toggleGroup(item.id,!selectedGroups.includes(item.id))}/><button class="v2-duplicate-group-title" type="button" disabled={mutating} title={duplicateGroupTitle(item)} onclick={()=>toggleGroup(item.id,!selectedGroups.includes(item.id))}>{duplicateGroupTitle(item)}</button></span><V2Badge text={`${item.members.length} assets`}/><V2Badge text={duplicateKindLabel(item.kind)}/><V2Badge tone={item.state==='Actionable'?'ok':item.state==='Blocked'?'bad':'warn'} text={item.state}/></V2Inline><V2Inline gap="sm" wrap={true}>{#if capabilities.decisions.includes('keep')}<V2Button disabled={mutating} onclick={()=>presetGroup(item,'keep')}>Keep all</V2Button>{/if}{#if capabilities.decisions.includes('delete')}<V2Button disabled={mutating} onclick={()=>presetGroup(item,'delete')}>Delete all</V2Button>{/if}{#if capabilities.decisions.includes('stack')}<V2Button disabled={mutating} onclick={()=>presetGroup(item,'stack')}>Stack all</V2Button>{/if}<V2Button disabled={mutating} onclick={()=>clearGroupChoices(item)}>Clear choices</V2Button><V2Button disabled={mutating} onclick={()=>openCompare(item.id,0)}>Compare</V2Button><V2Button variant="primary" disabled={mutating||!capabilities.canApplyDecisions||!groupComplete(item)||groupHasInvalidStack(item)} title={!groupComplete(item)?'Choose an action for every asset first':groupHasInvalidStack(item)?'Complete the pending stack first':'Review only this group'} onclick={()=>requestReviewGroup(item)}>Review group</V2Button></V2Inline></V2Inline>
      {#if capabilities.decisions.includes('stack')}<V2DuplicateStackControls stacks={groupStacks} activeStackId={stackWorkspace.activeByGroup[item.id]??null} disabled={mutating} onselect={(stackId)=>chooseStack(item.id,stackId)} oncreate={()=>newStack(item.id)}/>{/if}
      <div class="v2-duplicate-members">
      {#each item.members as member,index (member.asset.id)}
        {@const pendingStack=stackForAsset(stackWorkspace,member.asset.id)}
        <div class="v2-duplicate-member"><button class="v2-duplicate-image" disabled={mutating} onclick={()=>openCompare(item.id,index)}><V2LazyAssetMedia cacheKey={`duplicate-thumbnail:${member.asset.id}`} resolve={()=>libraryData.media.thumbnail(member.asset)} alt={member.asset.original_file_name}/>{#if pendingStack}<span class="v2-stack-primary-badge">{pendingStack.label}{pendingStack.primaryAssetId===member.asset.id?' · Primary':''}</span>{/if}<span class="v2-duplicate-image-meta"><b>{member.asset.original_file_name}</b><small>{member.asset.library_id?'External library':'Immich'} · {member.similarity===null?'Not calculated':`${member.similarity.toFixed(1)}%`}</small></span></button><V2DuplicateDecisionControls decision={decisions[member.asset.id]} stackLabel={pendingStack?.label??'Stack'} isPrimary={pendingStack?.primaryAssetId===member.asset.id} decisions={capabilities.decisions} disabled={mutating} ondecision={(decision)=>setDecision(item.id,member.asset.id,decision)} onprimary={()=>setStackPrimary(member.asset.id)}/></div>
      {/each}
    </div></V2Stack></V2Card>{/each}
    {#if total>0}<V2CollectionFooter resultMode={collection.resultMode} page={collection.page} pageSize={collection.pageSize} {total} loaded={groups.length} noun="groups" onpage={setPage} onloadmore={loadMore}/>{/if}
  {:else if tab==='Rules & discovery'}<V2Toolbar sticky={false}><b>Rules & discovery</b><V2Badge text={capabilities.canRunDiscovery?'Provider-backed':'Unavailable'}/></V2Toolbar><div class="v2-setting-grid"><V2Card title="Exact matches"><V2Stack gap="sm"><V2Checkbox label="Detect identical file hashes" checked={includeExact} onchange={(checked)=>includeExact=checked}/><V2Button disabled={!capabilities.canRunDiscovery||mutating} onclick={runDiscovery}>Apply & scan</V2Button></V2Stack></V2Card><V2Card title="Similarity discovery"><V2Stack gap="sm"><V2Field label="Minimum similarity" value={similarityThreshold} onchange={(value)=>similarityThreshold=value}/><V2Field label="Maximum candidates per asset" value={maxCandidates} onchange={(value)=>maxCandidates=value}/><V2Button variant="primary" disabled={!capabilities.canRunDiscovery||mutating} onclick={runDiscovery}>Run discovery</V2Button></V2Stack></V2Card></div>
  {:else}<V2Toolbar sticky={false}><V2Badge text="Resolution history"/></V2Toolbar><V2Stack gap="sm">{#each history as row (row.id)}<V2Card><V2Inline justify="between" wrap={true}><V2Stack gap="xs"><b>{row.groupLabel}</b><span class="v2-small v2-muted">{new Date(row.occurredAt).toLocaleString()}</span></V2Stack><span>{row.summary}</span></V2Inline></V2Card>{:else}<V2Card><span class="v2-muted">No resolution history in this range.</span></V2Card>{/each}</V2Stack>{/if}
  </V2Zone>
</V2PageLayout>

<V2DuplicateCompareViewer open={compare} groupTitle={activeGroup?duplicateGroupTitle(activeGroup):'Duplicate comparison'} groupKind={activeGroup?.kind??''} assetIds={activeAssetIds} similarities={activeSimilarities} decisionOptions={capabilities.decisions} stackLabel={activeCompareStack?.label??'Stack'} stackPrimary={activeCompareStack?.primaryAssetId===activeAssetIds[member]} disabled={mutating} bind:member bind:reference bind:decisions ondecisionchange={(assetId,decision)=>setDecision(group,assetId,decision)} ondecisionclear={(assetId)=>clearDecision(group,assetId)} onstackprimary={setStackPrimary} onreferencechange={switchReference} onclose={()=>{compare=false;persistSelection()}}/>
{#if pendingReview}<ConfirmDialog title={pendingReview.scope==='group'?`Review ${groupDisplayName(pendingReview.groupId)}?`:'Review duplicate actions?'} message={pendingReview.scope==='group'?'The action plan is ready. Execute the Keep, Delete and Stack choices for this group now? Other groups and their current choices will be left untouched.':`The action plan is ready. Execute the current ${Object.keys(pendingReview.plan.resolution.decisions).length} duplicate decisions?`} confirmLabel={pendingReview.scope==='group'?'Execute group plan':'Execute action plan'} icon="check" destructive={Object.values(pendingReview.plan.resolution.decisions).includes('delete')} pending={mutating} onconfirm={()=>void confirmPendingReview()} onclose={()=>{if(!mutating)pendingReview=null}}/>{/if}

<style>
  .v2-stack-primary-badge{position:absolute;z-index:3;top:8px;right:8px;display:inline-flex;align-items:center;gap:4px;padding:4px 7px;border:1px solid rgba(255,255,255,.36);border-radius:999px;background:rgba(8,13,19,.86);color:#fff;font-size:10px;font-weight:700;line-height:1;box-shadow:0 2px 8px rgba(0,0,0,.3)}
  .v2-duplicate-group-selector{display:flex;align-items:center;min-width:0;max-width:min(36rem,65vw)}
  .v2-duplicate-group-title{display:block;min-width:0;max-width:min(34rem,60vw);overflow:hidden;border:0;padding:4px 2px;background:transparent;color:inherit;font:inherit;font-weight:700;text-align:left;text-overflow:ellipsis;white-space:nowrap;cursor:pointer}
  .v2-duplicate-group-title:focus-visible{outline:2px solid var(--v2-accent);outline-offset:2px;border-radius:4px}
  .v2-duplicate-group-title:disabled{cursor:default;opacity:.55}
</style>
