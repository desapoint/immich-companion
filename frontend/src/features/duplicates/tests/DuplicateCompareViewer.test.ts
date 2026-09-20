import { readFileSync } from 'node:fs';
import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import type { DuplicateAdmissionEvidence, DuplicateMemberRecord } from '../types/contracts';
import type { ComparisonMemberData } from '../types/duplicateMember';
import DuplicateCompareViewer from '../components/DuplicateCompareViewer.svelte';
import DuplicateComparisonDetails from '../components/DuplicateComparisonDetails.svelte';

const viewerSource = [
  readFileSync(new URL('../components/DuplicateCompareViewer.svelte', import.meta.url), 'utf8'),
  readFileSync(new URL('../components/DuplicateComparisonDetails.svelte', import.meta.url), 'utf8'),
].join('\n');

function buttonWithText(body: string, text: string): string {
  return [...body.matchAll(/<button\b[^>]*>[\s\S]*?<\/button>/g)]
    .map((match) => match[0])
    .find((button) => button.includes(text)) ?? '';
}

function admission(overrides: Partial<DuplicateAdmissionEvidence> = {}): DuplicateAdmissionEvidence {
  return {
    admittedByAssetId: 'asset-2',
    admissionSimilarityPercent: 91.36,
    bestGroupMatchAssetId: 'asset-3',
    bestGroupMatchSimilarityPercent: 94.08,
    linkDepth: 1,
    modelVersion: 'appearance-v3',
    featureVersion: 5,
    comparisonVersion: 3,
    configFingerprint: 'fingerprint-123',
    ...overrides,
  };
}

function groupMember(
  id: string,
  name: string,
  similarity: number | null,
  admissionEvidence: DuplicateAdmissionEvidence | null = null,
): DuplicateMemberRecord {
  return {
    asset: { id, original_file_name: name } as DuplicateMemberRecord['asset'],
    similarity,
    similarityEvidence: null,
    admission: admissionEvidence,
  };
}

describe('DuplicateCompareViewer', () => {
  it('uses the shared decision controls with a layout-stable stack primary action', () => {
    const { body } = render(DuplicateCompareViewer, {
      props: {
        open: true,
        groupTitle: 'IMG_1234.JPG and 2 more',
        groupKind: 'similar',
        groupSimilarity: 96.456,
        assetIds: ['asset-1'],
        similarities: { 'asset-1': 97.2 },
        similarityEvidence: {
          'asset-1': {
            structuralPercent: 98.126,
            perceptualPercent: 96.9,
            colorPercent: 92.4,
            detailChangedPercent: 2.345,
            detailSource: 'original',
          },
        },
        decisions: { 'asset-1': 'stack' },
        decisionOptions: ['keep', 'delete', 'stack'],
        stackLabel: 'Stack 1',
        stackPrimary: true,
        selectedForReview: true,
        onclose: () => {},
      },
    });

    expect(body).toContain('IMG_1234.JPG and 2 more');
    expect(body).toContain('Appearance match');
    expect(body).toContain('Group similarity');
    expect(body).toContain('96.46%');
    expect(body).toContain('Similarity to reference');
    expect(body).toContain('Structure');
    expect(body).toContain('98.13%');
    expect(body).toContain('Perceptual hash');
    expect(body).toContain('96.90%');
    expect(body).toContain('Color');
    expect(body).toContain('92.40%');
    expect(body).toContain('Aligned detail changed area');
    expect(body).toContain('2.35%');
    expect(body).toContain('Detail evidence');
    expect(body).toContain('Original');
    expect(body).toContain('Difference shows displayed-pixel changes');
    expect(body).toContain('Local changes deliberately keeps the raw original-coordinate grid');
    expect(body).not.toContain('Similarity engine');
    expect(body).toContain('data-decision="stack"');
    expect(body).toContain('Stack 1');
    expect(body).toContain('Stack primary');
    expect(body).toContain('Selected for review');
    expect(body).toContain('Clear selection');
    expect(body).toContain('Property');
    expect(body).toContain('Selected');
    expect(body).toContain('Reference');
    expect(body).toContain('v2-compare-header-zone');
    expect(body).toContain('v2-compare-detail-scroll');
    expect(body).toContain('v2-compare-metadata-detail');
    expect(body.match(/<details[^>]*v2-compare-metadata-detail[^>]*>/)?.[0] ?? '').toContain('open');
    expect(body.indexOf('data-decision="stack"')).toBeLessThan(body.indexOf('Clear selection'));
    expect(body).not.toContain('Technical group ID');
  });

  it('shows unaligned and aligned detail scores when frame alignment was applied', () => {
    const member = (name: string, similarity: string): ComparisonMemberData => ({
      name,
      source: 'Immich uploads',
      size: '4 MB',
      sizeBytes: 4_000_000,
      dims: '4000 × 3000',
      taken: '—',
      codec: 'image/jpeg',
      library: 'Immich uploads',
      libraryId: null,
      folder: '/',
      uploaded: '—',
      similarity,
    });
    const { body } = render(DuplicateComparisonDetails, {
      props: {
        selectedData: member('selected.jpg', '97.20%'),
        referenceData: member('reference.jpg', '100.00%'),
        assetIds: ['selected-id', 'reference-id'],
        metadataRows: [],
        hasIndirectLinkedAdmission: false,
        selectedAdmission: null,
        admittedByMember: null,
        admittedByLabel: '—',
        bestGroupMatchLabel: '—',
        intermediateImageCount: 0,
        modeLabel: 'Linked',
        thresholdLabel: '60.00%',
        selectedSimilarity: 97.2,
        belowThreshold: false,
        selectedEvidence: {
          structuralPercent: 98,
          perceptualPercent: 97,
          colorPercent: 96,
          detailChangedPercent: 3.5,
          detailSource: 'original',
        },
        validationEvidenceLabel: 'Full-resolution validation',
        boundedValidation: false,
        selectedValidatedDimensions: '2048 × 1536',
        referenceValidatedDimensions: '2048 × 1536',
        sizeDifferenceLabel: '0 B',
        sameResolution: true,
        sameSourceCollection: true,
        folderScopeLabel: 'Folder',
        foldersComparable: true,
        sameFolder: true,
        localDiagnostics: {
          available: true,
          selectedAssetId: 'selected-id',
          referenceAssetId: 'reference-id',
          changedPercent: 18.25,
          localizedChangedPercent: 55,
          coherentChangedPercent: 12,
          largestChangedRegionPercent: 8,
          substantialRegionCount: 1,
          alignedChangedPercent: 3.5,
          rawSimilarityPercent: 88.4,
          alignedSimilarityPercent: 97.2,
          alignmentApplied: true,
          alignmentShiftPercent: 3.12,
          alignmentOverlapPercent: 94.2,
          rows: 2,
          columns: 2,
          cells: [[0, 10], [25, 40]],
          source: 'original',
        },
        localDiagnosticsLoading: false,
        showMemberById: () => {},
      },
    });

    expect(body).toContain('Frame alignment');
    expect(body).toContain('Applied');
    expect(body).toContain('Unaligned detail score');
    expect(body).toContain('88.40%');
    expect(body).toContain('Aligned detail score');
    expect(body).toContain('97.20%');
  });

  it('lets the page handle a decision before mutating the bound decision map', () => {
    expect(viewerSource).toContain('if (ondecisionchange) ondecisionchange(decisionKey, decision);');
    expect(viewerSource).toContain('else decisions = { ...decisions, [decisionKey]: decision };');
    expect(viewerSource.indexOf('if (ondecisionchange) ondecisionchange(decisionKey, decision);'))
      .toBeLessThan(viewerSource.indexOf('else decisions = { ...decisions, [decisionKey]: decision };'));
  });

  it('shows actual bounded validation dimensions without implying full-resolution proof', () => {
    const { body } = render(DuplicateCompareViewer, {
      props: {
        open: true,
        groupTitle: 'Oversized comparison',
        groupKind: 'similar',
        groupSimilarity: 98.72,
        assetIds: ['asset-1', 'asset-2'],
        similarities: { 'asset-1': 98.72, 'asset-2': 100 },
        similarityEvidence: {
          'asset-1': {
            structuralPercent: 99,
            perceptualPercent: 98,
            colorPercent: 97,
            detailChangedPercent: 1.2,
            detailSource: 'preview',
            validatedWidth: 4096,
            validatedHeight: 2276,
            referenceValidatedWidth: 3840,
            referenceValidatedHeight: 2160,
          },
        },
        member: 0,
        reference: 1,
        onclose: () => {},
      },
    });

    expect(body).toContain('98.72%');
    expect(body).toContain('Bounded validation');
    expect(body).toContain('Validated at');
    expect(body).toContain('4096 × 2276');
    expect(body).toContain('3840 × 2160');
    expect(body).toContain('actual rendition dimensions used');
    expect(body).toContain('not full-resolution or destructive proof');
  });

  it('explains linked admission even when similarity to the reference was not calculated', () => {
    const linked = groupMember('asset-1', 'linked.png', null, admission({
      admissionSimilarityPercent: 82.34,
      bestGroupMatchSimilarityPercent: 83.07,
      linkDepth: 2,
    }));
    const bridge = groupMember('asset-2', 'bridge.heic', 82.34);
    const best = groupMember('asset-3', 'best-match.heic', 83.07);
    const { body } = render(DuplicateCompareViewer, {
      props: {
        open: true,
        groupTitle: 'Linked comparison',
        groupKind: 'similar',
        groupSimilarity: 82.22,
        groupMembers: [linked, bridge, best],
        validationMode: 'linked',
        similarityThreshold: 82,
        assetIds: ['asset-1', 'asset-2', 'asset-3'],
        similarities: { 'asset-1': null, 'asset-2': 82.34, 'asset-3': 83.07 },
        member: 0,
        reference: 1,
        onclose: () => {},
      },
    });

    expect(body).toContain('Group minimum');
    expect(body).toContain('Not calculated');
    expect(body).toContain('Included through bridge.heic');
    expect(body).toContain('82.34% admission similarity');
    expect(body).toContain('Why is this image in the group?');
    expect(body).toContain('Admitted through');
    expect(body).toContain('bridge.heic');
    expect(buttonWithText(body, 'bridge.heic')).toContain('v2-compare-member-link');
    expect(buttonWithText(body, 'bridge.heic')).toContain('Select admitted-through asset bridge.heic in the comparison viewer');
    expect(body).toContain('Best group match');
    expect(body).toContain('best-match.heic');
    expect(body).toContain('83.07%');
    expect(body).toContain('Images in between');
    expect(body).toContain('>2</b>');
    expect(body).toContain('does not count either endpoint');
    expect(body).toContain('Changing the comparison reference does not rewrite the stored admission chain');
    expect(body).not.toContain('Link depth');
    expect(body).toContain('Technical linked data');
    expect(body).toContain('fingerprint-123');
    expect(body.indexOf('Metadata side by side')).toBeLessThan(body.indexOf('Why is this image in the group?'));
  });

  it('wires the admitted-through control to select that asset in the current viewer', () => {
    expect(viewerSource).toContain('onclick={() => showMemberById(admittedByMember.asset.id)}');
    expect(viewerSource).toContain('function showMemberById(assetId: string)');
    expect(viewerSource).toContain('const target = viewerSelectionTargetId(assetIds, assetId)');
  });

  it('does not describe a direct reference admission as a linked membership', () => {
    const direct = groupMember('asset-1', 'direct.png', 96, admission({
      admittedByAssetId: 'asset-2',
      admissionSimilarityPercent: 96,
      bestGroupMatchAssetId: 'asset-3',
      bestGroupMatchSimilarityPercent: 99,
      linkDepth: 0,
    }));
    const reference = groupMember('asset-2', 'reference.heic', 100);
    const stronger = groupMember('asset-3', 'stronger.heic', 99);
    const { body } = render(DuplicateCompareViewer, {
      props: {
        open: true,
        groupTitle: 'Direct comparison',
        groupKind: 'similar',
        groupSimilarity: 96,
        groupMembers: [direct, reference, stronger],
        validationMode: 'linked',
        similarityThreshold: 95,
        assetIds: ['asset-1', 'asset-2', 'asset-3'],
        similarities: { 'asset-1': 96, 'asset-2': 100, 'asset-3': 99 },
        member: 0,
        reference: 1,
        onclose: () => {},
      },
    });

    expect(body).not.toContain('Included through');
    expect(body).not.toContain('Why is this image in the group?');
    expect(body).not.toContain('Technical linked data');
  });

  it('renders duplicate-group navigation and wires Shift+Arrow keyboard shortcuts', () => {
    const { body } = render(DuplicateCompareViewer, {
      props: {
        open: true,
        groupTitle: 'Group navigation',
        groupKind: 'similar',
        assetIds: ['asset-1', 'asset-2'],
        canPreviousGroup: true,
        canNextGroup: true,
        ongroupnavigate: async () => {},
        onclose: () => {},
      },
    });

    expect(buttonWithText(body, 'Previous group')).not.toContain('disabled');
    expect(buttonWithText(body, 'Next group')).not.toContain('disabled');
    expect(body).toContain('Previous duplicate group');
    expect(body).toContain('Next duplicate group');
    expect(viewerSource).toContain("event.shiftKey && event.key === 'ArrowLeft'");
    expect(viewerSource).toContain("void navigateGroup('previous')");
    expect(viewerSource).toContain("event.shiftKey && event.key === 'ArrowRight'");
    expect(viewerSource).toContain("void navigateGroup('next')");
  });

  it('keeps inspection navigation enabled while write controls are disabled', () => {
    const { body } = render(DuplicateCompareViewer, {
      props: {
        open: true,
        groupTitle: 'Read-only comparison',
        groupKind: 'similar',
        assetIds: ['asset-1'],
        decisions: { 'asset-1': 'stack' },
        decisionOptions: ['keep', 'delete', 'stack'],
        disabled: true,
        onrevalidate: async () => {},
        onclose: () => {},
      },
    });

    expect(buttonWithText(body, '← Previous image')).not.toContain('disabled');
    expect(buttonWithText(body, 'Next image →')).not.toContain('disabled');
    expect(buttonWithText(body, 'Revalidate from reference')).toContain('disabled');
    expect(buttonWithText(body, 'Clear selection')).toContain('disabled');
    expect(buttonWithText(body, 'Keep')).toContain('disabled');
    expect(buttonWithText(body, 'Delete')).toContain('disabled');
    expect(buttonWithText(body, 'Stack')).toContain('disabled');
  });
});
