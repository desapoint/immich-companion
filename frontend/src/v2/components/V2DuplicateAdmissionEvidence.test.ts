import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import type { DuplicateMemberRecord } from '../data/contracts';
import V2DuplicateAdmissionEvidence from './V2DuplicateAdmissionEvidence.svelte';

function member(id: string, name: string, similarity: number, admittedByAssetId: string | null): DuplicateMemberRecord {
  return {
    asset: { id, original_file_name: name } as DuplicateMemberRecord['asset'],
    similarity,
    similarityEvidence: null,
    admission: admittedByAssetId === null ? null : {
      admittedByAssetId,
      admissionSimilarityPercent: 96,
      bestGroupMatchAssetId: admittedByAssetId,
      bestGroupMatchSimilarityPercent: 96,
      linkDepth: 1,
      modelVersion: 'test',
      featureVersion: 1,
      comparisonVersion: 1,
      configFingerprint: 'test',
    },
  };
}

describe('V2DuplicateAdmissionEvidence', () => {
  it('disables the reference-changing linked-admission control while writes are blocked', () => {
    const linked = member('asset-1', 'linked.jpg', 90, 'asset-2');
    const admittedBy = member('asset-2', 'bridge.jpg', 99, null);
    const { body } = render(V2DuplicateAdmissionEvidence, {
      props: {
        member: linked,
        members: [linked, admittedBy],
        mode: 'linked',
        threshold: 95,
        disabled: true,
        oninspect: () => {},
      },
    });

    expect(body).toContain('Linked through');
    expect(body).toContain('bridge.jpg');
    expect(body).toMatch(/<button\b[^>]*disabled[^>]*>\s*bridge\.jpg\s*<\/button>/);
  });

  it('keeps the linked-admission control available when writes are allowed', () => {
    const linked = member('asset-1', 'linked.jpg', 90, 'asset-2');
    const admittedBy = member('asset-2', 'bridge.jpg', 99, null);
    const { body } = render(V2DuplicateAdmissionEvidence, {
      props: {
        member: linked,
        members: [linked, admittedBy],
        mode: 'linked',
        threshold: 95,
        oninspect: () => {},
      },
    });

    const button = body.match(/<button\b[^>]*>\s*bridge\.jpg\s*<\/button>/)?.[0] ?? '';
    expect(button).not.toContain('disabled');
  });
});
