import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import AssetSelectionActions from './AssetSelectionActions.svelte';

describe('AssetSelectionActions', () => {
  it('keeps selection controls visible while reserving hidden actions when deselected', () => {
    const { body } = render(AssetSelectionActions, {
      props: {
        selectedCount: 0,
        matchingTotal: 66,
        currentPageCount: 24,
        allMatching: false,
        summary: null,
        albums: [],
        tags: [],
        plan: null,
        onselectpage: () => undefined,
        onselectall: () => undefined,
        oninvertpage: () => undefined,
        onclear: () => undefined,
        onplan: () => undefined,
        onrelationconfirm: () => undefined,
        onconfirm: () => undefined,
        oncancel: () => undefined,
      },
    });

    expect(body).toContain('0 selected');
    expect(body).toContain('aria-label="Selection controls"');
    expect(body).toContain('aria-label="Select current page"');
    expect(body).toMatch(/class="action-controls[^"]* hidden/);
    expect(body).toContain('inert');
    expect(body).toContain('aria-hidden="true"');
  });

  it('keeps favorite and trash primary while secondary actions use overflow', () => {
    const { body } = render(AssetSelectionActions, {
      props: {
        selectedCount: 3,
        matchingTotal: 66,
        currentPageCount: 24,
        allMatching: false,
        summary: {
          total: 3,
          archived: 1,
          unarchived: 2,
          favorite: 1,
          not_favorite: 2,
          trashed: 1,
          not_trashed: 2,
          archive_action: 'archive',
          favorite_action: 'favorite',
          can_trash: true,
          can_restore: true,
        },
        albums: [],
        tags: [],
        plan: null,
        onselectpage: () => undefined,
        onselectall: () => undefined,
        oninvertpage: () => undefined,
        onclear: () => undefined,
        onplan: () => undefined,
        onrelationconfirm: () => undefined,
        onconfirm: () => undefined,
        oncancel: () => undefined,
      },
    });

    expect(body).toContain('aria-label="Favorite selected assets"');
    expect(body).toContain('aria-label="Delete selected assets (move to trash)"');
    expect(body).toContain('aria-label="More actions for selected assets"');
    expect(body).toContain('aria-label="Add selected assets to album"');
    expect(body).toContain('Archive selected assets');
    expect(body).toContain('Add tags to selected assets');
    expect(body).toContain('Remove tags from selected assets');
    expect(body).toContain('Remove selected assets from albums');
    expect(body).toContain('Restore applicable selected assets');
    expect(body).not.toContain('class="group-label"');
  });

  it('switches to the inverse actions only when every selected asset is set', () => {
    const { body } = render(AssetSelectionActions, {
      props: {
        selectedCount: 2,
        matchingTotal: 2,
        currentPageCount: 2,
        allMatching: false,
        summary: {
          total: 2,
          archived: 2,
          unarchived: 0,
          favorite: 2,
          not_favorite: 0,
          trashed: 0,
          not_trashed: 2,
          archive_action: 'unarchive',
          favorite_action: 'unfavorite',
          can_trash: true,
          can_restore: false,
        },
        albums: [],
        tags: [],
        plan: null,
        onselectpage: () => undefined,
        onselectall: () => undefined,
        oninvertpage: () => undefined,
        onclear: () => undefined,
        onplan: () => undefined,
        onrelationconfirm: () => undefined,
        onconfirm: () => undefined,
        oncancel: () => undefined,
      },
    });

    expect(body).toContain('aria-label="Unfavorite selected assets"');
    expect(body).not.toContain('aria-label="Favorite selected assets"');
    expect(body).toContain('aria-label="Delete selected assets (move to trash)"');
    expect(body).toContain('Unarchive selected assets');
  });
});
