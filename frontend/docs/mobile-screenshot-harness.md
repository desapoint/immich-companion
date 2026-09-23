# Mobile screenshot harness

The screenshot harness captures the implemented routes at three responsive
viewports and produces a full-document image plus viewport-sized scroll slices.
It is intended for quick visual review of mobile, small-mobile, and tablet
layouts against live-dev or another running frontend.

From `frontend/`, run:

```bash
npm run screenshots:mobile -- --base-url http://127.0.0.1:5173 --label initial
```

The optional `--base-url` flag overrides `PLAYWRIGHT_BASE_URL` (which defaults
to `http://127.0.0.1:5173`). `--label` names the generation. By default,
screenshots, `manifest.json`, and `summary.json` are retained under the
Git-ignored repository `.local/mobile-visual-review/generation-NN-label/`
directory. Each run increments `NN`, so earlier generations remain available
for comparison. Set `MOBILE_SCREENSHOT_OUTPUT=/path/to/output` to use another
retained root.

The manifest records each route, viewport, the active scroll target, its
scrollable height, scroll positions, navigation failures, and browser/page errors.
On phones the active target is normally `window`; on larger layouts it is
normally `.v2-content`. The harness detects this from the rendered page instead
of assuming that the document is the scrolling surface. Warnings and errors are reported
without preventing the other routes from being captured. A non-zero exit code
is reserved for navigation failures or missing expected tablet scroll coverage;
browser warnings and page errors remain in the manifest so a visual review can
distinguish a captured UI from a runtime problem.

Files ending in `-viewport-NNN.png` are the preferred review images. They are
fixed viewport captures at each detected scroll position and therefore preserve
fixed mobile navigation in the same place a user sees it. Files ending in
`-document.png` are full-document snapshots for broad overview only; fixed
navigation may appear in a way that does not represent one continuous document
view.

For a different settle period or navigation timeout:

```bash
MOBILE_SCREENSHOT_SETTLE_MS=1200 MOBILE_SCREENSHOT_TIMEOUT_MS=30000 \
  npm run screenshots:mobile -- --label after-settings-change
```
