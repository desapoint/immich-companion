import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import DuplicateDecisionControls from '../components/DuplicateDecisionControls.svelte';

const renderControls = (decision: 'keep' | 'delete' | 'stack') => render(DuplicateDecisionControls, {
  props: {
    decision,
    decisions: ['keep', 'delete', 'stack'],
    ondecision: () => {},
    onprimary: () => {},
  },
}).body;

describe('DuplicateDecisionControls', () => {
  it.each(['keep', 'delete', 'stack'] as const)('exposes %s as the single active decision', (decision) => {
    const body = renderControls(decision);

    expect(body).toContain(`data-decision="${decision}"`);
    expect(body.match(/aria-pressed="true"/g)).toHaveLength(1);
    expect(body.match(/aria-pressed="false"/g)).toHaveLength(2);
  });
});
