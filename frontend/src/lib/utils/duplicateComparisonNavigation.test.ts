import { describe, expect, it } from 'vitest';

import { comparisonTargetId, stepComparisonTargetId, viewerSelectionTargetId } from './duplicateComparisonNavigation';

const ids = ['reference', 'second', 'third'];

describe('duplicate comparison navigation', () => {
  it('shows the next distinct image when the reference is selected', () => {
    expect(comparisonTargetId(ids, 'reference', 'reference')).toBe('second');
    expect(comparisonTargetId(ids, 'second', 'second')).toBe('third');
    expect(comparisonTargetId(ids, 'reference', 'third')).toBe('third');
  });

  it('keeps list opening distinct while allowing the viewer to select the reference', () => {
    expect(comparisonTargetId(ids, 'reference', 'reference')).toBe('second');
    expect(viewerSelectionTargetId(ids, 'reference')).toBe('reference');
    expect(viewerSelectionTargetId(ids, 'third')).toBe('third');
  });

  it('cycles through candidates without comparing the reference with itself', () => {
    expect(stepComparisonTargetId(ids, 'reference', 'third', 'next')).toBe('second');
    expect(stepComparisonTargetId(ids, 'reference', 'second', 'previous')).toBe('third');
    expect(stepComparisonTargetId(ids, 'reference', 'reference', 'next')).toBe('second');
  });

  it('keeps a single-image group usable', () => {
    expect(comparisonTargetId(['only'], 'only', 'only')).toBe('only');
    expect(stepComparisonTargetId(['only'], 'only', 'only', 'next')).toBe('only');
  });

  it('keeps the only other image visible in a two-image group', () => {
    expect(comparisonTargetId(['reference', 'other'], 'reference', 'reference')).toBe('other');
    expect(stepComparisonTargetId(['reference', 'other'], 'reference', 'other', 'next')).toBe('other');
  });
});
