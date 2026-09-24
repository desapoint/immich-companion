import { describe, expect, it, vi } from 'vitest';

vi.mock('../../../app/data/currentDataSource.svelte', () => ({
  libraryData: {
    duplicates: {
      selectedGroupIds: () => [],
    },
  },
}));

import type { DuplicateGroupRecord } from '../types/contracts';
import { DuplicatePagePersistence } from '../state/duplicatePagePersistence.svelte';
import {
  assignAssetToActiveStack,
  createDuplicateStackWorkspace,
  createPendingStack,
  removeAssetFromPendingStack,
  stacksForGroup,
} from '../state/duplicateStackResolution';

function groupWithSavedStacks(): DuplicateGroupRecord {
  return {
    id: 'group-1',
    selected: false,
    savedDecisions: { a: 'stack', b: 'stack', c: 'stack', d: 'stack' },
    savedStacks: [
      {
        id: 'group-group-1-stack-1',
        groupId: 'group-1',
        label: 'Stack 1',
        assetIds: ['a', 'b'],
        primaryAssetId: 'a',
      },
      {
        id: 'group-group-1-stack-2',
        groupId: 'group-1',
        label: 'Stack 2',
        assetIds: ['c', 'd'],
        primaryAssetId: 'c',
      },
    ],
    stackPrimaryAssetId: 'a',
    stackResolution: 'move_selected',
    members: ['a', 'b', 'c', 'd'].map((id) => ({ asset: { id } })),
  } as unknown as DuplicateGroupRecord;
}

describe('duplicate pending stack persistence', () => {
  it('rehydrates saved partitions without merging or accumulating empty stacks', () => {
    const persistence = new DuplicatePagePersistence();
    const item = groupWithSavedStacks();

    const first = persistence.hydrateWorkspace(
      [item],
      false,
      {},
      createDuplicateStackWorkspace(),
      [],
    );
    const second = persistence.hydrateWorkspace(
      [item],
      false,
      first.decisions,
      first.stackWorkspace,
      first.selectedGroups,
    );

    const stacks = stacksForGroup(second.stackWorkspace, item.id);
    expect(stacks).toHaveLength(2);
    expect(stacks.map((stack) => stack.assetIds)).toEqual([
      ['a', 'b'],
      ['c', 'd'],
    ]);
    expect(stacks.every((stack) => stack.assetIds.length > 0)).toBe(true);
  });

  it('keeps multi-stack partitions while navigating and refreshing pagination pages', () => {
    const persistence = new DuplicatePagePersistence();
    const firstPage = groupWithSavedStacks();
    const secondPage = {
      ...groupWithSavedStacks(),
      id: 'group-2',
      savedDecisions: { e: 'stack', f: 'stack', g: 'stack', h: 'stack' },
      savedStacks: [
        { id: 'saved-3', groupId: 'group-2', label: 'Stack 1', assetIds: ['e', 'f'], primaryAssetId: 'e' },
        { id: 'saved-4', groupId: 'group-2', label: 'Stack 2', assetIds: ['g', 'h'], primaryAssetId: 'g' },
      ],
      members: ['e', 'f', 'g', 'h'].map((id) => ({ asset: { id } })),
    } as unknown as DuplicateGroupRecord;

    const pageOne = persistence.hydrateWorkspace(
      [firstPage],
      true,
      {},
      createDuplicateStackWorkspace(),
      [],
    );
    const pageTwo = persistence.hydrateWorkspace(
      [secondPage],
      false,
      pageOne.decisions,
      pageOne.stackWorkspace,
      pageOne.selectedGroups,
    );
    const refreshedPageOne = persistence.hydrateWorkspace(
      [firstPage],
      false,
      pageTwo.decisions,
      pageTwo.stackWorkspace,
      pageTwo.selectedGroups,
    );

    expect(stacksForGroup(refreshedPageOne.stackWorkspace, 'group-1').map((stack) => stack.assetIds)).toEqual([
      ['a', 'b'],
      ['c', 'd'],
    ]);
    expect(stacksForGroup(refreshedPageOne.stackWorkspace, 'group-2').map((stack) => stack.assetIds)).toEqual([
      ['e', 'f'],
      ['g', 'h'],
    ]);
  });

  it('hydrates the same asset independently in overlapping groups', () => {
    const persistence = new DuplicatePagePersistence();
    const first = {
      ...groupWithSavedStacks(),
      id: 'group-1',
      savedDecisions: { shared: 'stack', a: 'stack' },
      savedStacks: [{
        id: 'g1-stack',
        groupId: 'group-1',
        label: 'Stack 1',
        assetIds: ['shared', 'a'],
        primaryAssetId: 'shared',
      }],
      members: ['shared', 'a'].map((id) => ({ asset: { id } })),
    } as unknown as DuplicateGroupRecord;
    const second = {
      ...groupWithSavedStacks(),
      id: 'group-2',
      savedDecisions: { shared: 'keep', b: 'stack' },
      savedStacks: [{
        id: 'g2-stack',
        groupId: 'group-2',
        label: 'Stack 1',
        assetIds: ['b'],
        primaryAssetId: 'b',
      }],
      members: ['shared', 'b'].map((id) => ({ asset: { id } })),
    } as unknown as DuplicateGroupRecord;

    const hydrated = persistence.hydrateWorkspace(
      [first, second],
      true,
      {},
      createDuplicateStackWorkspace(),
      [],
    );

    expect(hydrated.decisions['group-1']).toEqual({ shared: 'stack', a: 'stack' });
    expect(hydrated.decisions['group-2']).toEqual({ shared: 'keep', b: 'stack' });
    expect(stacksForGroup(hydrated.stackWorkspace, 'group-1')[0].assetIds).toEqual(['shared', 'a']);
    expect(stacksForGroup(hydrated.stackWorkspace, 'group-2')[0].assetIds).toEqual(['b']);
  });

  it('assigns the same asset to different pending stacks in different groups without moving either one', () => {
    let workspace = createDuplicateStackWorkspace();
    workspace = assignAssetToActiveStack(workspace, 'group-1', 'shared');
    workspace = assignAssetToActiveStack(workspace, 'group-1', 'a');
    workspace = assignAssetToActiveStack(workspace, 'group-2', 'shared');
    workspace = assignAssetToActiveStack(workspace, 'group-2', 'b');

    expect(stacksForGroup(workspace, 'group-1')[0].assetIds).toEqual(['shared', 'a']);
    expect(stacksForGroup(workspace, 'group-2')[0].assetIds).toEqual(['shared', 'b']);

    workspace = removeAssetFromPendingStack(workspace, 'group-2', 'shared');

    expect(stacksForGroup(workspace, 'group-1')[0].assetIds).toEqual(['shared', 'a']);
    expect(stacksForGroup(workspace, 'group-2')[0].assetIds).toEqual(['b']);
  });

  it('removes a pending stack when its last member moves out', () => {
    let workspace = createPendingStack(createDuplicateStackWorkspace(), 'group-1');
    workspace = assignAssetToActiveStack(workspace, 'group-1', 'a');
    const stackId = workspace.activeByGroup['group-1'];

    workspace = removeAssetFromPendingStack(workspace, 'group-1', 'a');

    expect(workspace.stacks[stackId]).toBeUndefined();
    expect(workspace.activeByGroup['group-1']).toBeUndefined();
    expect(stacksForGroup(workspace, 'group-1')).toEqual([]);
  });
});
