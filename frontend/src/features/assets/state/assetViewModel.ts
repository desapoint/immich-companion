import type {
  SearchCondition,
  SimpleAssetSearchFilters,
  SearchField,
  SearchGroup,
  SearchNode,
  SearchOperator,
} from '../types/assets';

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
  album: 'in_album',
};

export function createSearchCondition(field: SearchField = 'filename'): SearchCondition {
  const value = field === 'type' ? 'IMAGE' : field === 'favorite' || field === 'archived' || field === 'trashed' ? 'true' : '';
  return {
    id: nodeId('condition'),
    kind: 'condition',
    field,
    operator: DEFAULT_OPERATOR[field],
    value,
  };
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
  let value: string | number | boolean = node.value;
  if (node.field === 'width' || node.field === 'height') value = Number.parseInt(node.value, 10);
  if (node.field === 'aspect_ratio') value = Number.parseFloat(node.value);
  if (node.field === 'favorite' || node.field === 'archived' || node.field === 'trashed') {
    value = node.value === 'true';
  }
  if (node.field === 'taken_at') value = new Date(node.value).toISOString();
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
