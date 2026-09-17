# Agent guidance

This repository uses Svelte 5 heavily in the V2 frontend. Reactive loops can crash the entire frontend with `effect_update_depth_exceeded`, so treat `$effect` as a side-effect boundary, not as a general state-synchronization tool.

## Svelte reactive-safety rules

- Remember that Svelte tracks reactive reads made by synchronous functions called from a `$effect`, not only reads written directly in the effect body.
- Do not call a stateful controller method from `$effect` when that method reads and writes `$state` that can invalidate the same effect. Cleanup callbacks run as part of the same reactive lifecycle and can create the same feedback loop.
- In particular, never register a viewer DOM node with `ViewerViewportController.setViewport()` directly from `$effect`. Use `ViewportRegistrationController` from `frontend/src/v2/components/viewportRegistration.ts` and connect it from DOM/action or mount/unmount lifecycle instead. The registration helper deliberately uses `untrack()`.
- If an effect must call imperative code that reads reactive state, capture only the intended dependencies first and put the imperative call behind `untrack()`. Prefer event handlers, actions, `onMount`/`onDestroy`, or `$derived` when they express the lifecycle more directly.
- Avoid effects that both read and assign the same reactive state unless the assignment is demonstrably idempotent and cannot retrigger the effect. Be especially cautious with arrays, objects, `Set`, and `Map`, where creating a new identity counts as a change.
- When changing viewer, viewport, resize, media, or overlay lifecycle code, search for existing lifecycle helpers before adding another `$effect` bridge.

## Validation for frontend changes

Run from `frontend/`:

```bash
npm run check
npm test
```

For viewer/DOM lifecycle changes, also run the relevant Playwright regression when practical, for example:

```bash
npm run build
npm run test:browser -- v2-assets-shell.spec.ts
```

The V2 architecture tests intentionally contain regression guards for lifecycle patterns that previously caused `effect_update_depth_exceeded`; do not remove those guards to make a change pass.
