import { describe, expect, it } from 'vitest';

import type { DuplicateMember, ExactDuplicateGroup } from '../types/duplicates';
import {
  countDuplicateReviewFilters,
  duplicateGroupMatchesFilter,
  duplicateWorkflowLabel,
  type DuplicateReviewProjection,
} from './duplicateReviewFilters';

function member(overrides: Partial<DuplicateMember> = {}): DuplicateMember {
  return {
    id: 'member-1',
    source_kind: 'upload',
    library_id: null,
    original_file_name: 'photo.jpg',
    original_mime_type: 'image/jpeg',
    file_size_bytes: 10,
    file_modified_at: '2026-08-30T00:00:00Z',
    uploaded_at: '2026-08-30T00:00:00Z',
    is_offline: false,
    is_stacked: false,
    immich_url: null,
    verification: 'matching',
    content_checksum: 'sha1',
    evidence: {
      analysis_freshness: 'current',
      integrity_status: 'healthy',
      issue_codes: [],
      detected_format: 'jpeg',
      format_matches_declared: true,
      decode_supported: true,
      decode_valid: true,
      decoded_width: 10,
      decoded_height: 10,
      dimensions_match_immich: true,
    },
    similarity: null,
    ...overrides,
  };
}

function group(overrides: Partial<ExactDuplicateGroup> = {}): ExactDuplicateGroup {
  return {
    duplicate_id: 'group-1',
    group_id: 'group-1',
    discovery_source: 'immich_duplicate',
    classification: 'exact_file',
    status: 'exact',
    reason: null,
    keeper_asset_id: 'member-1',
    recommended_action: 'resolve',
    recommended_primary_asset_id: 'member-1',
    recommendation_reason_codes: ['exact_sha1'],
    auto_resolvable: true,
    auto_selected: true,
    action_source: 'automatic',
    primary_source: 'automatic',
    manual_action: null,
    manual_primary_asset_id: null,
    effective_action: 'resolve',
    effective_primary_asset_id: 'member-1',
    review_status: 'pending',
    member_fingerprint: 'fingerprint',
    members: [member()],
    eligible: true,
    ...overrides,
  };
}

function projection(overrides: Partial<DuplicateReviewProjection> = {}): DuplicateReviewProjection {
  return {
    group: group(),
    effectiveAction: 'resolve',
    actionable: true,
    analysisPending: false,
    ...overrides,
  };
}

describe('duplicate review filters', () => {
  it('classifies automatic and action-ready Immich groups', () => {
    const entry = projection();

    expect(duplicateGroupMatchesFilter(entry, 'all')).toBe(true);
    expect(duplicateGroupMatchesFilter(entry, 'immich_duplicates')).toBe(true);
    expect(duplicateGroupMatchesFilter(entry, 'auto_ready')).toBe(true);
    expect(duplicateGroupMatchesFilter(entry, 'resolve_ready')).toBe(false);
    expect(duplicateGroupMatchesFilter(entry, 'stack_ready')).toBe(false);
    expect(duplicateWorkflowLabel(entry)).toBe('Auto ready');
  });

  it('prioritizes active analysis and integrity warnings', () => {
    const analyzing = projection({
      analysisPending: true,
      group: group({
        members: [member({ evidence: { ...member().evidence, analysis_freshness: 'stale' } })],
      }),
    });
    const warning = projection({
      group: group({
        auto_selected: false,
        members: [member({ evidence: { ...member().evidence, decode_valid: false } })],
      }),
    });

    expect(duplicateGroupMatchesFilter(analyzing, 'analyzing')).toBe(true);
    expect(duplicateWorkflowLabel(analyzing)).toBe('Analyzing');
    expect(duplicateGroupMatchesFilter(warning, 'integrity_warning')).toBe(true);
    expect(duplicateWorkflowLabel(warning)).toBe('Integrity warning');
  });

  it('marks deferred, drifted, unsafe, and undecided groups as needing review', () => {
    const entries = [
      projection({ group: group({ review_status: 'review_later' }), effectiveAction: 'none', actionable: false }),
      projection({ group: group({ review_status: 'drifted' }) }),
      projection({ actionable: false }),
    ];

    expect(entries.every((entry) => duplicateGroupMatchesFilter(entry, 'needs_review'))).toBe(true);
  });

  it('uses the same matching rules for filter counts', () => {
    const entries = [
      projection(),
      projection({
        group: group({ duplicate_id: 'group-2', auto_selected: false, recommended_action: 'stack_all' }),
        effectiveAction: 'stack_all',
      }),
      projection({
        group: group({ duplicate_id: 'group-3', auto_selected: false, manual_action: 'resolve' }),
      }),
    ];

    expect(countDuplicateReviewFilters(entries)).toMatchObject({
      all: 3,
      auto_ready: 1,
      resolve_ready: 1,
      stack_ready: 1,
      needs_review: 0,
      immich_duplicates: 3,
    });
  });
});
