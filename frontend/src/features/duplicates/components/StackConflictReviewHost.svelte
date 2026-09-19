<script lang="ts">
  import { onMount } from 'svelte';
  import type { StackResolutionMap } from '../types/contracts';
  import {
    registerStackConflictReviewer,
    StackConflictReviewCancelled,
    type StackConflictReviewResult,
  } from '../state/stackConflictReviewBridge';
  import { conflictResolutionMap, type StackConflictReviewTarget } from '../types/stackResolution';
  import V2StackActionModal from '../../assets/components/StackActionModal.svelte';

  let reviews = $state<StackConflictReviewTarget[]>([]);
  let pending: {
    resolve: (result: StackConflictReviewResult) => void;
    reject: (error: Error) => void;
  } | null = null;

  function clear(): void {
    pending = null;
    reviews = [];
  }

  function begin(targets: StackConflictReviewTarget[]): Promise<StackConflictReviewResult> {
    if (pending) return Promise.reject(new Error('Another stack conflict review is already open.'));
    reviews = targets.map((target) => ({
      ...target,
      plan: { ...target.plan, conflicts: target.plan.conflicts.map((conflict) => ({ ...conflict })) },
    }));
    return new Promise((resolve, reject) => {
      pending = { resolve, reject };
    });
  }

  function change(reviewId: string, resolution: StackResolutionMap): void {
    reviews = reviews.map((review) => review.id === reviewId ? { ...review, resolution } : review);
  }

  function confirm(): void {
    const current = pending;
    if (!current) return;
    const result = Object.fromEntries(
      reviews.map((review) => [review.id, conflictResolutionMap(review.plan, review.resolution)]),
    );
    clear();
    current.resolve(result);
  }

  function close(): void {
    const current = pending;
    if (!current) return;
    clear();
    current.reject(new StackConflictReviewCancelled());
  }

  onMount(() => {
    const unregister = registerStackConflictReviewer(begin);
    return () => {
      unregister();
      const current = pending;
      clear();
      current?.reject(new StackConflictReviewCancelled());
    };
  });
</script>

{#if reviews.length}
  <V2StackActionModal
    {reviews}
    onreviewresolutionchange={change}
    onconfirm={confirm}
    onclose={close}
  />
{/if}
