import type { Token } from "./tokens-lib.mjs";

export const TOKENS_FILE: string;
export const TOKENS_CSS: string;
export const THEME_CSS: string;
export function loadTokens(file?: string): Token[];
export function build(options?: { check?: boolean }): { tokens: number; stale: string[] };
