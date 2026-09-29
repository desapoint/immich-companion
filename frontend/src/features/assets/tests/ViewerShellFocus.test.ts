import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const viewerShell = readFileSync(
  resolve(process.cwd(), 'src/features/assets/components/ViewerShell.svelte'),
  'utf8',
);

describe('viewer keyboard focus', () => {
  it('moves focus into the viewer when the dialog opens and restores it on close', () => {
    expect(viewerShell).toContain('tabindex="-1"');
    expect(viewerShell).toContain('use:focusViewer');
    expect(viewerShell).toContain('node.focus({ preventScroll: true })');
    expect(viewerShell).toContain('previousFocus?.isConnected');
    expect(viewerShell).toContain('previousFocus.focus({ preventScroll: true })');
  });
});
