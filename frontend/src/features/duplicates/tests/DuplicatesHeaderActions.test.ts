import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const pageSource = readFileSync(new URL('../components/DuplicatesPage.svelte', import.meta.url), 'utf8');
const stylesheet = readFileSync(new URL('../../../styles/duplicates.css', import.meta.url), 'utf8');

describe('duplicate mobile header actions', () => {
  it('keeps review actions as the primary header action', () => {
    expect(pageSource).toContain('class="v2-duplicates-header-primary"');
    expect(pageSource).toContain('variant="primary"');
    expect(pageSource).toContain('Review actions');
  });

  it('uses a narrow feature layout that gives each header action a full touch row', () => {
    expect(stylesheet).toContain('.v2-duplicates-header-actions');
    expect(stylesheet).toContain('grid-template-columns:minmax(0,1fr)');
    expect(stylesheet).toContain('.v2-duplicates-header-primary{order:-1}');
    expect(stylesheet).toContain('white-space:nowrap');
  });
});
