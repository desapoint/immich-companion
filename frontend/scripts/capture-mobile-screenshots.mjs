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

async function captureScrollSegments(page, directory, prefix, viewportHeight) {
  const documentHeight = await page.evaluate(() =>
    Math.max(document.body?.scrollHeight ?? 0, document.documentElement.scrollHeight),
  );
  const maxScroll = Math.max(0, documentHeight - viewportHeight);
  const positions = [];
  for (let position = 0; position < maxScroll; position += Math.max(1, viewportHeight * scrollStepRatio)) {
    positions.push(Math.round(position));
  }
  if (maxScroll > 0 && positions.at(-1) !== Math.round(maxScroll)) positions.push(Math.round(maxScroll));

  for (const [index, position] of positions.entries()) {
    await page.evaluate((scrollY) => window.scrollTo(0, scrollY), position);
    await page.waitForTimeout(50);
    await page.screenshot({
      path: path.join(directory, `${prefix}-scroll-${String(index + 1).padStart(3, '0')}.png`),
      fullPage: false,
    });
  }
  await page.evaluate(() => window.scrollTo(0, 0));
  return { documentHeight, scrollPositions: positions };
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
            path: path.join(directory, `${prefix}-full.png`),
            fullPage: true,
          });
          capture.files.push(`${viewport.name}/${prefix}-full.png`);
          const segments = await captureScrollSegments(page, directory, prefix, viewport.height);
          for (let index = 0; index < segments.scrollPositions.length; index += 1) {
            capture.files.push(`${viewport.name}/${prefix}-scroll-${String(index + 1).padStart(3, '0')}.png`);
          }
          capture.documentHeight = segments.documentHeight;
          capture.scrollPositions = segments.scrollPositions;
          capture.title = await page.title().catch(() => '');
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
    }, null, 2)}\n`,
  );
  console.log(`Captured ${manifest.captures.length} route/viewport combinations in ${outputRoot}`);
  console.log(`Browser/page warnings and errors: ${errors}; navigation failures: ${failed.length}`);
  if (failed.length) process.exitCode = 1;
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
