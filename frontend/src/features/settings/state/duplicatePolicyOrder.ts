import type { DuplicatePolicy, ImmichLibraryOption } from '../types/settings';

export interface OrderedPolicyItem {
  id: string;
  label: string;
  description: string;
  unavailable?: boolean;
}

export const tiebreakerDefinitions: OrderedPolicyItem[] = [
  { id: 'favorite', label: 'Favorite', description: 'Prefer assets marked as favorites.' },
  { id: 'resolution', label: 'Resolution', description: 'Prefer the largest pixel dimensions.' },
  { id: 'metadata_richness', label: 'Metadata richness', description: 'Prefer the asset with more populated EXIF fields.' },
  { id: 'file_size', label: 'Original file size', description: 'Prefer the largest original file.' },
  { id: 'oldest_capture', label: 'Oldest capture time', description: 'Prefer the earliest original capture.' },
  { id: 'uploaded_at', label: 'Most recently uploaded', description: 'Prefer the newest Immich upload timestamp.' },
];

export function orderedSourcePriority(policy: DuplicatePolicy, available: ImmichLibraryOption[]): string[] {
  const libraryIds = available.map((library) => library.id);
  const configured = [...policy.source_priority];
  if (configured.length === 0) {
    return policy.keeper_policy === 'prefer_external'
      ? [...libraryIds, 'unlisted', 'immich_uploads']
      : ['immich_uploads', ...libraryIds, 'unlisted'];
  }
  const next = [...configured];
  const unlistedIndex = next.indexOf('unlisted');
  next.splice(unlistedIndex < 0 ? next.length : unlistedIndex, 0, ...libraryIds.filter((id) => !next.includes(id)));
  if (!next.includes('immich_uploads')) next.push('immich_uploads');
  if (!next.includes('unlisted')) next.push('unlisted');
  return next;
}

export function orderedTiebreakers(policy: DuplicatePolicy): DuplicatePolicy['keeper_tiebreakers'] {
  const configured = [...policy.keeper_tiebreakers];
  return [
    ...configured,
    ...tiebreakerDefinitions
      .map((item) => item.id as DuplicatePolicy['keeper_tiebreakers'][number])
      .filter((id) => !configured.includes(id)),
  ];
}

export function sourcePriorityItems(priority: string[], available: ImmichLibraryOption[]): OrderedPolicyItem[] {
  const byId = new Map(available.map((library) => [library.id, library]));
  return priority.map((source): OrderedPolicyItem => {
    if (source === 'immich_uploads') return { id: source, label: 'Immich uploads', description: 'Assets managed in the upload library.' };
    if (source === 'unlisted') return { id: source, label: 'Unlisted sources', description: 'Libraries not explicitly ranked here.' };
    const library = byId.get(source);
    return library
      ? { id: source, label: library.name, description: `External library · ${library.assetCount ?? 'unknown'} assets` }
      : { id: source, label: `Library ${source.slice(0, 8)}…`, description: `Saved library UUID: ${source}`, unavailable: true };
  });
}
