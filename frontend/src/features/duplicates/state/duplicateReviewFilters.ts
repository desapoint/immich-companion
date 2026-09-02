import type { DuplicatePlanAction, ExactDuplicateGroup } from '../types/duplicates';

export type DuplicateReviewFilter =
  | 'all'
  | 'auto_ready'
  | 'resolve_ready'
  | 'stack_ready'
  | 'needs_review'
  | 'analyzing'
  | 'integrity_warning'
  | 'immich_duplicates';

export interface DuplicateReviewProjection {
  group: ExactDuplicateGroup;
  effectiveAction: DuplicatePlanAction;
  actionable: boolean;
  analysisPending: boolean;
}

export const duplicateReviewFilters: ReadonlyArray<{
  value: DuplicateReviewFilter;
  label: string;
}> = [
  { value: 'all', label: 'All' },
  { value: 'auto_ready', label: 'Auto ready' },
  { value: 'resolve_ready', label: 'Resolve ready' },
  { value: 'stack_ready', label: 'Stack ready' },
  { value: 'needs_review', label: 'Needs review' },
  { value: 'analyzing', label: 'Analyzing' },
  { value: 'integrity_warning', label: 'Integrity warning' },
  { value: 'immich_duplicates', label: 'Immich duplicates' },
];

export function duplicateGroupIsAnalyzing(entry: DuplicateReviewProjection): boolean {
  return entry.analysisPending
    && entry.group.members.some((member) => member.evidence.analysis_freshness !== 'current');
}

export function duplicateGroupHasIntegrityWarning(entry: DuplicateReviewProjection): boolean {
  return entry.group.members.some((member) => (
    member.evidence.integrity_status === 'warning'
    || member.evidence.integrity_status === 'malformed'
    || member.evidence.decode_valid === false
    || member.evidence.format_matches_declared === false
  ));
}

export function duplicateGroupMatchesFilter(
  entry: DuplicateReviewProjection,
  filter: DuplicateReviewFilter,
): boolean {
  if (filter === 'all') return true;
  if (filter === 'immich_duplicates') return entry.group.discovery_source === 'immich_duplicate';
  if (filter === 'analyzing') return duplicateGroupIsAnalyzing(entry);
  if (filter === 'integrity_warning') return duplicateGroupHasIntegrityWarning(entry);
  if (filter === 'auto_ready') {
    return entry.group.auto_selected
      && entry.group.manual_action === null
      && entry.group.review_status === 'pending';
  }
  if (filter === 'resolve_ready') {
    return entry.effectiveAction === 'resolve'
      && entry.actionable
      && !duplicateGroupMatchesFilter(entry, 'auto_ready');
  }
  if (filter === 'stack_ready') {
    return entry.effectiveAction === 'stack_all'
      && entry.actionable
      && !duplicateGroupMatchesFilter(entry, 'auto_ready');
  }
  if (duplicateGroupIsAnalyzing(entry)) return false;
  if (
    entry.group.review_status === 'review_later'
    || entry.group.review_status === 'drifted'
    || entry.effectiveAction === 'none'
    || !entry.actionable
  ) return true;
  if (
    duplicateGroupMatchesFilter(entry, 'auto_ready')
    || duplicateGroupMatchesFilter(entry, 'resolve_ready')
    || duplicateGroupMatchesFilter(entry, 'stack_ready')
  ) return false;
  return entry.group.review_status === 'pending';
}

export function countDuplicateReviewFilters(
  entries: DuplicateReviewProjection[],
): Record<DuplicateReviewFilter, number> {
  return Object.fromEntries(
    duplicateReviewFilters.map(({ value }) => [
      value,
      entries.filter((entry) => duplicateGroupMatchesFilter(entry, value)).length,
    ]),
  ) as Record<DuplicateReviewFilter, number>;
}

export function duplicateWorkflowLabel(entry: DuplicateReviewProjection): string {
  if (duplicateGroupIsAnalyzing(entry)) return 'Analyzing evidence';
  if (entry.group.review_status === 'drifted') return 'Group changed · review again';
  if (duplicateGroupHasIntegrityWarning(entry)) return 'Integrity warning · review required';
  if (duplicateGroupMatchesFilter(entry, 'auto_ready')) return 'Ready to review · recommended';
  if (duplicateGroupMatchesFilter(entry, 'resolve_ready')) return 'Ready to review · resolve';
  if (duplicateGroupMatchesFilter(entry, 'stack_ready')) return 'Ready to review · stack';
  if (duplicateGroupMatchesFilter(entry, 'needs_review')) return 'Needs decisions or attention';
  return entry.group.review_status.replaceAll('_', ' ');
}
