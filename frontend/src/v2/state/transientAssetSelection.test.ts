import { describe, expect, it } from 'vitest';
import { selectAllMatchingAssets, selectVisibleAssets, toggleAssetSelected } from '../components/assetSelection';
import { TransientAssetSelectionController } from './transientAssetSelection.svelte';

function storageFixture(initial?: string) {
  const values = new Map<string, string>();
  if (initial !== undefined) values.set('restore-test', initial);
  return {
    values,
    storage: {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => { values.set(key, value); },
      removeItem: (key: string) => { values.delete(key); },
    },
  };
}

describe('transient Restore asset selection', () => {
  it('restores explicit IDs and anchor from session storage', () => {
    const { storage } = storageFixture();
    const first = new TransientAssetSelectionController('restore-test', storage);
    first.replace(selectVisibleAssets(['trash-a', 'trash-b']));

    const restored = new TransientAssetSelectionController('restore-test', storage).snapshot();
    expect([...restored.selectedIds]).toEqual(['trash-a', 'trash-b']);
    expect(restored.anchor).toBe('trash-a');
    expect(restored.allMatchingSelected).toBe(false);
  });

  it('persists an all-matching expression and exclusions without asset records', () => {
    const { values, storage } = storageFixture();
    const controller = new TransientAssetSelectionController('restore-test', storage);
    controller.replace(toggleAssetSelected(selectAllMatchingAssets('trash-a'), 'trash-b'));

    expect(JSON.parse(values.get('restore-test') ?? '{}')).toEqual({
      selectedIds: [],
      excludedIds: ['trash-b'],
      allMatchingSelected: true,
      anchor: 'trash-b',
    });
  });

  it('ignores malformed persisted state and removes storage when cleared', () => {
    const { values, storage } = storageFixture('{"selectedIds":"not-an-array"}');
    const controller = new TransientAssetSelectionController('restore-test', storage);
    expect(controller.snapshot().selectedIds.size).toBe(0);

    controller.replace(selectVisibleAssets(['trash-a']));
    controller.clear();
    expect(values.has('restore-test')).toBe(false);
  });
});
