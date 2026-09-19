import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';
import { V2ToastController } from '../state/toasts.svelte';
import V2ToastViewport from './V2ToastViewport.svelte';

describe('V2ToastViewport', () => {
  it('renders multiple notifications in chronological DOM order at the configured anchor', () => {
    const controller = new V2ToastController('top-left');
    controller.push({ tone: 'success', title: 'First action', message: 'Completed.', durationMs: 0 });
    controller.push({ tone: 'warning', title: 'Second action', message: 'Needs review.', durationMs: 0 });
    const { body } = render(V2ToastViewport, { props: { controller } });
    expect(body).toContain('data-position="top-left"');
    expect(body).toContain('role="status"');
    expect(body.indexOf('First action')).toBeLessThan(body.indexOf('Second action'));
    controller.destroy();
  });

  it('uses alert semantics for errors', () => {
    const controller = new V2ToastController();
    controller.push({ tone: 'error', title: 'Action failed', message: 'Try again.', durationMs: 0 });
    expect(render(V2ToastViewport, { props: { controller } }).body).toContain('role="alert"');
    controller.destroy();
  });
});
