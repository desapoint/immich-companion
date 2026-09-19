import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const pageSource = readFileSync(new URL('../components/DuplicatesPage.svelte', import.meta.url), 'utf8');

describe('V2 duplicate viewer group navigation wiring', () => {
  it('passes group navigation state and callback into the comparison viewer', () => {
    expect(pageSource).toContain('{canPreviousGroup} {canNextGroup} {groupNavigationLoading} ongroupnavigate={navigateCompareGroup}');
    expect(pageSource).toContain('duplicateViewerGroupNavigationPlan');
  });

  it('passes the current group review-selection state into the comparison viewer', () => {
    expect(pageSource).toContain('selectedForReview={selectedGroups.includes(group)}');
  });

  it('loads adjacent pagination pages before activating the boundary group', () => {
    expect(pageSource).toContain("else if(plan.kind==='page')");
    expect(pageSource).toContain('collection.setPage(plan.page)');
    expect(pageSource).toContain('const loaded=await refreshGroups(true,true)');
    expect(pageSource).toContain("target=plan.edge==='first'?groups[0]:groups[groups.length-1]");
  });

  it('loads the next infinite batch before activating the first newly appended group', () => {
    expect(pageSource).toContain("else{\n        const before=groups.length;\n        await loadMore();");
    expect(pageSource).toContain('target=groups[plan.index]??groups[before]');
  });

  it('reuses the normal comparison activation path after group navigation', () => {
    expect(pageSource).toContain('function activateCompareGroup(item:DuplicateGroupRecord,index=0)');
    expect(pageSource).toContain('if(target)activateCompareGroup(target,0)');
  });
});
