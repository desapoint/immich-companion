<script lang="ts">
  let { variant = 'default', active = false, block = false, iconOnly = false, disabled = false, type = 'button', title, ariaLabel, onclick, children }: {
    variant?: 'default' | 'primary' | 'positive' | 'danger'; active?: boolean; block?: boolean; iconOnly?: boolean; disabled?: boolean;
    type?: 'button' | 'submit' | 'reset'; title?: string; ariaLabel?: string; onclick?: (event: MouseEvent) => void; children: import('svelte').Snippet;
  } = $props();
</script>

<button class="v2-button" data-variant={variant} data-active={active || undefined} data-block={block || undefined} data-icon-only={iconOnly || undefined} {disabled} {type} {title} aria-label={ariaLabel} {onclick}>
  {@render children()}
</button>
