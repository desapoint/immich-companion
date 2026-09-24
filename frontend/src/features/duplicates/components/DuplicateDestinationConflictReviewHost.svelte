<script lang="ts">
  import { onMount } from 'svelte';
  import DuplicateDestinationConflictModal from './DuplicateDestinationConflictModal.svelte';
  import type {
    DuplicateDestinationConflictResult,
    DuplicateDestinationConflictTarget,
  } from '../state/duplicateDestinationConflictReview';
  import {
    DuplicateDestinationConflictReviewCancelled,
    registerDuplicateDestinationConflictReviewer,
  } from '../state/duplicateDestinationConflictReviewBridge';

  let targets = $state<DuplicateDestinationConflictTarget[]>([]);
  let choices = $state<DuplicateDestinationConflictResult>({});
  let pending: {
    resolve: (result: DuplicateDestinationConflictResult) => void;
    reject: (error: Error) => void;
  } | null = null;

  function clear(): void {
    pending = null;
    targets = [];
    choices = {};
  }

  function begin(next: DuplicateDestinationConflictTarget[]): Promise<DuplicateDestinationConflictResult> {
    if (pending) return Promise.reject(new Error('Another proposed stack destination review is already open.'));
    targets = next;
    choices = {};
    return new Promise((resolve, reject) => {
      pending = { resolve, reject };
    });
  }

  function change(targetId: string, stackId: string): void {
    choices = { ...choices, [targetId]: stackId };
  }

  function confirm(): void {
    const current = pending;
    if (!current) return;
    const result = { ...choices };
    clear();
    current.resolve(result);
  }

  function close(): void {
    const current = pending;
    if (!current) return;
    clear();
    current.reject(new DuplicateDestinationConflictReviewCancelled());
  }

  onMount(() => {
    const unregister = registerDuplicateDestinationConflictReviewer(begin);
    return () => {
      unregister();
      const current = pending;
      clear();
      current?.reject(new DuplicateDestinationConflictReviewCancelled());
    };
  });
</script>

{#if targets.length}
  <DuplicateDestinationConflictModal
    {targets}
    {choices}
    onchange={change}
    onconfirm={confirm}
    onclose={close}
  />
{/if}
