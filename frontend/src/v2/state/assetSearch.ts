import type { AssetSearchCriteria,AssetSearchGroup,AssetSearchRule } from '../data/contracts';
import type { SimpleAdvancedFilters } from '../components/V2SimpleAdvancedFilters.svelte';

export type AssetSearchMode='Simple'|'Expert';
export type AssetRule={id:number;field:string;op:string;value:string};
export type AssetGroup={id:number;logic:'AND'|'OR';negated:boolean;rules:AssetRule[];groups:AssetGroup[]};
export type AssetSimpleSnapshot={filename:string;mediaType:string;favorite:string;archived:string;advanced:SimpleAdvancedFilters};

export const assetFieldOptions=[['filename','Filename'],['mediaType','Media type'],['favorite','Favorite'],['archived','Archived'],['stackMembership','Stack membership'],['stackRole','Stack role'],['album','Album'],['tag','Tag'],['takenDate','Taken date'],['width','Width'],['height','Height'],['aspectRatio','Aspect ratio']] as const;
export const assetOperatorOptions=[['is','is'],['all','matches all selected'],['isNot','is not'],['hasNone','has none'],['contains','contains'],['notContains','does not contain'],['gt','greater than'],['gte','at least'],['lt','less than'],['lte','at most']] as const;
export const assetFieldSelectOptions=assetFieldOptions.map(([value,label])=>({value,label}));
export const assetOperatorSelectOptions=assetOperatorOptions.map(([value,label])=>({value,label}));
export function assetOperatorOptionsForField(field:string){
  if(field==='filename')return[
    {value:'contains',label:'contains'},
    {value:'is',label:'is exactly'},
    {value:'isNot',label:'is not'},
    {value:'notContains',label:'does not contain'},
  ];
  if(field==='album'||field==='tag')return[
    {value:'is',label:'matches any selected (OR)'},
    {value:'all',label:'matches all selected (AND)'},
    {value:'isNot',label:'matches none selected (NOT)'},
    {value:'hasNone',label:`has no ${field==='album'?'albums':'tags'}`},
  ];
  if(field==='mediaType'||field==='favorite'||field==='archived')return[
    {value:'is',label:'is'},
    {value:'isNot',label:'is not'},
  ];
  if(field==='stackMembership'||field==='stackRole')return[{value:'is',label:'is'}];
  if(field==='takenDate')return[
    {value:'gte',label:'is on or after'},
    {value:'lte',label:'is on or before'},
  ];
  if(field==='aspectRatio')return[
    {value:'gte',label:'is at least'},
    {value:'lte',label:'is at most'},
    {value:'is',label:'is approximately'},
  ];
  return[
    {value:'gte',label:'is at least'},
    {value:'lte',label:'is at most'},
    {value:'is',label:'is equal to'},
  ];
}
export const savedAssetSearches=['Favorite images not archived','Family album or Vacation tag','Large landscape images'];

export const emptyAssetAdvanced=():SimpleAdvancedFilters=>({albumIds:'',tagIds:'',noAlbum:false,noTag:false,takenAfter:'',takenBefore:'',minWidth:'',maxWidth:'',minHeight:'',maxHeight:'',minAspectRatio:'',maxAspectRatio:''});
export const emptyAssetSimple=():AssetSimpleSnapshot=>({filename:'',mediaType:'',favorite:'',archived:'',advanced:emptyAssetAdvanced()});
export const splitAssetIds=(value:string)=>value.split(',').map((part)=>part.trim()).filter(Boolean);

const fieldLabel=(value:string)=>assetFieldOptions.find(([key])=>key===value)?.[1]??value;
const operatorLabel=(value:string)=>assetOperatorOptions.find(([key])=>key===value)?.[1]??value;
export const assetRuleText=(rule:AssetRule)=>`${fieldLabel(rule.field)} ${operatorLabel(rule.op)}${rule.op==='hasNone'?'':` ${rule.value||'…'}`}`;
const assetGroupExpressionText=(group:Pick<AssetGroup,'rules'|'groups'|'logic'|'negated'>):string=>{
  const parts=[...group.rules.map(assetRuleText),...(group.groups??[]).map(assetGroupExpressionText)];
  const text=`(${parts.join(` ${group.logic} `)||'empty'})`;
  return group.negated?`NOT ${text}`:text;
};
export function assetExpressionText(rules:AssetRule[],groups:AssetGroup[],root:'AND'|'OR',negated:boolean){
  return assetGroupExpressionText({rules,groups,logic:root,negated});
}

export function cloneAssetGroups(groups:readonly AssetGroup[]):AssetGroup[]{return groups.map((group)=>({...group,rules:group.rules.map((rule)=>({...rule})),groups:cloneAssetGroups(group.groups??[])}))}
export function assetRulesInGroups(groups:readonly AssetGroup[]):AssetRule[]{return groups.flatMap((group)=>[...group.rules,...assetRulesInGroups(group.groups??[])])}
export function assetSearchCounts(rules:readonly AssetRule[],groups:readonly AssetGroup[]):{rules:number;groups:number}{return groups.reduce((total,group)=>{const nested=assetSearchCounts(group.rules,group.groups??[]);return{rules:total.rules+nested.rules,groups:total.groups+1+nested.groups}},{rules:rules.length,groups:0})}
export function assetRuleCount(groups:readonly AssetGroup[]):number{return assetSearchCounts([],groups).rules}
export function assetGroupCount(groups:readonly AssetGroup[]):number{return assetSearchCounts([],groups).groups}
export function maxAssetSearchId(rules:readonly AssetRule[],groups:readonly AssetGroup[]):number{return Math.max(0,...rules.map((rule)=>rule.id),...groups.flatMap((group)=>[group.id,maxAssetSearchId(group.rules,group.groups??[])]))}
export function hydrateAssetGroups(groups:readonly AssetSearchGroup[],nextRuleId:()=>number,nextGroupId:()=>number):AssetGroup[]{return groups.map((group)=>({id:nextGroupId(),logic:group.logic,negated:group.negated,rules:group.rules.map((rule)=>({id:nextRuleId(),...rule})),groups:hydrateAssetGroups(group.groups??[],nextRuleId,nextGroupId)}))}

export function simpleAssetSearchToExpert(simple:AssetSimpleSnapshot,nextRuleId:()=>number):{rules:AssetRule[];groups:AssetGroup[];logic:'AND';negated:false}{
  const rules:AssetRule[]=[];
  const add=(field:string,op:string,value:string)=>rules.push({id:nextRuleId(),field,op,value});
  if(simple.filename.trim())add('filename','contains',simple.filename.trim());
  if(simple.mediaType)add('mediaType','is',simple.mediaType);
  if(simple.favorite)add('favorite','is',simple.favorite==='Favorite'?'true':'false');
  if(simple.archived)add('archived','is',simple.archived==='Archived'?'true':'false');
  const advanced=simple.advanced;
  if(splitAssetIds(advanced.albumIds).length)add('album','is',splitAssetIds(advanced.albumIds).join(','));
  if(splitAssetIds(advanced.tagIds).length)add('tag','is',splitAssetIds(advanced.tagIds).join(','));
  if(advanced.noAlbum)add('album','hasNone','');
  if(advanced.noTag)add('tag','hasNone','');
  if(advanced.takenAfter)add('takenDate','gte',advanced.takenAfter);
  if(advanced.takenBefore)add('takenDate','lte',advanced.takenBefore);
  for(const [key,field,op] of [['minWidth','width','gte'],['maxWidth','width','lte'],['minHeight','height','gte'],['maxHeight','height','lte'],['minAspectRatio','aspectRatio','gte'],['maxAspectRatio','aspectRatio','lte']] as const){const value=advanced[key];if(value)add(field,op,value)}
  return{rules,groups:[],logic:'AND',negated:false};
}

type CriteriaParts={rules:AssetSearchRule[];groups:AssetSearchGroup[]};
function criteriaParts(rules:readonly AssetRule[],groups:readonly AssetGroup[]):CriteriaParts{
  const output:CriteriaParts={rules:[],groups:groups.map(criteriaGroup)};
  for(const rule of rules){
    if((rule.field==='album'||rule.field==='tag')&&rule.op==='all'){
      const values=splitAssetIds(rule.value);
      if(values.length===1)output.rules.push({field:rule.field,op:'is',value:values[0]});
      else if(values.length>1)output.groups.push({logic:'AND',negated:false,rules:values.map((value)=>({field:rule.field,op:'is',value})),groups:[]});
      continue;
    }
    output.rules.push({field:rule.field,op:rule.op,value:rule.value});
  }
  return output;
}
function criteriaGroup(group:AssetGroup):AssetSearchGroup{
  const parts=criteriaParts(group.rules,group.groups??[]);
  return{logic:group.logic,negated:group.negated,rules:parts.rules,groups:parts.groups};
}

export function buildAssetCriteria(input:{sort:string;mode:AssetSearchMode;simple:AssetSimpleSnapshot;rules:AssetRule[];groups:AssetGroup[];logic:'AND'|'OR';negated:boolean}):AssetSearchCriteria{
  const[sortFieldRaw,sortDirectionRaw]=input.sort.split(':');
  const field=sortFieldRaw==='filename'?'filename':'takenDate';
  const direction=sortDirectionRaw==='asc'?'asc':'desc';
  if(input.mode==='Simple'){
    const advanced=input.simple.advanced;
    return{mode:'simple',sort:{field,direction},filters:{filename:input.simple.filename,mediaType:input.simple.mediaType as 'Image'|'Video'|'',favorite:input.simple.favorite as 'Favorite'|'Not favorite'|'',archived:input.simple.archived as 'Archived'|'Not archived'|'',albumIds:splitAssetIds(advanced.albumIds),tagIds:splitAssetIds(advanced.tagIds),noAlbum:advanced.noAlbum,noTag:advanced.noTag,takenAfter:advanced.takenAfter,takenBefore:advanced.takenBefore,minWidth:advanced.minWidth,maxWidth:advanced.maxWidth,minHeight:advanced.minHeight,maxHeight:advanced.maxHeight,minAspectRatio:advanced.minAspectRatio,maxAspectRatio:advanced.maxAspectRatio}};
  }
  const parts=criteriaParts(input.rules,input.groups);
  return{mode:'expert',sort:{field,direction},rules:parts.rules,groups:parts.groups,logic:input.logic,negated:input.negated};
}

export function savedAssetSearchPreset(value:string,nextRuleId:()=>number,nextGroupId:()=>number):{rules:AssetRule[];groups:AssetGroup[]}{
  if(value.includes('Favorite'))return{rules:[{id:nextRuleId(),field:'mediaType',op:'is',value:'Image'},{id:nextRuleId(),field:'favorite',op:'is',value:'true'},{id:nextRuleId(),field:'archived',op:'is',value:'false'}],groups:[]};
  if(value.includes('Family'))return{rules:[{id:nextRuleId(),field:'mediaType',op:'is',value:'Image'}],groups:[{id:nextGroupId(),logic:'OR',negated:false,rules:[{id:nextRuleId(),field:'album',op:'is',value:'Family'},{id:nextRuleId(),field:'tag',op:'is',value:'Vacation'}],groups:[]}]};
  if(value.includes('Large'))return{rules:[{id:nextRuleId(),field:'mediaType',op:'is',value:'Image'},{id:nextRuleId(),field:'width',op:'gte',value:'3000'},{id:nextRuleId(),field:'aspectRatio',op:'gt',value:'1'}],groups:[]};
  return{rules:[],groups:[]};
}
