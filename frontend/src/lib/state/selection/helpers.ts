import { MEMBER_BATCH_SIZE } from './constants';

export function batchIds(ids: readonly string[]): string[][] {
  if (!ids.length) return [[]];
  return Array.from(
    { length: Math.ceil(ids.length / MEMBER_BATCH_SIZE) },
    (_, index) => ids.slice(index * MEMBER_BATCH_SIZE, (index + 1) * MEMBER_BATCH_SIZE),
  );
}

export function applyMembership(
  source: Set<string>,
  ids: readonly string[],
  selected: boolean,
): number {
  let delta = 0;
  for (const id of ids) {
    const wasSelected = source.has(id);
    if (wasSelected === selected) continue;
    if (selected) source.add(id);
    else source.delete(id);
    delta += selected ? 1 : -1;
  }
  return delta;
}

export function visibleAnchor(selected: Set<string>, anchor: string | null): string | null {
  return selected.has(anchor ?? '') ? anchor : selected.values().next().value ?? null;
}
