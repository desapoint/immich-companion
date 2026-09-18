import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import type { DuplicateMemberRecord } from '../data/contracts';
import V2DuplicateAdmissionEvidence from './V2DuplicateAdmissionEvidence.svelte';

function member(
  id: string,
  name: string,
  similarity: number,
  admittedByAssetId: string | null,
  linkDepth = 1,
): DuplicateMemberRecord {
  return {
    asset: { id, original_file_name: name } as DuplicateMemberRecord['asset'],
    similarity,
    similarityEvidence: null,
    admission: admittedByAssetId === null ? null : {
      admittedByAssetId,
      admissionSimilarityPercent: 96,
      bestGroupMatchAssetId: admittedByAssetId,
      bestGroupMatchSimilarityPercent: 96,
      linkDepth,
      modelVersion: 'test',
      featureVersion: 1,
      comparisonVersion: 1,
      configFingerprint: 'test',
    },
  };
}

describe('V2DuplicateAdmissionEvidence', () => {
  it('links the admitting source to its deep-linked Assets viewer in a new tab', () => {
    const linked = member('asset-1', 'linked.jpg', 90, 'asset-2', 2);
    const admittedBy = member('asset-2', 'bridge.jpg', 99, null);
    const { body } = render(V2DuplicateAdmissionEvidence, {
      props: {
        member: linked,
        members: [linked, admittedBy],
        mode: 'linked',
        threshold: 95,
      },
    });

    expect(body).toContain('Linked through');
    expect(body).toContain('bridge.jpg');
    expect(body).toContain('href="/v2/assets/asset-2"');
    expect(body).toContain('target="_blank"');
    expect(body).toContain('rel="noopener noreferrer"');
  });

  it('does not call a direct reference admission a linked match', () => {
    const direct = member('asset-1', 'direct.jpg', 90, 'asset-2', 1);
    const reference = member('asset-2', 'reference.jpg', 100, null);
    const { body } = render(V2DuplicateAdmissionEvidence, {
      props: {
        member: direct,
        members: [direct, reference],
        mode: 'linked',
        threshold: 95,
      },
    });

    expect(body).not.toContain('Linked through');
    expect(body).not.toContain('reference.jpg');
  });

  it('labels bounded evidence with its original and actual validation dimensions', () => {
    const bounded = member('asset-1', 'large.jpg', 98.72, null);
    bounded.asset = {
      ...bounded.asset,
      width: 18_000,
      height: 10_000,
    };
    bounded.similarityEvidence = {
      structuralPercent: 99,
      perceptualPercent: 98,
      colorPercent: 97,
      detailSource: 'preview',
      validatedWidth: 4096,
      validatedHeight: 2276,
    };

    const { body } = render(V2DuplicateAdmissionEvidence, {
      props: {
        member: bounded,
        members: [bounded],
        mode: 'reference',
        threshold: 95,
      },
    });

    expect(body).toContain('98.72% similarity');
    expect(body).toContain('Bounded validation');
    expect(body).toContain('Original 18000 × 10000');
    expect(body).toContain('Validated at 4096 × 2276');
  });

  it('does not invent validated dimensions when bounded evidence does not provide them', () => {
    const bounded = member('asset-1', 'large.jpg', 98.72, null);
    bounded.asset = {
      ...bounded.asset,
      width: 18_000,
      height: 10_000,
    };
    bounded.similarityEvidence = {
      structuralPercent: 99,
      perceptualPercent: 98,
      colorPercent: 97,
      detailSource: 'preview',
    };

    const { body } = render(V2DuplicateAdmissionEvidence, {
      props: {
        member: bounded,
        members: [bounded],
        mode: 'reference',
        threshold: 95,
      },
    });

    expect(body).toContain('Bounded validation');
    expect(body).toContain('Original 18000 × 10000');
    expect(body).not.toContain('Validated at');
  });
});
