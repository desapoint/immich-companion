import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  analyzeDuplicateGroups,
  executeDuplicateResolution,
  loadDuplicateGroups,
  planDuplicateResolution,
  saveDuplicateReview,
} from './duplicateApi';

const options = {
  keeper_policy: 'prefer_upload' as const,
  external_library_ids: ['library-1'],
  verify_upload_streams: false,
};

describe('duplicate API', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('sends options to live review and candidate-only analysis', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ groups: [] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ task_id: 'task-1' }), { status: 202 }));
    vi.stubGlobal('fetch', fetchMock);

    await loadDuplicateGroups(options);
    await analyzeDuplicateGroups({ ...options, verify_upload_streams: true });

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/assets/duplicates/cross-source/search', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify(options),
    }));
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/assets/duplicates/cross-source/analyze', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ ...options, verify_upload_streams: true }),
    }));
  });

  it('creates a reviewed plan before executing it', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 'plan-1' }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ task_id: 'task-2' }), { status: 202 }));
    vi.stubGlobal('fetch', fetchMock);
    const request = {
      options,
      duplicate_ids: ['group-1'],
      all_eligible: false,
      keeper_overrides: { 'group-1': 'asset-1' },
      action_overrides: { 'group-1': 'resolve' as const },
    };

    await planDuplicateResolution(request);
    await executeDuplicateResolution('plan-1');

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/assets/duplicates/cross-source/plan', expect.objectContaining({
      body: JSON.stringify(request),
    }));
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/assets/duplicates/cross-source/execute', expect.objectContaining({
      body: JSON.stringify({ plan_id: 'plan-1' }),
    }));
  });

  it('persists a fingerprint-bound manual group decision', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      new Response(JSON.stringify({ duplicate_id: 'group-1' }), { status: 200 }),
    );
    vi.stubGlobal('fetch', fetchMock);
    const request = {
      duplicate_id: 'group-1',
      options,
      manual_action: 'keep_all' as const,
      manual_primary_asset_id: 'asset-1',
    };

    await saveDuplicateReview(request);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/assets/duplicates/cross-source/review',
      expect.objectContaining({ method: 'PUT', body: JSON.stringify(request) }),
    );
  });
});
