import { describe, expect, it, vi } from 'vitest';

import {
  resetDuplicateWorkspaceDecisions,
  saveDuplicateWorkspaceSelection,
} from './duplicateApi';

const options = {
  keeper_policy: 'prefer_upload' as const,
  external_library_ids: [],
  verify_upload_streams: false,
  automatic_handling_enabled: true,
  preselect_safe_groups: true,
  exact_file_action: 'resolve' as const,
  analyze_automatically: true,
};

function workspace(groupIds: string[]) {
  return {
    initialized: true,
    selected_group_ids: groupIds,
    active_group_id: groupIds[0] ?? null,
    stale_selected_groups: [],
    drafts: [],
  };
}

describe('duplicate workspace write ordering', () => {
  it('waits for an older selection save before resetting decisions', async () => {
    let releaseSelection!: (response: Response) => void;
    const pendingSelection = new Promise<Response>((resolve) => {
      releaseSelection = resolve;
    });
    const calls: string[] = [];
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      calls.push(url);
      if (url.endsWith('/workspace/selection')) return pendingSelection;
      if (url.endsWith('/workspace/reset')) {
        return Promise.resolve(new Response(JSON.stringify(workspace([])), { status: 200 }));
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    const save = saveDuplicateWorkspaceSelection({
      options,
      selected_group_ids: ['group-1'],
      active_group_id: 'group-1',
    });
    await Promise.resolve();

    const reset = resetDuplicateWorkspaceDecisions({
      options,
      group_ids: ['group-1'],
    });
    await Promise.resolve();

    expect(calls).toEqual(['/api/assets/duplicates/workspace/selection']);

    releaseSelection(new Response(JSON.stringify(workspace(['group-1'])), { status: 200 }));
    await save;
    await reset;

    expect(calls).toEqual([
      '/api/assets/duplicates/workspace/selection',
      '/api/assets/duplicates/workspace/reset',
    ]);

    vi.unstubAllGlobals();
  });

  it('serializes consecutive selection snapshots', async () => {
    let releaseFirst!: (response: Response) => void;
    const firstResponse = new Promise<Response>((resolve) => {
      releaseFirst = resolve;
    });
    const calls: string[] = [];
    let selectionCalls = 0;
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      calls.push(url);
      selectionCalls += 1;
      if (selectionCalls === 1) return firstResponse;
      return Promise.resolve(new Response(JSON.stringify(workspace(['group-2'])), { status: 200 }));
    });
    vi.stubGlobal('fetch', fetchMock);

    const first = saveDuplicateWorkspaceSelection({
      options,
      selected_group_ids: ['group-1'],
      active_group_id: 'group-1',
    });
    const second = saveDuplicateWorkspaceSelection({
      options,
      selected_group_ids: ['group-2'],
      active_group_id: 'group-2',
    });
    await Promise.resolve();

    expect(calls).toEqual(['/api/assets/duplicates/workspace/selection']);

    releaseFirst(new Response(JSON.stringify(workspace(['group-1'])), { status: 200 }));
    await Promise.all([first, second]);

    expect(calls).toEqual([
      '/api/assets/duplicates/workspace/selection',
      '/api/assets/duplicates/workspace/selection',
    ]);

    vi.unstubAllGlobals();
  });
});
