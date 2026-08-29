import type {
  SavedExpertSearch,
  SearchCondition,
  SearchField,
  SearchGroup,
  SearchNode,
  SearchOperator,
} from '../types/assets';
import { copySearchGroup } from './assetViewModel';

export const SAVED_EXPERT_SEARCHES_STORAGE_KEY = 'immich-companion:saved-expert-searches';
const MAX_SAVED_SEARCHES = 30;
const MAX_EXPRESSION_DEPTH = 12;

const SEARCH_FIELDS = new Set<SearchField>([
  'filename',
  'type',
  'taken_at',
  'width',
  'height',
  'aspect_ratio',
  'favorite',
  'archived',
  'album',
  'tag',
]);
const SEARCH_OPERATORS = new Set<SearchOperator>([
  'contains',
  'equals',
  'not_equals',
  'after',
  'before',
  'at_least',
  'at_most',
  'in_any',
  'in_all',
  'not_in_any',
  'has_none',
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isCondition(value: unknown): value is SearchCondition {
  if (!isRecord(value) || value.kind !== 'condition') return false;
  const conditionValue = value.value;
  return typeof value.id === 'string'
    && value.id.length > 0
    && typeof value.field === 'string'
    && SEARCH_FIELDS.has(value.field as SearchField)
    && typeof value.operator === 'string'
    && SEARCH_OPERATORS.has(value.operator as SearchOperator)
    && (typeof conditionValue === 'string'
      || (Array.isArray(conditionValue) && conditionValue.every((item) => typeof item === 'string')));
}

function isSearchNode(value: unknown, depth: number): value is SearchNode {
  if (depth > MAX_EXPRESSION_DEPTH || !isRecord(value)) return false;
  if (value.kind === 'condition') return isCondition(value);
  if (value.kind !== 'group' || typeof value.id !== 'string' || value.id.length === 0) return false;
  if ((value.operator !== 'and' && value.operator !== 'or') || typeof value.negate !== 'boolean') {
    return false;
  }
  return Array.isArray(value.children)
    && value.children.length <= 500
    && value.children.every((child) => isSearchNode(child, depth + 1));
}

function isSavedExpertSearch(value: unknown): value is SavedExpertSearch {
  return isRecord(value)
    && typeof value.id === 'string'
    && value.id.length > 0
    && typeof value.name === 'string'
    && value.name.trim().length > 0
    && value.name.length <= 80
    && typeof value.updated_at === 'string'
    && !Number.isNaN(Date.parse(value.updated_at))
    && isSearchNode(value.expression, 0)
    && value.expression.kind === 'group';
}

export function decodeSavedExpertSearches(raw: string | null): SavedExpertSearch[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed
      .slice(0, MAX_SAVED_SEARCHES)
      .filter(isSavedExpertSearch)
      .map((search) => ({ ...search, expression: copySearchGroup(search.expression) }));
  } catch {
    return [];
  }
}

export function upsertSavedExpertSearch(
  searches: SavedExpertSearch[],
  name: string,
  expression: SearchGroup,
  now = new Date(),
): SavedExpertSearch[] {
  const normalizedName = name.trim().slice(0, 80);
  if (!normalizedName) throw new Error('Enter a name before saving this search.');
  const existing = searches.find((search) => search.name.localeCompare(normalizedName, undefined, {
    sensitivity: 'accent',
  }) === 0);
  const saved: SavedExpertSearch = {
    id: existing?.id
      ?? globalThis.crypto?.randomUUID?.()
      ?? `saved-${Date.now()}-${Math.random().toString(36).slice(2)}`,
    name: normalizedName,
    expression: copySearchGroup(expression),
    updated_at: now.toISOString(),
  };
  return [saved, ...searches.filter((search) => search.id !== saved.id)].slice(0, MAX_SAVED_SEARCHES);
}

export function removeSavedExpertSearch(
  searches: SavedExpertSearch[],
  searchId: string,
): SavedExpertSearch[] {
  return searches.filter((search) => search.id !== searchId);
}
