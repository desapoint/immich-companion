import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const pageSource = readFileSync(new URL('../components/DuplicatesPage.svelte', import.meta.url), 'utf8');
const controllerSource = readFileSync(new URL('../state/duplicateDiscoveryController.ts', import.meta.url), 'utf8');

describe('V2 duplicate retained match limit', () => {
  it('defaults the retained similarity match limit to 5000', () => {
    expect(pageSource).toContain("maximumMatches=$state('5000')");
    expect(controllerSource).toContain('Number(current.maximumMatches) || 5000');
  });

  it('places the control with the discovery bounding settings and allows up to 50000', () => {
    expect(pageSource).toContain('label="Comparison candidates per image"');
    expect(pageSource).toContain('label="Maximum retained similarity matches"');
    expect(pageSource.indexOf('label="Comparison candidates per image"'))
      .toBeLessThan(pageSource.indexOf('label="Maximum retained similarity matches"'));
    expect(pageSource).toContain('max={50000}');
    expect(pageSource).toContain('defaults to 5,000 and can be raised to 50,000');
  });

  it('persists and sends the normalized retained match limit', () => {
    expect(controllerSource).toContain('Math.min(50_000, Math.max(1');
    expect(controllerSource).toContain('maximumMatches: normalizedMaximumMatches');
    expect(controllerSource).toContain('maximumMatches: String(saved.maximumMatches)');
  });

  it('shows a clear final badge for whether the retention cap was actually exceeded', () => {
    expect(pageSource).toContain("text={discoveryRetention.reached?'Retention limit reached':'Retention limit not reached'}");
    expect(pageSource).toContain("tone={discoveryRetention.reached?'bad':'ok'}");
    expect(pageSource).toContain('additional qualifying matches were found and not retained');
  });
});
