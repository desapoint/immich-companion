import { afterEach, describe, expect, it, vi } from 'vitest';

import type { AssetRecord, AssetRepository } from '../contracts';
import type { TaskRepository } from '../syncContracts';
import { createDuplicateRepository } from './duplicateRepository';

const ASSET_IDS = [
  '11111111-1111-4111-8111-111111111111',
  '22222222-2222-4222-8222-222222222222',
];

const group = {
  group_id: 'immich-group:stable-provider-id',
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
    similarity: index ? { state: 'current', reference_asset_id: ASSET_IDS[0], similarity_percent: 98.5 } : { state: 'reference', reference_asset_id: ASSET_IDS[0], similarity_percent: 100 },
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

function assets(): AssetRepository {
  const records = ASSET_IDS.map((id, index) => ({ id, original_file_name: `asset-${index}.jpg`, asset_type: 'IMAGE', library_id: index ? 'library-1' : null }) as AssetRecord);
  return { getMany: vi.fn(async (ids: readonly string[]) => records.filter((asset) => ids.includes(asset.id))) } as unknown as AssetRepository;
}

function tasks(): TaskRepository {
  return { get: vi.fn(async () => ({ status: 'completed', result: { summary: { failed_group_ids: [] } } })) } as unknown as TaskRepository;
}

afterEach(() => vi.unstubAllGlobals());

describe('live V2 duplicate repository', () => {
  it('loads stable provider groups, persisted decisions, and only hydrates visible assets', async () => {
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
    const assetRepository = assets();
    const repository = createDuplicateRepository(assetRepository, tasks());

    const result = await repository.search({ page: 1, pageSize: 1, state: 'All groups' });

    expect(result.items[0]).toMatchObject({
      id: group.group_id,
      state: 'Needs decisions',
      selected: true,
      savedDecisions: { [ASSET_IDS[0]]: 'keep' },
      members: [{ similarity: 100 }, { similarity: 98.5 }],
    });
    expect(assetRepository.getMany).toHaveBeenCalledOnce();
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
    const repository = createDuplicateRepository(assets(), tasks());
    await repository.search({ page: 1, pageSize: 10 });

    const plan = await repository.prepareDecisions({
      decisions: { [ASSET_IDS[0]]: 'keep', [ASSET_IDS[1]]: 'delete' },
      stacks: [],
    });
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
    const repository = createDuplicateRepository(assets(), tasks());
    await repository.search({ page: 1, pageSize: 10 });

    await expect(repository.prepareDecisions({ decisions: { [ASSET_IDS[0]]: 'keep' }, stacks: [] })).rejects.toThrow('images without a decision');
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});
