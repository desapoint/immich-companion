<script lang="ts">
  import { onMount } from 'svelte';
  import ConfirmDialog from '../../../lib/components/ui/ConfirmDialog.svelte';
  import NoticeDialog from '../../../lib/components/ui/NoticeDialog.svelte';
  import V2Badge from '../../../lib/components/ui/Badge.svelte';
  import V2Button from '../../../lib/components/ui/Button.svelte';
  import V2Card from '../../../lib/components/ui/Card.svelte';
  import V2Checkbox from '../../../lib/components/ui/Checkbox.svelte';
  import V2CollectionControls, { type ResultMode } from '../../../lib/components/ui/CollectionControls.svelte';
  import V2CollectionFooter from '../../../lib/components/ui/CollectionFooter.svelte';
  import V2CollectionLoadingOverlay from '../../../lib/components/ui/CollectionLoadingOverlay.svelte';
  import DuplicateCompareViewer from './DuplicateCompareViewer.svelte';
  import DuplicateDiscoveryIntro from './DuplicateDiscoveryIntro.svelte';
  import DuplicateHistoryControls from './DuplicateHistoryControls.svelte';
  import DuplicateHistoryList from './DuplicateHistoryList.svelte';
  import DuplicateReviewControls from './DuplicateReviewControls.svelte';
  import DuplicateReviewProgress from './DuplicateReviewProgress.svelte';
  import V2DuplicateHistoryDetail from './DuplicateHistoryDetail.svelte';
  import V2DuplicateAdmissionEvidence from './DuplicateAdmissionEvidence.svelte';
  import V2DuplicateCachePanel from './DuplicateCachePanel.svelte';
  import V2DuplicateDecisionControls from './DuplicateDecisionControls.svelte';
  import DuplicateKeeperModal from './DuplicateKeeperModal.svelte';
  import V2DuplicateStackControls from './DuplicateStackControls.svelte';
  import V2DuplicateValidationSettings from './DuplicateValidationSettings.svelte';
  import PerceptualDistanceSetting from './PerceptualDistanceSetting.svelte';
  import V2ErrorState from '../../../lib/components/ui/ErrorState.svelte';
  import V2Field from '../../../lib/components/ui/TextField.svelte';
  import V2Inline from '../../../lib/components/layout/Inline.svelte';
  import V2LazyAssetMedia from '../../assets/components/LazyAssetMedia.svelte';
  import OperationToast from '../../../lib/components/app/OperationToast.svelte';
  import OperationFeedback from '../../../lib/components/app/OperationFeedback.svelte';
  import V2PageLayout from '../../../lib/components/layout/PageLayout.svelte';
  import V2RoundCheckbox from '../../../lib/components/ui/RoundCheckbox.svelte';
  import V2Segmented from '../../../lib/components/ui/Segmented.svelte';
  import V2SimilarityEvidenceGenerationPanel from './SimilarityEvidenceGenerationPanel.svelte';
  import V2Stack from '../../../lib/components/layout/Stack.svelte';
  import V2Tabs from '../../../lib/components/ui/Tabs.svelte';
  import V2Toolbar from '../../../lib/components/layout/Toolbar.svelte';
  import V2Zone from '../../../lib/components/layout/Zone.svelte';
  import { createCollectionView } from '../../../lib/state/collectionView.svelte';
  import { backgroundTaskStatus } from '../../status/state/backgroundTaskStatus.svelte';
  import { duplicateDiscoverySettingsRepository } from '../api/duplicateDiscoverySettingsRepository';
  import { CollectionRequestController } from '../../../lib/state/collectionRequest.svelte';
  import { OperationController } from '../../../lib/state/operationController.svelte';
  import {
    assignAssetToActiveStack,
    assignGroupToSingleStack,
    clearGroupStacks,
    createDuplicateStackWorkspace,
    createPendingStack,
    removeAssetFromPendingStack,
    invalidPendingStacks,
    selectPendingStack,
    setPendingStackPrimary,
    stackForAsset,
    stacksForGroup,
  } from '../state/duplicateStackResolution';
  import { libraryData } from '../../../app/data/currentDataSource.svelte';
  import { clearAllDuplicateResolutionHistory, clearDuplicateResolutionHistory } from '../api/duplicateResolutionHistory';
  import { duplicateGroupTitle, duplicateKindLabel } from '../utils/duplicatePresentation';
  import { duplicateListMemberMeta, formatSimilarityPercent } from '../types/duplicateMember';
  import { duplicateSourceLabels } from '../utils/duplicateSource';
  import { comparisonTargetId } from '../../../lib/utils/duplicateComparisonNavigation';
  import { duplicateViewerGroupNavigationPlan, type DuplicateViewerGroupDirection } from '../state/duplicateViewerGroupNavigation';
  import { errorMessage, mutationFeedback, pendingOperationFeedback } from '../../../lib/api/mutationFeedback';
  import type { DuplicateCapabilities, DuplicateDecision, DuplicateGroupRecord, DuplicateHistoryRecord, DuplicateKeeperSelectionResult, DuplicatePreparedPlan, DuplicateResolutionPlan, DuplicateSourceFilter, DuplicateState, SimilarityCacheKind, SimilarityCacheStatus, SimilarityValidationMode } from '../types/contracts';
  import { currentResolution, groupComplete, groupResolution } from '../state/duplicateReviewHelpers';
  import {
    clearGroupDecision,
    clearGroupDecisions,
    decisionCount as duplicateDecisionCount,
    decisionFor,
    decisionsForGroup,
    filterDecisionWorkspaceByAssets,
    replaceGroupDecisions,
    setGroupDecision,
    type DuplicateDecisionWorkspace,
  } from '../state/duplicateDecisionWorkspace';
  import { DuplicatePagePersistence } from '../state/duplicatePagePersistence.svelte';
  import { DuplicateDiscoveryController } from '../state/duplicateDiscoveryController';
  import { duplicateGroupAnchorId, duplicateReviewIssues, type DuplicateReviewIssue } from '../state/duplicateReviewPreflight';
  import type { DuplicateReviewProgressPhase } from '../types/reviewProgress';

  type DuplicateTab='Review'|'Rules & discovery'|'Resolution history';
  type DuplicateSortField='reclaimable'|'members'|'similarity'|'date'|'discovered';
  type PendingReview={scope:'all'|'group';groupId:string|null;plan:DuplicatePreparedPlan};
  type DuplicateErrorDialog={title:string;message:string};
  const collection=createCollectionView({pageSize:6,resultModeStorageKey:'immichCompanionDuplicateResultMode'});
  let tab=$state<DuplicateTab>('Review'),compare=$state(false),group=$state(''),member=$state(0),reference=$state(0),selectionScope=$state<'Current page'|'All matching'>(typeof sessionStorage!=='undefined'&&sessionStorage.getItem('immich-companion:v2:duplicate-selection-scope')==='All matching'?'All matching':'Current page'),presetApplying=$state(false),selectingAll=$state(false);
  let decisions=$state<DuplicateDecisionWorkspace>({}),stackWorkspace=$state(createDuplicateStackWorkspace()),selectedGroups=$state<string[]>([]),reviewFilter=$state<DuplicateState|'All groups'|'Auto-ready'|'Selected'>('Actionable'),sort=$state('reclaimable:desc');
  let sourceFilter=$state<DuplicateSourceFilter>(typeof sessionStorage!=='undefined'&&['immich','similarity'].includes(sessionStorage.getItem('immich-companion:v2:duplicate-source-filter')??'')?sessionStorage.getItem('immich-companion:v2:duplicate-source-filter') as DuplicateSourceFilter:'both');
  let groups=$state<DuplicateGroupRecord[]>([]),total=$state(0),nextCursor=$state<string|null>(null),retryResolution=$state<DuplicateResolutionPlan|null>(null),pendingReview=$state<PendingReview|null>(null),interactionError=$state(''),errorDialog=$state<DuplicateErrorDialog|null>(null);
  let capabilities=$state<DuplicateCapabilities>({canRunDiscovery:false,canApplyDecisions:false,canViewHistory:false,reviewFilters:['All groups'],decisions:[]});
  let similarityThreshold=$state('95'),maximumPerceptualDistance=$state('12'),validationMode=$state<SimilarityValidationMode>('strict'),maxLinkDepth=$state('2'),includeSimilar=$state(true),includeExact=$state(true),maxCandidates=$state('8'),maximumMatches=$state('5000'),discoverySummary=$state(''),discoveryRetention=$state<{count:number;limit:number;reached:boolean}|null>(null);
  let historyRange=$state<'Last 30 days'|'Last 90 days'|'All history'>('Last 30 days'),history=$state<DuplicateHistoryRecord[]>([]),historyLoadedRange=$state<typeof historyRange|null>(null),historyClearTarget=$state<DuplicateHistoryRecord|null>(null),historyClearAll=$state(false),historyDetail=$state<DuplicateHistoryRecord|null>(null);
  let cacheTelemetry=$state.raw<SimilarityCacheStatus|null>(null),cacheLoading=$state(false),cacheLoaded=$state(false),cacheError=$state('');
  let planPreparing=$state(false),reviewProgressPhase=$state<DuplicateReviewProgressPhase|null>(null),groupLoads=$state(0),groupNavigationLoading=$state(false),initialLoading=$state(true),keeperRulesOpen=$state(false),keeperSummary=$state('');
  const groupRequests=new CollectionRequestController(),historyRequests=new CollectionRequestController(),operations=new OperationController((message)=>{pendingReview=null;historyClearTarget=null;historyClearAll=false;openErrorDialog('Duplicate operation failed',message)});
  const reviewLoading=$derived(initialLoading||groupLoads>0||groupRequests.loading),loading=$derived(tab==='Review'?reviewLoading:tab==='Resolution history'?historyRequests.loading:false),loadError=$derived(tab==='Review'?groupRequests.error:tab==='Resolution history'?historyRequests.error:''),mutating=$derived(operations.busy||planPreparing||presetApplying||selectingAll),operationError=$derived(operations.error),feedback=$derived(operations.feedback);

  const activeGroup=$derived(groups.find((item)=>item.id===group)),activeGroupIndex=$derived(groups.findIndex((item)=>item.id===group)),activeAssetIds=$derived(activeGroup?.members.map((item)=>item.asset.id)??[]),activeCompareStack=$derived(group?stackForAsset(stackWorkspace,group,activeAssetIds[member]??''):null),decisionCount=$derived(duplicateDecisionCount(decisions));
  const activeSimilarities=$derived(Object.fromEntries(activeGroup?.members.map((item)=>[item.asset.id,item.similarity])??[]));
  const activeSimilarityEvidence=$derived(Object.fromEntries(activeGroup?.members.map((item)=>[item.asset.id,item.similarityEvidence])??[]));
  const reviewFilterOptions=$derived(capabilities.reviewFilters.map(String));
  const invalidStackCount=$derived(invalidPendingStacks(stackWorkspace).length);
  const reviewConfirmationPhase=$derived<DuplicateReviewProgressPhase>(operations.phase==='reconciling'?'refreshing':operations.phase==='applying'?'applying':'ready');
  const discoveryReady=$derived(capabilities.canRunDiscovery&&(includeExact||includeSimilar));
  const groupNavigationState=$derived({resultMode:collection.resultMode,page:collection.page,pageSize:collection.pageSize,total,loadedCount:groups.length,currentIndex:activeGroupIndex,hasNextCursor:Boolean(nextCursor)});
  const previousGroupPlan=$derived(duplicateViewerGroupNavigationPlan('previous',groupNavigationState));
  const nextGroupPlan=$derived(duplicateViewerGroupNavigationPlan('next',groupNavigationState));
  const canPreviousGroup=$derived(compare&&!mutating&&!reviewLoading&&!groupNavigationLoading&&previousGroupPlan!==null);
  const canNextGroup=$derived(compare&&!mutating&&!reviewLoading&&!groupNavigationLoading&&nextGroupPlan!==null);
  const persistence = new DuplicatePagePersistence();
  let dataReady=false;
  const discovery = new DuplicateDiscoveryController({
    getState: () => ({ includeExact, includeSimilar, similarityThreshold, maximumPerceptualDistance, validationMode, maxLinkDepth, maxCandidates, maximumMatches }),
    setState: (state) => { includeExact=state.includeExact;includeSimilar=state.includeSimilar;similarityThreshold=state.similarityThreshold;maximumPerceptualDistance=state.maximumPerceptualDistance;validationMode=state.validationMode;maxLinkDepth=state.maxLinkDepth;maxCandidates=state.maxCandidates;maximumMatches=state.maximumMatches },
    isReady: () => discoveryReady,
    isMutating: () => mutating,
    clearOutcome: () => operations.clearOutcome(),
    setError: (message) => {interactionError=message;openErrorDialog('Duplicate discovery could not start',message)},
    setSummary: (summary) => discoverySummary=summary,
    setResult: (result) => {
      discoveryRetention=result&&result.retainedMatchCount!==null&&result.retainedMatchLimit!==null&&result.retentionLimitReached!==null
        ? {count:result.retainedMatchCount,limit:result.retainedMatchLimit,reached:result.retentionLimitReached}
        : null;
    },
    resetWorkspace: () => stackWorkspace=createDuplicateStackWorkspace(),
    pending,
    runOperation: (action, runner, options) => operations.run(action, runner, options),
    runDiscovery: (options, onProgress) => libraryData.duplicates.runDiscovery(options, onProgress),
    reconcile: () => reconcileGroups('Duplicate discovery'),
    updateProgress: (progress) => backgroundTaskStatus.updateDuplicateDiscovery(progress),
    startProgress: () => backgroundTaskStatus.startDuplicateDiscovery(),
    finishProgress: () => backgroundTaskStatus.finishDuplicateDiscovery(),
  });
  $effect(()=>{if(typeof sessionStorage!=='undefined')sessionStorage.setItem('immich-companion:v2:duplicate-selection-scope',selectionScope)});

  function openErrorDialog(title:string,message:string){const detail=message.trim();if(!detail)return;errorDialog={title,message:detail}}
  function surfaceInteractionError(error:unknown,fallback:string,title='Duplicate review could not continue'):string{const message=errorMessage(error,fallback);interactionError=message;openErrorDialog(title,message);return message}
  function hydrateWorkspace(items:DuplicateGroupRecord[],replace:boolean){const hydrated=persistence.hydrateWorkspace(items,replace,decisions,stackWorkspace,selectedGroups);decisions=hydrated.decisions;stackWorkspace=hydrated.stackWorkspace;selectedGroups=hydrated.selectedGroups}
  async function flushWorkspace():Promise<void>{await persistence.flushWorkspace(groups,(item)=>groupResolution(stackWorkspace,item,decisions))}
  function scheduleDraft(item:DuplicateGroupRecord){persistence.scheduleDraft(item,()=>groupResolution(stackWorkspace,item,decisions),(error)=>surfaceInteractionError(error,'Duplicate choices could not be saved.','Duplicate choices could not be saved'))}
  function persistSelection(){persistence.persistSelection(selectedGroups,compare?group:null,(error)=>surfaceInteractionError(error,'Duplicate group selection could not be saved.','Duplicate selection could not be saved'))}

  $effect(()=>{
    let next=stackWorkspace;
    for(const item of groups){
      for(const member of item.members){
        const id=member.asset.id;
        const decision=decisionFor(decisions,item.id,id);
        const pending=stackForAsset(next,item.id,id);
        if(decision==='stack'&&!pending)next=assignAssetToActiveStack(next,item.id,id);
        if(decision!=='stack'&&pending)next=removeAssetFromPendingStack(next,item.id,id);
      }
    }
    if(next!==stackWorkspace)stackWorkspace=next;
  });

  function parseSort():{field:DuplicateSortField;direction:'asc'|'desc'}{const[fieldRaw,directionRaw]=sort.split(':');const field=(['reclaimable','members','similarity','date','discovered'].includes(fieldRaw)?fieldRaw:'reclaimable') as DuplicateSortField;return{field,direction:directionRaw==='asc'?'asc':'desc'}}
  async function refreshGroups(reset=true,reuseCachedGroups=false):Promise<boolean>{
    if(groupRequests.loading&&!reset)return false;
    groupLoads+=1;
    try{
      if(reuseCachedGroups){
        // Page changes can immediately hydrate a new response. Await pending
        // draft and selection writes first so the response cannot restore an
        // older, page-local workspace over the durable all-matching selection.
        try{await flushWorkspace()}catch(error){surfaceInteractionError(error,'Duplicate choices could not be saved before refreshing.','Duplicate choices could not be saved');return false}
      }else{
        try{await flushWorkspace()}catch(error){surfaceInteractionError(error,'Duplicate choices could not be saved before refreshing.','Duplicate choices could not be saved');return false}
      }
      if(reset){nextCursor=null;if(collection.resultMode==='Infinite')collection.reset()}
      const query=collection.resultMode==='Pagination'?{state:reviewFilter,source:sourceFilter,sort:parseSort(),page:collection.page,pageSize:collection.pageSize,reuseCachedGroups}:{state:reviewFilter,source:sourceFilter,sort:parseSort(),pageSize:collection.pageSize,cursor:reset?null:nextCursor,reuseCachedGroups};
      const result=await groupRequests.run((signal)=>libraryData.duplicates.search({...query,signal}),{
        fallbackError:'Duplicate groups could not be loaded.',
        mode:collection.resultMode==='Infinite'&&!reset?'append':'replace',
        apply:(response,mode)=>{
          groups=mode==='append'?[...groups,...response.items]:response.items;
          hydrateWorkspace(response.items,mode==='replace'&&!reuseCachedGroups);
          // `search()` restores the complete durable workspace, while the
          // page response only contains one page of groups. Always adopt the
          // repository selection after hydration so a hard refresh cannot
          // reduce an all-matching selection to the visible page.
          selectedGroups=[...libraryData.duplicates.selectedGroupIds()];
          total=response.total;
          nextCursor=response.nextCursor;
          collection.clampPage(total);
        },
      });
      return result!==null;
    }finally{groupLoads-=1}
  }
  async function reconcileGroups(action:string):Promise<void>{if(!await refreshGroups()&&groupRequests.error)throw new Error(groupRequests.error||`${action} was applied, but duplicate groups could not be refreshed.`)}
  function pending(action:string){return(phase:'applying'|'reconciling')=>pendingOperationFeedback(action,phase==='applying'?'applying':'refreshing')}
  async function loadMore(){if(!nextCursor||groupRequests.loading)return;collection.loadMore(total);await refreshGroups(false,true)}
  function viewReviewIssue(issue:DuplicateReviewIssue|null){
    if(!issue)return;
    tab='Review';
    requestAnimationFrame(()=>{
      const target=document.getElementById(duplicateGroupAnchorId(issue.groupId));
      target?.scrollIntoView({behavior:'smooth',block:'center'});
      target?.focus({preventScroll:true});
    });
  }
  function blockForReviewIssue(groupIds:readonly string[]):boolean{const scope=new Set(groupIds);const issue=duplicateReviewIssues(stackWorkspace,decisions).find((candidate)=>scope.has(candidate.groupId))??null;if(!issue)return false;interactionError=issue.message;viewReviewIssue(issue);return true}
  function setPage(value:number){collection.setPage(value);void refreshGroups(true,true);document.querySelector<HTMLElement>('.v2-content')?.scrollTo({top:0,behavior:'auto'})}
  function setPageSize(value:number){collection.setPageSize(value,total);void refreshGroups(true,true)}
  function setMode(value:ResultMode){collection.setMode(value);void refreshGroups(true,true)}
  function setSort(value:string){sort=value;collection.reset();interactionError='';void refreshGroups(true,true)}
  function setReviewFilter(value:string){reviewFilter=value as typeof reviewFilter;collection.reset();interactionError='';void refreshGroups(true,true)}
  function setSourceFilter(value:string){sourceFilter=value as DuplicateSourceFilter;if(typeof sessionStorage!=='undefined')sessionStorage.setItem('immich-companion:v2:duplicate-source-filter',sourceFilter);collection.reset();interactionError='';void refreshGroups(true,true)}
  function activateCompareGroup(item:DuplicateGroupRecord,index=0){const ids=item.members.map((entry)=>entry.asset.id);group=item.id;reference=Math.max(0,ids.indexOf(item.referenceAssetId??''));member=Math.max(0,ids.indexOf(comparisonTargetId(ids,ids[reference]??'',ids[index]??'')));compare=true;persistSelection()}
  function openCompare(nextGroup:string,index:number){const item=groups.find((candidate)=>candidate.id===nextGroup);if(item)activateCompareGroup(item,index)}
  async function navigateCompareGroup(direction:DuplicateViewerGroupDirection){
    if(!compare||mutating||reviewLoading||groupNavigationLoading)return;
    const plan=duplicateViewerGroupNavigationPlan(direction,{resultMode:collection.resultMode,page:collection.page,pageSize:collection.pageSize,total,loadedCount:groups.length,currentIndex:groups.findIndex((item)=>item.id===group),hasNextCursor:Boolean(nextCursor)});
    if(!plan)return;
    groupNavigationLoading=true;
    try{
      let target:DuplicateGroupRecord|undefined;
      if(plan.kind==='loaded')target=groups[plan.index];
      else if(plan.kind==='page'){
        const previousPage=collection.page;
        collection.setPage(plan.page);
        const loaded=await refreshGroups(true,true);
        if(!loaded){collection.setPage(previousPage);return}
        target=plan.edge==='first'?groups[0]:groups[groups.length-1];
      }else{
        const before=groups.length;
        await loadMore();
        target=groups[plan.index]??groups[before];
      }
      if(target)activateCompareGroup(target,0);
    }finally{groupNavigationLoading=false}
  }
  async function switchReference(assetId:string){if(mutating||!activeGroup)return;try{const updated=await libraryData.duplicates.switchReference(activeGroup.id,assetId),ids=updated.members.map((entry)=>entry.asset.id);groups=groups.map((item)=>item.id===updated.id?updated:item);reference=Math.max(0,ids.indexOf(updated.referenceAssetId??''));member=Math.max(0,ids.indexOf(comparisonTargetId(ids,ids[reference]??'',assetId)))}catch(error){surfaceInteractionError(error,'The duplicate comparison reference could not be changed.','Reference change failed')}}
  function setDecision(groupId:string,assetId:string,decision:DuplicateDecision){if(mutating||!capabilities.decisions.includes(decision))return;const item=groups.find((entry)=>entry.id===groupId),wasComplete=item?groupComplete(item,decisions):false;const next=setGroupDecision(decisions,groupId,assetId,decision);decisions=next;stackWorkspace=decision==='stack'?assignAssetToActiveStack(stackWorkspace,groupId,assetId):removeAssetFromPendingStack(stackWorkspace,groupId,assetId);if(item){if(!wasComplete&&groupComplete(item,next)&&!selectedGroups.includes(item.id)){selectedGroups=[...selectedGroups,item.id];persistSelection()}scheduleDraft(item)}}
  function clearDecision(groupId:string,assetId:string){if(mutating||!decisionFor(decisions,groupId,assetId))return;decisions=clearGroupDecision(decisions,groupId,assetId);stackWorkspace=removeAssetFromPendingStack(stackWorkspace,groupId,assetId);selectedGroups=selectedGroups.filter((id)=>id!==groupId);persistSelection();const item=groups.find((entry)=>entry.id===groupId);if(!item)return;const resolution=groupResolution(stackWorkspace,item,decisions);if(Object.keys(resolution.decisions).length){scheduleDraft(item);return}persistence.cancelDraft(item.id);void libraryData.duplicates.saveDraft(item.id,{decisions:{},stacks:[]}).catch((error)=>surfaceInteractionError(error,'Duplicate choice could not be cleared.','Duplicate choice could not be cleared'))}
  function setStackPrimary(groupId:string,assetId:string){if(mutating||decisionFor(decisions,groupId,assetId)!=='stack')return;stackWorkspace=setPendingStackPrimary(stackWorkspace,groupId,assetId);const item=groups.find((entry)=>entry.id===groupId);if(item)scheduleDraft(item)}
  function newStack(groupId:string){stackWorkspace=createPendingStack(stackWorkspace,groupId)}
  function chooseStack(groupId:string,stackId:string){stackWorkspace=selectPendingStack(stackWorkspace,groupId,stackId)}
  function presetGroup(item:DuplicateGroupRecord,decision:DuplicateDecision){if(!capabilities.decisions.includes(decision))return;const groupDecisions=Object.fromEntries(item.members.map((member)=>[member.asset.id,decision])) as Record<string,DuplicateDecision>;decisions=replaceGroupDecisions(decisions,item.id,groupDecisions);stackWorkspace=decision==='stack'?assignGroupToSingleStack(stackWorkspace,item):clearGroupStacks(stackWorkspace,item.id);if(!selectedGroups.includes(item.id)){selectedGroups=[...selectedGroups,item.id];persistSelection()}scheduleDraft(item)}
  function clearGroupChoices(item:DuplicateGroupRecord){decisions=clearGroupDecisions(decisions,item.id);stackWorkspace=clearGroupStacks(stackWorkspace,item.id);selectedGroups=selectedGroups.filter((id)=>id!==item.id);persistSelection();void libraryData.duplicates.saveDraft(item.id,{decisions:{},stacks:[]}).catch((error)=>surfaceInteractionError(error,'Duplicate choices could not be cleared.','Duplicate choices could not be cleared'))}
  async function clearAllDecisions():Promise<void>{
    if(mutating)return;
    persistence.dispose();
    await persistence.waitForSelectionSave();
    const previousDecisions={...decisions};
    const previousStackWorkspace=stackWorkspace;
    const previousSelectedGroups=[...selectedGroups];
    const previousCompare=compare;
    decisions={};stackWorkspace=createDuplicateStackWorkspace();selectedGroups=[];compare=false;interactionError='';
    const cleared=await operations.run('Clear duplicate decisions',()=>libraryData.duplicates.clearDecisions(),{
      pending:pending('Clear duplicate decisions'),
      outcome:(count)=>count===0
        ? {tone:'ok',title:'No duplicate decisions to clear',detail:'There are no saved duplicate decisions or selections.',failures:[]}
        : {tone:'ok',title:'Duplicate decisions cleared',detail:`Cleared saved decisions for ${count.toLocaleString()} ${count===1?'group':'groups'}.`,failures:[]},
      reconcile:(count)=>count>0?reconcileGroups('Duplicate decisions'):Promise.resolve(),
      reconcileError:'Duplicate decisions were cleared, but the latest groups could not be loaded.',
    });
    if(cleared===null){
      decisions=previousDecisions;stackWorkspace=previousStackWorkspace;selectedGroups=previousSelectedGroups;compare=previousCompare;
      for(const item of groups)if(Object.keys(groupResolution(stackWorkspace,item,decisions).decisions).length)scheduleDraft(item);
    }
  }
  async function applyBulkPreset(decision:DuplicateDecision){if(!capabilities.decisions.includes(decision)||presetApplying)return;presetApplying=true;interactionError='';try{await flushWorkspace();const scope=selectionScope==='All matching'?'all_matching':'current_page';const result=await libraryData.duplicates.applyPreset(decision,scope,groups.map((item)=>item.id),reviewFilter,sourceFilter);if(result.skippedGroupIds.length)interactionError=`${result.skippedGroupIds.length} invalid or unavailable duplicate group${result.skippedGroupIds.length===1?' was':'s were'} skipped.`;await refreshGroups()}catch(error){surfaceInteractionError(error,'The duplicate preset could not be saved.','Duplicate preset could not be saved')}finally{presetApplying=false}}
  async function keeperRulesApplied(result:DuplicateKeeperSelectionResult){keeperSummary=`${result.appliedGroupCount.toLocaleString()} groups updated by automation · ${result.trashCount.toLocaleString()} automatic Delete decisions`;keeperRulesOpen=false;selectedGroups=[...libraryData.duplicates.selectedGroupIds()];selectionScope='All matching';reviewFilter='Selected';collection.reset();interactionError='';await refreshGroups(true,false)}
  async function selectAllGroups():Promise<void>{
    if(mutating)return;
    selectingAll=true;interactionError='';
    try{
      await flushWorkspace();
      selectedGroups=[...await libraryData.duplicates.selectAllGroups()];
      selectionScope='All matching';
      sourceFilter='both';
      if(typeof sessionStorage!=='undefined')sessionStorage.setItem('immich-companion:v2:duplicate-source-filter',sourceFilter);
      reviewFilter='Selected';
      collection.reset();
      await refreshGroups(true,false);
    }catch(error){surfaceInteractionError(error,'All duplicate groups could not be selected.','Duplicate selection failed')}finally{selectingAll=false}
  }
  const bulkPresetDisabled=$derived(mutating||presetApplying||(selectionScope==='Current page'&&!groups.length));
  function toggleGroup(id:string,checked:boolean){selectedGroups=checked?[...new Set([...selectedGroups,id])]:selectedGroups.filter((value)=>value!==id);persistSelection();if(reviewFilter==='Selected'&&!checked){groups=groups.filter((item)=>item.id!==id);total=Math.max(0,total-1);collection.clampPage(total)}}
  function groupDisplayName(groupId:string|null):string{const item=groups.find((entry)=>entry.id===groupId);return item?duplicateGroupTitle(item):'duplicate group'}
  async function prepareReview(scope:'all'|'group',groupId:string|null,resolution:DuplicateResolutionPlan){
    const reviewGroupIds=scope==='group'&&groupId?[groupId]:selectedGroups;
    if(blockForReviewIssue(reviewGroupIds))return;
    planPreparing=true;reviewProgressPhase='saving';
    try{
      await flushWorkspace();
      reviewProgressPhase='planning';
      const groupIds=scope==='group'&&groupId?[groupId]:[];
      const plan=await libraryData.duplicates.prepareDecisions(resolution,groupIds);
      pendingReview={scope,groupId,plan};
    }catch(error){surfaceInteractionError(error,'Duplicate actions could not be prepared.','Duplicate review could not continue')}
    finally{planPreparing=false;reviewProgressPhase=null}
  }
  function requestReviewAll(){
    interactionError='';
    // The durable workspace is authoritative for all-matching selections. A
    // page refresh can temporarily leave the local page model behind it, so
    // repair the local count before deciding that the action is unavailable.
    const persistedSelection=libraryData.duplicates.selectedGroupIds();
    if(selectionScope==='All matching'&&persistedSelection.length>selectedGroups.length)selectedGroups=[...persistedSelection];
    else if(persistedSelection.length&&!selectedGroups.length)selectedGroups=[...persistedSelection];
    if(!selectedGroups.length){interactionError='Select at least one duplicate group to review.';return}
    void prepareReview('all',null,currentResolution(stackWorkspace,decisions))
  }
  function requestReviewGroup(item:DuplicateGroupRecord){interactionError='';const label=duplicateGroupTitle(item);if(!groupComplete(item,decisions)){interactionError=`${label} still has assets without a decision.`;return}void prepareReview('group',item.id,groupResolution(stackWorkspace,item,decisions))}
  async function refillAfterGroupReview(groupId:string,label:string):Promise<void>{
    const remaining=groups.filter((item)=>item.id!==groupId);
    const query=collection.resultMode==='Pagination'?{state:reviewFilter,source:sourceFilter,page:collection.page,pageSize:collection.pageSize}:{state:reviewFilter,source:sourceFilter,pageSize:collection.pageSize,cursor:null};
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
  function clearAppliedGroupState(item:DuplicateGroupRecord){decisions=clearGroupDecisions(decisions,item.id);stackWorkspace=clearGroupStacks(stackWorkspace,item.id);selectedGroups=selectedGroups.filter((id)=>id!==item.id)}
  async function applyDecisionSet(plan:DuplicatePreparedPlan){
    const resolution=plan.resolution;if(!capabilities.canApplyDecisions||Object.keys(resolution.decisions).length===0||mutating)return;
    operations.clearOutcome();interactionError='';
    await operations.run('Duplicate decisions',()=>libraryData.duplicates.executePlan(plan),{
      pending:pending('Duplicate decisions'),
      outcome:(result)=>mutationFeedback('Duplicate decisions',result),
      onOutcome:(_feedback,result)=>{const failedIds=new Set(result.failed.map((failure)=>failure.id));const failedDecisions=Object.fromEntries(Object.entries(resolution.decisions).filter(([id])=>failedIds.has(id))) as Record<string,DuplicateDecision>;retryResolution=result.failed.length?{decisions:failedDecisions,stacks:resolution.stacks.filter((stack)=>stack.assetIds.some((id)=>failedIds.has(id)))}:null;decisions=filterDecisionWorkspaceByAssets(decisions,failedIds);stackWorkspace=createDuplicateStackWorkspace();selectedGroups=[];compare=false},
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
  async function confirmPendingReview(){const review=pendingReview;if(!review||mutating)return;if(review.scope==='group'&&review.groupId!==null)await applyGroupDecisionSet(review.groupId,review.plan);else await applyDecisionSet(review.plan);await operations.waitForReconciliation();historyLoadedRange=null;pendingReview=null}
  async function runDiscovery(anchorAssetId?:string){await discovery.run(anchorAssetId);cacheLoaded=false}
  async function revalidateFromReference(assetId:string){
    if(mutating||!activeGroup)return;
    includeSimilar=true;
    validationMode=activeGroup.similarityValidationMode??validationMode;
    if(activeGroup.similarityThresholdPercent!==null)similarityThreshold=String(activeGroup.similarityThresholdPercent);
    compare=false;
    await runDiscovery(assetId);
  }
  async function refreshHistory(force=true):Promise<boolean>{
    if(!capabilities.canViewHistory){history=[];historyLoadedRange=historyRange;return true}
    if(!force&&historyLoadedRange===historyRange)return true;
    const result=await historyRequests.run((signal)=>libraryData.duplicates.history({range:historyRange,page:1,pageSize:50,signal}),{
      fallbackError:'Resolution history could not be loaded.',
      apply:(response)=>{history=response.items;historyLoadedRange=historyRange},
    });
    return result!==null;
  }
  async function clearHistoryResolution():Promise<void>{
    const target=historyClearTarget;
    if(!target||mutating||operations.reconciling)return;
    operations.clearOutcome();interactionError='';
    const cleared=await operations.run('Clear duplicate resolution',()=>clearDuplicateResolutionHistory(target.id),{
      pending:pending('Clear duplicate resolution'),
      outcome:()=>({tone:'ok',title:'Resolution cleared',detail:'Companion can review a currently discovered matching group again.',failures:[]}),
      reconcile:async()=>{
        const historyLoaded=await refreshHistory();
        const groupsLoaded=await refreshGroups(true,false);
        if(!historyLoaded||!groupsLoaded)throw new Error('The resolution was cleared, but the latest duplicate state could not be loaded.');
      },
      reconcileError:'Resolution was cleared, but the latest duplicate state could not be loaded.',
    });
    if(cleared!==null){historyClearTarget=null;if(historyDetail?.id===target.id)historyDetail=null}
  }
  async function clearAllHistoryResolutions():Promise<void>{
    if(mutating||operations.reconciling)return;
    operations.clearOutcome();interactionError='';
    const cleared=await operations.run('Clear all duplicate resolution history',clearAllDuplicateResolutionHistory,{
      pending:pending('Clear all duplicate resolution history'),
      outcome:(count)=>count===0
        ? {tone:'ok',title:'No resolution history to clear',detail:'There are no completed duplicate resolutions.',failures:[]}
        : {tone:'ok',title:'Resolution history cleared',detail:`Cleared ${count.toLocaleString()} completed ${count===1?'resolution':'resolutions'}.`,failures:[]},
      reconcile:async()=>{
        const historyLoaded=await refreshHistory();
        const groupsLoaded=await refreshGroups(true,false);
        if(!historyLoaded||!groupsLoaded)throw new Error('Resolution history was cleared, but the latest duplicate state could not be loaded.');
      },
      reconcileError:'Resolution history was cleared, but the latest duplicate state could not be loaded.',
    });
    if(cleared!==null){historyClearAll=false;historyClearTarget=null;historyDetail=null}
  }

  async function refreshCacheStatus(force=true){if(cacheLoading||(!force&&cacheLoaded))return;cacheLoading=true;cacheError='';try{cacheTelemetry=await libraryData.duplicates.cacheStatus();cacheLoaded=true}catch(error){cacheError=errorMessage(error,'Similarity cache status could not be loaded.')}finally{cacheLoading=false}}
  async function clearCache(cache:SimilarityCacheKind){if(cacheLoading)return;cacheLoading=true;cacheError='';try{cacheTelemetry=await libraryData.duplicates.clearCache(cache);cacheLoaded=true}catch(error){cacheError=errorMessage(error,'The disposable similarity cache could not be cleared.')}finally{cacheLoading=false}}
  function selectTab(value:string){tab=value as DuplicateTab;if(!dataReady)return;if(tab==='Resolution history')void refreshHistory(false);else if(tab==='Rules & discovery')void refreshCacheStatus(false)}

  onMount(()=>{void(async()=>{try{await libraryData.initialize();collection.hydrate();capabilities=await libraryData.duplicates.capabilities();try{const saved=await duplicateDiscoverySettingsRepository.load();includeExact=saved.includeExact;includeSimilar=saved.includeSimilar;similarityThreshold=String(saved.similarityThreshold);maximumPerceptualDistance=String(saved.maximumPerceptualDistance);validationMode=saved.validationMode;maxLinkDepth=String(saved.maxLinkDepth);maxCandidates=String(saved.maxCandidates);maximumMatches=String(saved.maximumMatches)}catch(error){interactionError=errorMessage(error,'Saved duplicate discovery settings could not be loaded from Companion.')}if(!capabilities.reviewFilters.includes(reviewFilter))reviewFilter=capabilities.reviewFilters[0]??'All groups';dataReady=true;if(tab==='Resolution history')void refreshHistory(false);else if(tab==='Rules & discovery')void refreshCacheStatus(false);await refreshGroups(true,true)}catch(error){groupRequests.setError(errorMessage(error,'The duplicate data source could not be initialized.'))}finally{initialLoading=false}})();return()=>{groupRequests.cancel();historyRequests.cancel();persistence.dispose()}});
</script>

<V2PageLayout title="Duplicates" description="Review similar assets, choose keepers, and apply duplicate actions safely.">
  {#snippet headerActions()}<V2Inline class="v2-duplicates-header-actions" gap="sm" wrap={true}><div class="v2-duplicates-header-scope"><V2Segmented items={[{value:'Current page',label:'Current page only'},{value:'All matching',label:'All matching filters'}]} active={selectionScope} onselect={(value)=>selectionScope=value as typeof selectionScope} ariaLabel="Duplicate bulk-action scope"/></div><div class="v2-duplicates-header-secondary"><V2Button disabled={!discoveryReady||loading||mutating} onclick={()=>void runDiscovery()}>{mutating?(operations.phase==='reconciling'?'Refreshing…':'Working…'):'Run discovery'}</V2Button></div><div class="v2-duplicates-header-primary"><V2Button variant="primary" disabled={!capabilities.canApplyDecisions||mutating} onclick={()=>requestReviewAll()}>Review actions{selectedGroups.length?` (${selectedGroups.length})`:''}</V2Button></div></V2Inline>{/snippet}
  {#snippet tabs()}<V2Tabs items={['Review','Rules & discovery','Resolution history']} active={tab} ariaLabel="Duplicate sections" onselect={selectTab}/>{/snippet}
  {#snippet context()}<V2Zone>{#if tab==='Review'}<DuplicateReviewControls sourceFilter={sourceFilter} reviewFilter={reviewFilter} reviewFilterOptions={reviewFilterOptions} selectionScope={selectionScope} groupCount={groups.length} mutating={mutating} keeperSummary={keeperSummary} decisions={capabilities.decisions} bulkPresetDisabled={bulkPresetDisabled} onsourcefilter={setSourceFilter} onreviewfilter={setReviewFilter} onselectionchange={(value)=>selectionScope=value} onopenkeeper={()=>keeperRulesOpen=true} onpreset={applyBulkPreset}/>{:else if tab==='Rules & discovery'}<DuplicateDiscoveryIntro />{:else}<DuplicateHistoryControls historyRange={historyRange} canViewHistory={capabilities.canViewHistory} mutating={mutating} reconciling={operations.reconciling} onrangechange={(value)=>{historyRange=value as typeof historyRange;void refreshHistory(true)}} onrefresh={()=>refreshHistory(true)} onclearall={()=>historyClearAll=true}/>{/if}</V2Zone>{/snippet}

  <V2Zone>
    {#if loadError}<V2ErrorState title={tab==='Resolution history'?'Resolution history unavailable':'Duplicate groups unavailable'} message={loadError} onretry={()=>void (tab==='Resolution history'?refreshHistory(true):refreshGroups())}/>{/if}
    {#if interactionError}<V2ErrorState title="Duplicate review needs attention" message={interactionError}/>{/if}
    {#if feedback?.tone==='pending'}<OperationFeedback {feedback}/>{/if}
    <OperationToast {feedback} error={operationError} failureTitle="Duplicate operation failed" retryLabel={retryResolution?'Retry failed':''} onretry={retryResolution?()=>requestReviewAll():undefined}/>
    {#if tab==='Rules & discovery'}<V2SimilarityEvidenceGenerationPanel/>{/if}
    {#if tab==='Review'}<V2Toolbar><V2Badge text={`${total} groups`}/><V2Badge tone="ok" text={`${groups.filter((item)=>item.state==='Actionable').length} loaded ready`}/><V2Badge text={`${decisionCount} decisions`}/>{#if invalidStackCount}<V2Badge tone="warn" text={`${invalidStackCount} stack${invalidStackCount===1?'':'s'} in progress`}/>{/if}{#snippet actions()}<V2CollectionControls id="duplicate-results" {sort} sortFields={[{value:'reclaimable',label:'Reclaimable space'},{value:'members',label:'Group size'},{value:'similarity',label:'Similarity'},{value:'date',label:'Date'},{value:'discovered',label:'Recently discovered'}]} pageSize={collection.pageSize} pageSizes={[6,12,24,48,96,192]} batchLabel="page" resultMode={collection.resultMode} onsort={setSort} onpagesize={setPageSize} onmode={setMode}/><V2Button disabled={reviewLoading||mutating} onclick={()=>void selectAllGroups()}>{selectingAll?'Selecting…':'Select all groups'}</V2Button><V2Button disabled={reviewLoading||mutating} onclick={()=>void refreshGroups(true,false)}>Refresh groups</V2Button><V2Button disabled={mutating} onclick={()=>void clearAllDecisions()}>Clear decisions</V2Button>{/snippet}</V2Toolbar>
    {#each groups as item (item.id)}
      {@const groupStacks=stacksForGroup(stackWorkspace,item.id)}
      <div id={duplicateGroupAnchorId(item.id)} class="duplicate-group-anchor" tabindex="-1"><V2Card class="v2-duplicate-group"><V2Stack gap="md"><V2Inline justify="between" align="start" wrap={true}><V2Inline gap="sm" wrap={true}><span class="v2-duplicate-group-selector"><V2RoundCheckbox checked={selectedGroups.includes(item.id)} disabled={mutating} ariaLabel={`${selectedGroups.includes(item.id)?'Deselect':'Select'} ${duplicateGroupTitle(item)}`} onclick={()=>toggleGroup(item.id,!selectedGroups.includes(item.id))}/><button class="v2-duplicate-group-title" type="button" disabled={mutating} title={duplicateGroupTitle(item)} onclick={()=>toggleGroup(item.id,!selectedGroups.includes(item.id))}>{duplicateGroupTitle(item)}</button></span><V2Badge text={`${item.members.length} assets`}/><V2Badge text={duplicateKindLabel(item.kind)}/>{#each duplicateSourceLabels(item.discoverySources) as source (source)}<V2Badge text={source}/>{/each}{#if item.groupSimilarity!==null}<V2Badge text={`${formatSimilarityPercent(item.groupSimilarity)} group similarity`}/>{/if}{#if item.similarityValidationMode}<V2Badge text={`${item.similarityValidationMode} validation`}/>{/if}<V2Badge tone={item.state==='Actionable'?'ok':item.state==='Blocked'?'bad':'warn'} text={item.state}/></V2Inline><V2Inline gap="sm" wrap={true}>{#if capabilities.decisions.includes('keep')}<V2Button disabled={mutating} onclick={()=>presetGroup(item,'keep')}>Keep all</V2Button>{/if}{#if capabilities.decisions.includes('delete')}<V2Button disabled={mutating} onclick={()=>presetGroup(item,'delete')}>Delete all</V2Button>{/if}{#if capabilities.decisions.includes('stack')}<V2Button disabled={mutating} onclick={()=>presetGroup(item,'stack')}>Stack all</V2Button>{/if}<V2Button disabled={mutating} onclick={()=>clearGroupChoices(item)}>Clear choices</V2Button><V2Button onclick={()=>openCompare(item.id,0)}>Compare</V2Button><V2Button variant="primary" disabled={mutating||!capabilities.canApplyDecisions||!groupComplete(item,decisions)} title={!groupComplete(item,decisions)?'Choose an action for every asset first':'Review only this group'} onclick={()=>requestReviewGroup(item)}>Review group</V2Button></V2Inline></V2Inline>
      {#if capabilities.decisions.includes('stack')}<V2DuplicateStackControls stacks={groupStacks} activeStackId={stackWorkspace.activeByGroup[item.id]??null} disabled={mutating} onselect={(stackId)=>chooseStack(item.id,stackId)} oncreate={()=>newStack(item.id)}/>{/if}
      <div class="v2-duplicate-members">
      {#each item.members as member,index (member.asset.id)}
        {@const pendingStack=stackForAsset(stackWorkspace,item.id,member.asset.id)}
        <div class="v2-duplicate-member"><div class="v2-duplicate-image-wrap"><button class="v2-duplicate-image" onclick={()=>openCompare(item.id,index)}><V2LazyAssetMedia cacheKey={`duplicate-thumbnail:${member.asset.id}`} resolve={()=>libraryData.media.thumbnail(member.asset)} alt={member.asset.original_file_name}/>{#if pendingStack}<span class="v2-stack-primary-badge">{pendingStack.label}{pendingStack.primaryAssetId===member.asset.id?' · Primary':''}</span>{/if}<span class="v2-duplicate-image-meta"><span class="v2-duplicate-image-meta-heading"><b>{member.asset.original_file_name}</b>{#if member.similarity!==null}<span class="v2-duplicate-image-similarity">{formatSimilarityPercent(member.similarity)}</span>{/if}</span><small>{duplicateListMemberMeta(member.asset,null)}</small></span></button><V2DuplicateAdmissionEvidence {member} members={item.members} mode={item.similarityValidationMode}/></div><V2DuplicateDecisionControls decision={decisionFor(decisions,item.id,member.asset.id)} stackLabel={pendingStack?.label??'Stack'} isPrimary={pendingStack?.primaryAssetId===member.asset.id} decisions={capabilities.decisions} disabled={mutating} ondecision={(decision)=>setDecision(item.id,member.asset.id,decision)} onprimary={()=>setStackPrimary(item.id,member.asset.id)}/></div>
      {/each}
    </div></V2Stack></V2Card></div>{/each}
    {#if !loading && total===0}<V2Card><V2Stack gap="xs"><b>No duplicate groups found</b><span class="v2-muted">Try another source or review state, or run discovery to look for new matches.</span></V2Stack></V2Card>{/if}
    {#if total>0}<V2CollectionFooter resultMode={collection.resultMode} page={collection.page} pageSize={collection.pageSize} {total} loaded={groups.length} noun="groups" onpage={setPage} onloadmore={loadMore}/>{/if}
  {:else if tab==='Rules & discovery'}<V2Toolbar sticky={false}><b>Rules & discovery</b><V2Badge text={capabilities.canRunDiscovery?'Available':'Unavailable'}/></V2Toolbar><V2Card title="Duplicate discovery"><V2Stack gap="md"><V2Checkbox label="Verify duplicate groups reported by Immich" checked={includeExact} onchange={(checked)=>includeExact=checked}/><V2Checkbox label="Find visually similar images" checked={includeSimilar} onchange={(checked)=>includeSimilar=checked}/>{#if includeSimilar}<V2Field label="Minimum visual similarity (%)" type="number" min={50} max={100} step={0.1} value={similarityThreshold} onchange={(value)=>similarityThreshold=value}/><PerceptualDistanceSetting value={maximumPerceptualDistance} onchange={(value)=>maximumPerceptualDistance=String(value)}/><V2DuplicateValidationSettings mode={validationMode} onchange={(mode)=>validationMode=mode}/>{#if validationMode==='linked'}<V2Field label="Maximum link depth" type="number" min={0} max={64} step={1} value={maxLinkDepth} onchange={(value)=>maxLinkDepth=value}/><span class="v2-small v2-muted">0 keeps only direct matches to the group reference. 1 also allows matches found from those direct matches. 2 allows one more linked expansion. This value matches the link-depth number shown on indirectly linked image pills.</span>{/if}<V2Field label="Comparison candidates per image" type="number" min={1} max={64} step={1} value={maxCandidates} onchange={(value)=>maxCandidates=value}/><V2Field label="Maximum retained similarity matches" type="number" min={1} max={50000} step={1} value={maximumMatches} onchange={(value)=>maximumMatches=value}/><span class="v2-small v2-muted">The retained-match limit defaults to 5,000 and can be raised to 50,000. When more above-threshold pairs are found, Companion keeps the strongest matches and reports that the retention limit was reached. Higher candidate and retention limits increase scan work, memory, and stored result size. These discovery defaults are stored in Companion's database and shared across browsers when discovery is run. Running discovery explicitly revalidates group membership; changing the comparison reference does not.</span>{/if}<V2Button variant="primary" disabled={!discoveryReady||mutating} onclick={()=>void runDiscovery()}>{mutating?(operations.phase==='reconciling'?'Refreshing results…':'Running discovery…'):'Run duplicate discovery'}</V2Button>{#if !includeExact&&!includeSimilar}<span class="v2-small v2-muted">Select at least one discovery method.</span>{/if}{#if discoveryRetention}<V2Inline gap="sm" wrap={true}><V2Badge tone={discoveryRetention.reached?'bad':'ok'} text={discoveryRetention.reached?'Retention limit reached':'Retention limit not reached'}/><span class="v2-small v2-muted">{discoveryRetention.count.toLocaleString()} / {discoveryRetention.limit.toLocaleString()} similarity matches retained{discoveryRetention.reached?' · additional qualifying matches were found and not retained':''}.</span></V2Inline>{/if}{#if discoverySummary}<span class="v2-small v2-muted">{discoverySummary}</span>{/if}</V2Stack></V2Card><V2DuplicateCachePanel status={cacheTelemetry} loading={cacheLoading} error={cacheError} onrefresh={()=>void refreshCacheStatus(true)} onclear={(cache)=>void clearCache(cache)}/>
  {:else if historyRequests.loading}<V2Card><span class="v2-muted" role="status">Loading resolution history…</span></V2Card>
  {:else}<DuplicateHistoryList history={history} mutating={mutating} reconciling={operations.reconciling} onselect={(row)=>historyDetail=row} onclear={(row)=>historyClearTarget=row}/>{/if}
  </V2Zone>
</V2PageLayout>

{#if reviewLoading && tab==='Review'}<V2CollectionLoadingOverlay label="Loading duplicate groups…" />{/if}
{#if planPreparing && reviewProgressPhase}<DuplicateReviewProgress phase={reviewProgressPhase} overlay={true}/>{/if}

{#if keeperRulesOpen}<DuplicateKeeperModal groupIds={groups.map((item)=>item.id)} initialScope={selectionScope==='All matching'?'all_matching':'current_page'} {reviewFilter} {sourceFilter} onclose={()=>keeperRulesOpen=false} onapplied={(result)=>void keeperRulesApplied(result)}/>{/if}
{#if historyDetail}<V2DuplicateHistoryDetail resolution={historyDetail} onclose={()=>historyDetail=null}/>{/if}

<DuplicateCompareViewer open={compare} groupTitle={activeGroup?duplicateGroupTitle(activeGroup):'Duplicate comparison'} groupKind={activeGroup?.kind??''} groupSimilarity={activeGroup?.groupSimilarity??null} groupMembers={activeGroup?.members??[]} validationMode={activeGroup?.similarityValidationMode??null} similarityThreshold={activeGroup?.similarityThresholdPercent??null} assetIds={activeAssetIds} similarities={activeSimilarities} similarityEvidence={activeSimilarityEvidence} decisions={decisionsForGroup(decisions,group) as Record<string,DuplicateDecision>} decisionOptions={capabilities.decisions} stackLabel={activeCompareStack?.label??'Stack'} stackPrimary={activeCompareStack?.primaryAssetId===activeAssetIds[member]} selectedForReview={selectedGroups.includes(group)} disabled={mutating} {canPreviousGroup} {canNextGroup} {groupNavigationLoading} ongroupnavigate={navigateCompareGroup} bind:member bind:reference ondecisionchange={(assetId,decision)=>setDecision(group,assetId,decision)} ondecisionclear={(assetId)=>clearDecision(group,assetId)} onstackprimary={(assetId)=>setStackPrimary(group,assetId)} onreferencechange={switchReference} onrevalidate={activeGroup?.similarityValidationMode?revalidateFromReference:undefined} onclose={()=>{compare=false;persistSelection()}}/>
{#if errorDialog}<NoticeDialog id="duplicate-review-error" title={errorDialog.title} message={errorDialog.message} onclose={()=>errorDialog=null}/>{/if}
{#if pendingReview}
  <ConfirmDialog title={pendingReview.scope==='group'?`Review ${groupDisplayName(pendingReview.groupId)}?`:'Review duplicate actions?'} message={pendingReview.scope==='group'?'The action plan is ready. Execute the Keep, Delete and Stack choices for this group now? Other groups and their current choices will be left untouched.':`The frozen plan contains ${pendingReview.plan.groupIds.length} selected duplicate ${pendingReview.plan.groupIds.length===1?'group':'groups'}. Execute its saved Keep, Delete and Stack choices?`} confirmLabel={pendingReview.scope==='group'?'Execute group plan':'Execute action plan'} icon="check" size="wide" destructive={pendingReview.plan.destructive??Object.values(pendingReview.plan.resolution.decisions).includes('delete')} pending={mutating} pendingLabel={operations.phase==='reconciling'?'Refreshing results…':'Applying actions…'} onconfirm={()=>void confirmPendingReview()} onclose={()=>{if(!mutating)pendingReview=null}}>
    {#snippet detail()}<DuplicateReviewProgress phase={reviewConfirmationPhase}/>{/snippet}
  </ConfirmDialog>
{/if}
{#if historyClearTarget}<ConfirmDialog title="Clear this resolution?" message="This removes Companion's completed-resolution record so a currently discovered matching group can be reviewed again. It does not restore trashed assets, undo stacks, or reverse changes already applied in Immich." confirmLabel="Clear resolution" icon="trash" destructive={true} pending={mutating} onconfirm={()=>void clearHistoryResolution()} onclose={()=>{if(!mutating)historyClearTarget=null}}/>{/if}
{#if historyClearAll}<ConfirmDialog title="Clear all resolution history?" message="This removes every completed duplicate-resolution record in Companion, including history outside the currently selected date range, so matching groups can be reviewed again. It does not restore trashed assets, undo stacks, or reverse changes already applied in Immich." confirmLabel="Clear all resolution history" icon="trash" destructive={true} pending={mutating} onconfirm={()=>void clearAllHistoryResolutions()} onclose={()=>{if(!mutating)historyClearAll=false}}/>{/if}

<style>
  .v2-duplicate-image-wrap{position:relative;width:100%}
  .v2-duplicate-image-meta-heading{display:flex;align-items:center;gap:6px;min-width:0}
  .v2-duplicate-image-meta-heading b{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .v2-duplicate-image-similarity{flex:none;margin-left:auto;padding:2px 5px;border:1px solid rgba(255,255,255,.32);border-radius:999px;background:rgba(8,13,19,.78);color:#fff;font-size:10px;font-weight:800;line-height:1.2;text-shadow:none}
  .v2-stack-primary-badge{position:absolute;z-index:3;top:8px;right:8px;display:inline-flex;align-items:center;gap:4px;padding:4px 7px;border:1px solid rgba(255,255,255,.36);border-radius:999px;background:rgba(8,13,19,.86);color:#fff;font-size:10px;font-weight:700;line-height:1;box-shadow:0 2px 8px rgba(0,0,0,.3)}
  .v2-duplicate-group-selector{display:flex;align-items:center;min-width:0;max-width:min(36rem,65vw)}
  .v2-duplicate-group-title{display:block;min-width:0;max-width:min(34rem,60vw);overflow:hidden;border:0;padding:4px 2px;background:transparent;color:inherit;font:inherit;font-weight:700;text-align:left;text-overflow:ellipsis;white-space:nowrap;cursor:pointer}
  .v2-duplicate-group-title:focus-visible{outline:2px solid var(--v2-accent);outline-offset:2px;border-radius:4px}
  .v2-duplicate-group-title:disabled{cursor:default;opacity:.55}
  .duplicate-group-anchor{border-radius:var(--v2-radius)}
  .duplicate-group-anchor:focus{outline:2px solid var(--v2-warn, #f0ad4e);outline-offset:4px}
</style>
