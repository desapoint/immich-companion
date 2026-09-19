import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import V2AssetRelationRemoveModal from './V2AssetRelationRemoveModal.svelte';

describe('V2AssetRelationRemoveModal', () => {
  it('shows mixed-selection applicability and requires an explicit choice', () => {
    const { body } = render(V2AssetRelationRemoveModal, {
      props: {
        kind: 'tags',
        selectedCount: 3,
        values: [],
        options: [{ value: 'tag-1', label: 'Vacation', subtitle: 'Linked to 2 selected assets', selectedAssetCount: 2 }],
        onvalueschange: () => {},
        onclose: () => {},
        onapply: () => {},
      },
    });

    expect(body).toContain('Remove tags');
    expect(body).toContain('Assets without a chosen relationship are skipped.');
    expect(body).toContain('Vacation');
    expect(body).toContain('Select all');
    expect(body).toContain('disabled');
  });

  it('enables Select all when linked options remain unselected', () => {
    const { body } = render(V2AssetRelationRemoveModal, {
      props: {
        kind: 'album',
        selectedCount: 2,
        values: ['album-1'],
        options: [
          { value: 'album-1', label: 'First', subtitle: '', selectedAssetCount: 1 },
          { value: 'album-2', label: 'Second', subtitle: '', selectedAssetCount: 1 },
        ],
        onvalueschange: () => {},
        onclose: () => {},
        onapply: () => {},
      },
    });

    expect(body).toContain('Select all');
    expect(body).toContain('Second');
  });
});
