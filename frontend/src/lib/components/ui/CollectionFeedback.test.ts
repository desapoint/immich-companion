import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import CollectionFeedback from './CollectionFeedback.svelte';

describe('CollectionFeedback', () => {
  it('renders a blocking retry state before a collection has loaded', () => {
    const { body } = render(CollectionFeedback, {
      props: {
        hasLoaded: false,
        initialLoading: false,
        refreshing: false,
        error: 'Could not load albums.',
        empty: false,
        loadingLabel: 'Loading albums…',
        refreshingLabel: 'Refreshing albums…',
        emptyLabel: 'No albums found.',
        onretry: () => {},
      },
    });

    expect(body).toContain('Could not load albums.');
    expect(body).toContain('Retry');
    expect(body).toContain('role="alert"');
  });

  it('keeps refresh and empty states non-blocking after data has loaded', () => {
    const refreshing = render(CollectionFeedback, {
      props: {
        hasLoaded: true,
        initialLoading: false,
        refreshing: true,
        error: null,
        empty: false,
        loadingLabel: 'Loading…',
        refreshingLabel: 'Refreshing…',
        emptyLabel: 'Nothing here.',
        onretry: () => {},
      },
    }).body;
    const empty = render(CollectionFeedback, {
      props: {
        hasLoaded: true,
        initialLoading: false,
        refreshing: false,
        error: null,
        empty: true,
        loadingLabel: 'Loading…',
        refreshingLabel: 'Refreshing…',
        emptyLabel: 'Nothing here.',
        onretry: () => {},
      },
    }).body;

    expect(refreshing).toContain('Refreshing…');
    expect(empty).toContain('Nothing here.');
  });
});
