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
  it('keeps generated stack identifiers bounded for long similarity group ids', () => {
    const longGroupId = 'companion:appearance-normalized-v1:6:8:a546bb2e720b:linked:cohesion-4:0825b4c6-e946-414d-92d6-3583d0d518c5:7e4ea637-dd9d-49f8-834d-b07b96fb81ed:a6e34534-133b-4799-bda8-f64c91e7b698:b76b3bb2-06af-4881-9d59-d5e58a221b97:b7829690-9cf9-41c4-a370-f5fecf7ee834:c988ae86-7c99-467a-a97e-1c19990e393c:e2d32c35-5c2e-49f7-ac9f-a27ee98fc668';
    let workspace = createPendingStack(createDuplicateStackWorkspace(), longGroupId);
    const firstId = workspace.activeByGroup[longGroupId];
    workspace = createPendingStack(workspace, longGroupId);
    const secondId = workspace.activeByGroup[longGroupId];

    expect(firstId.length).toBeLessThanOrEqual(256);
    expect(firstId).toMatch(/^pending-stack-[0-9a-z]+-1$/);
    expect(secondId).toMatch(/^pending-stack-[0-9a-z]+-2$/);
    expect(secondId).not.toBe(firstId);
  });

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
