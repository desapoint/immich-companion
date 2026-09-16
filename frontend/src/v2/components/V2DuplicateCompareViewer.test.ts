import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import V2DuplicateCompareViewer from './V2DuplicateCompareViewer.svelte';

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
    expect(body).toContain('96.9%');
    expect(body).toContain('Color');
    expect(body).toContain('92.4%');
    expect(body).toContain('Detail changed area');
    expect(body).toContain('2.35%');
    expect(body).toContain('Detail evidence');
    expect(body).toContain('Original');
    expect(body).toContain('Use Difference mode');
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
});
