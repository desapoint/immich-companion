import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import type { DuplicateMember } from '../types/duplicates';
import GroupEvidencePills from './GroupEvidencePills.svelte';

const member: DuplicateMember = {
  id: '11111111-1111-4111-8111-111111111111',
  source_kind: 'external',
  library_id: '22222222-2222-4222-8222-222222222222',
  original_file_name: 'phone.heic',
  original_mime_type: 'image/heic',
  file_size_bytes: 4096,
  file_modified_at: '2026-08-30T12:00:00Z',
  uploaded_at: '2026-08-30T12:00:00Z',
  is_offline: false,
  is_stacked: false,
  immich_url: null,
  verification: 'matching',
  content_checksum: 'a'.repeat(40),
  evidence: {
    analysis_freshness: 'current',
    integrity_status: 'healthy',
    issue_codes: [],
    detected_format: 'heic',
    format_matches_declared: true,
    decode_supported: true,
    decode_valid: true,
    decoded_width: 4032,
    decoded_height: 3024,
    dimensions_match_immich: true,
  },
  similarity: {
    state: 'current',
    reference_asset_id: '33333333-3333-4333-8333-333333333333',
    similarity_percent: 98.25,
    structural_percent: 99,
    perceptual_percent: 97,
    color_percent: 95,
    normalized_luminance_mae: 0.01,
    normalized_luminance_rmse: 0.02,
    normalized_luminance_ssim: 0.99,
    aspect_ratio_difference: 0,
    dimensions_equal: true,
    exact_thumbnail_match: false,
    exact_pixel_match: false,
    model_version: 'appearance-v1',
    feature_version: 1,
    comparison_version: 1,
  },
  preservation: {
    pixel_normalization_version: 1,
    pixel_sha256: 'b'.repeat(64),
    decoded_width: 4032,
    decoded_height: 3024,
    bit_depth: 8,
    channel_count: 3,
    has_alpha: false,
    color_space: 'RGB',
    orientation: 1,
    icc_profile_present: true,
    has_exif: true,
    has_capture_time: true,
    has_camera_info: true,
    has_gps: false,
    has_orientation_metadata: true,
    metadata_richness: 5,
  },
};

describe('GroupEvidencePills', () => {
  it('renders cached safety, match, format, and decode evidence', () => {
    const { body } = render(GroupEvidencePills, {
      props: { member, analysisPending: false },
    });

    expect(body).toContain('Healthy');
    expect(body).toContain('Byte match');
    expect(body).toContain('HEIC');
    expect(body).toContain('Decoded');
    expect(body).toContain('98.3% vs reference');
    expect(body).toContain('4032×3024');
    expect(body).toContain('ICC');
  });

  it('surfaces normalized pixel equality separately from visual similarity', () => {
    const { body } = render(GroupEvidencePills, {
      props: {
        member: {
          ...member,
          similarity: { ...member.similarity!, exact_pixel_match: true },
        },
        analysisPending: false,
      },
    });

    expect(body).toContain('Pixel match');
  });

  it('distinguishes pending stale evidence from a corruption result', () => {
    const { body } = render(GroupEvidencePills, {
      props: {
        member: {
          ...member,
          evidence: { ...member.evidence, analysis_freshness: 'stale' },
        },
        analysisPending: true,
      },
    });

    expect(body).toContain('Analyzing');
    expect(body).not.toContain('Malformed');
  });
});
