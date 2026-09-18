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
  it('renders linked admission as a compact depth pill that opens the admitting asset in a new tab', () => {
    const linked = member('asset-1', 'linked.jpg', 99, 'asset-2', 2);
    const admittedBy = member('asset-2', 'bridge.jpg', 99, null);
    const { body } = render(V2DuplicateAdmissionEvidence, {
      props: {
        member: linked,
        members: [linked, admittedBy],
        mode: 'linked',
      },
    });

    expect(body).toContain('v2-linked-admission-pill');
    expect(body).toContain('href="/v2/assets/asset-2"');
    expect(body).toContain('target="_blank"');
    expect(body).toContain('rel="noopener noreferrer"');
    expect(body).toContain('Linked through bridge.jpg, depth 2');
    expect(body).toMatch(/<span>2<\/span>/);
  });

  it('shows linked provenance from admission data even when the direct reference score is not below threshold', () => {
    const linked = member('asset-1', 'linked.jpg', 99.5, 'asset-2', 3);
    const admittedBy = member('asset-2', 'bridge.jpg', 99.7, null);
    const { body } = render(V2DuplicateAdmissionEvidence, {
      props: {
        member: linked,
        members: [linked, admittedBy],
        mode: 'linked',
      },
    });

    expect(body).toContain('depth 3');
    expect(body).toMatch(/<span>3<\/span>/);
  });

  it('does not render a pill for a direct reference admission', () => {
    const direct = member('asset-1', 'direct.jpg', 90, 'asset-2', 1);
    const reference = member('asset-2', 'reference.jpg', 100, null);
    const { body } = render(V2DuplicateAdmissionEvidence, {
      props: {
        member: direct,
        members: [direct, reference],
        mode: 'linked',
      },
    });

    expect(body).not.toContain('v2-linked-admission-pill');
    expect(body).not.toContain('reference.jpg');
  });

  it('does not render a linked pill outside linked validation mode or without a resolvable admitting asset', () => {
    const linked = member('asset-1', 'linked.jpg', 90, 'asset-2', 2);
    const admittedBy = member('asset-2', 'bridge.jpg', 99, null);

    const nonLinkedMode = render(V2DuplicateAdmissionEvidence, {
      props: {
        member: linked,
        members: [linked, admittedBy],
        mode: 'reference',
      },
    });
    const missingParent = render(V2DuplicateAdmissionEvidence, {
      props: {
        member: linked,
        members: [linked],
        mode: 'linked',
      },
    });

    expect(nonLinkedMode.body).not.toContain('v2-linked-admission-pill');
    expect(missingParent.body).not.toContain('v2-linked-admission-pill');
  });

  it('keeps validation and similarity evidence out of the duplicate-list overlay', () => {
    const linked = member('asset-1', 'linked.jpg', 98.72, 'asset-2', 2);
    linked.asset = { ...linked.asset, width: 18_000, height: 10_000 };
    linked.similarityEvidence = {
      structuralPercent: 99,
      perceptualPercent: 98,
      colorPercent: 97,
      detailSource: 'preview',
      validatedWidth: 4096,
      validatedHeight: 2276,
    };
    const admittedBy = member('asset-2', 'bridge.jpg', 99, null);
    const { body } = render(V2DuplicateAdmissionEvidence, {
      props: {
        member: linked,
        members: [linked, admittedBy],
        mode: 'linked',
      },
    });

    expect(body).toContain('v2-linked-admission-pill');
    expect(body).not.toContain('98.72% similarity');
    expect(body).not.toContain('Bounded validation');
    expect(body).not.toContain('Full-resolution validation');
    expect(body).not.toContain('Search-only appearance');
    expect(body).not.toContain('Validated at');
  });
});
