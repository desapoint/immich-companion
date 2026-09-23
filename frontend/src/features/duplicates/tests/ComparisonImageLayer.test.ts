import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';
import ComparisonImageLayer from '../components/ComparisonImageLayer.svelte';

describe('ComparisonImageLayer', () => {
  it('renders the shared transformed image layer contract', () => {
    const { body } = render(ComparisonImageLayer, {
      props: {
        image: { src: '/selected.jpg', label: 'Selected image' },
        transform: 'translate(2px, 3px) scale(1.5)',
        top: true,
        clipPath: 'inset(0 0 0 40%)',
        opacity: 0.5,
      },
    });

    expect(body).toContain('class="v2-compare-layer top"');
    expect(body).toContain('clip-path:inset(0 0 0 40%)');
    expect(body).toContain('opacity:0.5');
    expect(body).toContain('visibility:visible');
    expect(body).toContain('style="transform:translate(2px, 3px) scale(1.5)"');
    expect(body).toContain('src="/selected.jpg"');
    expect(body).toContain('alt="Selected image"');
  });

  it('preserves the accessibility state for a hidden comparison layer', () => {
    const { body } = render(ComparisonImageLayer, {
      props: {
        image: { src: '/reference.jpg', label: 'Reference image' },
        transform: 'none',
        visible: false,
      },
    });

    expect(body).toContain('aria-hidden="true"');
    expect(body).toContain('visibility:hidden');
  });
});
