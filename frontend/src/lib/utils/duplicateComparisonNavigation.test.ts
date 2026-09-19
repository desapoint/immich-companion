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

  it('cycles through every member, including the reference', () => {
    expect(stepComparisonTargetId(ids, 'reference', 'third', 'next')).toBe('reference');
    expect(stepComparisonTargetId(ids, 'reference', 'second', 'previous')).toBe('reference');
    expect(stepComparisonTargetId(ids, 'reference', 'reference', 'next')).toBe('second');
    expect(stepComparisonTargetId(ids, 'reference', 'reference', 'previous')).toBe('third');
  });

  it('keeps a single-image group usable', () => {
    expect(comparisonTargetId(['only'], 'only', 'only')).toBe('only');
    expect(stepComparisonTargetId(['only'], 'only', 'only', 'next')).toBe('only');
  });

  it('cycles between the reference and the other image in a two-image group', () => {
    expect(comparisonTargetId(['reference', 'other'], 'reference', 'reference')).toBe('other');
    expect(stepComparisonTargetId(['reference', 'other'], 'reference', 'other', 'next')).toBe('reference');
    expect(stepComparisonTargetId(['reference', 'other'], 'reference', 'reference', 'next')).toBe('other');
  });
});
