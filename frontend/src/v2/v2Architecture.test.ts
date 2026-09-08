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

describe('V2 architecture boundary', () => {
  it('does not import feature-owned V1 modules', () => {
    const root = resolve(process.cwd(), 'src/v2');
    const violations = sourceFiles(root).flatMap((path) => {
      const source = readFileSync(path, 'utf8');
      return /(?:from\s+|import\s*\()['"][^'"]*features\//.test(source)
        ? [path.slice(root.length + 1)]
        : [];
    });

    expect(violations).toEqual([]);
  });
});
