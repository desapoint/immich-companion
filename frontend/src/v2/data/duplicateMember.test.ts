import { describe, expect, it } from 'vitest';
import type { AssetRecord } from './contracts';
import { assetFolder, comparisonMemberData } from './duplicateMember';

function asset(patch: Partial<AssetRecord> = {}): AssetRecord {
  return {
    id: 'asset-1', owner_id: null, library_id: null, asset_type: 'IMAGE',
    original_file_name: 'photo.heic', original_path: null, original_mime_type: 'image/heic', checksum: null,
    file_size_bytes: 1_048_576, width: 1200, height: 800, duration: null,
    file_created_at: '2026-01-01T00:00:00Z', file_modified_at: '2026-01-01T00:00:00Z',
    local_date_time: null, immich_created_at: '2026-01-02T00:00:00Z', immich_updated_at: null,
    is_favorite: false, is_archived: false, is_offline: false, is_edited: false, has_metadata: true,
    visibility: null, live_photo_video_id: null, tags: [], albums: [], stack: null, synced_at: '2026-01-01T00:00:00Z',
    ...patch,
  };
}

describe('duplicate comparison member data', () => {
  it('identifies Immich uploads', () => {
    expect(comparisonMemberData(asset(), 98.25).source).toBe('Immich upload');
    expect(comparisonMemberData(asset(), null).similarity).toBe('Not calculated');
  });

  it('identifies an external library by name and exposes its folder', () => {
    const data = comparisonMemberData(
      asset({ library_id: 'library-1', original_path: '/photos/trips/photo.heic' }),
      98.25,
      new Map([['library-1', 'Archive']]),
    );
    expect(data.source).toBe('External · Archive');
    expect(data.folder).toBe('/photos/trips');
  });

  it('normalizes Windows paths for folder comparison', () => {
    expect(assetFolder('D:\\Photos\\Trips\\photo.heic')).toBe('D:/Photos/Trips');
  });
});
