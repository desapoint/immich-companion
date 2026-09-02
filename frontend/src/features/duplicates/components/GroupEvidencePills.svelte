<script lang="ts">
  import type { DuplicateMember } from '../types/duplicates';

  interface Props {
    member: DuplicateMember;
    analysisPending: boolean;
  }

  let { member, analysisPending }: Props = $props();
  const evidence = $derived(member.evidence);
  const isSimilarityReference = $derived(member.similarity?.state === 'reference');
  const integrityLabel = $derived.by(() => {
    if (evidence.analysis_freshness !== 'current') {
      return analysisPending ? 'Analyzing' : evidence.analysis_freshness === 'stale' ? 'Stale' : 'Not analyzed';
    }
    return ({
      healthy: 'Healthy',
      warning: 'Warning',
      malformed: 'Malformed',
      hash_only: 'Hash only',
    } as const)[evidence.integrity_status ?? 'hash_only'];
  });
  const integrityTone = $derived(
    evidence.analysis_freshness !== 'current'
      ? analysisPending ? 'pending' : 'neutral'
      : evidence.integrity_status === 'malformed'
        ? 'negative'
        : evidence.integrity_status === 'warning'
          ? 'warning'
          : evidence.integrity_status === 'healthy'
            ? 'positive'
            : 'neutral',
  );
  const decodeLabel = $derived(
    evidence.decode_supported === false
      ? 'No decoder'
      : evidence.decode_valid === true
        ? 'Decoded'
        : evidence.decode_valid === false
          ? 'Decode failed'
          : null,
  );
</script>

<div class="evidence-pills" aria-label={`Evidence for ${member.original_file_name}`}>
  <span class={`pill ${integrityTone}`} title={evidence.issue_codes.join('\n') || integrityLabel}>{integrityLabel}</span>
  <span class={`pill match ${member.verification}`}>{member.verification === 'matching' ? 'Byte match' : member.verification === 'mismatch' ? 'Different bytes' : 'Unverified'}</span>
  {#if evidence.detected_format}
    <span class="pill neutral">{evidence.detected_format.toUpperCase()}</span>
  {/if}
  {#if decodeLabel}
    <span class:negative={evidence.decode_valid === false} class:positive={evidence.decode_valid === true} class="pill">{decodeLabel}</span>
  {/if}
  {#if !isSimilarityReference && member.similarity?.state === 'current'}
    <span class="pill positive">{member.similarity.similarity_percent?.toFixed(1)}% vs reference</span>
  {:else if !isSimilarityReference && member.similarity?.state === 'pending'}
    <span class="pill pending">Similarity pending</span>
  {/if}
  {#if !isSimilarityReference && member.similarity?.exact_pixel_match}
    <span class="pill positive">Pixel match</span>
  {/if}
  {#if member.preservation}
    <span class="pill neutral">{member.preservation.decoded_width}×{member.preservation.decoded_height}</span>
    {#if member.preservation.icc_profile_present}<span class="pill neutral">ICC</span>{/if}
    {#if member.preservation.has_alpha}<span class="pill neutral">Alpha</span>{/if}
  {/if}
</div>

<style>
  .evidence-pills { display: flex; min-width: 0; flex-wrap: wrap; gap: .28rem; }
  .pill { max-width: 100%; overflow: hidden; padding: .18rem .38rem; border-radius: 999px; color: var(--color-ink-muted); background: var(--color-surface-soft); font-size: .57rem; font-weight: 780; line-height: 1.2; text-overflow: ellipsis; white-space: nowrap; }
  .positive, .match.matching { color: var(--color-positive-ink); background: var(--color-positive-surface); }
  .warning, .pending { color: var(--color-warning-ink); background: var(--color-warning-surface); }
  .negative, .match.mismatch { color: var(--color-negative-ink); background: var(--color-negative-surface); }
</style>
