"use client";

import { Button, Checkbox, Switch } from "@numo9/ui";
import { useId } from "react";

import { useFormatMessage, type MessageDescriptor } from "@/i18n";

import { FILTER_KEYS, type DirectoryState, type FacetValue, type FilterKey } from "./api";
import { m } from "./messages";

export const FACET_TITLES: Record<FilterKey, MessageDescriptor> = {
  package: m.facetPackage,
  status: m.facetStatus,
  province: m.facetProvince,
  fye: m.facetFye,
  gst_cycle: m.facetGstCycle,
  payroll: m.facetPayroll,
  overdue: m.facetOverdue,
  unfiled: m.facetUnfiled,
  tag: m.facetTag,
};

export interface FiltersPanelProps {
  facets: Partial<Record<FilterKey, FacetValue[]>>;
  state: DirectoryState;
  onToggle: (filter: FilterKey, value: string, on: boolean) => void;
  onArchived: (on: boolean) => void;
  onClose: () => void;
}

/**
 * Filters panel (V-01-T11): one group per filter; each option shows how many organisations the
 * list would show with that option added (the server's facet counts — every other filter
 * applied), so choosing it narrows the list to exactly that number. Options with 0 stay, dimmed.
 * Each group is a `fieldset` with its `legend`; the count is part of the checkbox's name.
 */
export function FiltersPanel({ facets, state, onToggle, onArchived, onClose }: FiltersPanelProps) {
  const t = useFormatMessage();
  const headingId = useId();
  return (
    <aside
      aria-labelledby={headingId}
      data-filters-panel=""
      className="flex w-full shrink-0 flex-col gap-3 rounded-lg border border-border bg-surface p-3 md:w-72"
    >
      <div className="flex items-center justify-between">
        <h2 id={headingId} className="text-base font-bold text-fg">
          {t(m.filtersTitle)}
        </h2>
        <Button variant="ghost" size="sm" onClick={onClose}>
          {t(m.filtersClose)}
        </Button>
      </div>
      <div className="flex max-h-[60vh] flex-col gap-3 overflow-y-auto pe-1 md:max-h-none">
        {FILTER_KEYS.map((key) => {
          const options = facets[key] ?? [];
          const selected = state.filters[key] ?? [];
          return (
            <fieldset key={key} className="flex flex-col gap-1" data-facet={key}>
              <legend className="mb-1 text-xs font-bold tracking-wide text-fg-muted uppercase">
                {t(FACET_TITLES[key])}
              </legend>
              {options.length === 0 ? (
                <p className="text-sm text-fg-muted">{t(m.facetNone)}</p>
              ) : (
                options.map((option) => (
                  <div
                    key={option.value}
                    className="flex items-center justify-between gap-2"
                    data-option={option.value}
                    data-count={option.count}
                  >
                    <Checkbox
                      label={
                        <span className={option.count === 0 ? "text-fg-muted" : undefined}>
                          {option.label}
                          <span className="sr-only">
                            {t(m.filterCount, { count: option.count })}
                          </span>
                        </span>
                      }
                      checked={selected.includes(option.value)}
                      onCheckedChange={(checked) => onToggle(key, option.value, checked === true)}
                    />
                    <span aria-hidden="true" className="text-sm text-fg-muted tabular-nums">
                      {new Intl.NumberFormat().format(option.count)}
                    </span>
                  </div>
                ))
              )}
            </fieldset>
          );
        })}
        <Switch
          label={t(m.showArchived)}
          checked={state.archived}
          onCheckedChange={(checked) => onArchived(checked)}
        />
      </div>
      <p className="text-xs text-fg-muted">{t(m.filtersHint)}</p>
    </aside>
  );
}
