import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import AssetResultStatus from './AssetResultStatus.svelte';

describe('AssetResultStatus', () => {
  it('keeps card tag configuration out of the Asset Finder controls', () => {
    const { body } = render(AssetResultStatus, {
      props: {
        total: 66,
        shown: 24,
        selected: 0,
        syncing: false,
        syncMessage: null,
        onsync: () => undefined,
      },
    });

    expect(body).toContain('66 matching assets');
    expect(body).not.toContain('Inline card tags');
  });
});
