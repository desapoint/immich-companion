import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const viewerSource = readFileSync(
  new URL('../components/SimilarityDebugCompareViewer.svelte', import.meta.url),
  'utf8',
);

describe('SimilarityDebugCompareViewer', () => {
  it('keeps localized diagnostics in Local changes mode instead of duplicating them in the sidebar', () => {
    expect(viewerSource).toContain("const localDiagnostics = $derived(toLocalDiagnostics(pair));");
    expect(viewerSource).toContain('{localDiagnostics}');
    expect(viewerSource).toContain("'5': 'Local changes'");
    expect(viewerSource).not.toContain('title="Localized detail diagnostics"');
    expect(viewerSource).not.toContain('similarity-debug-cell-grid');
  });

  it('shows compact green or red badges for every pair-local stop gate', () => {
    for (const label of [
      'Evidence available',
      'Final similarity',
      'Candidate gates',
      'Score threshold',
      'Pair-local pipeline',
      'pHash distance',
      'Aspect difference',
    ]) {
      expect(viewerSource).toContain(label);
    }

    expect(viewerSource).toContain("tone={pair.evidence_available ? 'ok' : 'bad'}");
    expect(viewerSource).toContain("tone={pair.candidate_pair_pass ? 'ok' : 'bad'}");
    expect(viewerSource).toContain("tone={pair.similarity_threshold_pass ? 'ok' : 'bad'}");
    expect(viewerSource).toContain("tone={pair.would_pass_pair_pipeline ? 'ok' : 'bad'}");
    expect(viewerSource).toContain("tone={pair.perceptual_gate_pass ? 'ok' : 'bad'}");
    expect(viewerSource).toContain("tone={pair.aspect_gate_pass ? 'ok' : 'bad'}");
    expect(viewerSource).not.toContain("tone={pair.would_pass_pair_pipeline ? 'ok' : 'warn'}");
  });
});
