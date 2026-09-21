import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import PerceptualDistanceSetting from '../components/PerceptualDistanceSetting.svelte';

describe('PerceptualDistanceSetting', () => {
  it('renders the full dHash range and an approximate interpretation guide', () => {
    const { body } = render(PerceptualDistanceSetting, {
      props: { value: 12, onchange: () => undefined },
    });

    expect(body).toContain('Maximum dHash distance');
    expect(body).toContain('12 / 64');
    expect(body).toContain('Approximate dHash distance guide');
    expect(body).toContain('Strong near-duplicate candidate; 12 is the default.');
    expect(body).toContain('Final similarity validation still decides');
  });
});
