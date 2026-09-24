import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const source = readFileSync(new URL('../components/DuplicatesPage.svelte', import.meta.url), 'utf8');
const historyDetailSource = readFileSync(new URL('../components/DuplicateHistoryDetail.svelte', import.meta.url), 'utf8');

describe('V2DuplicatesPage evidence controls', () => {
  it('mounts evidence generation only in Rules & discovery', () => {
    expect(source).toContain("{#if tab==='Rules & discovery'}<V2SimilarityEvidenceGenerationPanel/>{/if}");
    expect(source).not.toContain("{#if tab!=='Resolution history'}<V2SimilarityEvidenceGenerationPanel/>{/if}");
  });

  it('keeps the review confirmation mounted until reconciliation finishes', () => {
    const confirmation = source.indexOf('await operations.waitForReconciliation();historyLoadedRange=null;pendingReview=null');
    const apply = source.indexOf('await applyGroupDecisionSet(review.groupId,review.plan)');
    expect(confirmation).toBeGreaterThan(apply);
    expect(source).toContain("pendingLabel={operations.phase==='reconciling'?'Refreshing results…':'Applying actions…'}");
    expect(source).toContain('icon="check" size="lg"');
    expect(source).toContain('<DuplicateReviewProgress phase={reviewConfirmationPhase}/>');
  });

  it('shows continuous preparation progress and blocks collection navigation for stack issues', () => {
    expect(source).toContain("planPreparing=true;reviewProgressPhase='saving'");
    expect(source).toContain("reviewProgressPhase='planning'");
    expect(source).toContain('<DuplicateReviewProgress phase={reviewProgressPhase} overlay={true}/>');
    expect(source).toContain('function setPage(value:number){if(blockForReviewIssue())return;');
    expect(source).toContain('async function loadMore(){if(!nextCursor||groupRequests.loading||blockForReviewIssue())return;');
  });

  it('renders a persistent issue notice with a focusable group anchor', () => {
    expect(source).toContain('<DuplicateReviewIssueNotice issue={reviewIssue}');
    expect(source).toContain('onview={()=>viewReviewIssue(reviewIssue)}');
    expect(source).toContain('onkeep={()=>keepReviewIssue(reviewIssue)}');
    expect(source).toContain('id={duplicateGroupAnchorId(item.id)}');
    expect(source).toContain('tabindex="-1"');
  });

  it('lazy-loads hidden duplicate tabs and scopes their errors', () => {
    const mount = source.slice(source.indexOf('onMount(()=>'), source.indexOf('</script>'));
    expect(mount).not.toContain('void refreshHistory();');
    expect(mount).not.toContain('void refreshCacheStatus();');
    expect(mount).toContain("if(tab==='Resolution history')void refreshHistory(false)");
    expect(source).toContain("if(tab==='Resolution history')void refreshHistory(false)");
    expect(source).toContain("else if(tab==='Rules & discovery')void refreshCacheStatus(false)");
    expect(source).toContain("loadError=$derived(tab==='Review'?groupRequests.error:tab==='Resolution history'?historyRequests.error:'')");
    expect(source).toContain('error={cacheError}');
  });

  it('passes the selected history row to detail and resolves active assets before trash', () => {
    expect(source).toContain('onselect={(row)=>historyDetail=row}');
    expect(source).toContain('resolution={historyDetail}');
    expect(historyDetailSource).not.toContain('duplicateResolutionHistoryDetail');
    expect(historyDetailSource).toContain('resolveDuplicateHistoryAssets(resolution.memberAssetIds, libraryData.assets)');
  });
});
