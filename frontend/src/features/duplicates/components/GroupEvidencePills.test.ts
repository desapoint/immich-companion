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
