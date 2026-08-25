import type {
  AssetComparisonSource,
  AssetCardInlineTagMode,
  AssetTagSummary,
  AssetStackMember,
  AssetSummary,
  SearchCondition,
  SimpleAssetSearchFilters,
  SearchField,
  SearchGroup,
  SearchNode,
  SearchOperator,
} from '../types/assets';
import { parseAspectRatioInput } from '../../../lib/utils/aspectRatio';

export interface AssetComparisonState {
  selectedId: string;
  visibleId: string;
}

let nextSearchNodeId = 0;

function nodeId(prefix: 'condition' | 'group'): string {
  nextSearchNodeId += 1;
  return `${prefix}-${nextSearchNodeId}`;
}

const DEFAULT_OPERATOR: Record<SearchField, SearchOperator> = {
  filename: 'contains',
  type: 'equals',
  taken_at: 'after',
  width: 'at_least',
  height: 'at_least',
  aspect_ratio: 'at_least',
  favorite: 'equals',
  archived: 'equals',
  trashed: 'equals',
  album: 'in_any',
  tag: 'in_any',
};

export function createSearchCondition(field: SearchField = 'filename'): SearchCondition {
  const value = field === 'type'
    ? 'IMAGE'
    : field === 'favorite' || field === 'archived' || field === 'trashed'
      ? 'true'
      : field === 'album' || field === 'tag'
        ? []
        : '';
  return {
    id: nodeId('condition'),
    kind: 'condition',
    field,
    operator: DEFAULT_OPERATOR[field],
    value,
  };
}

export function createEmptyRelationCondition(field: 'album' | 'tag'): SearchCondition {
  const condition = createSearchCondition(field);
  condition.operator = 'has_none';
  return condition;
}

export function resetSearchConditionField(
  condition: SearchCondition,
  field: SearchField,
): void {
  const replacement = createSearchCondition(field);
  condition.field = replacement.field;
  condition.operator = replacement.operator;
  condition.value = replacement.value;
}

export function createSearchGroup(operator: 'and' | 'or' = 'and'): SearchGroup {
  return {
    id: nodeId('group'),
    kind: 'group',
    operator,
    negate: false,
    children: [],
  };
}

export function copySearchGroup(group: SearchGroup): SearchGroup {
  return JSON.parse(JSON.stringify(group)) as SearchGroup;
}

export function createSimpleAssetSearchFilters(): SimpleAssetSearchFilters {
  return {
    query: '',
    assetType: '',
    favorite: 'any',
    archived: 'any',
    trashed: 'false',
    albumIds: [],
    tagIds: [],
    noAlbum: false,
    noTag: false,
    takenAfter: '',
    takenBefore: '',
    minWidth: '',
    maxWidth: '',
    minHeight: '',
    maxHeight: '',
    minAspectRatio: '',
    maxAspectRatio: '',
  };
}

export function simpleFiltersToSearchGroup(filters: SimpleAssetSearchFilters): SearchGroup {
  const group = createSearchGroup();
  const query = filters.query.trim();

  if (query) {
    const condition = createSearchCondition('filename');
    condition.value = query;
    group.children.push(condition);
  }
  if (filters.assetType) {
    const condition = createSearchCondition('type');
    condition.value = filters.assetType;
    group.children.push(condition);
  }
  for (const field of ['favorite', 'archived', 'trashed'] as const) {
    const value = filters[field];
    if (value === 'any') continue;
    const condition = createSearchCondition(field);
    condition.value = value;
    group.children.push(condition);
  }

  if (filters.noAlbum) {
    group.children.push(createEmptyRelationCondition('album'));
  } else if (filters.albumIds.length) {
    const condition = createSearchCondition('album');
    condition.value = [...filters.albumIds];
    group.children.push(condition);
  }
  if (filters.noTag) {
    group.children.push(createEmptyRelationCondition('tag'));
  } else if (filters.tagIds.length) {
    const condition = createSearchCondition('tag');
    condition.value = [...filters.tagIds];
    group.children.push(condition);
  }

  const ranges = [
    ['taken_at', 'after', filters.takenAfter],
    ['taken_at', 'before', filters.takenBefore],
    ['width', 'at_least', filters.minWidth],
    ['width', 'at_most', filters.maxWidth],
    ['height', 'at_least', filters.minHeight],
    ['height', 'at_most', filters.maxHeight],
    ['aspect_ratio', 'at_least', filters.minAspectRatio],
    ['aspect_ratio', 'at_most', filters.maxAspectRatio],
  ] as const;

  for (const [field, operator, rawValue] of ranges) {
    const value = rawValue.trim();
    if (!value) continue;
    const condition = createSearchCondition(field);
    condition.operator = operator;
    condition.value = value;
    group.children.push(condition);
  }

  return group;
}

function serializeNode(node: SearchNode): Record<string, unknown> {
  if (node.kind === 'group') {
    return {
      kind: 'group',
      operator: node.operator,
      negate: node.negate,
      children: node.children.map(serializeNode),
    };
  }
  let value: string | number | boolean | string[] = Array.isArray(node.value)
    ? [...node.value]
    : node.value;
  if (node.field === 'width' || node.field === 'height') value = Number.parseInt(String(node.value), 10);
  if (node.field === 'aspect_ratio') value = parseAspectRatioInput(String(node.value));
  if (node.field === 'favorite' || node.field === 'archived' || node.field === 'trashed') {
    value = node.value === 'true';
  }
  if (node.field === 'taken_at') value = new Date(String(node.value)).toISOString();
  return { kind: 'condition', field: node.field, operator: node.operator, value };
}

export function serializeSearchGroup(group: SearchGroup): Record<string, unknown> {
  return serializeNode(group);
}

export function nextViewerIndex(
  currentIndex: number,
  direction: 'previous' | 'next',
  total: number,
): number {
  if (direction === 'previous') return Math.max(0, currentIndex - 1);
  return Math.min(Math.max(total - 1, 0), currentIndex + 1);
}

export function toggleSelectedAsset(selectedIds: Set<string>, assetId: string): Set<string> {
  const next = new Set(selectedIds);
  if (next.has(assetId)) next.delete(assetId);
  else next.add(assetId);
  return next;
}

export function assetAsStackMember(asset: AssetSummary): AssetStackMember {
  return {
    id: asset.id,
    type: asset.type,
    original_file_name: asset.original_file_name,
    original_mime_type: asset.original_mime_type,
    width: asset.width,
    height: asset.height,
    taken_at: asset.taken_at,
  };
}

export function stackMembersForAsset(asset: AssetSummary): AssetStackMember[] {
  const members = asset.stack?.assets ?? [];
  const unique = new Map(members.map((member) => [member.id, member]));
  if (!unique.has(asset.id)) unique.set(asset.id, assetAsStackMember(asset));
  return [...unique.values()];
}

export function searchedTagIds(group: SearchGroup): string[] {
  const identifiers = new Set<string>();
  function visit(node: SearchNode): void {
    if (node.kind === 'group') {
      node.children.forEach(visit);
      return;
    }
    if (node.field !== 'tag' || !Array.isArray(node.value)) return;
    node.value.forEach((identifier) => identifiers.add(identifier));
  }
  visit(group);
  return [...identifiers];
}

export function inlineTagsForAsset(
  tags: AssetTagSummary[],
  mode: AssetCardInlineTagMode,
  matchingTagIds: ReadonlySet<string>,
): AssetTagSummary[] {
  if (mode === 'hidden') return [];
  if (mode === 'matching') return tags.filter((tag) => matchingTagIds.has(tag.id));
  return tags;
}

export function comparisonPreviewState(
  source: AssetComparisonSource,
  selectedId: string,
  targetId: string,
): AssetComparisonState {
  return {
    selectedId: source === 'similar' ? targetId : selectedId,
    visibleId: targetId,
  };
}

export function restoreComparisonState(selectedId: string): AssetComparisonState {
  return { selectedId, visibleId: selectedId };
}

export function formatAssetBytes(value: number | null): string | null {
  if (value === null) return null;
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(1)} MB`;
  return `${(value / 1024 ** 3).toFixed(1)} GB`;
}

export function formatAssetDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}
