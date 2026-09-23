# Mobile screenshot harness

The screenshot harness captures the implemented routes at three responsive
viewports and produces both a full-page image and viewport-sized scroll slices.
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

The manifest records each route, viewport, document height, scroll positions,
navigation failures, and browser/page errors. Warnings and errors are reported
without preventing the other routes from being captured. A non-zero exit code
is reserved for navigation failures; browser warnings and page errors remain in
the manifest so a visual review can distinguish a captured UI from a runtime
problem.

For a different settle period or navigation timeout:

```bash
MOBILE_SCREENSHOT_SETTLE_MS=1200 MOBILE_SCREENSHOT_TIMEOUT_MS=30000 \
  npm run screenshots:mobile -- --label after-settings-change
```
