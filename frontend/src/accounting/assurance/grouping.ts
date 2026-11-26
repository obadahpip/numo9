/**
 * Findings grouped by rule (K-09-T21): one group per rule, most severe first, then by name; the
 * items of a group by amount (largest first). The score's tone follows the bands of the
 * wireframe (≥ 80 good, ≥ 50 fair, below poor).
 */
import type { Finding, Severity } from "./api";

export const SEVERITIES: readonly Severity[] = ["critical", "warning", "info"];

export interface FindingGroup {
  rule: string;
  name: string;
  severity: Severity;
  findings: Finding[];
}

const RANK: Record<Severity, number> = { critical: 0, warning: 1, info: 2 };

function size(amount: string | null): number {
  return amount === null ? 0 : Math.abs(Number(amount));
}

export function groupFindings(findings: readonly Finding[]): FindingGroup[] {
  const groups = new Map<string, FindingGroup>();
  for (const finding of findings) {
    const group = groups.get(finding.rule);
    if (group) {
      group.findings.push(finding);
      if (RANK[finding.severity] < RANK[group.severity]) group.severity = finding.severity;
    } else {
      groups.set(finding.rule, {
        rule: finding.rule,
        name: finding.rule_name,
        severity: finding.severity,
        findings: [finding],
      });
    }
  }
  const list = [...groups.values()];
  for (const group of list) group.findings.sort((a, b) => size(b.amount) - size(a.amount));
  return list.sort((a, b) => RANK[a.severity] - RANK[b.severity] || a.name.localeCompare(b.name));
}

export type ScoreTone = "success" | "warning" | "danger";

export function scoreTone(score: number): ScoreTone {
  if (score >= 80) return "success";
  if (score >= 50) return "warning";
  return "danger";
}
