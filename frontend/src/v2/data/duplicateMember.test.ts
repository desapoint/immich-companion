import { describe, expect, it } from 'vitest';
import type { AssetRecord } from './contracts';
import {
  FULL_RESOLUTION_VALIDATION_PIXEL_LIMIT,
  assetFolder,
  comparisonMemberData,
  duplicateListMemberMeta,
  formatImageDimensions,
  formatSimilarityPercent,
  linkedIntermediateCount,
  similarityValidatedDimensions,
  similarityValidationEvidenceLabel,
  similarityValidationEvidenceTier,
  usesBoundedValidation,
} from './duplicateMember';

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

  it('shows exactly two similarity percentage decimals', () => {
    expect(formatSimilarityPercent(98.256)).toBe('98.26%');
    expect(formatSimilarityPercent(98.2)).toBe('98.20%');
    expect(formatSimilarityPercent(99.98)).toBe('99.98%');
    expect(formatSimilarityPercent(100)).toBe('100.00%');
    expect(comparisonMemberData(asset(), 98.256).similarity).toBe('98.26%');
    expect(formatSimilarityPercent(null)).toBe('Not calculated');
  });

  it('counts only images between the reference and a linked member', () => {
    expect(linkedIntermediateCount(0)).toBe(0);
    expect(linkedIntermediateCount(1)).toBe(1);
    expect(linkedIntermediateCount(2)).toBe(2);
    expect(linkedIntermediateCount(3)).toBe(3);
  });

  it('formats duplicate list member metadata with viewer file sizes', () => {
    expect(duplicateListMemberMeta(asset(), 99.98)).toBe('Immich upload · 1.00 MB · 99.98% similarity');
    expect(duplicateListMemberMeta(asset(), null)).toBe('Immich upload · 1.00 MB');
  });

  it('does not infer bounded validation from source dimensions', () => {
    const oversized = asset({ width: 16320, height: 12240, file_size_bytes: 50_000_000 });
    expect(FULL_RESOLUTION_VALIDATION_PIXEL_LIMIT).toBe(64_000_000);
    expect(usesBoundedValidation(oversized)).toBe(false);
    expect(duplicateListMemberMeta(oversized, 94.25)).toBe('Immich upload · 47.7 MB · 94.25% similarity');
  });

  it('labels validation from persisted detail evidence rather than dimensions', () => {
    expect(usesBoundedValidation({ detailSource: 'preview' })).toBe(true);
    expect(usesBoundedValidation({ detailSource: 'original' })).toBe(false);
    expect(similarityValidationEvidenceTier(94.25, { detailSource: 'preview' })).toBe('bounded');
    expect(similarityValidationEvidenceLabel(94.25, { detailSource: 'preview' })).toBe('Bounded validation');
    expect(similarityValidationEvidenceLabel(94.25, { detailSource: 'original' })).toBe('Full-resolution validation');
    expect(similarityValidationEvidenceLabel(94.25, { detailSource: 'transcoded' })).toBe('Full-resolution validation');
    expect(similarityValidationEvidenceLabel(94.25, { detailSource: null })).toBe('Search-only appearance');
    expect(similarityValidationEvidenceLabel(94.25, null)).toBe('Search-only appearance');
    expect(similarityValidationEvidenceLabel(null, { detailSource: 'preview' })).toBeNull();
  });

  it('formats actual validation dimensions independently for member and reference', () => {
    const evidence = {
      validatedWidth: 4096,
      validatedHeight: 2276,
      referenceValidatedWidth: 3840,
      referenceValidatedHeight: 2160,
    };
    expect(similarityValidatedDimensions(evidence)).toBe('4096 × 2276');
    expect(similarityValidatedDimensions(evidence, 'reference')).toBe('3840 × 2160');
    expect(similarityValidatedDimensions({ ...evidence, validatedHeight: null })).toBeNull();
    expect(formatImageDimensions(18_000, 10_000)).toBe('18000 × 10000');
    expect(formatImageDimensions(null, 10_000)).toBeNull();
  });

  it('keeps normal-size and unknown-size assets from being treated as evidence of bounded validation', () => {
    expect(usesBoundedValidation(asset({ width: 8000, height: 8000 }))).toBe(false);
    expect(usesBoundedValidation(asset({ width: 8001, height: 8000 }))).toBe(false);
    expect(usesBoundedValidation(asset({ width: null, height: 12000 }))).toBe(false);
    expect(usesBoundedValidation(asset({ width: 16000, height: null }))).toBe(false);
  });

  it('uses KB for files smaller than one MB', () => {
    const data = comparisonMemberData(asset({ file_size_bytes: 128 * 1024 }), 98.25);
    expect(data.size).toBe('128.0 KB');
    expect(data.sizeBytes).toBe(128 * 1024);
  });

  it('exposes the folder from upload asset details', () => {
    const data = comparisonMemberData(
      asset({ original_path: '/data/upload/library/user/2026/photo.heic' }),
      98.25,
    );

    expect(data.folder).toBe('/data/upload/library/user/2026');
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
