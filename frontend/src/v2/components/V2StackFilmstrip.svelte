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
