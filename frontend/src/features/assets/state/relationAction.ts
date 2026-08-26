import type { SelectOption } from '../../../lib/types/ui';

export const ALL_RELATIONS_VALUE = '__all_relations__';

export function relationDialogOptions(
  options: SelectOption[],
  remove: boolean,
  relationName: 'albums' | 'tags',
): SelectOption[] {
  return remove
    ? [{ value: ALL_RELATIONS_VALUE, label: `All ${relationName}` }, ...options]
    : options;
}
export function updateRelationSelection(
  previous: string[],
  next: string[],
  remove: boolean,
): string[] {
  if (!remove) return next;
  if (next.includes(ALL_RELATIONS_VALUE) && !previous.includes(ALL_RELATIONS_VALUE)) {
    return [ALL_RELATIONS_VALUE];
  }
  return next.filter((value) => value !== ALL_RELATIONS_VALUE);
}

export function resolveRelationSelection(
  values: string[],
  options: SelectOption[],
): string[] {
  return values.includes(ALL_RELATIONS_VALUE)
    ? options.map((option) => option.value)
    : values;
}
