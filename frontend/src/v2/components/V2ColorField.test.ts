import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import V2ColorField from './V2ColorField.svelte';
import V2ColorSwatch from './V2ColorSwatch.svelte';

describe('V2ColorField', () => {
  it('renders a normalized current color as an accessible closed field', () => {
    const { body } = render(V2ColorField, { props: { id: 'tag-color-1', label: 'Color', value: '#9a78ff' } });

    expect(body).toContain('for="tag-color-1"');
    expect(body).toContain('id="tag-color-1"');
    expect(body).toContain('#9A78FF');
    expect(body).toContain('aria-haspopup="dialog"');
    expect(body).toContain('aria-expanded="false"');
  });

  it('renders the nullable and disabled states without exposing the popup', () => {
    const { body } = render(V2ColorField, { props: { id: 'tag-color-empty', label: 'Color', value: null, disabled: true } });

    expect(body).toContain('No color');
    expect(body).toContain('data-empty="true"');
    expect(body).toContain('data-disabled="true"');
    expect(body).toContain('disabled');
    expect(body).not.toContain('role="dialog"');
  });
});

describe('V2ColorSwatch', () => {
  it('normalizes colors and gives an empty swatch explicit semantics when requested', () => {
    expect(render(V2ColorSwatch, { props: { color: '#fff', decorative: false } }).body).toContain('aria-label="#FFFFFF"');
    const empty = render(V2ColorSwatch, { props: { color: null, decorative: false } }).body;
    expect(empty).toContain('aria-label="No color"');
    expect(empty).toContain('data-empty="true"');
  });
});
