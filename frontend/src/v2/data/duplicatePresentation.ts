import type { DuplicateGroupRecord } from './contracts';

type DuplicateGroupPresentation = Pick<DuplicateGroupRecord, 'kind' | 'members'>;

export function referenceFirstDuplicateMembers(
  members: ReadonlyArray<DuplicateGroupRecord['members'][number]>,
  referenceAssetId: string | null,
): DuplicateGroupRecord['members'] {
  const ordered = [...members];
  if (!referenceAssetId) return ordered;
  const referenceIndex = ordered.findIndex((member) => member.asset.id === referenceAssetId);
  if (referenceIndex <= 0) return ordered;
  const [reference] = ordered.splice(referenceIndex, 1);
  return [reference, ...ordered];
}

const KIND_LABELS: Record<string, string> = {
  'exact file': 'Byte-perfect match',
  'exact pixels': 'Pixel-perfect match',
  'likely same': 'Likely same image',
  similar: 'Appearance match',
  mismatch: 'Content mismatch',
  unverified: 'Unverified match',
  unavailable: 'Unavailable file',
  ineligible: 'Not actionable',
};

export function duplicateGroupTitle(group: DuplicateGroupPresentation): string {
  const representative = group.members[0]?.asset.original_file_name.trim() || 'Duplicate group';
  const remaining = Math.max(0, group.members.length - 1);
  return remaining ? `${representative} and ${remaining} more` : representative;
}

export function duplicateKindLabel(kind: string): string {
  const normalized = kind.trim().replaceAll('_', ' ').replace(/\s+/g, ' ');
  if (!normalized) return 'Duplicate match';
  return KIND_LABELS[normalized.toLowerCase()] ?? normalized[0].toUpperCase() + normalized.slice(1);
}

export function duplicateAssetSourceLabel(libraryId: string | null, libraryName?: string): string {
  if (!libraryId) return 'Immich upload';
  return libraryName ? `External · ${libraryName}` : 'External library';
}
