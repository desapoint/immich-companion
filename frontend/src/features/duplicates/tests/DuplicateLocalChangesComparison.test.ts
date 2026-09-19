import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';
import type { LocalChangeDiagnostics } from '../utils/localChangeDiagnostics';
import DuplicateLocalChangesComparison from '../components/DuplicateLocalChangesComparison.svelte';

function diagnostics32(): LocalChangeDiagnostics {
  return {
    available: true,
    selectedAssetId: 'selected',
    referenceAssetId: 'reference',
    changedPercent: 12.5,
    localizedChangedPercent: 12.5,
    coherentChangedPercent: 10,
    largestChangedRegionPercent: 4,
    substantialRegionCount: 2,
    rows: 32,
    columns: 32,
    cells: Array.from({ length: 32 }, (_, row) => (
      Array.from({ length: 32 }, (_, column) => (row + column) % 101)
    )),
    source: 'preview',
  };
}

describe('DuplicateLocalChangesComparison', () => {
  it('renders the fixed 32x32 diagnostics as persistent DOM cells instead of a canvas', () => {
    const { body } = render(DuplicateLocalChangesComparison, {
      props: {
        selectedSrc: '/selected',
        referenceSrc: '/reference',
        selectedLabel: 'Selected',
        referenceLabel: 'Reference',
        transform: 'translate(0px, 0px) scale(1)',
        diagnostics: diagnostics32(),
      },
    });

    expect(body).not.toContain('<canvas');
    expect(body).toContain('v2-local-change-grid');
    expect(body.match(/v2-local-change-cell/g)).toHaveLength(1024);
    expect(body.match(/v2-local-change-label/g)).toHaveLength(1024);
  });

  it('keeps percentage labels mounted even before viewport geometry makes them visible', () => {
    const { body } = render(DuplicateLocalChangesComparison, {
      props: {
        selectedSrc: '/selected',
        referenceSrc: '/reference',
        selectedLabel: 'Selected',
        referenceLabel: 'Reference',
        transform: 'translate(0px, 0px) scale(1)',
        diagnostics: diagnostics32(),
        minimumDifference: 50,
      },
    });

    expect(body).toContain('0%');
    expect(body).toContain('50%');
    expect(body).toContain('difference-visible');
  });
});
