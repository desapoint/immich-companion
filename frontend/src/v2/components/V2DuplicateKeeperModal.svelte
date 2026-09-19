<script lang="ts">
  import { ArrowDown, ArrowUp, Plus, Trash2 } from '@lucide/svelte';
  import { onMount } from 'svelte';
  import { jsonRequest, requestJson } from '../../lib/api/http';
  import SelectField, { type SelectOption } from './SelectField.svelte';
  import DateTimePickerField from './DateTimePickerField.svelte';
  import V2Badge from './V2Badge.svelte';
  import V2Button from './V2Button.svelte';
  import V2Card from './V2Card.svelte';
  import V2Checkbox from './V2Checkbox.svelte';
  import V2Field from './V2Field.svelte';
  import V2Inline from './V2Inline.svelte';
  import V2Modal from './V2Modal.svelte';
  import V2Segmented from './V2Segmented.svelte';
  import V2Stack from './V2Stack.svelte';
  import { libraryData } from '../data/currentDataSource.svelte';
  import DuplicateAutomationRulesEditor from '../../features/duplicates/components/DuplicateAutomationRulesEditor.svelte';
  import DuplicateKeeperPriorityEditor from '../../features/duplicates/components/DuplicateKeeperPriorityEditor.svelte';
  import type {
    AssetRecord,
    DuplicateDecision,
    DuplicateGroupRecord,
    DuplicateKeeperRuleField,
    DuplicateKeeperSelectionResult,
    DuplicateSource,
    DuplicateSourceFilter,
    DuplicateState,
  } from '../data/contracts';
  import {
    automationActionOptions,
    automationConditionFieldOptions,
    automationConditionNeedsValue,
    automationConditionScopeOptions,
    automationFlowOptions,
    automationOperatorOptions,
    automationPreset,
    automationPresetNames,
    automationRuleValid,
    automationTargetOptions,
    evaluateDuplicateAutomation,
    newAutomationCondition,
    newAutomationRule,
    type AutomationPresetName,
    type DuplicateAutomationConditionField,
    type DuplicateAutomationConditionScope,
    type DuplicateAutomationExistingDecision,
    type DuplicateAutomationUiCondition,
    type DuplicateAutomationUiRule,
  } from '../../features/duplicates/state/duplicateAutomationRules';
  import {
    keeperEffectOptions,
    keeperFieldDefinition,
    keeperOperatorOptions,
    keeperPreset,
    keeperPresetNames,
    keeperRuleFieldOptions,
    keeperRuleNeedsValue,
    newKeeperRule,
    normalizeKeeperRule,
    type DuplicateKeeperUiRule,
    type KeeperPresetName,
  } from '../state/duplicateKeeperRules';

  let {
    groupIds,
    initialScope = 'current_page',
    reviewFilter,
    sourceFilter,
    onclose,
    onapplied,
  }: {
    groupIds: string[];
    initialScope?: 'current_page'|'all_matching';
    reviewFilter: DuplicateState|'All groups'|'Auto-ready'|'Selected';
    sourceFilter: DuplicateSourceFilter;
    onclose: () => void;
    onapplied?: (result: DuplicateKeeperSelectionResult) => void;
  } = $props();

  type ApiDuplicateMember = {
    id:string;
    library_id:string|null;
    original_file_name:string;
    original_mime_type:string|null;
    file_size_bytes:number|null;
    file_modified_at:string;
    uploaded_at:string|null;
    is_offline:boolean;
    evidence:{decoded_width?:number|null;decoded_height?:number|null};
    similarity:{state:'reference'|'current'|'pending'|'unavailable';similarity_percent:number|null;structural_percent:number|null;perceptual_percent:number|null;color_percent:number|null;detail_changed_percent?:number|null;detail_source?:'original'|'transcoded'|'preview'|null}|null;
    admission:{admitted_by_asset_id:string|null;admission_similarity_percent:number|null;best_group_match_asset_id:string|null;best_group_match_similarity_percent:number|null;link_depth:number;model_version:string;feature_version:number;comparison_version:number;config_fingerprint:string}|null;
  };
  type ApiDuplicateGroup = {
    group_id:string;
    discovery_source:DuplicateSource;
    discovery_sources?:DuplicateSource[];
    reference_asset_id:string|null;
    group_similarity_percent:number|null;
    similarity_engine:string|null;
    similarity_model_version:string|null;
    similarity_feature_version:number|null;
    similarity_comparison_version:number|null;
    similarity_validation_mode:'reference'|'linked'|'strict'|null;
    similarity_threshold_percent:number|null;
    classification:'exact_file'|'exact_pixels'|'likely_same'|'similar'|'mismatch'|'unverified'|'unavailable'|'ineligible';
    status:'exact'|'unverified'|'mismatch'|'ineligible';
    reason:string|null;
    auto_resolvable:boolean;
    auto_selected:boolean;
    member_fingerprint:string;
    members:ApiDuplicateMember[];
    eligible:boolean;
  };
  type ApiDuplicatePage={items:ApiDuplicateGroup[];total:number;page:number;page_size:number;pages:number};
  type ApiDraftDecision={asset_id:string;disposition:DuplicateDecision;source?:'manual'|'automatic';status?:'pending'|'completed'};
  type ApiDraft={group_id:string;member_fingerprint:string;decisions:ApiDraftDecision[];stack_primary_asset_id:string|null;stack_resolution:'keep_existing'|'move_selected'|'include_existing';metadata_keeper_asset_id?:string|null;status:'pending'|'completed';stale:boolean};
  type ApiWorkspace={revision:number;selected_group_ids:string[];active_group_id:string|null;drafts:ApiDraft[]};
  type AutomationSummary=DuplicateKeeperSelectionResult&{
    completeGroupCount:number;
    partialGroupCount:number;
    manualReviewGroupCount:number;
    keepCount:number;
    stackCount:number;
    undecidedMemberCount:number;
  };

  const ANALYSIS_OPTIONS={keeper_policy:'prefer_upload',external_library_ids:[],verify_upload_streams:false,automatic_handling_enabled:true,preselect_safe_groups:true,exact_file_action:'resolve',analyze_automatically:false} as const;
  const MAX_AUTOMATION_GROUPS=10_000;
  const WRITE_CONCURRENCY=4;
  const PAGE_SIZE=100;

  let nextAutomationRuleId=1,nextConditionId=1,nextKeeperId=1;
  const automationRuleId=()=>nextAutomationRuleId++;
  const conditionId=()=>nextConditionId++;
  const keeperId=()=>nextKeeperId++;
  let scope=$state<'current_page'|'all_matching'>('current_page');
  $effect(()=>{scope=initialScope});
  let preset=$state<AutomationPresetName>('Protect uploads for review');
  let rules=$state<DuplicateAutomationUiRule[]>(automationPreset('Protect uploads for review',automationRuleId,conditionId));
  let keeperPresetName=$state<KeeperPresetName>('Highest quality');
  let keeperRules=$state<DuplicateKeeperUiRule[]>(keeperPreset('Highest quality',keeperId));
  let overwriteManual=$state(false);
  let preview=$state<AutomationSummary|null>(null);
  let busy=$state(false),error=$state('');
  let albumOptions=$state<SelectOption[]>([]),tagOptions=$state<SelectOption[]>([]);
  let albumLoading=$state(false),tagLoading=$state(false);

  const normalizedKeeperRules=$derived(keeperRules.map(normalizeKeeperRule).filter((rule)=>!keeperRuleNeedsValue(rule)||rule.value.trim().length>0));
  const rulesValid=$derived(rules.length>0&&rules.every(automationRuleValid));
  const canRun=$derived(rulesValid&&normalizedKeeperRules.length>0&&!busy&&(scope==='all_matching'||groupIds.length>0));

  function markDirty(){preview=null;error=''}
  function applyAutomationPreset(value:string){preset=value as AutomationPresetName;rules=automationPreset(preset,automationRuleId,conditionId);markDirty()}
  function addAutomationRule(){rules=[...rules,newAutomationRule(automationRuleId(),conditionId())];markDirty()}
  function removeAutomationRule(id:number){rules=rules.filter((rule)=>rule.id!==id);markDirty()}
  function moveAutomationRule(index:number,direction:-1|1){const target=index+direction;if(target<0||target>=rules.length)return;const copy=[...rules];[copy[index],copy[target]]=[copy[target],copy[index]];rules=copy;markDirty()}
  function updateAutomationRule(id:number,patch:Partial<DuplicateAutomationUiRule>){rules=rules.map((rule)=>rule.id===id?{...rule,...patch}:rule);markDirty()}
  function addCondition(ruleId:number){rules=rules.map((rule)=>rule.id===ruleId?{...rule,conditions:[...rule.conditions,newAutomationCondition(conditionId())]}:rule);markDirty()}
  function removeCondition(ruleId:number,condition:number){rules=rules.map((rule)=>rule.id===ruleId?{...rule,conditions:rule.conditions.filter((item)=>item.id!==condition)}:rule);markDirty()}
  function updateCondition(ruleId:number,conditionIdValue:number,patch:Partial<DuplicateAutomationUiCondition>){
    rules=rules.map((rule)=>{
      if(rule.id!==ruleId)return rule;
      return{...rule,conditions:rule.conditions.map((condition)=>{
        if(condition.id!==conditionIdValue)return condition;
        let next={...condition,...patch};
        if(patch.scope){
          next=patch.scope==='group'
            ?{...next,field:'classification',operator:'is',value:'exact file'}
            :{...next,field:'library',operator:'is',value:'upload'};
        }
        if(patch.field||patch.scope){
          const operators=automationOperatorOptions(next);
          if(!operators.some((item)=>item.value===next.operator))next={...next,operator:(operators[0]?.value??'is') as DuplicateAutomationUiCondition['operator'],value:''};
        }
        if(patch.operator&&!automationConditionNeedsValue(next))next={...next,value:''};
        return next;
      })};
    });
    markDirty();
  }

  function applyKeeperPreset(value:string){keeperPresetName=value as KeeperPresetName;keeperRules=keeperPreset(keeperPresetName,keeperId);markDirty()}
  function updateKeeperRule(id:number,patch:Partial<DuplicateKeeperUiRule>){
    keeperRules=keeperRules.map((rule)=>{
      if(rule.id!==id)return rule;
      const next={...rule,...patch};
      if(patch.field||patch.effect){const operators=keeperOperatorOptions(next.field,next.effect);if(!operators.some((item)=>item.value===next.operator)){next.operator=(operators[0]?.value??'is') as DuplicateKeeperUiRule['operator'];next.value=''}}
      if(patch.operator&&!keeperRuleNeedsValue(next))next.value='';
      return next;
    });markDirty();
  }
  function addKeeperRule(){keeperRules=[...keeperRules,newKeeperRule(keeperId())];markDirty()}
  function removeKeeperRule(id:number){keeperRules=keeperRules.filter((rule)=>rule.id!==id);markDirty()}
  function moveKeeperRule(index:number,direction:-1|1){const target=index+direction;if(target<0||target>=keeperRules.length)return;const copy=[...keeperRules];[copy[index],copy[target]]=[copy[target],copy[index]];keeperRules=copy;markDirty()}

  async function loadOptions(kind:'album'|'tag',query=''){
    if(kind==='album')albumLoading=true;else tagLoading=true;
    try{
      const result=kind==='album'?await libraryData.albums.searchOptions({query,pageSize:50}):await libraryData.tags.searchOptions({query,pageSize:50});
      const options=result.items.map((item)=>({value:item.value,label:item.label,subtitle:item.subtitle}));
      if(kind==='album')albumOptions=options;else tagOptions=options;
    }finally{if(kind==='album')albumLoading=false;else tagLoading=false}
  }
  function relationValues(value:string){return value.split(',').map((part)=>part.trim()).filter(Boolean)}
  function setConditionRelations(ruleId:number,condition:DuplicateAutomationUiCondition,values:string[]){updateCondition(ruleId,condition.id,{value:values.join(',')})}
  function setKeeperRelations(rule:DuplicateKeeperUiRule,values:string[]){updateKeeperRule(rule.id,{value:values.join(',')})}
  function memberInputKind(field:DuplicateKeeperRuleField){return keeperFieldDefinition(field).kind}
  function groupInputKind(field:DuplicateAutomationConditionField){return['member_count','group_similarity','decision_count','undecided_count'].includes(field)?'number':['auto_ready','selected','eligible'].includes(field)?'boolean':'text'}
  function conditionInputKind(condition:DuplicateAutomationUiCondition){return condition.scope==='group'?groupInputKind(condition.field):memberInputKind(condition.field as DuplicateKeeperRuleField)}
  function placeholder(field:DuplicateAutomationConditionField){if(field==='library')return'upload or library UUID';if(field==='folder')return'/photos/originals';if(field==='extension')return'dng, heic, jpg…';if(field==='mime_type')return'image/jpeg';if(field==='classification')return'exact file, exact pixels';if(field==='review_state')return'Needs review';if(field==='discovery_source')return'immich_duplicate';return'Value'}

  function reviewStateParam(state:typeof reviewFilter){if(state==='Needs review')return'needs_review';if(state==='Auto-ready')return'auto_ready';if(state==='Blocked')return'blocked';if(state==='Actionable')return'actionable';if(state==='Needs decisions')return'needs_decisions';return'all'}
  function draftFor(workspace:ApiWorkspace,groupId:string){return workspace.drafts.find((draft)=>draft.group_id===groupId)}
  function groupState(raw:ApiDuplicateGroup,draft:ApiDraft|undefined):DuplicateState{if(!raw.eligible||raw.status==='ineligible'||draft?.stale)return'Blocked';const count=draft?.decisions.length??0;if(count>0&&count<raw.members.length)return'Needs decisions';if(count===raw.members.length||raw.auto_resolvable||raw.auto_selected)return'Actionable';return'Needs review'}
  function fallbackAsset(member:ApiDuplicateMember):AssetRecord{return{id:member.id,owner_id:null,library_id:member.library_id,asset_type:member.original_mime_type?.startsWith('video/')?'VIDEO':member.original_mime_type?.startsWith('audio/')?'AUDIO':member.original_mime_type?.startsWith('image/')?'IMAGE':'OTHER',original_file_name:member.original_file_name,original_path:null,original_mime_type:member.original_mime_type,checksum:null,file_size_bytes:member.file_size_bytes,width:member.evidence.decoded_width??null,height:member.evidence.decoded_height??null,duration:null,file_created_at:member.uploaded_at??member.file_modified_at,file_modified_at:member.file_modified_at,local_date_time:null,immich_created_at:member.uploaded_at,immich_updated_at:null,is_favorite:false,is_archived:false,is_offline:member.is_offline,is_edited:false,has_metadata:false,visibility:null,live_photo_video_id:null,tags:[],albums:[],stack:null,synced_at:member.file_modified_at}}
  function materializeGroup(raw:ApiDuplicateGroup,assets:Map<string,AssetRecord>,workspace:ApiWorkspace):DuplicateGroupRecord{
    const draft=draftFor(workspace,raw.group_id);
    const savedDecisions=Object.fromEntries((draft?.decisions??[]).map((decision)=>[decision.asset_id,decision.disposition])) as Record<string,DuplicateDecision>;
    return{id:raw.group_id,discoverySources:raw.discovery_sources?.length?raw.discovery_sources:[raw.discovery_source],state:groupState(raw,draft),autoReady:raw.auto_selected,kind:raw.classification.replaceAll('_',' '),reason:raw.reason,referenceAssetId:raw.reference_asset_id,groupSimilarity:raw.group_similarity_percent,similarityEngine:raw.similarity_engine,similarityModelVersion:raw.similarity_model_version,similarityFeatureVersion:raw.similarity_feature_version,similarityComparisonVersion:raw.similarity_comparison_version,similarityValidationMode:raw.similarity_validation_mode,similarityThresholdPercent:raw.similarity_threshold_percent,memberFingerprint:raw.member_fingerprint,selected:workspace.selected_group_ids.includes(raw.group_id),savedDecisions,stackPrimaryAssetId:draft?.stack_primary_asset_id??null,stackResolution:draft?.stack_resolution??'move_selected',members:raw.members.map((member)=>({asset:assets.get(member.id)??fallbackAsset(member),similarity:member.similarity?.state==='reference'?100:member.similarity?.similarity_percent??null,similarityEvidence:member.similarity?{structuralPercent:member.similarity.structural_percent,perceptualPercent:member.similarity.perceptual_percent,colorPercent:member.similarity.color_percent,...(member.similarity.detail_changed_percent!==undefined?{detailChangedPercent:member.similarity.detail_changed_percent}:{}),...(member.similarity.detail_source!==undefined?{detailSource:member.similarity.detail_source}:{}),}:null,admission:member.admission?{admittedByAssetId:member.admission.admitted_by_asset_id,admissionSimilarityPercent:member.admission.admission_similarity_percent,bestGroupMatchAssetId:member.admission.best_group_match_asset_id,bestGroupMatchSimilarityPercent:member.admission.best_group_match_similarity_percent,linkDepth:member.admission.link_depth,modelVersion:member.admission.model_version,featureVersion:member.admission.feature_version,comparisonVersion:member.admission.comparison_version,configFingerprint:member.admission.config_fingerprint}:null}))}
  }
  async function loadAssets(rawGroups:ApiDuplicateGroup[]):Promise<Map<string,AssetRecord>>{const ids=[...new Set(rawGroups.flatMap((item)=>item.members.map((member)=>member.id)))],result=new Map<string,AssetRecord>();for(let offset=0;offset<ids.length;offset+=200){const assets=await libraryData.assets.getMany(ids.slice(offset,offset+200));for(const asset of assets)result.set(asset.id,asset)}return result}
  function existingDecisions(draft:ApiDraft|undefined):DuplicateAutomationExistingDecision[]{return(draft?.decisions??[]).map((decision)=>({assetId:decision.asset_id,disposition:decision.disposition,source:decision.source??'manual',status:decision.status??'pending'}))}
  async function saveAutomationDraft(group:DuplicateGroupRecord,draft:ApiDraft|undefined,evaluation:ReturnType<typeof evaluateDuplicateAutomation>){
    const manualIds=new Set(evaluation.decisions.filter((decision)=>decision.source==='manual').map((decision)=>decision.assetId));
    const stackPrimary=draft?.stack_primary_asset_id&&manualIds.has(draft.stack_primary_asset_id)&&evaluation.decisions.some((decision)=>decision.assetId===draft.stack_primary_asset_id&&decision.disposition==='stack')?draft.stack_primary_asset_id:null;
    const existingMetadata=draft?.metadata_keeper_asset_id??null;
    const metadataKeeper=evaluation.metadataKeeperAssetId??(existingMetadata&&manualIds.has(existingMetadata)?existingMetadata:null);
    await requestJson('/api/assets/duplicates/workspace/group',jsonRequest('PUT',{group_id:group.id,member_fingerprint:group.memberFingerprint,options:ANALYSIS_OPTIONS,decisions:evaluation.decisions.map((decision)=>({asset_id:decision.assetId,disposition:decision.disposition,source:decision.source,status:decision.status})),stack_primary_asset_id:stackPrimary,stack_resolution:draft?.stack_resolution??'move_selected',metadata_keeper_asset_id:metadataKeeper,status:evaluation.decisions.length===group.members.length?'completed':'pending'}));
  }
  async function mapLimit<T>(items:T[],limit:number,worker:(item:T)=>Promise<void>){let next=0;await Promise.all(Array.from({length:Math.min(limit,items.length)},async()=>{while(next<items.length){const index=next++;await worker(items[index])}}))}
  function emptySummary():AutomationSummary{return{matchedGroupCount:0,validGroupCount:0,resolvedGroupCount:0,wouldApplyGroupCount:0,appliedGroupCount:0,ambiguousGroupCount:0,blockedGroupCount:0,preservedManualGroupCount:0,missingGroupCount:0,keeperCount:0,trashCount:0,limitExceeded:false,completeGroupCount:0,partialGroupCount:0,manualReviewGroupCount:0,keepCount:0,stackCount:0,undecidedMemberCount:0}}

  async function runAutomation(apply:boolean):Promise<AutomationSummary>{
    const workspace=await requestJson<ApiWorkspace>('/api/assets/duplicates/workspace');
    const summary=emptySummary();
    const explicitIds=scope==='current_page'?new Set(groupIds):reviewFilter==='Selected'?new Set(workspace.selected_group_ids):null;
    if(scope==='all_matching'&&reviewFilter==='Selected'&&explicitIds&&explicitIds.size>MAX_AUTOMATION_GROUPS){summary.matchedGroupCount=explicitIds.size;summary.limitExceeded=true;return summary}
    const found=new Set<string>(),appliedIds:string[]=[];
    let page=1,pages=1;
    do{
      const params=new URLSearchParams({page:String(page),page_size:String(PAGE_SIZE),source:sourceFilter,state:reviewStateParam(reviewFilter),sort:'reclaimable',direction:'desc'});
      const rawPage=await requestJson<ApiDuplicatePage>(`/api/assets/duplicates/cross-source/page?${params.toString()}`,jsonRequest('POST',ANALYSIS_OPTIONS));
      pages=rawPage.pages;
      if(page===1&&scope==='all_matching'&&reviewFilter!=='Selected'&&rawPage.total>MAX_AUTOMATION_GROUPS){summary.matchedGroupCount=rawPage.total;summary.limitExceeded=true;return summary}
      const candidates=explicitIds?rawPage.items.filter((item)=>explicitIds.has(item.group_id)):rawPage.items;
      for(const item of candidates)found.add(item.group_id);
      summary.matchedGroupCount+=candidates.length;
      if(candidates.length){
        const assets=await loadAssets(candidates);
        const saves:Array<{group:DuplicateGroupRecord;draft:ApiDraft|undefined;evaluation:ReturnType<typeof evaluateDuplicateAutomation>}>=[];
        for(const raw of candidates){
          const draft=draftFor(workspace,raw.group_id),group=materializeGroup(raw,assets,workspace);
          if(group.state==='Blocked'){summary.blockedGroupCount+=1;continue}
          summary.validGroupCount+=1;
          const evaluation=evaluateDuplicateAutomation(group,rules,existingDecisions(draft),normalizedKeeperRules,overwriteManual);
          if(evaluation.preservedManual)summary.preservedManualGroupCount+=1;
          if(evaluation.ambiguous)summary.ambiguousGroupCount+=1;
          if(!evaluation.touched)continue;
          summary.wouldApplyGroupCount+=1;
          summary.keepCount+=evaluation.keepCount;summary.keeperCount+=evaluation.keepCount;summary.trashCount+=evaluation.deleteCount;summary.stackCount+=evaluation.stackCount;summary.undecidedMemberCount+=evaluation.undecidedCount;
          if(evaluation.complete){summary.completeGroupCount+=1;summary.resolvedGroupCount+=1}else if(evaluation.partial)summary.partialGroupCount+=1;
          if(evaluation.manualReview)summary.manualReviewGroupCount+=1;
          if(apply){appliedIds.push(group.id);if(evaluation.persistDraft)saves.push({group,draft,evaluation})}
        }
        if(apply&&saves.length)await mapLimit(saves,WRITE_CONCURRENCY,({group,draft,evaluation})=>saveAutomationDraft(group,draft,evaluation));
      }
      if(explicitIds&&found.size>=explicitIds.size)break;
      page+=1;
    }while(page<=pages);
    if(explicitIds)summary.missingGroupCount=Math.max(0,explicitIds.size-found.size);
    if(apply&&appliedIds.length){
      const selected=[...new Set([...workspace.selected_group_ids,...appliedIds])];
      const active=workspace.active_group_id&&selected.includes(workspace.active_group_id)?workspace.active_group_id:null;
      await libraryData.duplicates.saveSelection(selected,active);
      await libraryData.duplicates.flushDrafts();
      summary.appliedGroupCount=new Set(appliedIds).size;
    }
    return summary;
  }

  async function runPreview(){if(!canRun)return;busy=true;error='';try{preview=await runAutomation(false)}catch(reason){error=reason instanceof Error?reason.message:'Automation preview failed.'}finally{busy=false}}
  async function applyRules(){if(!canRun)return;busy=true;error='';try{const result=await runAutomation(true);preview=result;if(!result.limitExceeded)onapplied?.(result)}catch(reason){error=reason instanceof Error?reason.message:'Automation rules could not be applied.'}finally{busy=false}}
  onMount(()=>{void Promise.all([loadOptions('album'),loadOptions('tag')])});
</script>

<V2Modal id="duplicate-automation-rules" title="Automation rules" description="Apply ordered group and member rules to generate reviewable decision drafts. Rules may decide only part of a group; untouched members stay undecided for manual review. Nothing is trashed until you review and execute a complete draft." size="xl" onclose={onclose}>
  <V2Stack gap="md">
    <V2Card>
      <V2Stack gap="sm">
        <div class="automation-grid automation-grid--scope">
          <SelectField id="automation-preset" label="Quick preset" value={preset} options={automationPresetNames.map((value)=>({value,label:value}))} onchange={applyAutomationPreset}/>
          <div><span class="v2-field-label">Scope</span><V2Segmented items={[{value:'current_page',label:`Current page · ${groupIds.length} loaded`},{value:'all_matching',label:'All groups matching filters'}]} active={scope} ariaLabel="Automation scope" onselect={(value)=>{scope=value as typeof scope;markDirty()}}/></div>
        </div>
        <span class="v2-small v2-muted">Current page evaluates only the groups loaded in the review list. All groups matching filters evaluates the full current source/state result set. Processing is paged and automatic draft writes are limited to {WRITE_CONCURRENCY} at a time.</span>
        <V2Inline gap="md" wrap><V2Badge>State: {reviewFilter}</V2Badge><V2Badge>Source: {sourceFilter}</V2Badge><V2Checkbox label="Allow automation to replace manual choices" checked={overwriteManual} onchange={(value)=>{overwriteManual=value;markDirty()}}/></V2Inline>
      </V2Stack>
    </V2Card>

    <DuplicateAutomationRulesEditor rules={rules} {albumOptions} {tagOptions} {albumLoading} {tagLoading} updateRule={updateAutomationRule} addRule={addAutomationRule} removeRule={removeAutomationRule} moveRule={moveAutomationRule} {addCondition} {removeCondition} {updateCondition} {loadOptions} {conditionInputKind} {placeholder} {setConditionRelations}/>

    <DuplicateKeeperPriorityEditor rules={keeperRules} presetName={keeperPresetName} {albumOptions} {tagOptions} {albumLoading} {tagLoading} setPreset={applyKeeperPreset} updateRule={updateKeeperRule} addRule={addKeeperRule} removeRule={removeKeeperRule} moveRule={moveKeeperRule} {loadOptions}/>

    {#if preview}
      <V2Card><V2Stack gap="sm"><strong>{preview.wouldApplyGroupCount.toLocaleString()} groups would receive automation changes</strong><div class="preview-grid"><span><b>{preview.matchedGroupCount.toLocaleString()}</b> in scope</span><span><b>{preview.completeGroupCount.toLocaleString()}</b> complete drafts</span><span><b>{preview.partialGroupCount.toLocaleString()}</b> partial drafts</span><span><b>{preview.manualReviewGroupCount.toLocaleString()}</b> need manual review</span><span><b>{preview.keepCount.toLocaleString()}</b> automatic Keep</span><span><b>{preview.trashCount.toLocaleString()}</b> automatic Delete</span><span><b>{preview.stackCount.toLocaleString()}</b> automatic Stack</span><span><b>{preview.undecidedMemberCount.toLocaleString()}</b> members left undecided</span><span><b>{preview.preservedManualGroupCount.toLocaleString()}</b> groups preserving manual choices</span><span><b>{preview.ambiguousGroupCount.toLocaleString()}</b> safely left ambiguous</span><span><b>{preview.blockedGroupCount.toLocaleString()}</b> blocked groups skipped</span></div>{#if preview.limitExceeded}<p class="automation-warning">The matching set exceeds the {MAX_AUTOMATION_GROUPS.toLocaleString()}-group safety limit. Narrow the current filters before applying.</p>{/if}</V2Stack></V2Card>
    {/if}
    {#if error}<p class="automation-error" role="alert">{error}</p>{/if}
  </V2Stack>
  {#snippet footer()}<V2Inline gap="sm"><V2Button disabled={!canRun} onclick={()=>void runPreview()}>{busy?'Working…':'Preview'}</V2Button><V2Button variant="primary" disabled={!canRun||Boolean(preview?.limitExceeded)} onclick={()=>void applyRules()}>{busy?'Working…':'Generate decision drafts'}</V2Button><V2Button onclick={onclose}>Close</V2Button></V2Inline>{/snippet}
</V2Modal>

<style>
  .automation-grid{display:grid;gap:12px;grid-template-columns:repeat(2,minmax(0,1fr))}
  .preview-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px 16px}
  .automation-warning,.automation-error{margin:0;color:var(--v2-danger)}
  @media(max-width:760px){.automation-grid,.preview-grid{grid-template-columns:1fr}}
</style>
