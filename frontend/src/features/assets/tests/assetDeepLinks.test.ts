import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const assetsPage = readFileSync(resolve(process.cwd(), 'src/features/assets/components/AssetsPage.svelte'), 'utf8');
const admissionEvidence = readFileSync(
    resolve(process.cwd(), 'src/features/duplicates/components/DuplicateAdmissionEvidence.svelte'),
  'utf8',
);

describe('asset deep links', () => {
  it('opens and keeps the asset viewer synchronized with /assets/:assetId', () => {
    expect(assetsPage).toContain('assetIdFromPath');
    expect(assetsPage).toContain('assetViewerPath');
    expect(assetsPage).toContain('onpopstate={syncViewerFromLocation}');
    expect(assetsPage).toContain("setViewerUrl(id,'replace')");
    expect(assetsPage).toContain('syncViewerFromLocation()}catch');
  });

  it('opens linked duplicate admission sources in a new Assets viewer tab', () => {
    expect(admissionEvidence).toContain('href={assetViewerPath(admittedBy.asset.id)}');
    expect(admissionEvidence).toContain('target="_blank"');
    expect(admissionEvidence).toContain('rel="noopener noreferrer"');
    expect(admissionEvidence).not.toContain('oninspect');
  });
});
