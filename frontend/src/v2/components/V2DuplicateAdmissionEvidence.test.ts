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
        oninspect: () => {},
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
        oninspect: () => {},
      },
    });

    expect(body).toContain('Bounded validation');
    expect(body).toContain('Original 18000 × 10000');
    expect(body).not.toContain('Validated at');
  });
});
