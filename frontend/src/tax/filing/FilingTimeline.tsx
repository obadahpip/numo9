"use client";

/**
 * Filing periods timeline (G-03a-T18, wireframe 65): one block per period of a registration,
 * sized by its days and coloured by what it needs (filed green, open blue, due soon amber,
 * overdue red — the state is also written, never colour alone); a marker where each filing
 * frequency takes effect; a hover / focus card with the dates, the sequence number and the
 * return and payment due dates (an asterisk on a due date moved to the next business day).
 * The blocks are the API's periods, in its order: no gap, no overlap — except a **"Not
 * registered" band** (G-03b-T11, wireframe 70) from the day after a stop to the day before the
 * restart (open-ended while stopped), with a stop marker at its start and a restart marker at
 * its end.
 */
import { CloseIcon, LockIcon, Tooltip, formatDate, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";

import { useFormatMessage } from "@/i18n";

import {
  blockState,
  daysIn,
  type BlockState,
  type FilingCycle,
  type FilingPeriod,
  type RegistrationGap,
} from "./api";
import { fmsg, frequencyLabels, kindLabels, stateLabels } from "./messages";
import { smsg } from "./stopMessages";

/** Width (in days) of a band still open: a stopped registration has no end date. */
const OPEN_GAP_DAYS = 90;
const DAY = 86_400_000;
const shift = (day: string, days: number) =>
  new Date(Date.parse(`${day}T00:00:00Z`) + days * DAY).toISOString().slice(0, 10);

const TONES: Record<BlockState, string> = {
  filed: "bg-surface-success-subtle text-fg-success border-fg-success",
  open: "bg-surface-info-subtle text-fg-info border-fg-info",
  due_soon: "bg-surface-warning-subtle text-fg-warning border-fg-warning",
  overdue: "bg-surface-danger-subtle text-fg-danger border-fg-danger",
};
const STATES: BlockState[] = ["filed", "open", "due_soon", "overdue"];

export interface FilingTimelineProps {
  periods: FilingPeriod[];
  cycles: FilingCycle[];
  /** Called with a custom period when its block's remove action is used (T20). */
  onRemoveCustom?: (period: FilingPeriod) => void;
  /** Not-registered spans between a stop and a restart (G-03b-T11). */
  gaps?: RegistrationGap[];
}

function GapBand({ gap }: { gap: RegistrationGap }) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const date = (day: string) => formatDate(day, { locale });
  const dates = gap.end
    ? fm(smsg.gapDates, { start: date(gap.start), end: date(gap.end) })
    : fm(smsg.gapOpen, { start: date(gap.start) });
  return (
    <li
      className="relative min-w-24"
      style={{
        flexGrow: gap.end ? daysIn(gap.start, gap.end) : OPEN_GAP_DAYS,
        flexBasis: 0,
      }}
      data-gap={gap.start}
      data-gap-end={gap.end ?? ""}
    >
      <span
        data-marker="stop"
        className="absolute -top-6 left-0 border-l-2 border-fg-danger pl-1 text-xs whitespace-nowrap text-fg-danger"
      >
        {fm(smsg.stopMarker, { date: date(shift(gap.start, -1)) })}
      </span>
      {gap.end ? (
        <span
          data-marker="restart"
          className="absolute -top-6 right-0 border-r-2 border-fg-success pr-1 text-xs whitespace-nowrap text-fg-success"
        >
          {fm(smsg.restartMarker, { date: date(shift(gap.end, 1)) })}
        </span>
      ) : null}
      <div
        role="img"
        aria-label={fm(smsg.gapName, { dates })}
        className="flex h-14 w-full flex-col items-center justify-center rounded-sm border border-dashed border-border bg-surface-subtle px-1.5 text-xs text-fg-muted"
      >
        <span aria-hidden="true" className="font-semibold">
          {fm(smsg.notRegistered)}
        </span>
        <span aria-hidden="true" className="truncate">
          {dates}
        </span>
      </div>
    </li>
  );
}

export function FilingTimeline({
  periods,
  cycles,
  onRemoveCustom,
  gaps = [],
}: FilingTimelineProps) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const date = (day: string) => formatDate(day, { locale });
  const total = periods.reduce((sum, p) => sum + daysIn(p.start, p.end), 0);
  const first = periods[0]?.start ?? "";
  const anyRolled = periods.some((p) => p.due_rolled);
  // A marker sits before the first block starting on or after the cycle's date.
  const markers = new Map<string, FilingCycle>();
  for (const cycle of cycles) {
    const block = periods.find((p) => p.start >= cycle.effective_from) ?? null;
    if (block && (cycle.effective_from >= first || block === periods[0])) {
      markers.set(block.id, cycle);
    }
  }

  const blockFor = (period: FilingPeriod) => {
    const state = blockState(period);
    const marker = markers.get(period.id);
    const label = fm(fmsg.period, {
      n: period.sequence_no,
      start: date(period.start),
      end: date(period.end),
      state: fm(stateLabels[state]),
    });
    return (
      <li
        key={period.id}
        className="relative min-w-10"
        style={{ flexGrow: daysIn(period.start, period.end), flexBasis: 0 }}
        data-period={period.start}
        data-state={state}
        data-kind={period.kind}
        data-share={total ? (daysIn(period.start, period.end) / total).toFixed(4) : "0"}
      >
        {marker ? (
          <span
            data-switch={marker.effective_from}
            className="absolute -top-6 left-0 border-l-2 border-fg pl-1 text-xs whitespace-nowrap text-fg"
          >
            {fm(fmsg.switchMarker, {
              frequency: fm(frequencyLabels[marker.frequency]),
              date: date(marker.effective_from),
            })}
          </span>
        ) : null}
        <Tooltip
          content={
            <span className="flex flex-col gap-0.5 text-xs" data-hover-card="">
              <strong>{fm(fmsg.sequence, { n: period.sequence_no })}</strong>
              <span>
                {fm(fmsg.periodDates, { start: date(period.start), end: date(period.end) })}
              </span>
              <span>
                {fm(fmsg.kindState, {
                  kind: fm(kindLabels[period.kind]),
                  state: fm(stateLabels[state]),
                })}
              </span>
              <span>
                {fm(period.due_rolled ? fmsg.returnDueRolled : fmsg.returnDue, {
                  date: date(period.due_date),
                })}
              </span>
              <span>{fm(fmsg.paymentDue, { date: date(period.payment_due_date) })}</span>
            </span>
          }
        >
          <button
            type="button"
            className={`flex h-14 w-full flex-col items-start justify-center overflow-hidden rounded-sm border px-1.5 text-left text-xs ${TONES[state]} ${
              period.kind === "custom" ? "border-dashed" : ""
            }`}
          >
            <span className="sr-only">{label}</span>
            <span aria-hidden="true" className="inline-flex items-center gap-1 font-semibold">
              {state === "filed" ? (
                <span data-testid="period-lock" className="inline-flex">
                  <LockIcon />
                </span>
              ) : null}
              {period.sequence_no}
            </span>
            <span aria-hidden="true" className="truncate">
              {fm(stateLabels[state])}
            </span>
          </button>
        </Tooltip>
        {period.kind === "custom" && onRemoveCustom && state !== "filed" ? (
          <button
            type="button"
            className="mt-1 text-xs text-fg underline"
            onClick={() => onRemoveCustom(period)}
            aria-label={fm(fmsg.removeCustom, {
              start: date(period.start),
              end: date(period.end),
            })}
          >
            <CloseIcon />
          </button>
        ) : null}
      </li>
    );
  };

  return (
    <section aria-label={fm(fmsg.timeline)} data-filing-timeline="">
      <ol className="flex w-full items-stretch gap-px overflow-x-auto pt-6 pb-1">
        {periods.flatMap((period, index) => {
          // A band goes before the first period after it, or after the last period.
          const before = gaps.filter(
            (g) =>
              g.start <= period.start && (index === 0 || g.start > (periods[index - 1]?.end ?? "")),
          );
          const after =
            index === periods.length - 1 ? gaps.filter((g) => g.start > period.end) : [];
          return [
            ...before.map((g) => <GapBand key={`gap-${g.start}`} gap={g} />),
            blockFor(period),
            ...after.map((g) => <GapBand key={`gap-${g.start}`} gap={g} />),
          ];
        })}
      </ol>
      <ul aria-label={fm(fmsg.legend)} className="mt-2 flex flex-wrap gap-3 text-xs text-fg-muted">
        {STATES.map((state) => (
          <li key={state} className="flex items-center gap-1.5">
            <span aria-hidden="true" className={`size-3 rounded-sm border ${TONES[state]}`} />
            {fm(stateLabels[state])}
          </li>
        ))}
        {anyRolled ? <li>{fm(fmsg.rolledNote)}</li> : null}
      </ul>
    </section>
  );
}
