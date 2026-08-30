import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import type { AssetIntegrityReport, AssetTaskStatus } from '../types/assets';
import AssetIntegrityDialog from './AssetIntegrityDialog.svelte';

const report: AssetIntegrityReport = {
  asset_id: '11111111-1111-4111-8111-111111111111',
  analyzer_version: 3,
  byte_size: 4096,
  sha1_hex: 'a'.repeat(40),
  sha256_hex: 'b'.repeat(64),
  detected_format: 'jpeg',
  format_matches_declared: true,
  classification: 'warning',
  structurally_valid: true,
  container_valid: true,
  decode_supported: false,
  decode_valid: null,
  decoded_width: null,
  decoded_height: null,
  dimensions_match_immich: null,
  jpeg_eoi_offset: 4088,
  trailing_byte_count: 8,
  immich_checksum_match: true,
  issues: [],
  analyzed_at: '2026-08-28T12:00:00Z',
};

function task(): AssetTaskStatus {
  return {
    id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    task_type: 'asset_integrity',
    status: 'running',
    payload: {},
    checkpoint: {},
    counters: { bytes_processed: 1024 },
    progress: { phase: 'integrity', completed: 1024, total: 4096, percent: 25 },
    result: null,
    error: null,
    attempt: 1,
    next_attempt_at: null,
    created_at: '2026-08-28T12:00:00Z',
    started_at: '2026-08-28T12:00:00Z',
    completed_at: null,
  };
}

describe('AssetIntegrityDialog', () => {
  it('renders determinate loading without exposing replacement actions', () => {
    const { body } = render(AssetIntegrityDialog, {
      props: {
        filename: 'fixture.jpg',
        report: null,
        task: task(),
        error: null,
        onreanalyze: () => undefined,
        onclose: () => undefined,
      },
    });

    expect(body).toContain('Analyzing original file…');
    expect(body).toContain('aria-valuenow="25"');
    expect(body).toContain('1.0 KB processed');
    expect(body).not.toContain('Re-analyze');
  });

  it('renders the persisted report and re-analysis action', () => {
    const { body } = render(AssetIntegrityDialog, {
      props: {
        filename: 'fixture.jpg',
        report,
        task: null,
        error: null,
        onreanalyze: () => undefined,
        onclose: () => undefined,
      },
    });

    expect(body).toContain('Integrity warning');
    expect(body).toContain('4.0 KB');
    expect(body).toContain('Trailing bytes');
    expect(body).toContain('Re-analyze');
    expect(body).toContain(report.sha256_hex);
  });
});
