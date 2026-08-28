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
        onfullsync: () => undefined,
      },
    });

    expect(body).toContain('66 matching assets');
    expect(body).not.toContain('Inline card tags');
  });

  it('labels media progress with the authoritative asset total', () => {
    const { body } = render(AssetResultStatus, {
      props: {
        total: 64,
        shown: 24,
        selected: 0,
        syncing: true,
        syncMessage: null,
        syncProgress: {
          phase: 'assets',
          completed: 37,
          total: 64,
          percent: 57.8,
          detail: 'Media 37/64',
        },
        onsync: () => undefined,
        onfullsync: () => undefined,
      },
    });

    expect(body).toContain('Step 2 of 5 · Media');
    expect(body).toContain('37 of 64 media items processed');
  });

  it('does not present finalization as one media item', () => {
    const { body } = render(AssetResultStatus, {
      props: {
        total: 64,
        shown: 24,
        selected: 0,
        syncing: true,
        syncMessage: null,
        syncProgress: {
          phase: 'finalizing',
          completed: 0,
          total: 1,
          percent: 0,
          detail: 'Validating synchronized state',
        },
        onsync: () => undefined,
        onfullsync: () => undefined,
      },
    });

    expect(body).toContain('Step 5 of 5 · Finalizing');
    expect(body).not.toContain('of 1');
    expect(body).toContain('Validating synchronized state');
  });
});
