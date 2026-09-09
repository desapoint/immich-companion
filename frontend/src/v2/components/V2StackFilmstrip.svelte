<script lang="ts">
  import { Star, Unlink } from '@lucide/svelte';
  import { libraryData } from '../data/currentDataSource.svelte';
  import type { AssetRecord } from '../data/contracts';

  let {
    members = [],
    currentId = null,
    primaryId = null,
    removedIds = new Set<string>(),
    readyIds = new Set<string>(),
    disabled = false,
    onselect,
  }: {
    members?: AssetRecord[];
    currentId?: string | null;
    primaryId?: string | null;
    removedIds?: Set<string>;
    readyIds?: Set<string>;
    disabled?: boolean;
    onselect: (id: string) => void;
  } = $props();
</script>

<div class="v2-stack-filmstrip" aria-label="Stack members">
  {#each members as member (member.id)}
    <button
      type="button"
      class="v2-stack-filmstrip-item"
      class:active={member.id===currentId}
      class:removed={removedIds.has(member.id)}
      class:loading={!readyIds.has(member.id)&&member.asset_type!=='VIDEO'}
      {disabled}
      aria-label={`${member.original_file_name}${member.id===primaryId?' · primary asset':''}${removedIds.has(member.id)?' · removed from stack':''}`}
      aria-current={member.id===currentId?'true':undefined}
      title={`${member.original_file_name}${member.width&&member.height?` · ${member.width}×${member.height}`:''}`}
      onclick={()=>onselect(member.id)}
    >
      <img src={libraryData.media.thumbnail(member).url} alt="" loading="eager" draggable="false"/>
      {#if member.id===primaryId}<span class="v2-stack-filmstrip-state primary" title="Primary asset"><Star size={11} fill="currentColor" aria-hidden="true"/></span>{/if}
      {#if removedIds.has(member.id)}<span class="v2-stack-filmstrip-state removed-mark" title="Removed from stack"><Unlink size={11} aria-hidden="true"/></span>{/if}
      <span class="v2-stack-filmstrip-name">{member.original_file_name}</span>
    </button>
  {/each}
</div>

<style>
  .v2-stack-filmstrip{display:flex;gap:7px;min-width:0;overflow-x:auto;padding:2px 1px 5px;scrollbar-width:thin;scrollbar-color:#475970 transparent}
  .v2-stack-filmstrip::-webkit-scrollbar{height:6px}.v2-stack-filmstrip::-webkit-scrollbar-track{background:transparent}.v2-stack-filmstrip::-webkit-scrollbar-thumb{background:#475970;border-radius:999px}
  .v2-stack-filmstrip-item{position:relative;flex:0 0 92px;height:66px;overflow:hidden;border:1px solid var(--v2-line);border-radius:8px;background:#0b1118;color:var(--v2-text);padding:0;cursor:pointer;box-shadow:none}
  .v2-stack-filmstrip-item:hover:not(:disabled){border-color:#5a6e8a}.v2-stack-filmstrip-item.active{border-color:var(--v2-accent);box-shadow:inset 0 0 0 2px color-mix(in srgb,var(--v2-accent) 72%,transparent)}
  .v2-stack-filmstrip-item.removed{opacity:.64}.v2-stack-filmstrip-item.removed.active{opacity:.86}.v2-stack-filmstrip-item.loading::after{content:"";position:absolute;inset:0;background:linear-gradient(110deg,transparent 20%,rgba(255,255,255,.09) 45%,transparent 70%);animation:v2-stack-thumb-loading 1.1s linear infinite}
  .v2-stack-filmstrip-item img{width:100%;height:100%;display:block;object-fit:cover}.v2-stack-filmstrip-name{position:absolute;left:0;right:0;bottom:0;padding:12px 5px 4px;background:linear-gradient(transparent,rgba(0,0,0,.82));font-size:9px;line-height:1.1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:left;text-shadow:0 1px 2px #000}
  .v2-stack-filmstrip-state{position:absolute;top:4px;width:19px;height:19px;display:grid;place-items:center;border-radius:999px;background:rgba(7,12,18,.88);box-shadow:0 1px 4px rgba(0,0,0,.32)}.v2-stack-filmstrip-state.primary{left:4px;color:#f8d46e}.v2-stack-filmstrip-state.removed-mark{right:4px;color:#f2a1a1}
  @keyframes v2-stack-thumb-loading{from{transform:translateX(-100%)}to{transform:translateX(100%)}}
</style>
