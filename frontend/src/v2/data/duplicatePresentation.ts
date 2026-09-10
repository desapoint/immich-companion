import type { DuplicateGroupRecord } from './contracts';

type DuplicateGroupPresentation = Pick<DuplicateGroupRecord, 'kind' | 'members'>;

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
