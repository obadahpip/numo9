import type { Token } from "./tokens-lib.mjs";

export interface ContrastPairsDoc {
  minRatio?: number;
  pairs: { foreground: string; background: string; use?: string }[];
}

export interface ContrastResult {
  foreground: string;
  background: string;
  fg: string;
  bg: string;
  ratio: number;
  min: number;
  pass: boolean;
  use?: string;
}

export function luminance(hex: string): number;
export function contrastRatio(a: string, b: string): number;
export function evaluatePairs(tokens: Token[], pairsDoc: ContrastPairsDoc): ContrastResult[];
