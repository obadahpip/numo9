/** Types for tokens-lib.mjs (A-10-T03). */
export interface Token {
  path: string[];
  type: string | undefined;
  value: unknown;
}

export function kebab(name: string): string;
export function flatten(node: object, path?: string[], inheritedType?: string): Token[];
export function cssVar(path: string[]): string;
export function resolveAlias(tokens: Token[], value: unknown, seen?: Set<string>): unknown;
export function cssValue(token: Token): string;
export function renderTokensCss(tokens: Token[]): string;
export function themeVar(path: string[]): string | null;
export function renderThemeCss(tokens: Token[]): string;
