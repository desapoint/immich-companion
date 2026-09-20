import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const pageSource = readFileSync(new URL('../components/DuplicatesPage.svelte', import.meta.url), 'utf8');

describe('duplicate bulk-action scope', () => {
  it('switches to all matching after selecting every group', () => {
    expect(pageSource).toContain('selectedGroups=[...await libraryData.duplicates.selectAllGroups()];\n      selectionScope=\'All matching\';');
  });

  it('switches to all matching after keeper automation updates the selection', () => {
    expect(pageSource).toContain("selectedGroups=[...libraryData.duplicates.selectedGroupIds()];selectionScope='All matching';reviewFilter='Selected'");
  });
});
