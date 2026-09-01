import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  analyzeDuplicateGroups,
  cancelDuplicateTask,
  executeDuplicateResolution,
  loadDuplicateGroups,
  loadDuplicateTask,
  loadLatestSimilarityScan,
  loadDuplicateWorkspace,
  loadSimilarityScanTasks,
  planDuplicateResolution,
  saveDuplicateReview,
  saveDuplicateGroupDraft,
  saveDuplicateWorkspaceSelection,
  startDuplicateSimilarityScan,
  switchDuplicateSimilarityReference,
} from './duplicateApi';

const options = {
  keeper_policy: 'prefer_upload' as const,
  external_library_ids: ['library-1'],
  verify_upload_streams: false,
  automatic_handling_enabled: true,
  preselect_safe_groups: true,
  exact_file_action: 'resolve' as const,
  analyze_automatically: true,
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

  it('does not auto-requeue duplicate analysis on its completion refresh', async () => {
    const completedTask = {
      id: 'analysis-1',
      task_type: 'cross_source_duplicates',
      status: 'completed',
      progress: {},
      error: null,
      result: null,
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(completedTask), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ groups: [] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ groups: [] }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    await loadDuplicateTask('analysis-1');
    await loadDuplicateGroups(options);
    await loadDuplicateGroups(options);

    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/assets/duplicates/cross-source/search', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ ...options, analyze_automatically: false }),
    }));
    expect(fetchMock).toHaveBeenNthCalledWith(3, '/api/assets/duplicates/cross-source/search', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify(options),
    }));
  });

  it('creates a reviewed plan before executing it', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 'plan-1' }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ task_id: 'task-2' }), { status: 202 }));
    vi.stubGlobal('fetch', fetchMock);
    const request = {
      options,
      group_ids: ['group-1'],
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
      new Response(JSON.stringify({ group_id: 'group-1' }), { status: 200 }),
    );
    vi.stubGlobal('fetch', fetchMock);
    const request = {
      group_id: 'group-1',
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

  it('restores durable workspace state and saves selected groups', async () => {
    const restored = {
      initialized: true,
      selected_group_ids: ['group-1'],
      active_group_id: 'group-1',
      stale_selected_groups: [],
      drafts: [],
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(restored), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(restored), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    const request = {
      options,
      selected_group_ids: ['group-1'],
      active_group_id: 'group-1',
    };

    await loadDuplicateWorkspace();
    await saveDuplicateWorkspaceSelection(request);

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/assets/duplicates/workspace', expect.any(Object));
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/assets/duplicates/workspace/selection', expect.objectContaining({
      method: 'PUT',
      body: JSON.stringify(request),
    }));
  });

  it('saves per-image decisions and a stack primary independently of execution', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      new Response(JSON.stringify({ group_id: 'group-1' }), { status: 200 }),
    );
    vi.stubGlobal('fetch', fetchMock);
    const request = {
      group_id: 'group-1',
      member_fingerprint: 'fingerprint-1',
      options,
      decisions: [
        { asset_id: 'asset-1', disposition: 'stack' as const, source: 'manual' as const, status: 'pending' as const },
        { asset_id: 'asset-2', disposition: 'keep' as const, source: 'manual' as const, status: 'pending' as const },
      ],
      stack_primary_asset_id: 'asset-1',
      metadata_keeper_asset_id: 'asset-2',
      status: 'pending' as const,
    };

    await saveDuplicateGroupDraft(request);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/assets/duplicates/workspace/group',
      expect.objectContaining({ method: 'PUT', body: JSON.stringify(request) }),
    );
  });

  it('requests a group-scoped similarity reference', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      new Response(JSON.stringify({ group_id: 'group/one' }), { status: 200 }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await switchDuplicateSimilarityReference('group/one', 'asset-2');

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/assets/duplicates/cross-source/group%2Fone/similarity-reference',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ reference_asset_id: 'asset-2' }),
      }),
    );
  });

  it('starts a bounded conservative similarity scan', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      new Response(JSON.stringify({ task_id: 'scan-task' }), { status: 202 }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await startDuplicateSimilarityScan(92.5);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/assets/duplicates/similarity-scan',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          similarity_threshold: 92.5,
          scope: 'all_eligible_assets',
          maximum_perceptual_distance: 12,
          maximum_aspect_difference: 0.05,
          maximum_neighbors_per_asset: 8,
          maximum_matches: 5000,
        }),
      }),
    );
  });

  it('loads scan provenance and cancels through the shared task API', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ scan_id: 'scan-1' }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([{ id: 'task-1' }]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 'task-1', status: 'cancelled' }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    await loadLatestSimilarityScan();
    await loadSimilarityScanTasks();
    await cancelDuplicateTask('task/1');

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/assets/duplicates/similarity-scan/latest', expect.any(Object));
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/tasks?task_type=similarity_scan&limit=1', expect.any(Object));
    expect(fetchMock).toHaveBeenNthCalledWith(3, '/api/tasks/task%2F1/cancel', expect.objectContaining({ method: 'POST' }));
  });
});
