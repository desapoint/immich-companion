import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const pageSource = readFileSync(new URL('./V2DuplicatesPage.svelte', import.meta.url), 'utf8');
const admissionSource = readFileSync(
  new URL('../components/V2DuplicateAdmissionEvidence.svelte', import.meta.url),
  'utf8',
);

describe('V2 duplicate member tiles', () => {
  it('keeps the linked intermediate-count pill as a sibling overlay rather than nesting it in the compare button', () => {
    expect(pageSource).toContain('class="v2-duplicate-image-wrap"');
    expect(pageSource).toContain('</button><V2DuplicateAdmissionEvidence {member} members={item.members} mode={item.similarityValidationMode}/></div>');
    expect(pageSource).not.toContain('threshold={item.similarityThresholdPercent}');
  });

  it('keeps each available similarity percentage visible in the duplicate tile footer', () => {
    expect(pageSource).toContain('class="v2-duplicate-image-similarity">{formatSimilarityPercent(member.similarity)}');
    expect(pageSource).toContain('duplicateListMemberMeta(member.asset,null)');
    expect(pageSource).toContain('.v2-duplicate-image-meta-heading{display:flex;align-items:center;gap:6px;min-width:0}');
  });

  it('pins linked provenance to the top-left while stack state stays top-right', () => {
    expect(pageSource).toContain('.v2-duplicate-image-wrap{position:relative;width:100%}');
    expect(admissionSource).toContain('top:8px;left:8px');
    expect(pageSource).toContain('.v2-stack-primary-badge{position:absolute;z-index:3;top:8px;right:8px');
  });

  it('does not render list-level validation or match-type labels', () => {
    expect(admissionSource).not.toContain('similarityValidationEvidenceLabel');
    expect(admissionSource).not.toContain('Bounded validation');
    expect(admissionSource).not.toContain('Full-resolution validation');
    expect(admissionSource).not.toContain('Search-only appearance');
    expect(admissionSource).not.toContain('Validated at');
  });
});
