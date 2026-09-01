import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import DuplicateDispositionControls from './DuplicateDispositionControls.svelte';
import StackPrimaryControl from './StackPrimaryControl.svelte';

describe('duplicate disposition controls', () => {
  it('shows one explicit selected choice per image', () => {
    const { body } = render(DuplicateDispositionControls, { props: { value: 'delete' } });

    expect(body).toContain('>Keep<');
    expect(body).toContain('>Delete<');
    expect(body).toContain('>Stack<');
    expect(body).toMatch(/aria-pressed="true" class="[^"]*active delete"/);
  });

  it('requires the Stack disposition before primary selection', () => {
    const unavailable = render(StackPrimaryControl, {
      props: { eligible: false, selected: false },
    }).body;
    const selected = render(StackPrimaryControl, {
      props: { eligible: true, selected: true },
    }).body;

    expect(unavailable).toContain('disabled');
    expect(unavailable).toContain('Choose Stack first');
    expect(selected).not.toContain('disabled');
    expect(selected).toContain('aria-pressed="true"');
    expect(selected).toContain('Stack main');
  });

  it('supports an icon-only stack-primary control for media overlays', () => {
    const body = render(StackPrimaryControl, {
      props: { eligible: true, selected: false, iconOnly: true },
    }).body;

    expect(body).toContain('aria-label="Make stack main"');
    expect(body).toMatch(/class="[^\"]*icon-only/);
    expect(body).toMatch(/class="[^\"]*visually-hidden/);
  });
});
