import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// jsdom lacks a few browser APIs that Radix primitives use (A-10-T06).
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;
Element.prototype.hasPointerCapture ??= () => false;
Element.prototype.releasePointerCapture ??= () => undefined;
Element.prototype.setPointerCapture ??= () => undefined;
Element.prototype.scrollIntoView ??= () => undefined;
// axe-core probes canvas for icon ligatures; jsdom has no canvas.
HTMLCanvasElement.prototype.getContext = (() =>
  null) as typeof HTMLCanvasElement.prototype.getContext;

// jsdom has no layout: give virtualised scrollers (DataGrid, A-10-T10) the height set in their style.
for (const property of ["clientHeight", "offsetHeight"] as const) {
  const original = Object.getOwnPropertyDescriptor(HTMLElement.prototype, property);
  Object.defineProperty(HTMLElement.prototype, property, {
    configurable: true,
    get(this: HTMLElement) {
      if (this.hasAttribute("data-grid-scroller")) return parseInt(this.style.height, 10) || 0;
      return original?.get?.call(this) ?? 0;
    },
  });
}
Object.defineProperty(HTMLElement.prototype, "clientWidth", {
  configurable: true,
  get(this: HTMLElement) {
    return this.hasAttribute("data-grid-scroller") ? 1024 : 0;
  },
});

afterEach(() => {
  cleanup();
});
