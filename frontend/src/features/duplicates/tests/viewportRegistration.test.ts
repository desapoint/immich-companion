import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it, vi } from 'vitest';
import { createViewportAttachment } from '../state/comparisonViewportAttachment';

describe('createViewportAttachment', () => {
  it('registers the exact viewport node and clears it on detach', () => {
    const node = {} as HTMLElement;
    const registered: HTMLElement[] = [];
    const register = vi.fn((value: HTMLElement | null) => {
      if (value) registered.push(value);
    });
    const attachment = createViewportAttachment(register);

    const cleanup = attachment(node);
    expect(registered).toEqual([node]);
    expect(register).toHaveBeenCalledWith(node);

    cleanup?.();
    expect(register).toHaveBeenLastCalledWith(null);
  });

  it('observes resize and disconnects the observer when detached', () => {
    const node = {} as HTMLElement;
    const disconnect = vi.fn();
    const observe = vi.fn();
    const ResizeObserverMock = vi.fn(function (this: ResizeObserver) {
      Object.assign(this, { disconnect, observe });
    });
    vi.stubGlobal('ResizeObserver', ResizeObserverMock);
    const onresize = vi.fn();

    const cleanup = createViewportAttachment(vi.fn(), onresize)(node);
    expect(observe).toHaveBeenCalledWith(node);
    expect(onresize).toHaveBeenCalledTimes(1);

    cleanup?.();
    expect(disconnect).toHaveBeenCalledTimes(1);
    vi.unstubAllGlobals();
  });

  it('keeps localized viewport registration outside the attachment effect graph', () => {
    const attachmentSource = readFileSync(
      fileURLToPath(new URL('../state/comparisonViewportAttachment.ts', import.meta.url)),
      'utf8',
    );
    const localizedSource = readFileSync(
      fileURLToPath(new URL('../components/DuplicateLocalChangesComparison.svelte', import.meta.url)),
      'utf8',
    );

    expect(attachmentSource).toContain("import { untrack } from 'svelte';");
    expect(attachmentSource).toContain('untrack(() => register(node))');
    expect(attachmentSource).toContain('if (onresize) untrack(onresize)');
    expect(localizedSource).toContain('let viewport: HTMLElement | null = null;');
    expect(localizedSource).not.toContain('let viewport = $state<HTMLElement | null>(null);');
  });
});
