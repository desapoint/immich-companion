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
        groupSimilarity: 96.4,
        similarityEngine: 'appearance',
        similarityModelVersion: 'appearance-v1',
        similarityFeatureVersion: 2,
        similarityComparisonVersion: 4,
        assetIds: ['asset-1'],
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
    expect(body).toContain('96.4%');
    expect(body).toContain('Similarity to reference');
    expect(body).toContain('appearance · appearance-v1 · features v2 · comparison v4');
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
