<script lang="ts">
  import { formatBytes } from '../../lib/utils/fileSize';
  import type { SimilarityCacheKind, SimilarityCacheStatus } from '../data/contracts';
  import V2Badge from './V2Badge.svelte';
  import V2Button from './V2Button.svelte';
  import V2Card from './V2Card.svelte';
  import V2Inline from './V2Inline.svelte';
  import V2Stack from './V2Stack.svelte';

  let { status, loading=false, onrefresh, onclear }: {
    status: SimilarityCacheStatus|null;
    loading?: boolean;
    onrefresh:()=>void;
    onclear:(cache:SimilarityCacheKind)=>void;
  }=$props();

  const ratio=(hits:number,misses:number)=>hits+misses?`${Math.round(hits/(hits+misses)*100)}% hit`:'No requests yet';
</script>

<V2Card title="Similarity cache">
  <V2Stack gap="md">
    {#if status}
      <V2Inline gap="sm" wrap={true}>
        <V2Badge text={`${status.featureCount.toLocaleString()} durable features`}/>
        <V2Badge text={`Config ${status.configFingerprint.slice(0,8)}`}/>
        {#if status.referenceLatencyP95Ms!==null}<V2Badge text={`Reference p95 ${status.referenceLatencyP95Ms.toLocaleString()} ms`}/>{/if}
      </V2Inline>
      <div class="v2-cache-grid">
        <section>
          <b>Preview LRU</b>
          <span>{formatBytes(status.previews.usedBytes)} / {formatBytes(status.previews.maxBytes)}</span>
          <small>{status.previews.entryCount.toLocaleString()} files · {ratio(status.previews.hits,status.previews.misses)}</small>
          <V2Button disabled={loading||status.previews.entryCount===0} onclick={()=>onclear('previews')}>Clear previews</V2Button>
        </section>
        <section>
          <b>Pair results</b>
          <span>{formatBytes(status.pairEstimatedBytes)} / {formatBytes(status.pairMaxBytes)}</span>
          <small>{status.pairCount.toLocaleString()} pairs · {ratio(status.pairHits,status.pairMisses)}</small>
          <V2Button disabled={loading||status.pairCount===0} onclick={()=>onclear('pairs')}>Clear pair results</V2Button>
        </section>
        <section>
          <b>Hot groups</b>
          <span>{formatBytes(status.hotEstimatedBytes)} / {formatBytes(status.hotMaxBytes)}</span>
          <small>{status.hotCount.toLocaleString()} pairs · {ratio(status.hotHits,status.hotMisses)}</small>
          <V2Button disabled={loading||status.hotCount===0} onclick={()=>onclear('hot')}>Clear memory cache</V2Button>
        </section>
        <section>
          <b>Decode workspace</b>
          <span>{formatBytes(status.decode.usedBytes)} / {formatBytes(status.decode.maxBytes)}</span>
          <small>{status.decode.healthy?'Writable':'Unavailable'} · {status.decode.cleanupFailures.toLocaleString()} cleanup failures</small>
          <V2Button disabled={loading||status.decode.entryCount===0} onclick={()=>onclear('decode')}>Clear abandoned files</V2Button>
        </section>
      </div>
      <small class="v2-muted">Clearing disposable previews or pair results does not remove durable Appearance features, review decisions, or history.</small>
    {:else}
      <span class="v2-muted">Cache telemetry is unavailable for this data source.</span>
    {/if}
    <V2Button disabled={loading} onclick={onrefresh}>{loading?'Refreshing cache…':'Refresh cache status'}</V2Button>
  </V2Stack>
</V2Card>

<style>
  .v2-cache-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}
  section{display:flex;flex-direction:column;gap:7px;padding:12px;border:1px solid var(--v2-border,rgba(127,127,127,.22));border-radius:10px;background:var(--v2-surface,Canvas)}
  section small{opacity:.7}
</style>
