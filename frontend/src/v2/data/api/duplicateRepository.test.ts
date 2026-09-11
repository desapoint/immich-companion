import { afterEach, describe, expect, it, vi } from 'vitest';

import type { TaskRepository } from '../syncContracts';
import { createDuplicateRepository } from './duplicateRepository';

const ASSET_IDS = [
  '11111111-1111-4111-8111-111111111111',
  '22222222-2222-4222-8222-222222222222',
];
const OVERLAP_ASSET_ID = '33333333-3333-4333-8333-333333333333';

const group = {
  group_id: 'immich-group:stable-provider-id',
  reference_asset_id: ASSET_IDS[0],
  group_similarity_percent: 98.5,
  similarity_engine: 'appearance',
  similarity_model_version: 'appearance-v1',
  similarity_feature_version: 2,
  similarity_comparison_version: 4,
  discovery_source: 'immich_duplicate',
  provider_group_id: 'stable-provider-id',
  classification: 'exact_file',
  status: 'exact',
  reason: null,
  keeper_asset_id: ASSET_IDS[0],
  recommended_action: 'resolve',
  recommended_primary_asset_id: ASSET_IDS[0],
  recommendation_reason_codes: [],
  auto_resolvable: true,
  auto_selected: true,
  action_source: 'automatic',
  primary_source: 'automatic',
  manual_action: null,
  manual_primary_asset_id: null,
  effective_action: 'resolve',
  effective_primary_asset_id: ASSET_IDS[0],
  review_status: 'pending',
  member_fingerprint: 'fingerprint-v1',
  eligible: true,
  members: ASSET_IDS.map((id, index) => ({
    id,
    source_kind: index ? 'external' : 'upload',
    library_id: index ? 'library-1' : null,
    original_file_name: `asset-${index}.jpg`,
    original_mime_type: 'image/jpeg',
    file_size_bytes: 100,
    file_modified_at: '2026-09-01T00:00:00Z',
    uploaded_at: null,
    is_offline: false,
    is_stacked: false,
    immich_url: null,
    verification: 'matching',
    content_checksum: 'abc',
    evidence: {},
    similarity: index
      ? { state: 'current', reference_asset_id: ASSET_IDS[0], similarity_percent: 98.5, structural_percent: 99.1, perceptual_percent: 96.9, color_percent: 97.2 }
      : { state: 'reference', reference_asset_id: ASSET_IDS[0], similarity_percent: 100, structural_percent: 100, perceptual_percent: 100, color_percent: 100 },
    preservation: null,
  })),
};

const duplicateResult = {
  generated_at: '2026-09-10T00:00:00Z',
  analysis_task_id: null,
  analysis_pending_count: 0,
  analysis_candidate_count: 2,
  analysis_cached_count: 2,
  group_count: 1,
  exact_group_count: 1,
  unverified_group_count: 0,
  mismatch_group_count: 0,
  ineligible_group_count: 0,
  groups: [group],
};

const emptyWorkspace = {
  initialized: true,
  selected_group_ids: [],
  active_group_id: null,
  stale_selected_groups: [],
  drafts: [],
};

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
}

function tasks(): TaskRepository {
  return { get: vi.fn(async () => ({ status: 'completed', result: { summary: { failed_group_ids: [] } } })) } as unknown as TaskRepository;
}

afterEach(() => vi.unstubAllGlobals());

describe('live V2 duplicate repository', () => {
  it('loads stable provider groups and persisted decisions without per-member summary requests', async () => {
    const selectedWorkspace = {
      ...emptyWorkspace,
      selected_group_ids: [group.group_id],
      drafts: [{
        group_id: group.group_id,
        discovery_source: 'immich_duplicate',
        member_fingerprint: group.member_fingerprint,
        decisions: [{ asset_id: ASSET_IDS[0], disposition: 'keep', source: 'manual', status: 'pending' }],
        stack_primary_asset_id: null,
        stack_resolution: 'move_selected',
        metadata_keeper_asset_id: null,
        status: 'pending',
        stale: false,
      }],
    };
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => String(input).endsWith('/workspace') ? response(selectedWorkspace) : response(duplicateResult)));
    const fetcher = vi.mocked(fetch);
    const repository = createDuplicateRepository(tasks());

    const result = await repository.search({ page: 1, pageSize: 1, state: 'All groups' });

    expect(result.items[0]).toMatchObject({
      id: group.group_id,
      state: 'Needs decisions',
      selected: true,
      savedDecisions: { [ASSET_IDS[0]]: 'keep' },
      referenceAssetId: ASSET_IDS[0],
      groupSimilarity: 98.5,
      similarityEngine: 'appearance',
      members: [
        { similarity: 100, similarityEvidence: { structuralPercent: 100, perceptualPercent: 100, colorPercent: 100 }, asset: { id: ASSET_IDS[0], original_file_name: 'asset-0.jpg', asset_type: 'IMAGE' } },
        { similarity: 98.5, similarityEvidence: { structuralPercent: 99.1, perceptualPercent: 96.9, colorPercent: 97.2 }, asset: { id: ASSET_IDS[1], original_file_name: 'asset-1.jpg', asset_type: 'IMAGE', library_id: 'library-1' } },
      ],
    });
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(fetcher.mock.calls.some(([input]) => String(input).includes('/summary'))).toBe(false);
  });

  it('does not present verified content hashes as visual similarity scores', async () => {
    const exactOnly = {
      ...duplicateResult,
      groups: [{
        ...group,
        group_similarity_percent: null,
        similarity_engine: null,
        members: group.members.map((member) => ({ ...member, similarity: null })),
      }],
    };
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => String(input).endsWith('/workspace') ? response(emptyWorkspace) : response(exactOnly)));
    const repository = createDuplicateRepository(tasks());

    const result = await repository.search({ page: 1, pageSize: 1, state: 'All groups' });

    expect(result.items[0]?.members.map((member) => member.similarity)).toEqual([null, null]);
  });

  it('persists complete per-image choices before planning and executing them', async () => {
    const calls: Array<{ path: string; body: Record<string, unknown> }> = [];
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      const body = init?.body ? JSON.parse(String(init.body)) as Record<string, unknown> : {};
      calls.push({ path, body });
      if (path.endsWith('/cross-source/search')) return response(duplicateResult);
      if (path.endsWith('/workspace') && init?.method !== 'PUT') return response(emptyWorkspace);
      if (path.endsWith('/workspace/group')) return response({ ...emptyWorkspace, ...body, discovery_source: 'immich_duplicate', stale: false });
      if (path.endsWith('/workspace/selection')) return response({ ...emptyWorkspace, selected_group_ids: body.selected_group_ids, active_group_id: body.active_group_id });
      if (path.endsWith('/cross-source/plan')) return response({ id: 'plan-1' });
      if (path.endsWith('/cross-source/execute')) return response({ task_id: 'task-1' }, 202);
      throw new Error(`Unexpected request: ${path}`);
    }));
    const repository = createDuplicateRepository(tasks());
    await repository.search({ page: 1, pageSize: 10 });

    const plan = await repository.prepareDecisions({
      decisions: { [ASSET_IDS[0]]: 'keep', [ASSET_IDS[1]]: 'delete' },
      stacks: [],
    }, [group.group_id]);
    expect(calls.at(-1)?.path).toBe('/api/assets/duplicates/cross-source/plan');

    const result = await repository.executePlan(plan);

    expect(result).toEqual({ affectedIds: ASSET_IDS, failed: [] });
    expect(calls.map((call) => call.path).slice(2)).toEqual([
      '/api/assets/duplicates/workspace/group',
      '/api/assets/duplicates/workspace/selection',
      '/api/assets/duplicates/cross-source/plan',
      '/api/assets/duplicates/cross-source/execute',
    ]);
    expect(calls.find((call) => call.path.endsWith('/workspace/group'))?.body).toMatchObject({
      group_id: group.group_id,
      member_fingerprint: group.member_fingerprint,
      status: 'completed',
    });
    expect(calls.find((call) => call.path.endsWith('/cross-source/plan'))?.body).toMatchObject({
      group_ids: [group.group_id],
      action_overrides: { [group.group_id]: 'resolve' },
      keeper_overrides: { [group.group_id]: ASSET_IDS[0] },
    });
  });

  it('rejects incomplete groups before creating an action plan', async () => {
    const fetcher = vi.fn(async (input: RequestInfo | URL) => String(input).endsWith('/workspace') ? response(emptyWorkspace) : response(duplicateResult));
    vi.stubGlobal('fetch', fetcher);
    const repository = createDuplicateRepository(tasks());
    await repository.search({ page: 1, pageSize: 10 });

    await expect(repository.prepareDecisions({ decisions: { [ASSET_IDS[0]]: 'keep' }, stacks: [] }, [group.group_id])).rejects.toThrow('images without a decision');
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it('prepares only the requested group when similarity groups share an asset', async () => {
    const overlappingGroup = {
      ...group,
      group_id: 'companion:appearance-v1:overlap',
      provider_group_id: null,
      member_fingerprint: 'fingerprint-overlap',
      members: [
        group.members[0],
        {
          ...group.members[1],
          id: OVERLAP_ASSET_ID,
          original_file_name: 'overlap.jpg',
        },
      ],
    };
    const resultWithOverlap = {
      ...duplicateResult,
      group_count: 2,
      groups: [group, overlappingGroup],
    };
    const calls: Array<{ path: string; body: Record<string, unknown> }> = [];
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      const body = init?.body ? JSON.parse(String(init.body)) as Record<string, unknown> : {};
      calls.push({ path, body });
      if (path.endsWith('/cross-source/search')) return response(resultWithOverlap);
      if (path.endsWith('/workspace') && init?.method !== 'PUT') return response(emptyWorkspace);
      if (path.endsWith('/workspace/group')) return response({ ...emptyWorkspace, ...body, discovery_source: 'immich_duplicate', stale: false });
      if (path.endsWith('/workspace/selection')) return response({ ...emptyWorkspace, selected_group_ids: body.selected_group_ids, active_group_id: body.active_group_id });
      if (path.endsWith('/cross-source/plan')) return response({ id: 'plan-overlap' });
      throw new Error(`Unexpected request: ${path}`);
    }));
    const repository = createDuplicateRepository(tasks());
    await repository.search({ page: 1, pageSize: 10 });

    const plan = await repository.prepareDecisions({
      decisions: { [ASSET_IDS[0]]: 'keep', [ASSET_IDS[1]]: 'delete' },
      stacks: [],
    }, [group.group_id]);

    expect(plan.groupIds).toEqual([group.group_id]);
    expect(calls.find((call) => call.path.endsWith('/cross-source/plan'))?.body).toMatchObject({
      group_ids: [group.group_id],
    });
  });

  it('clears every discovered group through one durable workspace reset', async () => {
    const calls: Array<{ path: string; body: Record<string, unknown> }> = [];
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      const body = init?.body ? JSON.parse(String(init.body)) as Record<string, unknown> : {};
      calls.push({ path, body });
      if (path.endsWith('/cross-source/search')) return response(duplicateResult);
      if (path.endsWith('/workspace/reset')) return response(emptyWorkspace);
      if (path.endsWith('/workspace')) return response(emptyWorkspace);
      throw new Error(`Unexpected request: ${path}`);
    }));
    const repository = createDuplicateRepository(tasks());
    await repository.search({ page: 1, pageSize: 1, state: 'All groups' });

    const cleared = await repository.clearDecisions();

    expect(cleared).toBe(1);
    expect(calls.at(-1)).toEqual({
      path: '/api/assets/duplicates/workspace/reset',
      body: expect.objectContaining({ group_ids: [group.group_id] }),
    });
  });

  it('switches only the display reference contract returned by the backend', async () => {
    const switched = {
      ...group,
      reference_asset_id: ASSET_IDS[1],
      members: group.members.map((member, index) => ({
        ...member,
        similarity: index
          ? { ...member.similarity, state: 'reference', reference_asset_id: ASSET_IDS[1], similarity_percent: 100 }
          : { ...member.similarity, state: 'current', reference_asset_id: ASSET_IDS[1], similarity_percent: 97.1 },
      })),
    };
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path.endsWith('/cross-source/search')) return response(duplicateResult);
      if (path.endsWith('/workspace')) return response(emptyWorkspace);
      if (path.includes('/similarity-reference')) return response(switched);
      throw new Error(`Unexpected request: ${path}`);
    }));
    const repository = createDuplicateRepository(tasks());
    await repository.search({ page: 1, pageSize: 10 });

    const result = await repository.switchReference(group.group_id, ASSET_IDS[1]);

    expect(result).toMatchObject({
      referenceAssetId: ASSET_IDS[1],
      groupSimilarity: 98.5,
      similarityEngine: 'appearance',
      kind: 'exact file',
      members: [{ similarity: 97.1 }, { similarity: 100 }],
    });
  });

  it('maps exact and similarity tasks into one monotonic discovery range', async () => {
    const taskRepository = {
      get: vi.fn()
        .mockResolvedValueOnce({status:'completed',progress:{phase:'complete',completed:10,total:10,percent:100,detail:'Exact evidence ready'},counters:{}})
        .mockResolvedValueOnce({status:'completed',progress:{phase:'similarity_finalizing',completed:50,total:50,percent:100,detail:'Similarity scan ready'},counters:{candidate_pairs:50,matches_retained:8}}),
    } as unknown as TaskRepository;
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path.endsWith('/cross-source/analyze')) return response({task_id:'exact-task'},202);
      if (path.endsWith('/similarity-scan')) return response({task_id:'similarity-task'},202);
      if (path.endsWith('/cross-source/search')) return response(duplicateResult);
      throw new Error(`Unexpected request: ${path}`);
    }));
    const progress: number[] = [];
    const repository = createDuplicateRepository(taskRepository);

    await repository.runDiscovery({similarityThreshold:90,includeSimilar:true,includeExact:true,maxCandidates:20},(update)=>{if(update.percent!==null)progress.push(update.percent)});

    expect(progress).toEqual([25,98,99]);
  });

});
