import type { AssetSearchCriteria } from '../data/contracts';
import type { SimpleAdvancedFilters } from '../components/V2SimpleAdvancedFilters.svelte';

export type AssetSearchMode='Simple'|'Expert';
export type AssetRule={id:number;field:string;op:string;value:string};
export type AssetGroup={id:number;logic:'AND'|'OR';negated:boolean;rules:AssetRule[]};
export type AssetSimpleSnapshot={filename:string;mediaType:string;favorite:string;archived:string;advanced:SimpleAdvancedFilters};

export const assetFieldOptions=[['filename','Filename'],['mediaType','Media type'],['favorite','Favorite'],['archived','Archived'],['album','Album'],['tag','Tag'],['takenDate','Taken date'],['width','Width'],['height','Height'],['aspectRatio','Aspect ratio']] as const;
export const assetOperatorOptions=[['is','is'],['isNot','is not'],['contains','contains'],['notContains','does not contain'],['gt','greater than'],['gte','at least'],['lt','less than'],['lte','at most']] as const;
export const assetFieldSelectOptions=assetFieldOptions.map(([value,label])=>({value,label}));
export const assetOperatorSelectOptions=assetOperatorOptions.map(([value,label])=>({value,label}));
export const savedAssetSearches=['Favorite images not archived','Family album or Vacation tag','Large landscape images'];

export const emptyAssetAdvanced=():SimpleAdvancedFilters=>({albumIds:'',tagIds:'',noAlbum:false,noTag:false,takenAfter:'',takenBefore:'',minWidth:'',maxWidth:'',minHeight:'',maxHeight:'',minAspectRatio:'',maxAspectRatio:''});
export const emptyAssetSimple=():AssetSimpleSnapshot=>({filename:'',mediaType:'',favorite:'',archived:'',advanced:emptyAssetAdvanced()});
export const splitAssetIds=(value:string)=>value.split(',').map((part)=>part.trim()).filter(Boolean);

const fieldLabel=(value:string)=>assetFieldOptions.find(([key])=>key===value)?.[1]??value;
const operatorLabel=(value:string)=>assetOperatorOptions.find(([key])=>key===value)?.[1]??value;
export const assetRuleText=(rule:AssetRule)=>`${fieldLabel(rule.field)} ${operatorLabel(rule.op)} ${rule.value||'…'}`;
export function assetExpressionText(rules:AssetRule[],groups:AssetGroup[],root:'AND'|'OR',negated:boolean){
  const base=`(${rules.map(assetRuleText).join(` ${root} `)||'empty'})`;
  const nested=groups.map((group)=>`${group.negated?'NOT ':''}(${group.rules.map(assetRuleText).join(` ${group.logic} `)||'empty'})`);
  const text=[base,...nested].join(` ${root} `);
  return negated?`NOT (${text})`:text;
}

export function buildAssetCriteria(input:{sort:string;mode:AssetSearchMode;simple:AssetSimpleSnapshot;rules:AssetRule[];groups:AssetGroup[];logic:'AND'|'OR';negated:boolean}):AssetSearchCriteria{
  const[sortFieldRaw,sortDirectionRaw]=input.sort.split(':');
  const field=sortFieldRaw==='filename'?'filename':'takenDate';
  const direction=sortDirectionRaw==='asc'?'asc':'desc';
  if(input.mode==='Simple'){
    const advanced=input.simple.advanced;
    return{mode:'simple',sort:{field,direction},filters:{filename:input.simple.filename,mediaType:input.simple.mediaType as 'Image'|'Video'|'',favorite:input.simple.favorite as 'Favorite'|'Not favorite'|'',archived:input.simple.archived as 'Archived'|'Not archived'|'',albumIds:splitAssetIds(advanced.albumIds),tagIds:splitAssetIds(advanced.tagIds),noAlbum:advanced.noAlbum,noTag:advanced.noTag,takenAfter:advanced.takenAfter,takenBefore:advanced.takenBefore,minWidth:advanced.minWidth,maxWidth:advanced.maxWidth,minHeight:advanced.minHeight,maxHeight:advanced.maxHeight,minAspectRatio:advanced.minAspectRatio,maxAspectRatio:advanced.maxAspectRatio}};
  }
  return{mode:'expert',sort:{field,direction},rules:input.rules.map(({field,op,value})=>({field,op,value})),groups:input.groups.map((group)=>({logic:group.logic,negated:group.negated,rules:group.rules.map(({field,op,value})=>({field,op,value}))})),logic:input.logic,negated:input.negated};
}

export function savedAssetSearchPreset(value:string,nextRuleId:()=>number,nextGroupId:()=>number):{rules:AssetRule[];groups:AssetGroup[]}{
  if(value.includes('Favorite'))return{rules:[{id:nextRuleId(),field:'mediaType',op:'is',value:'Image'},{id:nextRuleId(),field:'favorite',op:'is',value:'true'},{id:nextRuleId(),field:'archived',op:'is',value:'false'}],groups:[]};
  if(value.includes('Family'))return{rules:[{id:nextRuleId(),field:'mediaType',op:'is',value:'Image'}],groups:[{id:nextGroupId(),logic:'OR',negated:false,rules:[{id:nextRuleId(),field:'album',op:'contains',value:'Family'},{id:nextRuleId(),field:'tag',op:'contains',value:'Vacation'}]}]};
  if(value.includes('Large'))return{rules:[{id:nextRuleId(),field:'mediaType',op:'is',value:'Image'},{id:nextRuleId(),field:'width',op:'gte',value:'3000'},{id:nextRuleId(),field:'aspectRatio',op:'gt',value:'1'}],groups:[]};
  return{rules:[],groups:[]};
}
