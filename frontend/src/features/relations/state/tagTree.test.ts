import { describe, expect, it } from 'vitest';
import { flattenTagTree } from './tagTree';
import type { ManagedRelation } from '../types/relations';

const tree: ManagedRelation[] = [
  { id: 'root', name: 'Root', asset_count: 0, children: [
    { id: 'child', name: 'Child', parent_id: 'root', asset_count: 0, children: [
      { id: 'leaf', name: 'Leaf', parent_id: 'child', asset_count: 0 },
    ] },
  ] },
];

describe('tag tree visibility', () => {
  it('expands loaded branches by default', () => {
    expect(flattenTagTree(tree, new Set()).map(({ item }) => item.id)).toEqual([
      'root', 'child', 'leaf',
    ]);
  });

  it('preserves explicit collapsed branches', () => {
    expect(flattenTagTree(tree, new Set(['root'])).map(({ item }) => item.id)).toEqual(['root']);
    expect(flattenTagTree(tree, new Set(['child'])).map(({ item }) => item.id)).toEqual([
      'root', 'child',
    ]);
  });

  it('renders all matching hierarchy context when search forces expansion', () => {
    expect(flattenTagTree(tree, new Set(['root', 'child']), true).map(({ item, depth }) => [item.id, depth])).toEqual([
      ['root', 0], ['child', 1], ['leaf', 2],
    ]);
  });
});
