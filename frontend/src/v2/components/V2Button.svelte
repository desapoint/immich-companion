<script lang="ts">
  let {
    variant = 'default',
    active = false,
    block = false,
    disabled = false,
    type = 'button',
    title,
    ariaLabel,
    onclick,
    children,
  }: {
    variant?: 'default' | 'primary' | 'danger';
    active?: boolean;
    block?: boolean;
    disabled?: boolean;
    type?: 'button' | 'submit' | 'reset';
    title?: string;
    ariaLabel?: string;
    onclick?: (event: MouseEvent) => void;
    children: import('svelte').Snippet;
  } = $props();
</script>

<button
  class="v2-button"
  class:v2-button-primary={variant === 'primary'}
  class:v2-button-danger={variant === 'danger'}
  class:v2-button-active={active}
  class:v2-button-block={block}
  {disabled}
  {type}
  {title}
  aria-label={ariaLabel}
  {onclick}
>
  {@render children()}
</button>
