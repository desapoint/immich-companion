import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import type { AssetSummary } from '../types/assets';
import AssetInfoRelationships from './AssetInfoRelationships.svelte';

function relationRichAsset(): AssetSummary {
  return {
    id: 'asset-1',
    type: 'IMAGE',
    original_file_name: 'base-scene.png',
    original_mime_type: 'image/png',
    width: 1920,
    height: 1080,
    duration: null,
    taken_at: '2026-08-24T12:00:00Z',
    file_modified_at: '2026-08-24T12:00:00Z',
    is_favorite: true,
    is_archived: false,
    is_trashed: false,
    is_offline: false,
    is_edited: false,
    visibility: 'timeline',
    has_metadata: true,
    live_photo_video_id: null,
    file_size_bytes: 1234,
    people_count: 2,
    tag_count: 2,
    stack_count: 4,
    albums: [
      { id: 'album-1', name: 'Reference scenes' },
      { id: 'album-2', name: 'Review queue' },
    ],
    tags: [
      { id: 'tag-1', name: 'Review', color: '#2a9d8f' },
      { id: 'tag-2', name: 'Similar candidate', color: '#e9c46a' },
    ],
    stack: {
      id: 'stack-1',
      primary_asset_id: 'asset-1',
      asset_count: 4,
      assets: [],
    },
    source: {
      kind: 'external',
      library_id: 'library-1',
      original_path: '/photos/base-scene.png',
    },
    immich_url: 'http://localhost:22830/photos/asset-1',
  };
}

describe('asset info relationships', () => {
  it('renders complete relation, source, people, and state information', () => {
    const { body } = render(AssetInfoRelationships, {
      props: { asset: relationRichAsset() },
    });

    expect(body).toContain('Reference scenes');
    expect(body).toContain('Review queue');
    expect(body).toContain('Review');
    expect(body).toContain('Similar candidate');
    expect(body).toContain('4 images');
    expect(body).toContain('Primary asset');
    expect(body).toContain('External library');
    expect(body).toContain('library-1');
    expect(body).toContain('/photos/base-scene.png');
    expect(body).toContain('>2</dd>');
    expect(body).toContain('Favorite');
  });
});
