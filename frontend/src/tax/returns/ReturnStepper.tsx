/** The status stepper of a return: prepare → review → file (G-03-T11). */
import { cn } from "@numo9/ui";

import { useFormatMessage } from "@/i18n";

import { STEPS, stepIndex, type ReturnStatus } from "./api";
import { retm } from "./messages";

export function ReturnStepper({ status }: { status: ReturnStatus }) {
  const fm = useFormatMessage();
  const at = stepIndex(status);
  const finished = status === "filed" || status === "amended";
  return (
    <ol aria-label={fm(retm.steps)} className="flex flex-wrap gap-2" data-testid="return-stepper">
      {STEPS.map((step, index) => {
        const label = fm(retm.step, { step });
        const done = index < at || (finished && index === at);
        const current = index === at && !finished;
        return (
          <li
            key={step}
            aria-current={current ? "step" : undefined}
            className={cn(
              "flex items-center gap-2 rounded-full border px-3 py-1 text-sm",
              done && "border-border-success bg-surface-success",
              current && "border-fg-info font-semibold",
              !done && !current && "border-border text-fg-muted",
            )}
          >
            <span aria-hidden="true" className="tabular-nums">
              {index + 1}
            </span>
            <span>
              {done
                ? fm(retm.stepDone, { label })
                : current
                  ? fm(retm.stepCurrent, { label })
                  : label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
