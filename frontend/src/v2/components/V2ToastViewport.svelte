<script lang="ts">
  import V2Toast from './V2Toast.svelte';
  import type { V2ToastAction, V2ToastController } from '../state/toasts.svelte';

  let { controller }: { controller: V2ToastController } = $props();
  function runAction(id: number, action: V2ToastAction): void {
    controller.dismiss(id);
    void action.run();
  }
</script>

<div class="v2-toast-viewport" data-position={controller.position} aria-label="Notifications">
  {#each controller.toasts as toast (toast.id)}
    <V2Toast {toast} ondismiss={() => controller.dismiss(toast.id)} onaction={() => toast.action && runAction(toast.id, toast.action)}/>
  {/each}
</div>

<style>
  .v2-toast-viewport{position:fixed;z-index:4000;display:flex;gap:.55rem;max-height:calc(100vh - 1.5rem);overflow-y:auto;padding:.75rem;pointer-events:none;scrollbar-width:thin}
  .v2-toast-viewport[data-position^="top-"]{top:0;flex-direction:column}.v2-toast-viewport[data-position^="bottom-"]{bottom:0;flex-direction:column-reverse}
  .v2-toast-viewport[data-position$="-left"]{left:0;align-items:flex-start}.v2-toast-viewport[data-position$="-right"]{right:0;align-items:flex-end}
</style>
