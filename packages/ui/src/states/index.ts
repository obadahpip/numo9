/** State components (A-10-T12): empty, loading, error and explain (gated / permission / lock / 404). */
export { EmptyState, MAX_EMPTY_STATE_ACTIONS, type EmptyStateProps } from "./EmptyState";
export { ErrorState, type ErrorStateProps } from "./ErrorState";
export { ExplainPanel, type ExplainKind, type ExplainPanelProps } from "./ExplainPanel";
export { Illustration, type IllustrationName } from "./illustrations";
export {
  LoadingRegion,
  Skeleton,
  SkeletonTable,
  SkeletonText,
  skeletonWidth,
  type SkeletonProps,
} from "./Skeleton";
