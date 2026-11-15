import { useEffect, useState } from "react";

/** The directory's search waits this long after the last key before asking the server (V-01-T10). */
export const SEARCH_DEBOUNCE_MS = 150;

/** The value of `value`, `delay` ms after it last changed. */
export function useDebounced<T>(value: T, delay: number): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setSettled(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return settled;
}
