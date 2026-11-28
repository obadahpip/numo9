"use client";

/**
 * Rule settings (K-09-T23, wireframe A4), the *Rule settings* tab of Assurance: every rule with
 * its on/off toggle, severity and parameters. Each parameter is validated as it is typed against
 * the rule's schema (type, minimum, maximum, choices) and shown inline; *Save* sends what changed
 * per rule (`PATCH assurance/rules/<code>`, audited server side) and the next run uses it
 * ("Changes apply on the next run"). *Reset to defaults* puts every rule back to its defaults
 * (then Save). Viewing needs `accounting.assurance.view`; saving needs `…manage` (the server
 * refuses otherwise and the message is shown).
 */
import { Badge, Button, EmptyState, ErrorState, INPUT_BASE } from "@numo9/ui";
import { useCallback, useEffect, useId, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { assuranceApi, type RuleParam, type RuleSetting, type Severity } from "./api";
import { SEVERITIES } from "./grouping";
import { am } from "./messages";
import {
  changesOf,
  defaultDraft,
  draftOf,
  problemsOf,
  type ParamProblem,
  type RawValue,
  type RuleDraft,
} from "./ruleSettings";

function ParamField({
  id,
  param,
  value,
  problem,
  onChange,
}: {
  id: string;
  param: RuleParam;
  value: RawValue;
  problem: ParamProblem | undefined;
  onChange: (value: RawValue) => void;
}) {
  const fm = useFormatMessage();
  const errorId = `${id}-error`;
  const border = problem ? "border-border-danger" : "border-border";
  const shared = {
    id,
    "aria-invalid": problem ? true : undefined,
    "aria-describedby": problem ? errorId : undefined,
    "data-param": param.name,
  } as const;
  let control;
  if (param.kind === "bool") {
    control = (
      <input
        {...shared}
        type="checkbox"
        className="size-5"
        checked={value === true}
        onChange={(event) => onChange(event.target.checked)}
      />
    );
  } else if (param.kind === "choice") {
    control = (
      <select
        {...shared}
        className={`${INPUT_BASE} ${border}`}
        value={String(value)}
        onChange={(event) => onChange(event.target.value)}
      >
        {param.choices.map((choice) => (
          <option key={choice} value={choice}>
            {fm(am.choice, { value: choice })}
          </option>
        ))}
      </select>
    );
  } else {
    const numeric = param.kind === "int" || param.kind === "decimal";
    control = (
      <input
        {...shared}
        type="text"
        inputMode={numeric ? (param.kind === "int" ? "numeric" : "decimal") : undefined}
        className={`${INPUT_BASE} ${border} ${numeric ? "w-28 text-end tabular-nums" : "w-40"}`}
        placeholder={param.kind === "codes" ? fm(am.codesHint) : undefined}
        title={param.kind === "codes" ? fm(am.codesHint) : undefined}
        value={String(value)}
        onChange={(event) => onChange(event.target.value)}
      />
    );
  }
  return (
    <div className="flex flex-col gap-1">
      <label
        htmlFor={id}
        className={
          param.kind === "bool"
            ? "flex items-center gap-2 text-sm text-fg"
            : "flex flex-col gap-1 text-sm text-fg"
        }
      >
        {param.kind === "bool" ? control : null}
        <span>{param.label}</span>
        {param.kind === "bool" ? null : control}
      </label>
      {problem ? (
        <p id={errorId} className="text-xs font-medium text-fg-danger" data-param-error="">
          {fm(am.paramProblem, {
            kind: problem.kind,
            min: problem.kind === "min" ? problem.min : "",
            max: problem.kind === "max" ? problem.max : "",
          })}
        </p>
      ) : null}
    </div>
  );
}

export function RuleSettings({ org }: { org: string }) {
  const fm = useFormatMessage();
  const ids = useId();
  const [rules, setRules] = useState<RuleSetting[] | null>(null);
  const [drafts, setDrafts] = useState<Record<string, RuleDraft>>({});
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  /** Server refusals by rule code and parameter name. */
  const [refusals, setRefusals] = useState<Record<string, Record<string, string>>>({});

  const load = useCallback(async () => {
    const answer = await assuranceApi.rules(org).catch(() => null);
    if (answer?.status === 200 && Array.isArray(answer.body.rules)) {
      setRules(answer.body.rules);
      setDrafts(Object.fromEntries(answer.body.rules.map((r) => [r.code, draftOf(r)])));
      setFailed(false);
    } else setFailed(true);
  }, [org]);

  useEffect(() => {
    void load();
  }, [load]);

  const edit = (code: string, changes: Partial<RuleDraft>) => {
    setNotice("");
    setDrafts((current) => ({ ...current, [code]: { ...current[code]!, ...changes } }));
    setRefusals((current) => ({ ...current, [code]: {} }));
  };

  const problems = Object.fromEntries(
    (rules ?? []).map((rule) => [rule.code, problemsOf(rule, drafts[rule.code] ?? draftOf(rule))]),
  );
  const invalid = Object.values(problems).some((p) => Object.keys(p).length > 0);

  const save = async () => {
    if (!rules) return;
    setError("");
    setNotice("");
    if (invalid) {
      setError(fm(am.rulesFixErrors));
      return;
    }
    const pending = rules
      .map((rule) => ({ rule, changes: changesOf(rule, drafts[rule.code] ?? draftOf(rule)) }))
      .filter((p) => p.changes !== null);
    if (!pending.length) {
      setNotice(fm(am.rulesUnchanged));
      return;
    }
    setBusy(true);
    let saved = 0;
    const refused: Record<string, Record<string, string>> = {};
    const updated = new Map<string, RuleSetting>();
    for (const { rule, changes } of pending) {
      const answer = await assuranceApi.updateRule(org, rule.code, changes!).catch(() => null);
      if (answer?.status === 200) {
        saved += 1;
        updated.set(rule.code, answer.body);
      } else {
        const detail = answer?.body?.detail || fm(am.failed);
        refused[rule.code] = { [answer?.body?.param ?? ""]: detail };
        setError(detail);
      }
    }
    setBusy(false);
    setRules((current) => (current ?? []).map((r) => updated.get(r.code) ?? r));
    setDrafts((current) => {
      const next = { ...current };
      for (const [code, rule] of updated) next[code] = draftOf(rule);
      return next;
    });
    setRefusals(refused);
    if (saved) setNotice(fm(am.rulesSaved, { count: saved }));
  };

  const reset = () => {
    setNotice("");
    setDrafts(Object.fromEntries((rules ?? []).map((r) => [r.code, defaultDraft(r)])));
  };

  if (failed) {
    return (
      <ErrorState
        title={fm(am.rulesLoadFailed)}
        retryLabel={fm(am.retry)}
        onRetry={() => void load()}
      />
    );
  }
  if (rules === null) return null;
  if (rules.length === 0) return <EmptyState title={fm(am.rulesLoadFailed)} compact />;

  return (
    <div className="flex flex-col gap-3" data-rule-settings="">
      <p className="text-sm text-fg-muted">{fm(am.rulesIntro)}</p>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-fg-muted">
            <th scope="col" className="py-1 text-start">
              {fm(am.ruleColumn)}
            </th>
            <th scope="col" className="py-1 text-start">
              {fm(am.onColumn)}
            </th>
            <th scope="col" className="py-1 text-start">
              {fm(am.severityColumn)}
            </th>
            <th scope="col" className="py-1 text-start">
              {fm(am.paramsColumn)}
            </th>
          </tr>
        </thead>
        <tbody>
          {rules.map((rule) => {
            const draft = drafts[rule.code] ?? draftOf(rule);
            const base = `${ids}-${rule.code}`;
            const changed = changesOf(rule, draft) !== null;
            const refusal = refusals[rule.code] ?? {};
            return (
              <tr
                key={rule.code}
                className="border-t border-border align-top"
                data-rule={rule.code}
                data-enabled={draft.enabled ? "true" : "false"}
              >
                <td className="max-w-md py-3 pe-3">
                  <p className="flex flex-wrap items-center gap-2 font-medium text-fg">
                    <span>{rule.name}</span>
                    {changed ? <Badge tone="info">{fm(am.changed)}</Badge> : null}
                  </p>
                  <p className="text-xs text-fg-muted">{rule.description}</p>
                  {rule.incremental ? (
                    <p className="text-xs text-fg-muted">{fm(am.onPosting)}</p>
                  ) : null}
                  {refusal[""] ? (
                    <p className="text-xs font-medium text-fg-danger">{refusal[""]}</p>
                  ) : null}
                </td>
                <td className="py-3 pe-3">
                  <input
                    type="checkbox"
                    role="switch"
                    className="size-5"
                    aria-label={fm(am.ruleOn, { rule: rule.name })}
                    aria-checked={draft.enabled}
                    checked={draft.enabled}
                    onChange={(event) => edit(rule.code, { enabled: event.target.checked })}
                  />
                </td>
                <td className="py-3 pe-3">
                  <select
                    aria-label={fm(am.severityOf, { rule: rule.name })}
                    className={`${INPUT_BASE} border-border`}
                    value={draft.severity}
                    onChange={(event) =>
                      edit(rule.code, { severity: event.target.value as Severity })
                    }
                  >
                    {SEVERITIES.map((severity) => (
                      <option key={severity} value={severity}>
                        {fm(am.severity, { severity })}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="py-3">
                  {rule.params.length === 0 ? (
                    <span className="text-xs text-fg-muted">{fm(am.noParams)}</span>
                  ) : (
                    <div className="flex flex-wrap gap-3">
                      {rule.params.map((param) => (
                        <div key={param.name} className="flex flex-col gap-1">
                          <ParamField
                            id={`${base}-${param.name}`}
                            param={param}
                            value={draft.values[param.name] ?? ""}
                            problem={problems[rule.code]?.[param.name]}
                            onChange={(value) =>
                              edit(rule.code, { values: { ...draft.values, [param.name]: value } })
                            }
                          />
                          {refusal[param.name] ? (
                            <p className="text-xs font-medium text-fg-danger">
                              {refusal[param.name]}
                            </p>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {error ? (
        <p role="alert" className="text-sm text-fg-danger">
          {error}
        </p>
      ) : null}
      <p role="status" className="text-sm text-fg-success">
        {notice}
      </p>
      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="secondary" disabled={busy} onClick={reset}>
          {fm(am.resetDefaults)}
        </Button>
        <Button variant="primary" disabled={busy || invalid} onClick={() => void save()}>
          {fm(am.save)}
        </Button>
      </div>
    </div>
  );
}
