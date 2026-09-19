/// <reference types="node" />

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

function sourceFiles(root: string): string[] {
  return readdirSync(root).flatMap((name: string) => {
    const path = resolve(root, name);
    if (statSync(path).isDirectory()) return sourceFiles(path);
    return /\.(?:ts|svelte)$/.test(name) && !name.endsWith('.test.ts') ? [path] : [];
  });
}

describe('frontend architecture boundary', () => {
  it('keeps shared library modules independent of feature and migration code', () => {
    const root = resolve(process.cwd(), 'src/lib');
    const violations = sourceFiles(root).flatMap((path) => {
      const source = readFileSync(path, 'utf8');
      return /(?:from\s+|import\s*\()['"][^'"]*(?:features|v2)\//.test(source)
        ? [path.slice(root.length + 1)]
        : [];
    });

    expect(violations).toEqual([]);
  });

  it('keeps the shared image viewport registration outside a reactive effect', () => {
    const path = resolve(process.cwd(), 'src/features/assets/components/ImageViewport.svelte');
    const source = readFileSync(path, 'utf8');

    expect(source).toContain("import { ViewportRegistrationController } from '../state/viewportRegistration';");
    expect(source).toContain('use:registerViewport={controller}');
    expect(source).not.toContain('controller.setViewport(viewport)');
    expect(source).not.toContain('return () => controller.setViewport(null)');
  });
});
