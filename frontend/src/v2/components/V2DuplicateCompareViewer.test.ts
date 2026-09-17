import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import V2DuplicateCompareViewer from './V2DuplicateCompareViewer.svelte';

function buttonWithText(body: string, text: string): string {
  return [...body.matchAll(/<button\b[^>]*>[\s\S]*?<\/button>/g)]
    .map((match) => match[0])
    .find((button) => button.includes(text)) ?? '';
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
