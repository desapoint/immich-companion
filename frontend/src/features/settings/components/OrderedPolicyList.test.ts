import { render } from 'svelte/server';
import { describe, expect, it, vi } from 'vitest';

import OrderedPolicyList from './OrderedPolicyList.svelte';

const items = [
  { id: 'a', label: 'Library A', description: 'First library' },
  { id: 'b', label: 'Library B', description: 'Second library', unavailable: true },
];

describe('OrderedPolicyList', () => {
  it('renders accessible move controls and unavailable saved sources', () => {
    const { body } = render(OrderedPolicyList, {
      props: { id: 'sources', label: 'Sources', items, onchange: vi.fn() },
    });

    expect(body).toContain('aria-label="Move Library B up"');
    expect(body).toContain('Unavailable');
    expect(body).toContain('Second library');
  });
});
