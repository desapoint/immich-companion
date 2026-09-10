import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import V2DuplicateDecisionControls from './V2DuplicateDecisionControls.svelte';

const renderControls = (decision: 'keep' | 'delete' | 'stack') => render(V2DuplicateDecisionControls, {
  props: {
    decision,
    decisions: ['keep', 'delete', 'stack'],
    ondecision: () => {},
    onprimary: () => {},
  },
}).body;

describe('V2DuplicateDecisionControls', () => {
  it.each(['keep', 'delete', 'stack'] as const)('exposes %s as the single active decision', (decision) => {
    const body = renderControls(decision);

    expect(body).toContain(`data-decision="${decision}"`);
    expect(body.match(/aria-pressed="true"/g)).toHaveLength(1);
    expect(body.match(/aria-pressed="false"/g)).toHaveLength(2);
  });
});
