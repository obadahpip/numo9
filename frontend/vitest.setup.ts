import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// jsdom has no layout: give virtualised scrollers (DataGrid, A-10-T10) the height set in their
// style, as packages/ui/vitest.setup.ts does, so screens built on the grid render their rows.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
if (typeof HTMLElement !== "undefined") {
  globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;
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
  const clientWidth = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "clientWidth");
  Object.defineProperty(HTMLElement.prototype, "clientWidth", {
    configurable: true,
    get(this: HTMLElement) {
      if (this.hasAttribute("data-grid-scroller")) return 1024;
      return clientWidth?.get?.call(this) ?? 0;
    },
  });
}

afterEach(() => {
  cleanup();
});
