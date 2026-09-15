import type {
  DuplicateDecision,
  DuplicateGroupRecord,
  DuplicateKeeperRule,
  DuplicateKeeperRuleField,
  DuplicateKeeperRuleOperator,
} from '../data/contracts';
import {
  keeperFieldDefinition,
  keeperOperatorOptions,
  keeperRuleFieldOptions,
} from './duplicateKeeperRules';

export type DuplicateAutomationConditionScope =
  | 'group'
  | 'member'
  | 'any_member'
  | 'all_members'
  | 'no_members'
  | 'at_least_members';
export type DuplicateAutomationLogic = 'all' | 'any';
export type DuplicateAutomationTarget = 'matching_members' | 'remaining_members' | 'whole_group';
export type DuplicateAutomationAction =
  | 'keep'
  | 'delete'
  | 'stack'
  | 'resolve_keeper'
  | 'leave_undecided'
  | 'manual_review';
export type DuplicateAutomationFlow = 'continue' | 'stop_affected' | 'stop_group';
export type DuplicateAutomationGroupField =
  | 'classification'
  | 'review_state'
  | 'member_count'
  | 'group_similarity'
  | 'discovery_source'
  | 'auto_ready'
  | 'selected'
  | 'eligible'
  | 'decision_count'
  | 'undecided_count';
export type DuplicateAutomationConditionField = DuplicateKeeperRuleField | DuplicateAutomationGroupField;

export type DuplicateAutomationUiCondition = {
  id: number;
  scope: DuplicateAutomationConditionScope;
  field: DuplicateAutomationConditionField;
  operator: DuplicateKeeperRuleOperator;
  value: string;
  count: number;
};
export type DuplicateAutomationUiRule = {
  id: number;
  logic: DuplicateAutomationLogic;
  conditions: DuplicateAutomationUiCondition[];
  target: DuplicateAutomationTarget;
  action: DuplicateAutomationAction;
  flow: DuplicateAutomationFlow;
};
export type DuplicateAutomationExistingDecision = {
  assetId: string;
  disposition: DuplicateDecision;
  source: 'manual' | 'automatic';
  status?: 'pending' | 'completed';
};
export type DuplicateAutomationDecision = Required<DuplicateAutomationExistingDecision>;

export type DuplicateAutomationEvaluation = {
  matched: boolean;
  touched: boolean;
  persistDraft: boolean;
  complete: boolean;
  partial: boolean;
  manualReview: boolean;
  ambiguous: boolean;
  preservedManual: boolean;
  matchedRuleCount: number;
  keepCount: number;
  deleteCount: number;
  stackCount: number;
  undecidedCount: number;
  metadataKeeperAssetId: string | null;
  decisions: DuplicateAutomationDecision[];
};

export type AutomationRuleValueKind = 'text' | 'number' | 'boolean';
export const automationGroupFields: Array<{
  value: DuplicateAutomationGroupField;
  label: string;
  kind: AutomationRuleValueKind;
}> = [
  { value: 'classification', label: 'Classification', kind: 'text' },
  { value: 'review_state', label: 'Review state', kind: 'text' },
  { value: 'member_count', label: 'Member count', kind: 'number' },
  { value: 'group_similarity', label: 'Group minimum similarity', kind: 'number' },
  { value: 'discovery_source', label: 'Discovery source', kind: 'text' },
  { value: 'auto_ready', label: 'Auto-ready', kind: 'boolean' },
  { value: 'selected', label: 'Selected', kind: 'boolean' },
  { value: 'eligible', label: 'Eligible', kind: 'boolean' },
  { value: 'decision_count', label: 'Saved decision count', kind: 'number' },
  { value: 'undecided_count', label: 'Undecided member count', kind: 'number' },
];

export const automationConditionScopeOptions = [
  { value: 'group', label: 'Group', subtitle: 'Match a property of the whole duplicate group' },
  { value: 'member', label: 'Member', subtitle: 'Match individual members and expose them as targets' },
  { value: 'any_member', label: 'Any member', subtitle: 'Group matches when at least one member matches' },
  { value: 'all_members', label: 'All members', subtitle: 'Group matches only when every member matches' },
  { value: 'no_members', label: 'No members', subtitle: 'Group matches only when no member matches' },
  { value: 'at_least_members', label: 'At least N members', subtitle: 'Group matches when enough members match' },
] as const;
export const automationTargetOptions = [
  { value: 'matching_members', label: 'Matching members', subtitle: 'Only members matched by Member conditions' },
  { value: 'remaining_members', label: 'Remaining undecided members', subtitle: 'Only members not already decided by an earlier rule or manual choice' },
  { value: 'whole_group', label: 'Whole group', subtitle: 'Apply across the group while preserving protected manual choices' },
] as const;
export const automationActionOptions = [
  { value: 'keep', label: 'Keep', subtitle: 'Write Keep only for the targeted members' },
  { value: 'delete', label: 'Delete', subtitle: 'Write Delete only for the targeted members; never auto-delete every member' },
  { value: 'stack', label: 'Stack', subtitle: 'Write Stack for the targeted members; primary can be reviewed later' },
  { value: 'resolve_keeper', label: 'Resolve using keeper priority', subtitle: 'Pick one keeper from the targeted undecided members and mark the rest Delete' },
  { value: 'leave_undecided', label: 'Leave undecided', subtitle: 'Intentionally make no decision for the targeted members' },
  { value: 'manual_review', label: 'Require manual review', subtitle: 'Select the group for review without assigning member decisions' },
] as const;
export const automationFlowOptions = [
  { value: 'continue', label: 'Continue', subtitle: 'Allow later rules to handle remaining undecided members' },
  { value: 'stop_affected', label: 'Stop for affected members', subtitle: 'Later rules cannot touch the targeted members' },
  { value: 'stop_group', label: 'Stop this group', subtitle: 'Do not evaluate any later rules for this group' },
] as const;

const textOperators: Array<{ value: DuplicateKeeperRuleOperator; label: string }> = [
  { value: 'is', label: 'is' },
  { value: 'is_not', label: 'is not' },
  { value: 'contains', label: 'contains' },
  { value: 'not_contains', label: 'does not contain' },
  { value: 'starts_with', label: 'starts with' },
  { value: 'ends_with', label: 'ends with' },
];
const numericOperators: Array<{ value: DuplicateKeeperRuleOperator; label: string }> = [
  { value: 'is', label: 'is equal to' },
  { value: 'gte', label: 'is at least' },
  { value: 'lte', label: 'is at most' },
  { value: 'gt', label: 'is greater than' },
  { value: 'lt', label: 'is less than' },
];
const booleanOperators: Array<{ value: DuplicateKeeperRuleOperator; label: string }> = [
  { value: 'is_true', label: 'is true' },
  { value: 'is_false', label: 'is false' },
];

export function automationConditionFieldOptions(scope: DuplicateAutomationConditionScope) {
  return scope === 'group'
    ? automationGroupFields.map(({ value, label }) => ({ value, label }))
    : keeperRuleFieldOptions;
}

function groupFieldDefinition(field: DuplicateAutomationGroupField) {
  return automationGroupFields.find((item) => item.value === field) ?? automationGroupFields[0];
}

export function automationOperatorOptions(condition: Pick<DuplicateAutomationUiCondition, 'scope' | 'field'>) {
  if (condition.scope !== 'group') {
    return keeperOperatorOptions(condition.field as DuplicateKeeperRuleField, 'require');
  }
  const definition = groupFieldDefinition(condition.field as DuplicateAutomationGroupField);
  if (definition.kind === 'boolean') return booleanOperators;
  return definition.kind === 'number' ? numericOperators : textOperators;
}

export function automationConditionNeedsValue(condition: Pick<DuplicateAutomationUiCondition, 'operator'>) {
  return !['highest', 'lowest', 'is_true', 'is_false'].includes(condition.operator);
}

export function newAutomationCondition(
  id: number,
  scope: DuplicateAutomationConditionScope = 'member',
  field: DuplicateAutomationConditionField = 'library',
  operator: DuplicateKeeperRuleOperator = 'is',
  value = 'upload',
): DuplicateAutomationUiCondition {
  return { id, scope, field, operator, value, count: 1 };
}

export function newAutomationRule(id: number, conditionId: number): DuplicateAutomationUiRule {
  return {
    id,
    logic: 'all',
    conditions: [newAutomationCondition(conditionId)],
    target: 'matching_members',
    action: 'keep',
    flow: 'stop_group',
  };
}

export const automationPresetNames = [
  'Protect uploads for review',
  'Resolve exact copies',
  'Keep groups below 98%',
  'Protect favorites for review',
] as const;
export type AutomationPresetName = typeof automationPresetNames[number];

export function automationPreset(
  name: AutomationPresetName,
  nextRuleId: () => number,
  nextConditionId: () => number,
): DuplicateAutomationUiRule[] {
  const condition = (
    scope: DuplicateAutomationConditionScope,
    field: DuplicateAutomationConditionField,
    operator: DuplicateKeeperRuleOperator,
    value = '',
  ) => newAutomationCondition(nextConditionId(), scope, field, operator, value);
  const rule = (
    conditions: DuplicateAutomationUiCondition[],
    target: DuplicateAutomationTarget,
    action: DuplicateAutomationAction,
    flow: DuplicateAutomationFlow = 'stop_group',
  ): DuplicateAutomationUiRule => ({ id: nextRuleId(), logic: 'all', conditions, target, action, flow });

  if (name === 'Resolve exact copies') {
    return [
      rule(
        [condition('group', 'classification', 'is', 'exact file, exact pixels')],
        'whole_group',
        'resolve_keeper',
      ),
    ];
  }
  if (name === 'Keep groups below 98%') {
    return [
      rule([condition('group', 'group_similarity', 'lt', '98')], 'whole_group', 'keep'),
    ];
  }
  if (name === 'Protect favorites for review') {
    return [rule([condition('member', 'favorite', 'is_true')], 'matching_members', 'keep')];
  }
  return [
    rule([condition('member', 'library', 'is', 'upload')], 'matching_members', 'keep'),
  ];
}

export function automationRuleValid(rule: DuplicateAutomationUiRule): boolean {
  if (!rule.conditions.length) return false;
  if (rule.target === 'matching_members' && !rule.conditions.some((condition) => condition.scope === 'member')) {
    return false;
  }
  return rule.conditions.every((condition) => {
    if (condition.scope === 'at_least_members' && (!Number.isFinite(condition.count) || condition.count < 1)) return false;
    if (!automationConditionNeedsValue(condition)) return true;
    return condition.value.trim().length > 0;
  });
}

function values(value: string): string[] {
  return value.split(',').map((item) => item.trim().casefold()).filter(Boolean);
}

function folder(path: string | null): string {
  if (!path) return '';
  const normalized = path.replaceAll('\\', '/');
  const index = normalized.lastIndexOf('/');
  return index > 0 ? normalized.slice(0, index) : '';
}

function extension(name: string): string {
  const index = name.lastIndexOf('.');
  return index >= 0 ? name.slice(index + 1).toLocaleLowerCase() : '';
}

function formatQuality(name: string, mime: string | null): number {
  const ext = extension(name);
  const normalized = (mime ?? '').toLocaleLowerCase();
  if (['dng', 'nef', 'cr2', 'cr3', 'arw', 'raf', 'rw2', 'orf', 'pef'].includes(ext)) return 5;
  if (normalized.includes('raw') || normalized.includes('dng')) return 5;
  if (['tif', 'tiff', 'png'].includes(ext) || ['image/tiff', 'image/png'].includes(normalized)) return 4;
  if (['heic', 'heif', 'avif'].includes(ext) || ['heic', 'heif', 'avif'].some((marker) => normalized.includes(marker))) return 3;
  if (['jpg', 'jpeg', 'webp'].includes(ext) || ['jpeg', 'webp'].some((marker) => normalized.includes(marker))) return 2;
  return 1;
}

function referenceAsset(group: DuplicateGroupRecord) {
  return group.members.find((member) => member.asset.id === group.referenceAssetId)?.asset ?? null;
}

function memberValue(group: DuplicateGroupRecord, memberIndex: number, field: DuplicateKeeperRuleField): unknown {
  const member = group.members[memberIndex];
  const asset = member.asset;
  const reference = referenceAsset(group);
  if (field === 'library') return asset.library_id === null ? 'upload' : asset.library_id;
  if (field === 'folder') return folder(asset.original_path);
  if (field === 'filename') return asset.original_file_name;
  if (field === 'extension') return extension(asset.original_file_name);
  if (field === 'mime_type') return asset.original_mime_type;
  if (field === 'media_type') return asset.asset_type.toLocaleLowerCase();
  if (field === 'date') return asset.local_date_time ?? asset.file_created_at;
  if (field === 'modified_date') return asset.file_modified_at;
  if (field === 'immich_created_at') return asset.immich_created_at;
  if (field === 'immich_updated_at') return asset.immich_updated_at;
  if (field === 'file_size') return asset.file_size_bytes;
  if (field === 'resolution') return asset.width !== null && asset.height !== null ? asset.width * asset.height : null;
  if (field === 'width') return asset.width;
  if (field === 'height') return asset.height;
  if (field === 'aspect_ratio') return asset.width !== null && asset.height ? asset.width / asset.height : null;
  if (field === 'favorite') return asset.is_favorite;
  if (field === 'archived') return asset.is_archived;
  if (field === 'availability') return asset.is_offline ? 'offline' : 'online';
  if (field === 'edited') return asset.is_edited;
  if (field === 'has_metadata') return asset.has_metadata;
  if (field === 'visibility') return asset.visibility ?? '';
  if (field === 'live_photo') return Boolean(asset.live_photo_video_id);
  if (field === 'tag') return asset.tags.flatMap((tag) => [tag.id, tag.name, tag.value]).filter(Boolean);
  if (field === 'album') return (asset.albums ?? []).flatMap((album) => [album.id, album.name]).filter(Boolean);
  if (field === 'has_tag') return asset.tags.length > 0;
  if (field === 'has_album') return (asset.albums ?? []).length > 0;
  if (field === 'stack_membership') return asset.stack !== null;
  if (field === 'stack_primary') return asset.stack?.primaryAssetId === asset.id;
  if (field === 'owner') return asset.owner_id ?? '';
  if (field === 'checksum') return asset.checksum ?? '';
  if (field === 'reference') return asset.id === group.referenceAssetId;
  if (field === 'similarity') return member.similarity;
  if (field === 'structural_similarity') return member.similarityEvidence?.structuralPercent ?? null;
  if (field === 'perceptual_similarity') return member.similarityEvidence?.perceptualPercent ?? null;
  if (field === 'color_similarity') return member.similarityEvidence?.colorPercent ?? null;
  if (field === 'detail_change') return member.similarityEvidence?.detailChangedPercent ?? null;
  if (field === 'admission_similarity') return member.admission?.admissionSimilarityPercent ?? null;
  if (field === 'link_depth') return member.admission?.linkDepth ?? null;
  if (field === 'duration') return asset.duration;
  if (field === 'same_folder_as_reference') return reference !== null && folder(asset.original_path) === folder(reference.original_path);
  if (field === 'same_library_as_reference') return reference !== null && asset.library_id === reference.library_id;
  if (field === 'same_mime_as_reference') return reference !== null && asset.original_mime_type === reference.original_mime_type;
  if (field === 'metadata_richness') {
    return Number(asset.has_metadata) + asset.tags.length + (asset.albums ?? []).length + Number(Boolean(asset.local_date_time));
  }
  if (field === 'format_quality') return formatQuality(asset.original_file_name, asset.original_mime_type);
  return null;
}

function groupValue(group: DuplicateGroupRecord, field: DuplicateAutomationGroupField): unknown {
  if (field === 'classification') return group.kind;
  if (field === 'review_state') return group.state;
  if (field === 'member_count') return group.members.length;
  if (field === 'group_similarity') return group.groupSimilarity;
  if (field === 'discovery_source') return group.discoverySources;
  if (field === 'auto_ready') return group.autoReady;
  if (field === 'selected') return group.selected;
  if (field === 'eligible') return group.state !== 'Blocked';
  if (field === 'decision_count') return Object.keys(group.savedDecisions).length;
  if (field === 'undecided_count') return Math.max(0, group.members.length - Object.keys(group.savedDecisions).length);
  return null;
}

function asNumber(value: string): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function matches(actual: unknown, operator: DuplicateKeeperRuleOperator, expected: string, kind: 'text' | 'number' | 'date' | 'boolean' | 'relation'): boolean {
  if (operator === 'is_true') return actual === true;
  if (operator === 'is_false') return actual === false;
  if (Array.isArray(actual)) {
    const actualValues = new Set(actual.map((item) => String(item).toLocaleLowerCase()));
    const wanted = new Set(values(expected));
    if (operator === 'has_any' || operator === 'is') return [...wanted].some((item) => actualValues.has(item));
    if (operator === 'has_all') return wanted.size > 0 && [...wanted].every((item) => actualValues.has(item));
    if (operator === 'has_none' || operator === 'is_not') return ![...wanted].some((item) => actualValues.has(item));
    return false;
  }
  if (typeof actual === 'boolean') {
    const expectedBoolean = ['true', '1', 'yes', 'online'].includes(expected.trim().toLocaleLowerCase());
    if (operator === 'is') return actual === expectedBoolean;
    if (operator === 'is_not') return actual !== expectedBoolean;
    return false;
  }
  if (kind === 'number' && typeof actual === 'number') {
    const other = asNumber(expected);
    if (other === null) return false;
    if (operator === 'gt') return actual > other;
    if (operator === 'gte') return actual >= other;
    if (operator === 'lt') return actual < other;
    if (operator === 'lte') return actual <= other;
    if (operator === 'is') return actual === other;
    if (operator === 'is_not') return actual !== other;
    return false;
  }
  if (kind === 'date' && typeof actual === 'string') {
    const left = Date.parse(actual);
    const right = Date.parse(expected);
    if (!Number.isFinite(left) || !Number.isFinite(right)) return false;
    if (operator === 'gt') return left > right;
    if (operator === 'gte') return left >= right;
    if (operator === 'lt') return left < right;
    if (operator === 'lte') return left <= right;
    if (operator === 'is') return left === right;
    if (operator === 'is_not') return left !== right;
    return false;
  }
  const actualText = actual === null || actual === undefined ? '' : String(actual).toLocaleLowerCase();
  const expectedText = expected.trim().toLocaleLowerCase();
  if (operator === 'is') return expected.includes(',') ? values(expected).includes(actualText) : actualText === expectedText;
  if (operator === 'is_not') return expected.includes(',') ? !values(expected).includes(actualText) : actualText !== expectedText;
  if (operator === 'contains') return actualText.includes(expectedText);
  if (operator === 'not_contains') return !actualText.includes(expectedText);
  if (operator === 'starts_with') return actualText.startsWith(expectedText);
  if (operator === 'ends_with') return actualText.endsWith(expectedText);
  return false;
}

function memberMatches(group: DuplicateGroupRecord, memberIndex: number, field: DuplicateKeeperRuleField, operator: DuplicateKeeperRuleOperator, value: string): boolean {
  const definition = keeperFieldDefinition(field);
  const kind = definition.kind === 'date'
    ? 'date'
    : definition.kind === 'number'
      ? 'number'
      : definition.kind === 'boolean'
        ? 'boolean'
        : definition.kind === 'relation'
          ? 'relation'
          : 'text';
  return matches(memberValue(group, memberIndex, field), operator, value, kind);
}

function conditionResult(group: DuplicateGroupRecord, condition: DuplicateAutomationUiCondition): { matched: boolean; memberIds: Set<string> } {
  if (condition.scope === 'group') {
    const definition = groupFieldDefinition(condition.field as DuplicateAutomationGroupField);
    return {
      matched: matches(groupValue(group, condition.field as DuplicateAutomationGroupField), condition.operator, condition.value, definition.kind),
      memberIds: new Set(),
    };
  }
  const memberIds = new Set(
    group.members
      .filter((_, index) => memberMatches(group, index, condition.field as DuplicateKeeperRuleField, condition.operator, condition.value))
      .map((member) => member.asset.id),
  );
  if (condition.scope === 'member') return { matched: memberIds.size > 0, memberIds };
  if (condition.scope === 'any_member') return { matched: memberIds.size > 0, memberIds: new Set() };
  if (condition.scope === 'all_members') return { matched: group.members.length > 0 && memberIds.size === group.members.length, memberIds: new Set() };
  if (condition.scope === 'no_members') return { matched: memberIds.size === 0, memberIds: new Set() };
  return { matched: memberIds.size >= condition.count, memberIds: new Set() };
}

function ruleMatch(group: DuplicateGroupRecord, rule: DuplicateAutomationUiRule): { matched: boolean; matchingMemberIds: Set<string> } {
  const results = rule.conditions.map((condition) => ({ condition, result: conditionResult(group, condition) }));
  const matched = rule.logic === 'all'
    ? results.every(({ result }) => result.matched)
    : results.some(({ result }) => result.matched);
  if (!matched) return { matched: false, matchingMemberIds: new Set() };
  const memberSets = results
    .filter(({ condition, result }) => condition.scope === 'member' && (rule.logic === 'all' || result.matched))
    .map(({ result }) => result.memberIds);
  if (!memberSets.length) return { matched: true, matchingMemberIds: new Set() };
  if (rule.logic === 'any') return { matched: true, matchingMemberIds: new Set(memberSets.flatMap((set) => [...set])) };
  const [first, ...rest] = memberSets;
  return {
    matched: true,
    matchingMemberIds: new Set([...first].filter((id) => rest.every((set) => set.has(id)))),
  };
}

function rankValue(group: DuplicateGroupRecord, memberIndex: number, field: DuplicateKeeperRuleField): number | string | null {
  const value = memberValue(group, memberIndex, field);
  const definition = keeperFieldDefinition(field);
  if (value === null || value === undefined) return null;
  if (definition.kind === 'date' && typeof value === 'string') {
    const parsed = Date.parse(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  if (typeof value === 'number' || typeof value === 'string') return value;
  return null;
}

function chooseKeeper(group: DuplicateGroupRecord, candidateIds: string[], rules: readonly DuplicateKeeperRule[]): string | null {
  let candidates = [...candidateIds];
  if (candidates.length < 2) return null;
  const indexById = new Map(group.members.map((member, index) => [member.asset.id, index]));
  for (const rule of rules) {
    if (rule.effect !== 'require') continue;
    const matched = candidates.filter((id) => {
      const index = indexById.get(id);
      return index !== undefined && !['highest', 'lowest'].includes(rule.operator) && memberMatches(group, index, rule.field, rule.operator, rule.value);
    });
    if (!matched.length) return null;
    candidates = matched;
  }
  for (const rule of rules) {
    if (rule.effect === 'require') continue;
    if (rule.operator === 'highest' || rule.operator === 'lowest') {
      const valued = candidates
        .map((id) => ({ id, index: indexById.get(id) }))
        .filter((item): item is { id: string; index: number } => item.index !== undefined)
        .map((item) => ({ ...item, value: rankValue(group, item.index, rule.field) }))
        .filter((item): item is { id: string; index: number; value: number | string } => item.value !== null);
      if (!valued.length) continue;
      const sorted = [...valued].sort((left, right) => {
        if (left.value === right.value) return 0;
        const order = left.value > right.value ? 1 : -1;
        return rule.operator === 'highest' ? -order : order;
      });
      const best = sorted[0].value;
      const selected = new Set(sorted.filter((item) => item.value === best).map((item) => item.id));
      if (rule.effect === 'prefer') candidates = candidates.filter((id) => selected.has(id));
      else {
        const survivors = candidates.filter((id) => !selected.has(id));
        if (survivors.length) candidates = survivors;
      }
      continue;
    }
    const matching = new Set(candidates.filter((id) => {
      const index = indexById.get(id);
      return index !== undefined && memberMatches(group, index, rule.field, rule.operator, rule.value);
    }));
    if (rule.effect === 'prefer') {
      if (matching.size) candidates = candidates.filter((id) => matching.has(id));
    } else {
      const survivors = candidates.filter((id) => !matching.has(id));
      if (survivors.length) candidates = survivors;
    }
  }
  if (candidates.length === 1) return candidates[0];
  return group.referenceAssetId && candidates.includes(group.referenceAssetId) ? group.referenceAssetId : null;
}

function sameDecisionSet(left: readonly DuplicateAutomationExistingDecision[], right: readonly DuplicateAutomationDecision[]): boolean {
  const normalize = (items: readonly DuplicateAutomationExistingDecision[]) => items
    .map((item) => `${item.assetId}:${item.disposition}:${item.source}`)
    .sort();
  const a = normalize(left);
  const b = normalize(right);
  return a.length === b.length && a.every((item, index) => item === b[index]);
}

export function evaluateDuplicateAutomation(
  group: DuplicateGroupRecord,
  rules: readonly DuplicateAutomationUiRule[],
  existing: readonly DuplicateAutomationExistingDecision[],
  keeperRules: readonly DuplicateKeeperRule[],
  overwriteManual = false,
): DuplicateAutomationEvaluation {
  const memberIds = group.members.map((member) => member.asset.id);
  const manual = new Map<string, DuplicateAutomationExistingDecision>();
  if (!overwriteManual) {
    for (const decision of existing) if (decision.source === 'manual') manual.set(decision.assetId, decision);
  }
  const automatic = new Map<string, DuplicateDecision>();
  const lockedUndecided = new Set<string>();
  let matched = false;
  let touchedByRule = false;
  let manualReview = false;
  let ambiguous = false;
  let matchedRuleCount = 0;
  let metadataKeeperAssetId: string | null = null;

  const currentlyDecided = (id: string) => manual.has(id) || automatic.has(id) || lockedUndecided.has(id);

  for (const rule of rules) {
    if (!automationRuleValid(rule)) continue;
    const result = ruleMatch(group, rule);
    if (!result.matched) continue;
    matched = true;
    matchedRuleCount += 1;
    let targetIds = rule.target === 'matching_members' ? [...result.matchingMemberIds] : [...memberIds];
    targetIds = targetIds.filter((id) => !currentlyDecided(id));

    if (rule.action === 'manual_review') {
      touchedByRule = true;
      manualReview = true;
    } else if (rule.action === 'leave_undecided') {
      touchedByRule = true;
    } else if (rule.action === 'resolve_keeper') {
      touchedByRule = true;
      const keeperId = chooseKeeper(group, targetIds, keeperRules);
      if (keeperId === null) {
        ambiguous = true;
        manualReview = true;
      } else {
        metadataKeeperAssetId = keeperId;
        for (const id of targetIds) automatic.set(id, id === keeperId ? 'keep' : 'delete');
      }
    } else if (targetIds.length) {
      touchedByRule = true;
      if (rule.action === 'delete') {
        const candidateDeletes = new Set([
          ...[...manual.values()].filter((item) => item.disposition === 'delete').map((item) => item.assetId),
          ...[...automatic.entries()].filter(([, disposition]) => disposition === 'delete').map(([id]) => id),
          ...targetIds,
        ]);
        if (candidateDeletes.size >= memberIds.length) {
          ambiguous = true;
          manualReview = true;
        } else {
          for (const id of targetIds) automatic.set(id, 'delete');
        }
      } else {
        for (const id of targetIds) automatic.set(id, rule.action);
      }
    }

    if (rule.flow === 'stop_affected') for (const id of targetIds) lockedUndecided.add(id);
    if (rule.flow === 'stop_group') break;
  }

  const decisions: DuplicateAutomationDecision[] = [
    ...[...manual.values()].map((item) => ({
      assetId: item.assetId,
      disposition: item.disposition,
      source: 'manual' as const,
      status: item.status ?? 'pending' as const,
    })),
    ...[...automatic.entries()].map(([assetId, disposition]) => ({
      assetId,
      disposition,
      source: 'automatic' as const,
      status: 'pending' as const,
    })),
  ];
  const touched = touchedByRule || manualReview;
  const complete = touched && decisions.length === memberIds.length;
  const partial = touched && decisions.length > 0 && decisions.length < memberIds.length;
  if (touched && decisions.length < memberIds.length) manualReview = true;
  const persistDraft = touched && !sameDecisionSet(existing, decisions);
  return {
    matched,
    touched,
    persistDraft,
    complete,
    partial,
    manualReview,
    ambiguous,
    preservedManual: !overwriteManual && manual.size > 0,
    matchedRuleCount,
    keepCount: [...automatic.values()].filter((value) => value === 'keep').length,
    deleteCount: [...automatic.values()].filter((value) => value === 'delete').length,
    stackCount: [...automatic.values()].filter((value) => value === 'stack').length,
    undecidedCount: Math.max(0, memberIds.length - decisions.length),
    metadataKeeperAssetId,
    decisions,
  };
}
