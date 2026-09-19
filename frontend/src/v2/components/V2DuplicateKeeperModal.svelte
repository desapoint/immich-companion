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

    <div class="automation-heading"><div><h3>Decision rules</h3><p>Each rule has conditions, a target, an action, and flow control. Earlier decisions are protected from later rules. Manual choices are protected unless replacement is explicitly enabled.</p></div><V2Button onclick={addAutomationRule}><Plus size={15}/> Add rule</V2Button></div>

    <div class="automation-rule-list">
      {#each rules as rule,index (rule.id)}
        <V2Card>
          <V2Stack gap="sm">
            <div class="automation-rule-header">
              <div class="rule-order"><V2Button iconOnly ariaLabel="Move rule up" disabled={index===0} onclick={()=>moveAutomationRule(index,-1)}><ArrowUp size={15}/></V2Button><strong>Rule {index+1}</strong><V2Button iconOnly ariaLabel="Move rule down" disabled={index===rules.length-1} onclick={()=>moveAutomationRule(index,1)}><ArrowDown size={15}/></V2Button></div>
              <V2Inline gap="sm"><SelectField id={`automation-logic-${rule.id}`} label="Conditions" value={rule.logic} options={[{value:'all',label:'All must match'},{value:'any',label:'Any may match'}]} onchange={(value)=>updateAutomationRule(rule.id,{logic:value as DuplicateAutomationUiRule['logic']})}/><V2Button variant="danger" iconOnly ariaLabel="Remove rule" onclick={()=>removeAutomationRule(rule.id)}><Trash2 size={15}/></V2Button></V2Inline>
            </div>
            <div class="condition-list">
              {#each rule.conditions as condition (condition.id)}
                {@const conditionKind=conditionInputKind(condition)}
                {@const operators=automationOperatorOptions(condition)}
                <div class="condition-row">
                  <SelectField id={`condition-scope-${condition.id}`} label="When" value={condition.scope} options={[...automationConditionScopeOptions]} onchange={(value)=>updateCondition(rule.id,condition.id,{scope:value as DuplicateAutomationConditionScope})}/>
                  <SelectField id={`condition-field-${condition.id}`} label="Field" value={condition.field} options={automationConditionFieldOptions(condition.scope)} searchable onchange={(value)=>updateCondition(rule.id,condition.id,{field:value as DuplicateAutomationConditionField})}/>
                  <SelectField id={`condition-op-${condition.id}`} label="Match" value={condition.operator} options={[...operators]} onchange={(value)=>updateCondition(rule.id,condition.id,{operator:value as DuplicateAutomationUiCondition['operator']})}/>
                  {#if automationConditionNeedsValue(condition)}
                    {#if conditionKind==='media'}
                      <SelectField id={`condition-value-${condition.id}`} label="Value" value={condition.value} options={[{value:'image',label:'Image'},{value:'video',label:'Video'},{value:'audio',label:'Audio'},{value:'other',label:'Other'}]} onchange={(value)=>updateCondition(rule.id,condition.id,{value})}/>
                    {:else if conditionKind==='availability'}
                      <SelectField id={`condition-value-${condition.id}`} label="Value" value={condition.value} options={[{value:'online',label:'Online'},{value:'offline',label:'Offline'}]} onchange={(value)=>updateCondition(rule.id,condition.id,{value})}/>
                    {:else if conditionKind==='date'}
                      <DateTimePickerField id={`condition-value-${condition.id}`} label="Value" value={condition.value} showTime onchange={(value)=>updateCondition(rule.id,condition.id,{value})}/>
                    {:else if conditionKind==='relation'}
                      <SelectField id={`condition-value-${condition.id}`} label="Value" multiple values={relationValues(condition.value)} options={condition.field==='album'?albumOptions:tagOptions} searchable loading={condition.field==='album'?albumLoading:tagLoading} searchPlaceholder={`Search ${condition.field}s…`} onvalueschange={(values)=>setConditionRelations(rule.id,condition,values)} onsearchchange={(query)=>void loadOptions(condition.field==='album'?'album':'tag',query)}/>
                    {:else if condition.field==='classification'}
                      <SelectField id={`condition-value-${condition.id}`} label="Value" value={condition.value} multiple values={relationValues(condition.value)} options={[{value:'exact file',label:'Exact file'},{value:'exact pixels',label:'Exact pixels'},{value:'likely same',label:'Likely same'},{value:'similar',label:'Similar'},{value:'mismatch',label:'Mismatch'},{value:'unverified',label:'Unverified'},{value:'unavailable',label:'Unavailable'},{value:'ineligible',label:'Ineligible'}]} onvalueschange={(values)=>updateCondition(rule.id,condition.id,{value:values.join(',')})}/>
                    {:else if condition.field==='review_state'}
                      <SelectField id={`condition-value-${condition.id}`} label="Value" value={condition.value} options={['Actionable','Needs review','Needs decisions','Blocked'].map((value)=>({value,label:value}))} onchange={(value)=>updateCondition(rule.id,condition.id,{value})}/>
                    {:else if condition.field==='discovery_source'}
                      <SelectField id={`condition-value-${condition.id}`} label="Value" value={condition.value} options={[{value:'immich_duplicate',label:'Immich'},{value:'companion_similarity',label:'Similarity'}]} onchange={(value)=>updateCondition(rule.id,condition.id,{value})}/>
                    {:else}
                      <V2Field label="Value" type={conditionKind==='number'?'number':'text'} value={condition.value} placeholder={placeholder(condition.field)} step={conditionKind==='number'?'any':undefined} onvalueinput={(value)=>updateCondition(rule.id,condition.id,{value})}/>
                    {/if}
                  {:else}<div class="no-value">No value needed</div>{/if}
                  {#if condition.scope==='at_least_members'}<V2Field label="N" type="number" value={String(condition.count)} min="1" step="1" onvalueinput={(value)=>updateCondition(rule.id,condition.id,{count:Math.max(1,Number.parseInt(value||'1',10)||1)})}/>{/if}
                  <V2Button variant="danger" iconOnly ariaLabel="Remove condition" disabled={rule.conditions.length===1} onclick={()=>removeCondition(rule.id,condition.id)}><Trash2 size={15}/></V2Button>
                </div>
              {/each}
            </div>
            <V2Button onclick={()=>addCondition(rule.id)}><Plus size={15}/> Add condition</V2Button>
            <div class="rule-actions">
              <SelectField id={`automation-target-${rule.id}`} label="Target" value={rule.target} options={[...automationTargetOptions]} onchange={(value)=>updateAutomationRule(rule.id,{target:value as DuplicateAutomationUiRule['target']})}/>
              <SelectField id={`automation-action-${rule.id}`} label="Action" value={rule.action} options={[...automationActionOptions]} onchange={(value)=>updateAutomationRule(rule.id,{action:value as DuplicateAutomationUiRule['action']})}/>
              <SelectField id={`automation-flow-${rule.id}`} label="After" value={rule.flow} options={[...automationFlowOptions]} onchange={(value)=>updateAutomationRule(rule.id,{flow:value as DuplicateAutomationUiRule['flow']})}/>
            </div>
            {#if rule.target==='matching_members'&&!rule.conditions.some((condition)=>condition.scope==='member')}<p class="automation-warning">Matching members needs at least one condition whose scope is Member.</p>{/if}
          </V2Stack>
        </V2Card>
      {/each}
    </div>

    <div class="automation-heading"><div><h3>Keeper priority</h3><p>Used only when a rule chooses “Resolve using keeper priority”. Require filters candidates first; Prefer and Avoid then narrow them in order. A remaining tie uses the current reference, otherwise the group stays for manual review.</p></div><V2Button onclick={addKeeperRule}><Plus size={15}/> Add keeper condition</V2Button></div>
    <V2Card><SelectField id="keeper-preset" label="Keeper preset" value={keeperPresetName} options={keeperPresetNames.map((value)=>({value,label:value}))} onchange={applyKeeperPreset}/></V2Card>
    <div class="keeper-rule-list">
      {#each keeperRules as rule,index (rule.id)}
        {@const definition=keeperFieldDefinition(rule.field)}{@const operators=keeperOperatorOptions(rule.field,rule.effect)}
        <V2Card><div class="keeper-rule-row"><div class="rule-order"><V2Button iconOnly ariaLabel="Move keeper condition up" disabled={index===0} onclick={()=>moveKeeperRule(index,-1)}><ArrowUp size={15}/></V2Button><span>{index+1}</span><V2Button iconOnly ariaLabel="Move keeper condition down" disabled={index===keeperRules.length-1} onclick={()=>moveKeeperRule(index,1)}><ArrowDown size={15}/></V2Button></div><SelectField id={`keeper-effect-${rule.id}`} label="Behavior" value={rule.effect} options={keeperEffectOptions} onchange={(value)=>updateKeeperRule(rule.id,{effect:value as DuplicateKeeperUiRule['effect']})}/><SelectField id={`keeper-field-${rule.id}`} label="Condition" value={rule.field} options={keeperRuleFieldOptions} searchable onchange={(value)=>updateKeeperRule(rule.id,{field:value as DuplicateKeeperRuleField})}/><SelectField id={`keeper-operator-${rule.id}`} label="Match" value={rule.operator} options={[...operators]} onchange={(value)=>updateKeeperRule(rule.id,{operator:value as DuplicateKeeperUiRule['operator']})}/><div>{#if keeperRuleNeedsValue(rule)}{#if definition.kind==='media'}<SelectField id={`keeper-value-${rule.id}`} label="Value" value={rule.value} options={[{value:'image',label:'Image'},{value:'video',label:'Video'},{value:'audio',label:'Audio'},{value:'other',label:'Other'}]} onchange={(value)=>updateKeeperRule(rule.id,{value})}/>{:else if definition.kind==='availability'}<SelectField id={`keeper-value-${rule.id}`} label="Value" value={rule.value} options={[{value:'online',label:'Online'},{value:'offline',label:'Offline'}]} onchange={(value)=>updateKeeperRule(rule.id,{value})}/>{:else if definition.kind==='date'}<DateTimePickerField id={`keeper-value-${rule.id}`} label="Value" value={rule.value} showTime onchange={(value)=>updateKeeperRule(rule.id,{value})}/>{:else if definition.kind==='relation'}<SelectField id={`keeper-value-${rule.id}`} label="Value" multiple values={relationValues(rule.value)} options={rule.field==='album'?albumOptions:tagOptions} searchable loading={rule.field==='album'?albumLoading:tagLoading} onvalueschange={(values)=>setKeeperRelations(rule,values)} onsearchchange={(query)=>void loadOptions(rule.field==='album'?'album':'tag',query)}/>{:else}<V2Field label="Value" type={definition.kind==='number'?'number':'text'} value={rule.value} step={definition.kind==='number'?'any':undefined} onvalueinput={(value)=>updateKeeperRule(rule.id,{value})}/>{/if}{:else}<div class="no-value">No value needed</div>{/if}</div><V2Button variant="danger" iconOnly ariaLabel="Remove keeper condition" onclick={()=>removeKeeperRule(rule.id)}><Trash2 size={15}/></V2Button></div></V2Card>
      {/each}
    </div>

    {#if preview}
      <V2Card><V2Stack gap="sm"><strong>{preview.wouldApplyGroupCount.toLocaleString()} groups would receive automation changes</strong><div class="preview-grid"><span><b>{preview.matchedGroupCount.toLocaleString()}</b> in scope</span><span><b>{preview.completeGroupCount.toLocaleString()}</b> complete drafts</span><span><b>{preview.partialGroupCount.toLocaleString()}</b> partial drafts</span><span><b>{preview.manualReviewGroupCount.toLocaleString()}</b> need manual review</span><span><b>{preview.keepCount.toLocaleString()}</b> automatic Keep</span><span><b>{preview.trashCount.toLocaleString()}</b> automatic Delete</span><span><b>{preview.stackCount.toLocaleString()}</b> automatic Stack</span><span><b>{preview.undecidedMemberCount.toLocaleString()}</b> members left undecided</span><span><b>{preview.preservedManualGroupCount.toLocaleString()}</b> groups preserving manual choices</span><span><b>{preview.ambiguousGroupCount.toLocaleString()}</b> safely left ambiguous</span><span><b>{preview.blockedGroupCount.toLocaleString()}</b> blocked groups skipped</span></div>{#if preview.limitExceeded}<p class="automation-warning">The matching set exceeds the {MAX_AUTOMATION_GROUPS.toLocaleString()}-group safety limit. Narrow the current filters before applying.</p>{/if}</V2Stack></V2Card>
    {/if}
    {#if error}<p class="automation-error" role="alert">{error}</p>{/if}
  </V2Stack>
  {#snippet footer()}<V2Inline gap="sm"><V2Button disabled={!canRun} onclick={()=>void runPreview()}>{busy?'Working…':'Preview'}</V2Button><V2Button variant="primary" disabled={!canRun||Boolean(preview?.limitExceeded)} onclick={()=>void applyRules()}>{busy?'Working…':'Generate decision drafts'}</V2Button><V2Button onclick={onclose}>Close</V2Button></V2Inline>{/snippet}
</V2Modal>

<style>
  .automation-grid{display:grid;gap:12px;grid-template-columns:repeat(2,minmax(0,1fr))}
  .automation-heading,.automation-rule-header{display:flex;align-items:flex-end;justify-content:space-between;gap:16px}
  .automation-heading h3{margin:0 0 4px}.automation-heading p{margin:0;color:var(--v2-text-muted);max-width:820px}
  .automation-rule-list,.condition-list,.keeper-rule-list{display:grid;gap:10px}
  .rule-order{display:flex;align-items:center;gap:6px}.rule-order span{min-width:22px;text-align:center;font-variant-numeric:tabular-nums}
  .condition-row{display:grid;grid-template-columns:minmax(130px,.8fr) minmax(170px,1.2fr) minmax(140px,.9fr) minmax(170px,1fr) minmax(80px,.4fr) auto;gap:10px;align-items:end}
  .rule-actions{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
  .keeper-rule-row{display:grid;grid-template-columns:auto minmax(120px,.7fr) minmax(180px,1.25fr) minmax(150px,1fr) minmax(180px,1.2fr) auto;gap:10px;align-items:end}
  .no-value{min-height:40px;display:flex;align-items:center;color:var(--v2-text-muted);font-size:.9rem}
  .preview-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px 16px}
  .automation-warning,.automation-error{margin:0;color:var(--v2-danger)}
  @media(max-width:1050px){.condition-row{grid-template-columns:1fr 1fr 1fr}.keeper-rule-row{grid-template-columns:1fr 1fr}.rule-order{grid-column:1/-1}}
  @media(max-width:760px){.automation-grid,.rule-actions,.preview-grid,.condition-row{grid-template-columns:1fr}.automation-heading,.automation-rule-header{align-items:stretch;flex-direction:column}}
</style>
