#!/usr/bin/env node

import { chromium } from '@playwright/test';
import { mkdir, readdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import process from 'node:process';

function argumentValue(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : undefined;
}

const baseURL = argumentValue('--base-url') ?? process.env.PLAYWRIGHT_BASE_URL ?? 'http://127.0.0.1:5173';
const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const configuredOutput = process.env.MOBILE_SCREENSHOT_OUTPUT;
const reviewRoot = path.resolve(configuredOutput ?? path.join(repositoryRoot, '.local/mobile-visual-review'));
const label = safeName(argumentValue('--label') ?? process.env.MOBILE_SCREENSHOT_LABEL ?? 'capture') || 'capture';

async function nextGenerationDirectory() {
  await mkdir(reviewRoot, { recursive: true });
  const entries = await readdir(reviewRoot, { withFileTypes: true });
  const numbers = entries
    .filter((entry) => entry.isDirectory())
    .map((entry) => /^generation-(\d+)-/.exec(entry.name)?.[1])
    .filter(Boolean)
    .map(Number);
  const generation = (numbers.length ? Math.max(...numbers) : 0) + 1;
  return path.join(reviewRoot, `generation-${String(generation).padStart(2, '0')}-${label}`);
}

const viewports = [
  { name: 'small-mobile', width: 360, height: 800, deviceScaleFactor: 1 },
  { name: 'mobile', width: 390, height: 844, deviceScaleFactor: 1 },
  { name: 'tablet', width: 768, height: 1024, deviceScaleFactor: 1 },
];

const routes = [
  { name: 'status', path: '/' },
  { name: 'assets', path: '/assets' },
  { name: 'restore', path: '/restore' },
  { name: 'duplicates', path: '/duplicates' },
  { name: 'similarity-debug', path: '/similarity-debug' },
  { name: 'albums', path: '/albums' },
  { name: 'tags', path: '/tags' },
  { name: 'settings', path: '/settings' },
  { name: 'docs', path: '/docs' },
  { name: 'playground', path: '/playground' },
];

const settleMs = Number(process.env.MOBILE_SCREENSHOT_SETTLE_MS ?? 750);
const navigationTimeoutMs = Number(process.env.MOBILE_SCREENSHOT_TIMEOUT_MS ?? 15_000);
const scrollStepRatio = 0.85;
const scrollValidationRoutes = new Set(['/albums', '/tags', '/docs', '/playground']);

function safeName(value) {
  return value.replace(/[^a-z0-9_-]+/gi, '-').replace(/^-|-$/g, '').toLowerCase();
}

async function settlePage(page) {
  await page.waitForLoadState('domcontentloaded').catch(() => {});
  await page.evaluate(async () => {
    if (document.fonts?.ready) await document.fonts.ready;
    const style = document.createElement('style');
    style.dataset.mobileScreenshotHarness = 'true';
    style.textContent = `
      *, *::before, *::after {
        animation-delay: 0s !important;
        animation-duration: 0s !important;
        transition-duration: 0s !important;
        caret-color: transparent !important;
      }
    `;
    document.head.append(style);
  }).catch(() => {});
  await page.waitForTimeout(settleMs);
}

async function detectScrollTarget(page) {
  return page.evaluate(() => {
    const candidates = [
      { selector: '.v2-content', element: document.querySelector('.v2-content') },
      { selector: 'main', element: document.querySelector('main') },
    ];
    const elementTarget = candidates.find(({ element }) =>
      element instanceof HTMLElement && element.scrollHeight > element.clientHeight + 1,
    );
    if (elementTarget?.element instanceof HTMLElement) {
      const element = elementTarget.element;
      return {
        kind: 'element',
        selector: elementTarget.selector,
        scrollHeight: element.scrollHeight,
        viewportHeight: element.clientHeight,
        maxScroll: Math.max(0, element.scrollHeight - element.clientHeight),
      };
    }

    const scrollingElement = document.scrollingElement ?? document.documentElement;
    return {
      kind: 'window',
      selector: 'window',
      scrollHeight: Math.max(document.body?.scrollHeight ?? 0, scrollingElement.scrollHeight),
      viewportHeight: window.innerHeight,
      maxScroll: Math.max(0, scrollingElement.scrollHeight - window.innerHeight),
    };
  });
}

async function scrollTo(page, target, position) {
  return page.evaluate(({ target: scrollTarget, position: scrollPosition }) => {
    if (scrollTarget.kind === 'window') {
      window.scrollTo(0, scrollPosition);
      return Math.round(window.scrollY);
    }
    const element = document.querySelector(scrollTarget.selector);
    if (!(element instanceof HTMLElement)) return null;
    element.scrollTo({ top: scrollPosition, behavior: 'instant' });
    return Math.round(element.scrollTop);
  }, { target, position });
}

async function captureScrollSegments(page, directory, prefix) {
  const target = await detectScrollTarget(page);
  const maxScroll = target.maxScroll;
  const viewportHeight = target.viewportHeight;
  const positions = [];
  for (let position = 0; position < maxScroll; position += Math.max(1, viewportHeight * scrollStepRatio)) {
    positions.push(Math.round(position));
  }
  if (maxScroll > 0 && positions.at(-1) !== Math.round(maxScroll)) positions.push(Math.round(maxScroll));

  for (const [index, position] of positions.entries()) {
    const actualPosition = await scrollTo(page, target, position);
    if (actualPosition === null || Math.abs(actualPosition - position) > 1) {
      throw new Error(`Scroll target ${target.selector} did not reach ${position} (actual: ${actualPosition})`);
    }
    await page.waitForTimeout(50);
    await page.screenshot({
      path: path.join(directory, `${prefix}-viewport-${String(index + 1).padStart(3, '0')}.png`),
      fullPage: false,
    });
  }
  const resetPosition = await scrollTo(page, target, 0);
  if (resetPosition === null || resetPosition > 1) {
    throw new Error(`Scroll target ${target.selector} did not reset (actual: ${resetPosition})`);
  }
  return { target, scrollPositions: positions };
}

async function clickRoleIfPresent(page, role, name, timeout = 1_500) {
  const target = page.getByRole(role, { name, exact: true }).first();
  if (await target.count() === 0) return false;
  try {
    await target.click({ timeout });
    return true;
  } catch {
    return false;
  }
}

async function captureInteraction(page, directory, prefix, capture, state, settle = true) {
  if (settle) await settlePage(page);
  const filename = `${prefix}-${safeName(state)}.png`;
  await page.screenshot({ path: path.join(directory, filename), fullPage: false });
  capture.files.push(`${path.basename(directory)}/${filename}`);
  capture.interactionStates ??= [];
  capture.interactionStates.push({ name: state, file: `${path.basename(directory)}/${filename}` });
}

async function captureInteractionStates(page, route, directory, prefix, capture) {
  // These interactions intentionally avoid mutations. They are guarded because
  // a live environment may have an empty library or no duplicate groups yet.
  const taskSurface = page.locator('.v2-tasktray, .v2-task-bubbles').first();
  if (await taskSurface.count() && await taskSurface.isVisible().catch(() => false)) {
    await captureInteraction(page, directory, prefix, capture, 'task-progress');
  }

  if (route.path === '/' || route.path === '/assets' || route.path === '/restore' || route.path === '/duplicates') {
    if (await clickRoleIfPresent(page, 'button', 'More')) {
      await captureInteraction(page, directory, prefix, capture, 'more-navigation');
      await clickRoleIfPresent(page, 'button', 'Close');
    }
  }

  if (route.path === '/assets') {
    if (await clickRoleIfPresent(page, 'button', 'Convert to expert')) {
      await captureInteraction(page, directory, prefix, capture, 'expert-search-drawer');
      await page.keyboard.press('Escape').catch(() => {});
    }
    // A viewer is useful even when the asset API returns a different fixture
    // shape, so discover the rendered tile instead of assuming an asset id.
    const tile = page.locator('.v2-asset-main').first();
    if (await tile.count() && await tile.isVisible().catch(() => false)) {
      try {
        await tile.click({ timeout: 1_500 });
        await captureInteraction(page, directory, prefix, capture, 'asset-viewer');
        await page.keyboard.press('Escape').catch(() => {});
      } catch {
        // Empty or loading fixture: the stable base route remains recorded.
      }
    }
  }

  if (route.path === '/duplicates') {
    for (const tab of ['Rules & discovery', 'Resolution history']) {
      if (await clickRoleIfPresent(page, 'tab', tab)) {
        await captureInteraction(page, directory, prefix, capture, `duplicates-${tab}`);
      }
    }
    // Return to Review before looking for a comparison overlay.
    await clickRoleIfPresent(page, 'tab', 'Review');
    const compare = page.getByRole('button', { name: 'Compare', exact: true }).first();
    if (await compare.count() && await compare.isVisible().catch(() => false)) {
      try {
        await compare.click({ timeout: 1_500 });
        await captureInteraction(page, directory, prefix, capture, 'duplicate-comparison');
        await page.keyboard.press('Escape').catch(() => {});
      } catch {
        // Duplicate groups can disappear while the seed worker is reconciling.
      }
    }
  }

  if (route.path === '/settings') {
    for (const tab of ['Duplicates', 'Sync', 'Tasks']) {
      if (await clickRoleIfPresent(page, 'tab', tab)) {
        await captureInteraction(page, directory, prefix, capture, `settings-${tab}`);
      }
    }
  }
}

async function main() {
  const outputRoot = await nextGenerationDirectory();
  await mkdir(outputRoot, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const manifest = {
    baseURL,
    generatedAt: new Date().toISOString(),
    viewports,
    routes,
    captures: [],
  };

  try {
    for (const viewport of viewports) {
      const context = await browser.newContext({ viewport });
      const page = await context.newPage();
      page.setDefaultTimeout(navigationTimeoutMs);
      const browserErrors = [];
      page.on('console', (message) => {
        if (message.type() === 'error' || message.type() === 'warning') {
          browserErrors.push({ type: message.type(), text: message.text(), location: message.location() });
        }
      });
      page.on('pageerror', (error) => browserErrors.push({ type: 'pageerror', text: error.message }));

      for (const route of routes) {
        const directory = path.join(outputRoot, viewport.name);
        await mkdir(directory, { recursive: true });
        const prefix = `${safeName(route.name)}-${viewport.name}`;
        const capture = { viewport: viewport.name, route: route.path, files: [], errors: [] };
        browserErrors.length = 0;
        try {
          await page.goto(new URL(route.path, baseURL).toString(), {
            waitUntil: 'domcontentloaded',
            timeout: navigationTimeoutMs,
          });
          await settlePage(page);
          await page.screenshot({
            path: path.join(directory, `${prefix}-document.png`),
            fullPage: true,
          });
          capture.files.push(`${viewport.name}/${prefix}-document.png`);
          const segments = await captureScrollSegments(page, directory, prefix);
          for (let index = 0; index < segments.scrollPositions.length; index += 1) {
            capture.files.push(`${viewport.name}/${prefix}-viewport-${String(index + 1).padStart(3, '0')}.png`);
          }
          capture.scrollTarget = segments.target;
          capture.scrollPositions = segments.scrollPositions;
          capture.title = await page.title().catch(() => '');
          await captureInteractionStates(page, route, directory, prefix, capture);
        } catch (error) {
          capture.navigationError = error instanceof Error ? error.message : String(error);
        }
        capture.errors = [...browserErrors];
        manifest.captures.push(capture);
        console.log(`${capture.errors.length ? 'WARN' : 'OK  '} ${viewport.name} ${route.path} (${capture.files.length} screenshots)`);
      }
      await context.close();
    }
  } finally {
    await browser.close();
  }

  await writeFile(path.join(outputRoot, 'manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`);
  const failed = manifest.captures.filter((capture) => capture.navigationError);
  const errors = manifest.captures.reduce((total, capture) => total + capture.errors.length, 0);
  const screenshotCount = manifest.captures.reduce((total, capture) => total + capture.files.length, 0);
  const missingScrollCoverage = manifest.captures.filter((capture) =>
    capture.viewport === 'tablet' && scrollValidationRoutes.has(capture.route)
      && capture.scrollTarget?.maxScroll > 0 && capture.scrollPositions?.length < 2,
  );
  await writeFile(
    path.join(outputRoot, 'summary.json'),
    `${JSON.stringify({
      baseURL,
      generatedAt: manifest.generatedAt,
      generation: path.basename(outputRoot),
      routeViewportCombinations: manifest.captures.length,
      screenshots: screenshotCount,
      browserAndPageWarningsOrErrors: errors,
      navigationFailures: failed.length,
      missingScrollCoverage: missingScrollCoverage.map(({ route }) => route),
    }, null, 2)}\n`,
  );
  console.log(`Captured ${manifest.captures.length} route/viewport combinations in ${outputRoot}`);
  console.log(`Browser/page warnings and errors: ${errors}; navigation failures: ${failed.length}`);
  if (failed.length || missingScrollCoverage.length) process.exitCode = 1;
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
