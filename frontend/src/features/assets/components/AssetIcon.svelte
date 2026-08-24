<script lang="ts">
  interface Props {
    kind: 'album' | 'tag' | 'stack' | 'external' | 'immich';
  }

  let { kind }: Props = $props();
</script>

<svg viewBox="0 0 24 24" aria-hidden="true">
  {#if kind === 'album'}
    <path d="M3.5 6.5h6l1.7 2h9.3v9.75a2.25 2.25 0 0 1-2.25 2.25H5.75a2.25 2.25 0 0 1-2.25-2.25V6.5Z" />
    <path d="M3.5 9h17" />
  {:else if kind === 'tag'}
    <path d="M4 4h7.1l8.4 8.4a2 2 0 0 1 0 2.8l-4.3 4.3a2 2 0 0 1-2.8 0L4 11.1V4Z" />
    <circle cx="8" cy="8" r="1.35" />
  {:else if kind === 'stack'}
    <rect x="5.5" y="3.5" width="15" height="12" rx="2" />
    <path d="M3.5 7.5v10a3 3 0 0 0 3 3h12" />
    <path d="m8.5 12 3-3 2.5 2.5 2-2 2 2" />
  {:else if kind === 'external'}
    <path d="M13 4h7v7M20 4l-9 9" />
    <path d="M18 13v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h5" />
  {:else}
    <circle cx="12" cy="12" r="8.5" />
    <circle cx="12" cy="12" r="2.25" />
    <path d="M12 3.5v6.25M20.5 12h-6.25M12 20.5v-6.25M3.5 12h6.25" />
  {/if}
</svg>

<style>
  svg {
    display: block;
    width: 1rem;
    height: 1rem;
    fill: none;
    stroke: currentColor;
    stroke-linecap: round;
    stroke-linejoin: round;
    stroke-width: 1.65;
  }
</style>
