import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import type { DuplicateAdmissionEvidence, DuplicateMemberRecord } from '../data/contracts';
import V2DuplicateCompareViewer from './V2DuplicateCompareViewer.svelte';

function buttonWithText(body: string, text: string): string {
  return [...body.matchAll(/<button\b[^>]*>[\s\S]*?<\/button>/g)]
    .map((match) => match[0])
    .find((button) => button.includes(text)) ?? '';
}

function admission(overrides: Partial<DuplicateAdmissionEvidence> = {}): DuplicateAdmissionEvidence {
  return {
    admittedByAssetId: 'asset-2',
    admissionSimilarityPercent: 91.36,
    bestGroupMatchAssetId: 'asset-3',
    bestGroupMatchSimilarityPercent: 94.08,
    linkDepth: 2,
    modelVersion: 'appearance-v3',
    featureVersion: 5,
    comparisonVersion: 3,
    configFingerprint: 'fingerprint-123',
    ...overrides,
  };
}

function groupMember(
  id: string,
  name: string,
  similarity: number | null,
  admissionEvidence: DuplicateAdmissionEvidence | null = null,
): DuplicateMemberRecord {
  return {
    asset: { id, original_file_name: name } as DuplicateMemberRecord['asset'],
    similarity,
    similarityEvidence: null,
    admission: admissionEvidence,
  };
}

describe('V2DuplicateCompareViewer', () => {
  it('uses the shared decision controls with a layout-stable stack primary action', () => {
    const { body } = render(V2DuplicateCompareViewer, {
      props: {
        open: true,
        groupTitle: 'IMG_1234.JPG and 2 more',
        groupKind: 'similar',
        groupSimilarity: 96.456,
        assetIds: ['asset-1'],
        similarities: { 'asset-1': 97.2 },
        similarityEvidence: {
          'asset-1': {
            structuralPercent: 98.126,
            perceptualPercent: 96.9,
            colorPercent: 92.4,
            detailChangedPercent: 2.345,
            detailSource: 'original',
          },
        },
        decisions: { 'asset-1': 'stack' },
        decisionOptions: ['keep', 'delete', 'stack'],
        stackLabel: 'Stack 1',
        stackPrimary: true,
        onclose: () => {},
      },
    });

    expect(body).toContain('IMG_1234.JPG and 2 more');
    expect(body).toContain('Appearance match');
    expect(body).toContain('Group similarity');
    expect(body).toContain('96.46%');
    expect(body).toContain('Similarity to reference');
    expect(body).toContain('Structure');
    expect(body).toContain('98.13%');
    expect(body).toContain('Perceptual hash');
    expect(body).toContain('96.90%');
    expect(body).toContain('Color');
    expect(body).toContain('92.40%');
    expect(body).toContain('Detail changed area');
    expect(body).toContain('2.35%');
    expect(body).toContain('Detail evidence');
    expect(body).toContain('Original');
    expect(body).toContain('Difference shows displayed-pixel changes');
    expect(body).toContain('Local changes shows the validator grid');
    expect(body).not.toContain('Similarity engine');
    expect(body).toContain('data-decision="stack"');
    expect(body).toContain('Stack 1');
    expect(body).toContain('Stack primary');
    expect(body).toContain('Clear selection');
    expect(body).toContain('Property');
    expect(body).toContain('Selected');
    expect(body).toContain('Reference');
    expect(body).toContain('v2-compare-header-zone');
    expect(body).toContain('v2-compare-detail-scroll');
    expect(body).toContain('v2-compare-metadata-detail');
    expect(body.match(/<details[^>]*v2-compare-metadata-detail[^>]*>/)?.[0] ?? '').toContain('open');
    expect(body.indexOf('data-decision="stack"')).toBeLessThan(body.indexOf('Clear selection'));
    expect(body).not.toContain('Technical group ID');
  });

  it('shows actual bounded validation dimensions without implying full-resolution proof', () => {
    const { body } = render(V2DuplicateCompareViewer, {
      props: {
        open: true,
        groupTitle: 'Oversized comparison',
        groupKind: 'similar',
        groupSimilarity: 98.72,
        assetIds: ['asset-1', 'asset-2'],
        similarities: { 'asset-1': 98.72, 'asset-2': 100 },
        similarityEvidence: {
          'asset-1': {
            structuralPercent: 99,
            perceptualPercent: 98,
            colorPercent: 97,
            detailChangedPercent: 1.2,
            detailSource: 'preview',
            validatedWidth: 4096,
            validatedHeight: 2276,
            referenceValidatedWidth: 3840,
            referenceValidatedHeight: 2160,
          },
        },
        member: 0,
        reference: 1,
        onclose: () => {},
      },
    });

    expect(body).toContain('98.72%');
    expect(body).toContain('Bounded validation');
    expect(body).toContain('Validated at');
    expect(body).toContain('4096 × 2276');
    expect(body).toContain('3840 × 2160');
    expect(body).toContain('actual rendition dimensions used');
    expect(body).toContain('not full-resolution or destructive proof');
  });

  it('explains linked admission even when similarity to the reference was not calculated', () => {
    const linked = groupMember('asset-1', 'linked.png', null, admission({
      admissionSimilarityPercent: 82.34,
      bestGroupMatchSimilarityPercent: 83.07,
      linkDepth: 3,
    }));
    const bridge = groupMember('asset-2', 'bridge.heic', 82.34);
    const best = groupMember('asset-3', 'best-match.heic', 83.07);
    const { body } = render(V2DuplicateCompareViewer, {
      props: {
        open: true,
        groupTitle: 'Linked comparison',
        groupKind: 'similar',
        groupSimilarity: 82.22,
        groupMembers: [linked, bridge, best],
        validationMode: 'linked',
        similarityThreshold: 82,
        assetIds: ['asset-1', 'asset-2', 'asset-3'],
        similarities: { 'asset-1': null, 'asset-2': 82.34, 'asset-3': 83.07 },
        member: 0,
        reference: 1,
        onclose: () => {},
      },
    });

    expect(body).toContain('Group minimum');
    expect(body).toContain('Not calculated');
    expect(body).toContain('Included through bridge.heic');
    expect(body).toContain('82.34% admission similarity');
    expect(body).toContain('Why is this image in the group?');
    expect(body).toContain('Admitted through');
    expect(body).toContain('bridge.heic');
    expect(body).toContain('Best group match');
    expect(body).toContain('best-match.heic');
    expect(body).toContain('83.07%');
    expect(body).toContain('Link depth');
    expect(body).toContain('Technical linked data');
    expect(body).toContain('fingerprint-123');
    expect(body.indexOf('Metadata side by side')).toBeLessThan(body.indexOf('Why is this image in the group?'));
  });

  it('does not describe a direct reference admission as a linked membership', () => {
    const direct = groupMember('asset-1', 'direct.png', 96, admission({
      admittedByAssetId: 'asset-2',
      admissionSimilarityPercent: 96,
      bestGroupMatchAssetId: 'asset-3',
      bestGroupMatchSimilarityPercent: 99,
      linkDepth: 1,
    }));
    const reference = groupMember('asset-2', 'reference.heic', 100);
    const stronger = groupMember('asset-3', 'stronger.heic', 99);
    const { body } = render(V2DuplicateCompareViewer, {
      props: {
        open: true,
        groupTitle: 'Direct comparison',
        groupKind: 'similar',
        groupSimilarity: 96,
        groupMembers: [direct, reference, stronger],
        validationMode: 'linked',
        similarityThreshold: 95,
        assetIds: ['asset-1', 'asset-2', 'asset-3'],
        similarities: { 'asset-1': 96, 'asset-2': 100, 'asset-3': 99 },
        member: 0,
        reference: 1,
        onclose: () => {},
      },
    });

    expect(body).not.toContain('Included through');
    expect(body).not.toContain('Why is this image in the group?');
    expect(body).not.toContain('Technical linked data');
  });

  it('keeps inspection navigation enabled while write controls are disabled', () => {
    const { body } = render(V2DuplicateCompareViewer, {
      props: {
        open: true,
        groupTitle: 'Read-only comparison',
        groupKind: 'similar',
        assetIds: ['asset-1'],
        decisions: { 'asset-1': 'stack' },
        decisionOptions: ['keep', 'delete', 'stack'],
        disabled: true,
        onrevalidate: async () => {},
        onclose: () => {},
      },
    });

    expect(buttonWithText(body, '← Previous')).not.toContain('disabled');
    expect(buttonWithText(body, 'Next →')).not.toContain('disabled');
    expect(buttonWithText(body, 'Revalidate from reference')).toContain('disabled');
    expect(buttonWithText(body, 'Clear selection')).toContain('disabled');
    expect(buttonWithText(body, 'Keep')).toContain('disabled');
    expect(buttonWithText(body, 'Delete')).toContain('disabled');
    expect(buttonWithText(body, 'Stack')).toContain('disabled');
  });
});
