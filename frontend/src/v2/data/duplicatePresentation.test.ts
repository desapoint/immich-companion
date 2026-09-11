import { describe, expect, it } from 'vitest';

import type { DuplicateGroupRecord } from './contracts';
import { duplicateAssetSourceLabel, duplicateGroupTitle, duplicateKindLabel } from './duplicatePresentation';

function group(names: string[], kind = 'similar'): DuplicateGroupRecord {
  return {
    id: 'technical-group-id',
    state: 'Needs review',
    kind,
    reason: null,
    referenceAssetId: null,
    groupSimilarity: null,
    similarityEngine: null,
    similarityModelVersion: null,
    similarityFeatureVersion: null,
    similarityComparisonVersion: null,
    memberFingerprint: 'fingerprint',
    selected: false,
    savedDecisions: {},
    stackPrimaryAssetId: null,
    stackResolution: 'move_selected',
    members: names.map((name, index) => ({
      similarity: 100 - index,
      asset: { id: `asset-${index}`, original_file_name: name } as DuplicateGroupRecord['members'][number]['asset'],
    })),
  };
}

describe('duplicate presentation', () => {
  it('uses the representative filename and remaining member count instead of the technical id', () => {
    expect(duplicateGroupTitle(group(['IMG_1234.JPG', 'copy.jpg', 'edit.jpg']))).toBe('IMG_1234.JPG and 2 more');
  });

  it('falls back safely when the group has no usable filename', () => {
    expect(duplicateGroupTitle(group([]))).toBe('Duplicate group');
    expect(duplicateGroupTitle(group(['  ']))).toBe('Duplicate group');
  });

  it('turns backend classifications into concise match labels', () => {
    expect(duplicateKindLabel('exact_file')).toBe('Byte-perfect match');
    expect(duplicateKindLabel('similar')).toBe('Appearance match');
    expect(duplicateKindLabel('custom grouping')).toBe('Custom grouping');
  });

  it('uses consistent, unambiguous asset source labels', () => {
    expect(duplicateAssetSourceLabel(null)).toBe('Immich upload');
    expect(duplicateAssetSourceLabel('library-1')).toBe('External library');
    expect(duplicateAssetSourceLabel('library-1', 'Family archive')).toBe('External · Family archive');
  });
});
