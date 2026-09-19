import { describe, expect, it } from 'vitest';

import type { AssetRecord, DuplicateGroupRecord, DuplicateKeeperRule } from '../../../v2/data/contracts';
import {
  evaluateDuplicateAutomation,
  type DuplicateAutomationExistingDecision,
  type DuplicateAutomationUiRule,
} from '../state/duplicateAutomationRules';

let nextAsset = 0;
function asset(overrides: Partial<AssetRecord> = {}): AssetRecord {
  nextAsset += 1;
  return {
    id: `asset-${nextAsset}`,
    owner_id: 'owner',
    library_id: 'external-library',
    asset_type: 'IMAGE',
    original_file_name: `photo-${nextAsset}.jpg`,
    original_path: `/photos/photo-${nextAsset}.jpg`,
    original_mime_type: 'image/jpeg',
    checksum: `checksum-${nextAsset}`,
    file_size_bytes: 1_000,
    width: 100,
    height: 100,
    duration: null,
    file_created_at: '2026-01-01T00:00:00Z',
    file_modified_at: '2026-01-01T00:00:00Z',
    local_date_time: '2026-01-01T00:00:00Z',
    immich_created_at: '2026-01-01T00:00:00Z',
    immich_updated_at: '2026-01-01T00:00:00Z',
    is_favorite: false,
    is_archived: false,
    is_offline: false,
    is_edited: false,
    has_metadata: true,
    visibility: 'timeline',
    live_photo_video_id: null,
    tags: [],
    albums: [],
    stack: null,
    synced_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

function group(assets: AssetRecord[], similarities?: number[]): DuplicateGroupRecord {
  return {
    id: 'group-1',
    discoverySources: ['immich_duplicate'],
    state: 'Needs review',
    autoReady: false,
    kind: 'exact file',
    reason: null,
    referenceAssetId: assets[0]?.id ?? null,
    groupSimilarity: similarities?.length ? Math.min(...similarities) : 100,
    similarityEngine: null,
    similarityModelVersion: null,
    similarityFeatureVersion: null,
    similarityComparisonVersion: null,
    similarityValidationMode: null,
    similarityThresholdPercent: null,
    memberFingerprint: 'fingerprint',
    selected: false,
    savedDecisions: {},
    stackPrimaryAssetId: null,
    stackResolution: 'move_selected',
    members: assets.map((item, index) => ({
      asset: item,
      similarity: similarities?.[index] ?? 100,
      similarityEvidence: null,
      admission: null,
    })),
  };
}

const keeperRules: DuplicateKeeperRule[] = [
  { effect: 'prefer', field: 'library', operator: 'is', value: 'upload' },
  { effect: 'prefer', field: 'resolution', operator: 'highest', value: '' },
];

function rule(overrides: Partial<DuplicateAutomationUiRule> = {}): DuplicateAutomationUiRule {
  return {
    id: 1,
    logic: 'all',
    conditions: [{ id: 1, scope: 'member', field: 'library', operator: 'is', value: 'upload', count: 1 }],
    target: 'matching_members',
    action: 'keep',
    flow: 'stop_group',
    ...overrides,
  };
}

describe('duplicate automation rules', () => {
  it('keeps matching upload members and leaves the rest undecided', () => {
    const upload = asset({ library_id: null });
    const externalA = asset();
    const externalB = asset();
    const result = evaluateDuplicateAutomation(group([upload, externalA, externalB]), [rule()], [], keeperRules);

    expect(result.touched).toBe(true);
    expect(result.partial).toBe(true);
    expect(result.manualReview).toBe(true);
    expect(result.decisions).toEqual([
      expect.objectContaining({ assetId: upload.id, disposition: 'keep', source: 'automatic' }),
    ]);
    expect(result.undecidedCount).toBe(2);
  });

  it('supports different actions from ordered member conditions', () => {
    const upload = asset({ library_id: null });
    const external = asset({ library_id: 'library-a' });
    const rules: DuplicateAutomationUiRule[] = [
      rule({ flow: 'continue' }),
      {
        id: 2,
        logic: 'all',
        conditions: [{ id: 2, scope: 'member', field: 'library', operator: 'is_not', value: 'upload', count: 1 }],
        target: 'matching_members',
        action: 'delete',
        flow: 'stop_group',
      },
    ];
    const result = evaluateDuplicateAutomation(group([upload, external]), rules, [], keeperRules);

    expect(result.complete).toBe(true);
    expect(result.decisions).toEqual(expect.arrayContaining([
      expect.objectContaining({ assetId: upload.id, disposition: 'keep' }),
      expect.objectContaining({ assetId: external.id, disposition: 'delete' }),
    ]));
  });

  it('supports group conditions and keeper resolution', () => {
    const upload = asset({ library_id: null, width: 100, height: 100 });
    const external = asset({ width: 400, height: 400 });
    const resolveRule: DuplicateAutomationUiRule = {
      id: 1,
      logic: 'all',
      conditions: [{ id: 1, scope: 'group', field: 'classification', operator: 'is', value: 'exact file, exact pixels', count: 1 }],
      target: 'whole_group',
      action: 'resolve_keeper',
      flow: 'stop_group',
    };
    const result = evaluateDuplicateAutomation(group([upload, external]), [resolveRule], [], keeperRules);

    expect(result.complete).toBe(true);
    expect(result.decisions).toEqual(expect.arrayContaining([
      expect.objectContaining({ assetId: upload.id, disposition: 'keep' }),
      expect.objectContaining({ assetId: external.id, disposition: 'delete' }),
    ]));
    expect(result.metadataKeeperAssetId).toBe(upload.id);
  });

  it('does not nominate metadata keeper when a protected manual keep leaves multiple survivors', () => {
    const manualKeep = asset({ width: 100, height: 100 });
    const automaticKeep = asset({ width: 400, height: 400 });
    const deleted = asset({ width: 200, height: 200 });
    const existing: DuplicateAutomationExistingDecision[] = [
      { assetId: manualKeep.id, disposition: 'keep', source: 'manual', status: 'pending' },
    ];
    const resolveRule: DuplicateAutomationUiRule = {
      id: 1,
      logic: 'all',
      conditions: [{ id: 1, scope: 'group', field: 'classification', operator: 'is', value: 'exact file, exact pixels', count: 1 }],
      target: 'whole_group',
      action: 'resolve_keeper',
      flow: 'stop_group',
    };

    const result = evaluateDuplicateAutomation(
      group([manualKeep, automaticKeep, deleted]),
      [resolveRule],
      existing,
      keeperRules,
    );

    expect(result.complete).toBe(true);
    expect(result.metadataKeeperAssetId).toBeNull();
    expect(result.decisions).toEqual(expect.arrayContaining([
      expect.objectContaining({ assetId: manualKeep.id, disposition: 'keep', source: 'manual' }),
      expect.objectContaining({ assetId: automaticKeep.id, disposition: 'keep', source: 'automatic' }),
      expect.objectContaining({ assetId: deleted.id, disposition: 'delete', source: 'automatic' }),
    ]));
  });

  it('supports aggregate member conditions', () => {
    const first = asset();
    const second = asset();
    const keepAllRule: DuplicateAutomationUiRule = {
      id: 1,
      logic: 'all',
      conditions: [{ id: 1, scope: 'all_members', field: 'similarity', operator: 'gte', value: '99', count: 1 }],
      target: 'whole_group',
      action: 'keep',
      flow: 'stop_group',
    };
    const result = evaluateDuplicateAutomation(group([first, second], [99.5, 99.8]), [keepAllRule], [], keeperRules);

    expect(result.complete).toBe(true);
    expect(result.keepCount).toBe(2);
  });

  it('preserves manual decisions while automating remaining members', () => {
    const manualKeep = asset({ library_id: null });
    const external = asset();
    const other = asset();
    const existing: DuplicateAutomationExistingDecision[] = [
      { assetId: manualKeep.id, disposition: 'keep', source: 'manual', status: 'pending' },
    ];
    const deleteExternal: DuplicateAutomationUiRule = {
      id: 1,
      logic: 'all',
      conditions: [{ id: 1, scope: 'member', field: 'library', operator: 'is_not', value: 'upload', count: 1 }],
      target: 'matching_members',
      action: 'delete',
      flow: 'stop_affected',
    };
    const result = evaluateDuplicateAutomation(group([manualKeep, external, other]), [deleteExternal], existing, keeperRules);

    expect(result.preservedManual).toBe(true);
    expect(result.complete).toBe(true);
    expect(result.decisions).toEqual(expect.arrayContaining([
      expect.objectContaining({ assetId: manualKeep.id, disposition: 'keep', source: 'manual' }),
      expect.objectContaining({ assetId: external.id, disposition: 'delete', source: 'automatic' }),
      expect.objectContaining({ assetId: other.id, disposition: 'delete', source: 'automatic' }),
    ]));
  });

  it('refuses an automatic rule that would delete every member', () => {
    const first = asset();
    const second = asset();
    const deleteAll: DuplicateAutomationUiRule = {
      id: 1,
      logic: 'all',
      conditions: [{ id: 1, scope: 'all_members', field: 'availability', operator: 'is', value: 'online', count: 1 }],
      target: 'whole_group',
      action: 'delete',
      flow: 'stop_group',
    };
    const result = evaluateDuplicateAutomation(group([first, second]), [deleteAll], [], keeperRules);

    expect(result.ambiguous).toBe(true);
    expect(result.manualReview).toBe(true);
    expect(result.deleteCount).toBe(0);
    expect(result.decisions).toHaveLength(0);
  });
});
