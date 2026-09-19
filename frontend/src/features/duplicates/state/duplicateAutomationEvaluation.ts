import type { DuplicateDecision, DuplicateGroupRecord, DuplicateKeeperRule } from '../../../v2/data/contracts';
import { automationRuleValid } from './duplicateAutomationOptions';
import { chooseKeeper, ruleMatch } from './duplicateAutomationMatching';
import type { DuplicateAutomationDecision, DuplicateAutomationEvaluation, DuplicateAutomationExistingDecision, DuplicateAutomationUiRule } from './duplicateAutomationTypes';

function sameDecisionSet(left: readonly DuplicateAutomationExistingDecision[], right: readonly DuplicateAutomationDecision[]): boolean {
  const normalize = (items: readonly DuplicateAutomationExistingDecision[]) => items.map((item) => `${item.assetId}:${item.disposition}:${item.source}`).sort();
  const a = normalize(left); const b = normalize(right); return a.length === b.length && a.every((item, index) => item === b[index]);
}

export function evaluateDuplicateAutomation(group: DuplicateGroupRecord, rules: readonly DuplicateAutomationUiRule[], existing: readonly DuplicateAutomationExistingDecision[], keeperRules: readonly DuplicateKeeperRule[], overwriteManual = false): DuplicateAutomationEvaluation {
  const memberIds = group.members.map((member) => member.asset.id); const manual = new Map<string, DuplicateAutomationExistingDecision>();
  if (!overwriteManual) for (const decision of existing) if (decision.source === 'manual') manual.set(decision.assetId, decision);
  const automatic = new Map<string, DuplicateDecision>(); const lockedUndecided = new Set<string>(); let matched = false; let touchedByRule = false; let manualReview = false; let ambiguous = false; let matchedRuleCount = 0;
  const currentlyDecided = (id: string) => manual.has(id) || automatic.has(id) || lockedUndecided.has(id);
  for (const rule of rules) {
    if (!automationRuleValid(rule)) continue; const result = ruleMatch(group, rule); if (!result.matched) continue; matched = true; matchedRuleCount += 1;
    let targetIds = rule.target === 'matching_members' ? [...result.matchingMemberIds] : [...memberIds]; targetIds = targetIds.filter((id) => !currentlyDecided(id));
    if (rule.action === 'manual_review') { touchedByRule = true; manualReview = true; }
    else if (rule.action === 'leave_undecided') touchedByRule = true;
    else if (rule.action === 'resolve_keeper') { touchedByRule = true; const keeperId = chooseKeeper(group, targetIds, keeperRules); if (keeperId === null) { ambiguous = true; manualReview = true; } else for (const id of targetIds) automatic.set(id, id === keeperId ? 'keep' : 'delete'); }
    else if (targetIds.length) { touchedByRule = true; if (rule.action === 'delete') { const candidateDeletes = new Set([...manual.values()].filter((item) => item.disposition === 'delete').map((item) => item.assetId).concat([...automatic.entries()].filter(([, disposition]) => disposition === 'delete').map(([id]) => id), targetIds)); if (candidateDeletes.size >= memberIds.length) { ambiguous = true; manualReview = true; } else for (const id of targetIds) automatic.set(id, 'delete'); } else for (const id of targetIds) automatic.set(id, rule.action); }
    if (rule.flow === 'stop_affected') for (const id of targetIds) lockedUndecided.add(id); if (rule.flow === 'stop_group') break;
  }
  const decisions: DuplicateAutomationDecision[] = [
    ...[...manual.values()].map((item) => ({ assetId: item.assetId, disposition: item.disposition, source: 'manual' as const, status: item.status ?? 'pending' as const })),
    ...[...automatic.entries()].map(([assetId, disposition]) => ({ assetId, disposition, source: 'automatic' as const, status: 'pending' as const })),
  ];
  const decisionByAssetId = new Map(decisions.map((decision) => [decision.assetId, decision.disposition])); const hasDeletions = decisions.some((decision) => decision.disposition === 'delete'); const survivorIds = memberIds.filter((id) => decisionByAssetId.get(id) !== 'delete'); const metadataKeeperAssetId = hasDeletions && survivorIds.length === 1 ? survivorIds[0] : null;
  const touched = touchedByRule || manualReview; const complete = touched && decisions.length === memberIds.length; const partial = touched && decisions.length > 0 && decisions.length < memberIds.length; if (touched && decisions.length < memberIds.length) manualReview = true;
  return { matched, touched, persistDraft: touched && !sameDecisionSet(existing, decisions), complete, partial, manualReview, ambiguous, preservedManual: !overwriteManual && manual.size > 0, matchedRuleCount, keepCount: [...automatic.values()].filter((value) => value === 'keep').length, deleteCount: [...automatic.values()].filter((value) => value === 'delete').length, stackCount: [...automatic.values()].filter((value) => value === 'stack').length, undecidedCount: Math.max(0, memberIds.length - decisions.length), metadataKeeperAssetId, decisions };
}
