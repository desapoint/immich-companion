import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import V2StackActionModal from './V2StackActionModal.svelte';

const props = {
  primaryLabel: 'IMG_0001.jpg',
  onresolutionchange: () => {},
  onconfirm: () => {},
  onclose: () => {},
};

describe('V2StackActionModal', () => {
  it('requires a reconciliation choice when existing stacks conflict', () => {
    const { body } = render(V2StackActionModal, {
      props: {
        ...props,
        plan: { id: 'plan-1', targetCount: 3, primaryAssetId: 'asset-1', conflicts: [{ stackId: 'stack-1', selectedCount: 1, memberCount: 2, includesUnselected: true }] },
      },
    });

    expect(body).toContain('Move selected assets');
    expect(body).toContain('Keep existing stacks');
    expect(body).toContain('Include every member');
    expect(body).toContain('IMG_0001.jpg');
    expect(body).toContain('disabled');
  });

  it('shows a simple reviewed confirmation when no stacks conflict', () => {
    const { body } = render(V2StackActionModal, {
      props: {
        ...props,
        plan: { id: 'plan-2', targetCount: 2, primaryAssetId: 'asset-1', conflicts: [] },
      },
    });

    expect(body).toContain('2 selected assets will be placed in one stack.');
    expect(body).not.toContain('Existing stacks');
  });
});
