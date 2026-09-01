import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import type { AssetCardIndicatorConfig, AssetSummary } from '../types/assets';
import AssetGrid from './AssetGrid.svelte';

const asset: AssetSummary = {
  id: 'asset-1',
  type: 'IMAGE',
  original_file_name: 'layout-check.jpg',
  original_mime_type: 'image/jpeg',
  width: 1920,
  height: 1080,
  duration: null,
  taken_at: '2026-08-28T12:00:00Z',
  file_modified_at: '2026-08-28T12:00:00Z',
  is_favorite: false,
  is_archived: false,
  is_trashed: false,
  is_offline: false,
  is_edited: false,
  visibility: 'timeline',
  has_metadata: true,
  live_photo_video_id: null,
  file_size_bytes: 1234,
  people_count: 0,
  tag_count: 0,
  stack_count: 0,
  albums: [],
  tags: [],
  stack: null,
  source: { kind: 'upload', library_id: null, original_path: null },
  immich_url: null,
};

const indicatorConfig: AssetCardIndicatorConfig = {
  albums: true,
  tags: true,
  stack: true,
  external: true,
  immich: true,
  inlineTags: 'hidden',
};

function renderGrid(layout: 'normal' | 'condensed'): string {
  return render(AssetGrid, {
    props: {
      assets: [asset],
      selectedIds: new Set<string>(),
      selectionActive: false,
      indicatorConfig,
      matchingTagIds: new Set<string>(),
      layout,
      onopen: () => undefined,
      onselect: () => undefined,
      ondragstart: () => undefined,
      ondragenter: () => undefined,
    },
  }).body;
}

describe('AssetGrid', () => {
  it('renders structurally distinct normal and condensed asset cards', () => {
    const normal = renderGrid('normal');
    const condensed = renderGrid('condensed');

    expect(normal).toContain('class="asset-grid');
    expect(normal).not.toContain('asset-grid condensed');
    expect(normal).toContain('data-layout="normal"');
    expect(normal).toContain('class="card-content');
    expect(normal).toContain('class="card-decision');

    expect(condensed).toMatch(/class="asset-grid[^"]* condensed/);
    expect(condensed).toContain('data-layout="condensed"');
    expect(condensed).toMatch(/class="asset-card[^"]* condensed/);
    expect(condensed).toContain('class="condensed-selection');
    expect(condensed).not.toContain('class="card-content');
    expect(condensed).not.toContain('class="card-decision');
  });

  it('overlays the shared stack-main control without changing card structure', () => {
    const body = render(AssetGrid, {
      props: {
        assets: [asset],
        selectedIds: new Set(['asset-1']),
        selectionActive: true,
        stackPrimaryId: 'asset-1',
        indicatorConfig,
        matchingTagIds: new Set<string>(),
        layout: 'condensed',
        onopen: () => undefined,
        onselect: () => undefined,
        onsetstackprimary: () => undefined,
        ondragstart: () => undefined,
        ondragenter: () => undefined,
      },
    }).body;

    expect(body).toContain('class="stack-primary-selector');
    expect(body).toContain('aria-label="Stack main"');
    expect(body).toContain('aria-pressed="true"');
  });
});
