import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import AssetRelationActionDialog from './AssetRelationActionDialog.svelte';

describe('AssetRelationActionDialog', () => {
  it('uses the picker submit as the final relation-action confirmation', () => {
    const { body } = render(AssetRelationActionDialog, {
      props: {
        action: 'add_tag',
        options: [{ value: 'tag-1', label: 'Review later' }],
        selectedCount: 2,
        targetLabel: 'selected assets',
        onapply: () => undefined,
        onclose: () => undefined,
      },
    });

    expect(body).toContain('>Add tags</button>');
    expect(body).not.toContain('>Review add tags</button>');
  });
});
