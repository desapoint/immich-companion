import type { DuplicateGroupRecord, DuplicateKeeperRule, DuplicateKeeperRuleField, DuplicateKeeperRuleOperator } from '../types/contracts';
import { keeperFieldDefinition } from './duplicateKeeperRules';
import type { DuplicateAutomationConditionScope, DuplicateAutomationGroupField, DuplicateAutomationUiCondition, DuplicateAutomationUiRule } from './duplicateAutomationTypes';
import { automationGroupFields } from './duplicateAutomationOptions';

const values = (value: string) => value.split(',').map((item) => item.trim().toLocaleLowerCase()).filter(Boolean);
const folder = (path: string | null) => { if (!path) return ''; const normalized = path.replaceAll('\\', '/'); const index = normalized.lastIndexOf('/'); return index > 0 ? normalized.slice(0, index) : ''; };
const extension = (name: string) => { const index = name.lastIndexOf('.'); return index >= 0 ? name.slice(index + 1).toLocaleLowerCase() : ''; };
const formatQuality = (name: string, mime: string | null) => {
  const ext = extension(name); const normalized = (mime ?? '').toLocaleLowerCase();
  if (['dng', 'nef', 'cr2', 'cr3', 'arw', 'raf', 'rw2', 'orf', 'pef'].includes(ext) || normalized.includes('raw') || normalized.includes('dng')) return 5;
  if (['tif', 'tiff', 'png'].includes(ext) || ['image/tiff', 'image/png'].includes(normalized)) return 4;
  if (['heic', 'heif', 'avif'].includes(ext) || ['heic', 'heif', 'avif'].some((marker) => normalized.includes(marker))) return 3;
  if (['jpg', 'jpeg', 'webp'].includes(ext) || ['jpeg', 'webp'].some((marker) => normalized.includes(marker))) return 2;
  return 1;
};
const referenceAsset = (group: DuplicateGroupRecord) => group.members.find((member) => member.asset.id === group.referenceAssetId)?.asset ?? null;

function memberValue(group: DuplicateGroupRecord, memberIndex: number, field: DuplicateKeeperRuleField): unknown {
  const member = group.members[memberIndex]; const asset = member.asset; const reference = referenceAsset(group);
  if (field === 'library') return asset.library_id === null ? 'upload' : asset.library_id;
  if (field === 'folder') return folder(asset.original_path); if (field === 'filename') return asset.original_file_name; if (field === 'extension') return extension(asset.original_file_name);
  if (field === 'mime_type') return asset.original_mime_type; if (field === 'media_type') return asset.asset_type.toLocaleLowerCase(); if (field === 'date') return asset.local_date_time ?? asset.file_created_at;
  if (field === 'modified_date') return asset.file_modified_at; if (field === 'immich_created_at') return asset.immich_created_at; if (field === 'immich_updated_at') return asset.immich_updated_at;
  if (field === 'file_size') return asset.file_size_bytes; if (field === 'resolution') return asset.width !== null && asset.height !== null ? asset.width * asset.height : null; if (field === 'width') return asset.width; if (field === 'height') return asset.height;
  if (field === 'aspect_ratio') return asset.width !== null && asset.height ? asset.width / asset.height : null; if (field === 'favorite') return asset.is_favorite; if (field === 'archived') return asset.is_archived;
  if (field === 'availability') return asset.is_offline ? 'offline' : 'online'; if (field === 'edited') return asset.is_edited; if (field === 'has_metadata') return asset.has_metadata; if (field === 'visibility') return asset.visibility ?? '';
  if (field === 'live_photo') return Boolean(asset.live_photo_video_id); if (field === 'tag') return asset.tags.flatMap((tag) => [tag.id, tag.name, tag.value]).filter(Boolean); if (field === 'album') return (asset.albums ?? []).flatMap((album) => [album.id, album.name]).filter(Boolean);
  if (field === 'has_tag') return asset.tags.length > 0; if (field === 'has_album') return (asset.albums ?? []).length > 0; if (field === 'stack_membership') return asset.stack !== null; if (field === 'stack_primary') return asset.stack?.primaryAssetId === asset.id;
  if (field === 'owner') return asset.owner_id ?? ''; if (field === 'checksum') return asset.checksum ?? ''; if (field === 'reference') return asset.id === group.referenceAssetId; if (field === 'similarity') return member.similarity;
  if (field === 'structural_similarity') return member.similarityEvidence?.structuralPercent ?? null; if (field === 'perceptual_similarity') return member.similarityEvidence?.perceptualPercent ?? null; if (field === 'color_similarity') return member.similarityEvidence?.colorPercent ?? null;
  if (field === 'detail_change') return member.similarityEvidence?.detailChangedPercent ?? null; if (field === 'admission_similarity') return member.admission?.admissionSimilarityPercent ?? null; if (field === 'link_depth') return member.admission?.linkDepth ?? null; if (field === 'duration') return asset.duration;
  if (field === 'same_folder_as_reference') return reference !== null && folder(asset.original_path) === folder(reference.original_path); if (field === 'same_library_as_reference') return reference !== null && asset.library_id === reference.library_id;
  if (field === 'same_mime_as_reference') return reference !== null && asset.original_mime_type === reference.original_mime_type;
  if (field === 'metadata_richness') return Number(asset.has_metadata) + asset.tags.length + (asset.albums ?? []).length + Number(Boolean(asset.local_date_time));
  if (field === 'format_quality') return formatQuality(asset.original_file_name, asset.original_mime_type); return null;
}
function groupValue(group: DuplicateGroupRecord, field: DuplicateAutomationGroupField): unknown {
  if (field === 'classification') return group.kind; if (field === 'review_state') return group.state; if (field === 'member_count') return group.members.length; if (field === 'group_similarity') return group.groupSimilarity;
  if (field === 'discovery_source') return group.discoverySources; if (field === 'auto_ready') return group.autoReady; if (field === 'selected') return group.selected; if (field === 'eligible') return group.state !== 'Blocked';
  if (field === 'decision_count') return Object.keys(group.savedDecisions).length; if (field === 'undecided_count') return Math.max(0, group.members.length - Object.keys(group.savedDecisions).length); return null;
}
const asNumber = (value: string) => { const parsed = Number(value); return Number.isFinite(parsed) ? parsed : null; };
function matches(actual: unknown, operator: DuplicateKeeperRuleOperator, expected: string, kind: 'text' | 'number' | 'date' | 'boolean' | 'relation'): boolean {
  if (operator === 'is_true') return actual === true; if (operator === 'is_false') return actual === false;
  if (Array.isArray(actual)) { const actualValues = new Set(actual.map((item) => String(item).toLocaleLowerCase())); const wanted = new Set(values(expected)); if (operator === 'has_any' || operator === 'is') return [...wanted].some((item) => actualValues.has(item)); if (operator === 'has_all') return wanted.size > 0 && [...wanted].every((item) => actualValues.has(item)); if (operator === 'has_none' || operator === 'is_not') return ![...wanted].some((item) => actualValues.has(item)); return false; }
  if (typeof actual === 'boolean') { const expectedBoolean = ['true', '1', 'yes', 'online'].includes(expected.trim().toLocaleLowerCase()); if (operator === 'is') return actual === expectedBoolean; if (operator === 'is_not') return actual !== expectedBoolean; return false; }
  if (kind === 'number' && typeof actual === 'number') { const other = asNumber(expected); if (other === null) return false; if (operator === 'gt') return actual > other; if (operator === 'gte') return actual >= other; if (operator === 'lt') return actual < other; if (operator === 'lte') return actual <= other; if (operator === 'is') return actual === other; if (operator === 'is_not') return actual !== other; return false; }
  if (kind === 'date' && typeof actual === 'string') { const left = Date.parse(actual); const right = Date.parse(expected); if (!Number.isFinite(left) || !Number.isFinite(right)) return false; if (operator === 'gt') return left > right; if (operator === 'gte') return left >= right; if (operator === 'lt') return left < right; if (operator === 'lte') return left <= right; if (operator === 'is') return left === right; if (operator === 'is_not') return left !== right; return false; }
  const actualText = actual === null || actual === undefined ? '' : String(actual).toLocaleLowerCase(); const expectedText = expected.trim().toLocaleLowerCase();
  if (operator === 'is') return expected.includes(',') ? values(expected).includes(actualText) : actualText === expectedText; if (operator === 'is_not') return expected.includes(',') ? !values(expected).includes(actualText) : actualText !== expectedText; if (operator === 'contains') return actualText.includes(expectedText); if (operator === 'not_contains') return !actualText.includes(expectedText); if (operator === 'starts_with') return actualText.startsWith(expectedText); if (operator === 'ends_with') return actualText.endsWith(expectedText); return false;
}
function memberMatches(group: DuplicateGroupRecord, memberIndex: number, field: DuplicateKeeperRuleField, operator: DuplicateKeeperRuleOperator, value: string) {
  const definition = keeperFieldDefinition(field); const kind = definition.kind === 'date' ? 'date' : definition.kind === 'number' ? 'number' : definition.kind === 'boolean' ? 'boolean' : definition.kind === 'relation' ? 'relation' : 'text';
  return matches(memberValue(group, memberIndex, field), operator, value, kind);
}
function groupFieldDefinition(field: DuplicateAutomationGroupField) { return automationGroupFields.find((item) => item.value === field) ?? automationGroupFields[0]; }
function conditionResult(group: DuplicateGroupRecord, condition: DuplicateAutomationUiCondition): { matched: boolean; memberIds: Set<string> } {
  if (condition.scope === 'group') return { matched: matches(groupValue(group, condition.field as DuplicateAutomationGroupField), condition.operator, condition.value, groupFieldDefinition(condition.field as DuplicateAutomationGroupField).kind), memberIds: new Set() };
  const memberIds = new Set(group.members.filter((_, index) => memberMatches(group, index, condition.field as DuplicateKeeperRuleField, condition.operator, condition.value)).map((member) => member.asset.id));
  if (condition.scope === 'member') return { matched: memberIds.size > 0, memberIds }; if (condition.scope === 'any_member') return { matched: memberIds.size > 0, memberIds: new Set() }; if (condition.scope === 'all_members') return { matched: group.members.length > 0 && memberIds.size === group.members.length, memberIds: new Set() }; if (condition.scope === 'no_members') return { matched: memberIds.size === 0, memberIds: new Set() }; return { matched: memberIds.size >= condition.count, memberIds: new Set() };
}
export function ruleMatch(group: DuplicateGroupRecord, rule: DuplicateAutomationUiRule): { matched: boolean; matchingMemberIds: Set<string> } {
  const results = rule.conditions.map((condition) => ({ condition, result: conditionResult(group, condition) })); const matched = rule.logic === 'all' ? results.every(({ result }) => result.matched) : results.some(({ result }) => result.matched); if (!matched) return { matched: false, matchingMemberIds: new Set() };
  const memberSets = results.filter(({ condition, result }) => condition.scope === 'member' && (rule.logic === 'all' || result.matched)).map(({ result }) => result.memberIds); if (!memberSets.length) return { matched: true, matchingMemberIds: new Set() }; if (rule.logic === 'any') return { matched: true, matchingMemberIds: new Set(memberSets.flatMap((set) => [...set])) };
  const [first, ...rest] = memberSets; return { matched: true, matchingMemberIds: new Set([...first].filter((id) => rest.every((set) => set.has(id)))) };
}
function rankValue(group: DuplicateGroupRecord, memberIndex: number, field: DuplicateKeeperRuleField): number | string | null { const value = memberValue(group, memberIndex, field); const definition = keeperFieldDefinition(field); if (value === null || value === undefined) return null; if (definition.kind === 'date' && typeof value === 'string') { const parsed = Date.parse(value); return Number.isFinite(parsed) ? parsed : null; } return typeof value === 'number' || typeof value === 'string' ? value : null; }
export function chooseKeeper(group: DuplicateGroupRecord, candidateIds: string[], rules: readonly DuplicateKeeperRule[]): string | null {
  let candidates = [...candidateIds]; if (candidates.length < 2) return null; const indexById = new Map(group.members.map((member, index) => [member.asset.id, index]));
  for (const rule of rules) { if (rule.effect !== 'require') continue; const matched = candidates.filter((id) => { const index = indexById.get(id); return index !== undefined && !['highest', 'lowest'].includes(rule.operator) && memberMatches(group, index, rule.field, rule.operator, rule.value); }); if (!matched.length) return null; candidates = matched; }
  for (const rule of rules) { if (rule.effect === 'require') continue; if (rule.operator === 'highest' || rule.operator === 'lowest') { const valued = candidates.map((id) => ({ id, index: indexById.get(id) })).filter((item): item is { id: string; index: number } => item.index !== undefined).map((item) => ({ ...item, value: rankValue(group, item.index, rule.field) })).filter((item): item is { id: string; index: number; value: number | string } => item.value !== null); if (!valued.length) continue; const sorted = [...valued].sort((left, right) => { if (left.value === right.value) return 0; const order = left.value > right.value ? 1 : -1; return rule.operator === 'highest' ? -order : order; }); const best = sorted[0].value; const selected = new Set(sorted.filter((item) => item.value === best).map((item) => item.id)); if (rule.effect === 'prefer') candidates = candidates.filter((id) => selected.has(id)); else { const survivors = candidates.filter((id) => !selected.has(id)); if (survivors.length) candidates = survivors; } continue; }
    const matching = new Set(candidates.filter((id) => { const index = indexById.get(id); return index !== undefined && memberMatches(group, index, rule.field, rule.operator, rule.value); })); if (rule.effect === 'prefer') { if (matching.size) candidates = candidates.filter((id) => matching.has(id)); } else { const survivors = candidates.filter((id) => !matching.has(id)); if (survivors.length) candidates = survivors; }
  }
  if (candidates.length === 1) return candidates[0]; return group.referenceAssetId && candidates.includes(group.referenceAssetId) ? group.referenceAssetId : null;
}
