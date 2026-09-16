import {
  actualSizeZoom,
  anchoredPan,
  clampPan,
  normalizedFocusFromPan,
  panForNormalizedFocus,
  renderedSize,
  type NormalizedFocus,
  type ViewportSize,
} from './viewerViewport';

type ViewportMetrics = { width: number; height: number };

export class ViewerViewportController {
  zoom = $state(1);
  panX = $state(0);
  panY = $state(0);
  naturalWidth = $state(800);
  naturalHeight = $state(600);
  viewport = $state<HTMLElement | null>(null);

  readonly minZoom: number;
  readonly maxZoom: number;

  private viewportWidth = 0;
  private viewportHeight = 0;
  private pendingFocus: NormalizedFocus | null = null;
  private initializedNaturalSize = false;

  constructor(minZoom = 0.1, maxZoom = 8) {
    this.minZoom = minZoom;
    this.maxZoom = maxZoom;
  }

  get transform(): string {
    return `translate(${this.panX}px, ${this.panY}px) scale(${this.zoom})`;
  }

  private measureViewport(viewport: HTMLElement | null = this.viewport): ViewportMetrics | null {
    if (!viewport) return null;
    const rect = viewport.getBoundingClientRect();
    if (!rect.width || !rect.height) return null;
    return { width: rect.width, height: rect.height };
  }

  private storedSize(): ViewportSize | null {
    return renderedSize(
      this.viewportWidth,
      this.viewportHeight,
      this.naturalWidth,
      this.naturalHeight,
      this.zoom,
    );
  }

  private sizeFor(metrics: ViewportMetrics): ViewportSize | null {
    return renderedSize(
      metrics.width,
      metrics.height,
      this.naturalWidth,
      this.naturalHeight,
      this.zoom,
    );
  }

  private rememberViewport(metrics: ViewportMetrics): void {
    this.viewportWidth = metrics.width;
    this.viewportHeight = metrics.height;
  }

  private captureFocus(): NormalizedFocus {
    return normalizedFocusFromPan(this.panX, this.panY, this.storedSize());
  }

  private restoreFocus(focus: NormalizedFocus, metrics: ViewportMetrics): void {
    const next = panForNormalizedFocus(focus, this.sizeFor(metrics));
    this.panX = next.x;
    this.panY = next.y;
  }

  private clampWith(metrics: ViewportMetrics): void {
    const next = clampPan(this.panX, this.panY, this.sizeFor(metrics));
    this.panX = next.x;
    this.panY = next.y;
  }

  setViewport(viewport: HTMLElement | null): void {
    if (viewport === this.viewport) {
      if (viewport) this.remapViewport();
      return;
    }

    if (this.viewport && this.viewportWidth > 0 && this.viewportHeight > 0) {
      this.pendingFocus = this.captureFocus();
    }

    this.viewport = viewport;
    if (!viewport) return;

    const metrics = this.measureViewport(viewport);
    if (!metrics) return;

    if (this.pendingFocus) {
      this.restoreFocus(this.pendingFocus, metrics);
      this.pendingFocus = null;
    } else {
      this.clampWith(metrics);
    }
    this.rememberViewport(metrics);
  }

  setNaturalSize(width: number, height: number): void {
    const nextWidth = width > 0 ? width : this.naturalWidth;
    const nextHeight = height > 0 ? height : this.naturalHeight;
    if (nextWidth === this.naturalWidth && nextHeight === this.naturalHeight && this.initializedNaturalSize) return;

    if (!this.initializedNaturalSize) {
      this.naturalWidth = nextWidth;
      this.naturalHeight = nextHeight;
      this.initializedNaturalSize = true;
      this.zoom = 1;
      this.panX = 0;
      this.panY = 0;
      this.pendingFocus = null;
      const metrics = this.measureViewport();
      if (metrics) this.rememberViewport(metrics);
      return;
    }

    const focus = this.pendingFocus ?? this.captureFocus();
    this.naturalWidth = nextWidth;
    this.naturalHeight = nextHeight;

    const metrics = this.measureViewport();
    if (metrics) {
      this.restoreFocus(focus, metrics);
      this.rememberViewport(metrics);
      this.pendingFocus = null;
    } else {
      this.pendingFocus = focus;
    }
  }

  remapViewport(): void {
    const metrics = this.measureViewport();
    if (!metrics) return;
    if (!this.viewportWidth || !this.viewportHeight) {
      this.rememberViewport(metrics);
      this.clampWith(metrics);
      return;
    }
    if (metrics.width === this.viewportWidth && metrics.height === this.viewportHeight) return;

    const focus = this.pendingFocus ?? this.captureFocus();
    this.restoreFocus(focus, metrics);
    this.rememberViewport(metrics);
    this.pendingFocus = null;
  }

  fit(): void {
    this.zoom = 1;
    this.panX = 0;
    this.panY = 0;
    this.pendingFocus = null;
    const metrics = this.measureViewport();
    if (metrics) this.rememberViewport(metrics);
  }

  actual(): void {
    const metrics = this.measureViewport();
    if (!metrics) {
      this.fit();
      return;
    }
    this.zoom = actualSizeZoom(
      metrics.width,
      metrics.height,
      this.naturalWidth,
      this.naturalHeight,
      this.minZoom,
      this.maxZoom,
    );
    this.panX = 0;
    this.panY = 0;
    this.pendingFocus = null;
    this.rememberViewport(metrics);
  }

  clamp(): void {
    this.remapViewport();
    const metrics = this.measureViewport();
    if (!metrics) return;
    this.clampWith(metrics);
    this.rememberViewport(metrics);
  }

  setZoom(next: number, anchorX: number | null = null, anchorY: number | null = null): void {
    this.remapViewport();
    const previous = this.zoom;
    const nextZoom = Math.max(this.minZoom, Math.min(this.maxZoom, next));
    if (anchorX !== null && anchorY !== null) {
      const nextPan = anchoredPan(this.panX, this.panY, previous, nextZoom, anchorX, anchorY);
      this.panX = nextPan.x;
      this.panY = nextPan.y;
    }
    this.zoom = nextZoom;
    this.clamp();
  }

  panBy(deltaX: number, deltaY: number): void {
    this.remapViewport();
    this.panX += deltaX;
    this.panY += deltaY;
    this.clamp();
  }

  wheel(event: WheelEvent): void {
    if (!this.viewport) return;
    this.remapViewport();
    const rect = this.viewport.getBoundingClientRect();
    const anchorX = event.clientX - rect.left - rect.width / 2;
    const anchorY = event.clientY - rect.top - rect.height / 2;
    this.setZoom(this.zoom * (event.deltaY < 0 ? 1.12 : 1 / 1.12), anchorX, anchorY);
  }
}
