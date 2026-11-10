import type { CSSProperties } from "react";

import { cn } from "../primitives/cn";

export interface SkeletonProps {
  /** CSS width, e.g. "60%" or 120 (px). */
  width?: CSSProperties["width"];
  height?: CSSProperties["height"];
  shape?: "line" | "block" | "circle";
  className?: string;
}

/**
 * Skeleton placeholder (A-10-T12): the shape of content that is loading (Phase 0 UX principle 9:
 * no spinner longer than 300 ms without a skeleton). Decorative — wrap loading areas in
 * `LoadingRegion` so screen readers hear one "Loading…" message.
 */
export function Skeleton({ width = "100%", height, shape = "line", className }: SkeletonProps) {
  return (
    <span
      aria-hidden="true"
      data-skeleton=""
      className={cn(
        "block animate-pulse bg-surface-muted",
        shape === "circle" ? "rounded-full" : shape === "block" ? "rounded-lg" : "rounded",
        className,
      )}
      style={{
        width,
        height: height ?? (shape === "line" ? "0.75rem" : shape === "circle" ? width : "6rem"),
      }}
    />
  );
}

/** Paragraph of `lines` skeleton lines, the last one shorter. */
export function SkeletonText({ lines = 3 }: { lines?: number }) {
  return (
    <span className="grid gap-2" aria-hidden="true">
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} width={i === lines - 1 ? "60%" : "100%"} />
      ))}
    </span>
  );
}

/** Varying widths so skeleton rows don't look like a striped table. */
export function skeletonWidth(row: number, column: number): string {
  return `${50 + ((row + column) % 4) * 12}%`;
}

/** Table-shaped skeleton (rows × columns) for grids outside DataGrid. */
export function SkeletonTable({
  rows = 6,
  columns = 4,
  rowHeight = 44,
}: {
  rows?: number;
  columns?: number;
  rowHeight?: number;
}) {
  return (
    <div aria-hidden="true" className="grid">
      {Array.from({ length: rows }, (_, r) => (
        <div
          key={r}
          className="flex items-center gap-4 border-b border-border px-3"
          style={{ height: rowHeight }}
        >
          {Array.from({ length: columns }, (_, c) => (
            <div key={c} className="flex-1">
              <Skeleton width={skeletonWidth(r, c)} />
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

/** A loading area: announces `label` once (polite) and marks itself busy. */
export function LoadingRegion({
  label,
  children,
  className,
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div aria-busy="true" className={className}>
      <p role="status" className="sr-only">
        {label}
      </p>
      {children}
    </div>
  );
}
