import type {
  DuplicateKeeperRule,
  DuplicateKeeperRuleEffect,
  DuplicateKeeperRuleField,
  DuplicateKeeperRuleOperator,
} from '../data/contracts';

export type KeeperRuleValueKind = 'text'|'number'|'date'|'boolean'|'media'|'availability'|'relation';
export type DuplicateKeeperUiRule = DuplicateKeeperRule & { id: number };

export const keeperRuleFields: Array<{value:DuplicateKeeperRuleField;label:string;kind:KeeperRuleValueKind;rankable?:boolean}> = [
  {value:'library',label:'Library',kind:'text'},
  {value:'folder',label:'Folder',kind:'text'},
  {value:'filename',label:'Filename',kind:'text'},
  {value:'extension',label:'Extension',kind:'text'},
  {value:'mime_type',label:'MIME type',kind:'text'},
  {value:'media_type',label:'Media type',kind:'media'},
  {value:'date',label:'Date',kind:'date',rankable:true},
  {value:'modified_date',label:'Modified date',kind:'date',rankable:true},
  {value:'immich_created_at',label:'Added to Immich',kind:'date',rankable:true},
  {value:'immich_updated_at',label:'Updated in Immich',kind:'date',rankable:true},
  {value:'file_size',label:'File size',kind:'number',rankable:true},
  {value:'resolution',label:'Resolution',kind:'number',rankable:true},
  {value:'width',label:'Width',kind:'number',rankable:true},
  {value:'height',label:'Height',kind:'number',rankable:true},
  {value:'aspect_ratio',label:'Aspect ratio',kind:'number',rankable:true},
  {value:'favorite',label:'Favorite',kind:'boolean'},
  {value:'archived',label:'Archived',kind:'boolean'},
  {value:'availability',label:'Availability',kind:'availability'},
  {value:'edited',label:'Edited',kind:'boolean'},
  {value:'has_metadata',label:'Has metadata',kind:'boolean'},
  {value:'visibility',label:'Visibility',kind:'text'},
  {value:'live_photo',label:'Live Photo',kind:'boolean'},
  {value:'tag',label:'Tag',kind:'relation'},
  {value:'album',label:'Album',kind:'relation'},
  {value:'has_tag',label:'Has any tag',kind:'boolean'},
  {value:'has_album',label:'Has any album',kind:'boolean'},
  {value:'stack_membership',label:'Stack membership',kind:'boolean'},
  {value:'stack_primary',label:'Stack primary',kind:'boolean'},
  {value:'owner',label:'Owner',kind:'text'},
  {value:'checksum',label:'Checksum',kind:'text'},
  {value:'reference',label:'Current reference',kind:'boolean'},
  {value:'similarity',label:'Similarity',kind:'number',rankable:true},
  {value:'structural_similarity',label:'Structural similarity',kind:'number',rankable:true},
  {value:'perceptual_similarity',label:'Perceptual similarity',kind:'number',rankable:true},
  {value:'color_similarity',label:'Color similarity',kind:'number',rankable:true},
  {value:'detail_change',label:'Detail change',kind:'number',rankable:true},
  {value:'admission_similarity',label:'Admission similarity',kind:'number',rankable:true},
  {value:'link_depth',label:'Admission hops from group reference',kind:'number',rankable:true},
  {value:'duration',label:'Duration',kind:'number',rankable:true},
  {value:'same_folder_as_reference',label:'Same folder as reference',kind:'boolean'},
  {value:'same_library_as_reference',label:'Same library as reference',kind:'boolean'},
  {value:'same_mime_as_reference',label:'Same MIME as reference',kind:'boolean'},
  {value:'metadata_richness',label:'Metadata richness',kind:'number',rankable:true},
  {value:'format_quality',label:'Format quality',kind:'number',rankable:true},
];

export const keeperRuleFieldOptions=keeperRuleFields.map(({value,label})=>({value,label}));
export const keeperEffectOptions:Array<{value:DuplicateKeeperRuleEffect;label:string;subtitle:string}> = [
  {value:'require',label:'Require',subtitle:'Keeper candidates must match'},
  {value:'prefer',label:'Prefer',subtitle:'Use as an ordered tiebreaker'},
  {value:'avoid',label:'Avoid',subtitle:'Drop matching candidates when another remains'},
];

const textOperators:Array<{value:DuplicateKeeperRuleOperator;label:string}>=[
  {value:'is',label:'is'},
  {value:'is_not',label:'is not'},
  {value:'contains',label:'contains'},
  {value:'not_contains',label:'does not contain'},
  {value:'starts_with',label:'starts with'},
  {value:'ends_with',label:'ends with'},
];
const numericOperators:Array<{value:DuplicateKeeperRuleOperator;label:string}>=[
  {value:'is',label:'is equal to'},
  {value:'gte',label:'is at least'},
  {value:'lte',label:'is at most'},
  {value:'gt',label:'is greater than'},
  {value:'lt',label:'is less than'},
];
const relationOperators:Array<{value:DuplicateKeeperRuleOperator;label:string}>=[
  {value:'has_any',label:'has any selected'},
  {value:'has_all',label:'has all selected'},
  {value:'has_none',label:'has none selected'},
];

export function keeperFieldDefinition(field:DuplicateKeeperRuleField){
  return keeperRuleFields.find((item)=>item.value===field)??keeperRuleFields[0];
}
export function keeperOperatorOptions(field:DuplicateKeeperRuleField,effect:DuplicateKeeperRuleEffect){
  const definition=keeperFieldDefinition(field);
  if(definition.kind==='boolean')return[
    {value:'is_true',label:'is true'},
    {value:'is_false',label:'is false'},
  ] as const;
  if(definition.kind==='relation')return relationOperators;
  if(definition.kind==='media'||definition.kind==='availability')return[
    {value:'is',label:'is'},
    {value:'is_not',label:'is not'},
  ];
  const base=definition.kind==='number'||definition.kind==='date'?numericOperators:textOperators;
  return effect!=='require'&&definition.rankable
    ?[{value:'highest' as const,label:'highest wins'},{value:'lowest' as const,label:'lowest wins'},...base]
    :base;
}
export function keeperRuleNeedsValue(rule:Pick<DuplicateKeeperRule,'field'|'operator'>){
  return !['highest','lowest','is_true','is_false'].includes(rule.operator);
}
export function normalizeKeeperRule(rule:DuplicateKeeperUiRule):DuplicateKeeperRule{
  return{effect:rule.effect,field:rule.field,operator:rule.operator,value:rule.value.trim()};
}
export function newKeeperRule(id:number,field:DuplicateKeeperRuleField='resolution',effect:DuplicateKeeperRuleEffect='prefer',operator:DuplicateKeeperRuleOperator='highest',value=''):DuplicateKeeperUiRule{
  return{id,effect,field,operator,value};
}

export const keeperPresetNames=['Highest quality','Prefer originals','Prefer newest','Prefer oldest','Prefer organized','Prefer current reference'] as const;
export type KeeperPresetName=typeof keeperPresetNames[number];

export function keeperPreset(name:KeeperPresetName,nextId:()=>number):DuplicateKeeperUiRule[]{
  const add=(field:DuplicateKeeperRuleField,effect:DuplicateKeeperRuleEffect,operator:DuplicateKeeperRuleOperator,value='')=>newKeeperRule(nextId(),field,effect,operator,value);
  if(name==='Prefer originals')return[
    add('availability','require','is','online'),
    add('edited','avoid','is_true'),
    add('format_quality','prefer','highest'),
    add('resolution','prefer','highest'),
    add('file_size','prefer','highest'),
    add('metadata_richness','prefer','highest'),
  ];
  if(name==='Prefer newest')return[
    add('availability','require','is','online'),
    add('date','prefer','highest'),
    add('resolution','prefer','highest'),
  ];
  if(name==='Prefer oldest')return[
    add('availability','require','is','online'),
    add('date','prefer','lowest'),
    add('resolution','prefer','highest'),
  ];
  if(name==='Prefer organized')return[
    add('availability','require','is','online'),
    add('favorite','prefer','is_true'),
    add('has_album','prefer','is_true'),
    add('has_tag','prefer','is_true'),
    add('has_metadata','prefer','is_true'),
    add('resolution','prefer','highest'),
  ];
  if(name==='Prefer current reference')return[
    add('availability','require','is','online'),
    add('reference','prefer','is_true'),
  ];
  return[
    add('availability','require','is','online'),
    add('resolution','prefer','highest'),
    add('format_quality','prefer','highest'),
    add('file_size','prefer','highest'),
    add('metadata_richness','prefer','highest'),
    add('reference','prefer','is_true'),
  ];
}
