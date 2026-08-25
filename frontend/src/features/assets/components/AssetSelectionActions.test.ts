import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import AssetSelectionActions from './AssetSelectionActions.svelte';

describe('AssetSelectionActions', () => {
  it('shows one toggle direction and independently applicable trash actions', () => {
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
        onconfirm: () => undefined,
        oncancel: () => undefined,
      },
    });

    expect(body).toContain('aria-label="Archive selected assets"');
    expect(body).not.toContain('aria-label="Unarchive selected assets"');
    expect(body).toContain('aria-label="Favorite selected assets"');
    expect(body).not.toContain('aria-label="Unfavorite selected assets"');
    expect(body).toContain('aria-label="Trash applicable selected assets"');
    expect(body).toContain('aria-label="Restore applicable selected assets"');
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
        onconfirm: () => undefined,
        oncancel: () => undefined,
      },
    });

    expect(body).toContain('aria-label="Unarchive selected assets"');
    expect(body).not.toContain('aria-label="Archive selected assets"');
    expect(body).toContain('aria-label="Unfavorite selected assets"');
    expect(body).not.toContain('aria-label="Favorite selected assets"');
    expect(body).toContain('aria-label="Trash applicable selected assets"');
    expect(body).not.toContain('aria-label="Restore applicable selected assets"');
  });
});
