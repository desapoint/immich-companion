<script lang="ts">
  import type { IconName } from '../../types/ui';

  interface Props {
    name: IconName;
    size?: string;
    strokeWidth?: number;
  }

  let { name, size = '1rem', strokeWidth = 1.7 }: Props = $props();
</script>

<svg
  viewBox="0 0 24 24"
  width={size}
  height={size}
  aria-hidden="true"
  style:stroke-width={strokeWidth}
>
  {#if name === 'album' || name === 'album-add' || name === 'album-remove'}
    <path d="M3.5 6.5h6l1.7 2h9.3v9.75a2.25 2.25 0 0 1-2.25 2.25H5.75a2.25 2.25 0 0 1-2.25-2.25V6.5Z" />
    <path d="M3.5 9h17" />
    {#if name === 'album-add' || name === 'album-remove'}
      <circle class="action-badge" cx="17.2" cy="16.7" r="4.2" />
      <path class="action-badge-mark" d="M15.1 16.7h4.2" />
      {#if name === 'album-add'}<path class="action-badge-mark" d="M17.2 14.6v4.2" />{/if}
    {/if}
  {:else if name === 'tag' || name === 'tag-add' || name === 'tag-remove'}
    <path d="M4 4h7.1l8.4 8.4a2 2 0 0 1 0 2.8l-4.3 4.3a2 2 0 0 1-2.8 0L4 11.1V4Z" />
    <circle cx="8" cy="8" r="1.35" />
    {#if name === 'tag-add' || name === 'tag-remove'}
      <circle class="action-badge" cx="17.2" cy="16.7" r="4.2" />
      <path class="action-badge-mark" d="M15.1 16.7h4.2" />
      {#if name === 'tag-add'}<path class="action-badge-mark" d="M17.2 14.6v4.2" />{/if}
    {/if}
  {:else if name === 'stack'}
    <rect x="5.5" y="3.5" width="15" height="12" rx="2" />
    <path d="M3.5 7.5v10a3 3 0 0 0 3 3h12M8.5 12l3-3 2.5 2.5 2-2 2 2" />
  {:else if name === 'sync'}
    <path d="M20 7v5h-5M4 17v-5h5" /><path d="M18.2 12a6.5 6.5 0 0 0-11.1-4.6L5 9M6 12a6.5 6.5 0 0 0 11.1 4.6L19 15" />
  {:else if name === 'edit'}
    <path d="m5 16-.7 3.7L8 19l10.8-10.8a2.1 2.1 0 0 0-3-3L5 16Z" /><path d="m14.5 6.5 3 3" />
  {:else if name === 'filter'}
    <path d="M4 5h16l-6.3 7.1v5.1l-3.4 1.8v-6.9L4 5Z" />
  {:else if name === 'external'}
    <path d="M13 4h7v7M20 4l-9 9M18 13v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h5" />
  {:else if name === 'immich'}
    <circle cx="12" cy="12" r="8.5" /><circle cx="12" cy="12" r="2.25" />
    <path d="M12 3.5v6.25M20.5 12h-6.25M12 20.5v-6.25M3.5 12h6.25" />
  {:else if name === 'archive' || name === 'unarchive'}
    <path d="M4 7.5h16v11H4zM3 4h18v3.5H3zM9 12h6" />
    {#if name === 'unarchive'}<path d="m9 15 3-3 3 3M12 12v5" />{/if}
  {:else if name === 'favorite' || name === 'unfavorite'}
    <path d="M20.5 8.8c0 5.1-8.5 10-8.5 10s-8.5-4.9-8.5-10A4.6 4.6 0 0 1 12 6.3a4.6 4.6 0 0 1 8.5 2.5Z" />
    {#if name === 'unfavorite'}<path d="M4 4l16 16" />{/if}
  {:else if name === 'star'}
    <path d="m12 3.5 2.7 5.5 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1-4.4-4.3 6.1-.9L12 3.5Z" />
  {:else if name === 'trash'}
    <path d="M4.5 7h15M9 7V4.5h6V7m-8.5 0 .8 13h9.4l.8-13M10 10.5v6M14 10.5v6" />
  {:else if name === 'restore'}
    <path d="M5 8V3.8M5 8h4.2M5.2 8a8 8 0 1 1-1 7" /><path d="M12 7v5l3 2" />
  {:else if name === 'select-page'}
    <rect x="4" y="4" width="16" height="16" rx="2" /><path d="m8 12 2.5 2.5L16 9" />
  {:else if name === 'select-all'}
    <rect x="7" y="7" width="13" height="13" rx="2" /><path d="M4 16V5a1 1 0 0 1 1-1h11M10 13l2 2 4-4" />
  {:else if name === 'invert-selection'}
    <path d="M7 4H5a1 1 0 0 0-1 1v2M17 4h2a1 1 0 0 1 1 1v2M7 20H5a1 1 0 0 1-1-1v-2M17 20h2a1 1 0 0 0 1-1v-2" />
    <path d="M8 8h8v8H8z" fill="currentColor" stroke="none" />
  {:else if name === 'chevron'}
    <path d="m6.5 9 5.5 5.5L17.5 9" />
  {:else if name === 'clear-selection' || name === 'close'}
    <path d="M6 6l12 12M18 6 6 18" />
    {#if name === 'clear-selection'}<rect x="3" y="3" width="18" height="18" rx="3" />{/if}
  {:else if name === 'view'}
    <path d="M2.8 12s3.3-5.5 9.2-5.5 9.2 5.5 9.2 5.5-3.3 5.5-9.2 5.5S2.8 12 2.8 12Z" /><circle cx="12" cy="12" r="2.4" />
  {:else if name === 'select'}
    <circle cx="12" cy="12" r="8.5" /><path d="m8.5 12 2.3 2.3 4.8-5" />
  {:else if name === 'fit'}
    <path d="M9 4H4v5M15 4h5v5M9 20H4v-5M15 20h5v-5M4 9l5-5M20 9l-5-5M4 15l5 5M20 15l-5 5" />
  {:else if name === 'actual-size'}
    <path d="M4 8V4h4M16 4h4v4M4 16v4h4M20 16v4h-4M9 12h6M12 9v6" />
  {:else if name === 'zoom-in' || name === 'zoom-out'}
    <circle cx="10.5" cy="10.5" r="6.5" /><path d="m15.3 15.3 4.2 4.2M7.5 10.5h6" />
    {#if name === 'zoom-in'}<path d="M10.5 7.5v6" />{/if}
  {:else if name === 'reset-zoom'}
    <path d="M5 8V4M5 8h4M5.2 8a8 8 0 1 1-.8 7" /><circle cx="12" cy="12" r="2" />
  {:else if name === 'info'}
    <circle cx="12" cy="12" r="9" /><path d="M12 10.5v6M12 7.5h.01" />
  {:else if name === 'integrity'}
    <path d="M12 3.2 19 6v5.1c0 4.4-2.8 7.7-7 9.7-4.2-2-7-5.3-7-9.7V6l7-2.8Z" />
    <path d="m8.7 12 2.1 2.1 4.5-4.5" />
  {:else if name === 'keyboard'}
    <rect x="3" y="6" width="18" height="12" rx="2" /><path d="M6 9h1M10 9h1M14 9h1M18 9h.01M6 12h1M10 12h1M14 12h4M7 15h10" />
  {:else if name === 'more'}
    <circle cx="5" cy="12" r="1.2" fill="currentColor" stroke="none" />
    <circle cx="12" cy="12" r="1.2" fill="currentColor" stroke="none" />
    <circle cx="19" cy="12" r="1.2" fill="currentColor" stroke="none" />
  {:else}
    <path d="m5 12 4 4L19 6" />
  {/if}
</svg>

<style>
  svg {
    display: block;
    flex: 0 0 auto;
    fill: none;
    stroke: currentColor;
    stroke-linecap: round;
    stroke-linejoin: round;
  }

  .action-badge {
    fill: currentColor;
    stroke: currentColor;
  }

  .action-badge-mark {
    stroke: var(--color-surface-raised);
    stroke-width: 1.7;
  }
</style>
