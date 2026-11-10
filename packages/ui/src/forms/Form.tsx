"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  FormProvider,
  useForm,
  type DefaultValues,
  type FieldErrors,
  type FieldValues,
  type Resolver,
  type UseFormReturn,
} from "react-hook-form";
import type { z } from "zod";

import { ErrorSummary, type ErrorSummaryItem } from "./ErrorSummary";
import { StickySaveBar } from "./StickySaveBar";
import { UnsavedChangesDialog, useUnsavedChangesGuard } from "./useUnsavedChangesGuard";

/** Every visible string of the form kit (i18n messages from the app). */
export interface FormLabels {
  /** Error summary heading, e.g. (2) → "There are 2 problems with this form". */
  errorSummaryTitle: (count: number) => string;
  save: string;
  saving: string;
  discard: string;
  unsavedChanges: string;
  leaveTitle: string;
  leaveBody: string;
  stay: string;
  leave: string;
  close: string;
}

interface FormMeta {
  /** id of the form element, used to build field ids (`<formId>-<name>`). */
  formId: string;
  fieldId: (name: string) => string;
  labelFor: (name: string) => string | undefined;
  registerLabel: (name: string, label: string) => void;
}

const FormMetaContext = createContext<FormMeta | null>(null);

export function useFormMeta(): FormMeta {
  const meta = useContext(FormMetaContext);
  if (!meta) throw new Error("Form fields must be used inside <Form>.");
  return meta;
}

export interface FormProps<Schema extends z.ZodType<FieldValues, FieldValues>> {
  schema: Schema;
  defaultValues: DefaultValues<z.input<Schema>>;
  onSubmit: (
    values: z.output<Schema>,
    form: UseFormReturn<z.input<Schema>>,
  ) => void | Promise<void>;
  labels: FormLabels;
  children: ReactNode;
  /** Show the sticky save bar when there are unsaved changes (settings pages); default true. */
  saveBar?: boolean;
  /** Warn before leaving with unsaved changes; default true. */
  guard?: boolean;
  /** Navigation after "Leave" in the unsaved-changes dialog; defaults to a full page load. */
  onLeave?: (href: string) => void;
  /** Accessible name of the form (e.g. the page heading's text). */
  "aria-label"?: string;
  className?: string;
}

/**
 * Form kit (A-10-T07): React Hook Form + Zod.
 *
 * - Validation from the Zod schema; messages are the schema's (i18n) messages.
 * - Errors show inline under each field (`Field`) and, after a failed submit, in an error summary
 *   at the top with links to the fields; focus moves to the first field with an error (Phase 0
 *   UX principle 10, microcopy rules §3.5).
 * - Sticky save bar while there are unsaved changes (Save / Discard, Ctrl/⌘+S).
 * - Unsaved-changes guard: leaving the page (link, reload, close) asks first.
 */
export function Form<Schema extends z.ZodType<FieldValues, FieldValues>>({
  schema,
  defaultValues,
  onSubmit,
  labels,
  children,
  saveBar = true,
  guard = true,
  onLeave,
  className,
  ...aria
}: FormProps<Schema>) {
  type Input = z.input<Schema>;
  const form = useForm<Input>({
    // The resolver's output type is the schema output; RHF types the form by its input.
    resolver: zodResolver(schema as never) as unknown as Resolver<Input>,
    defaultValues,
    mode: "onTouched",
    shouldFocusError: false, // focus is moved below, in on-screen order
  });
  const formId = useId();
  const element = useRef<HTMLFormElement>(null);
  const labelsByName = useRef(new Map<string, string>());
  const [summary, setSummary] = useState<ErrorSummaryItem[] | null>(null);

  const fieldId = useCallback((name: string) => `${formId}-${name.replace(/\./g, "-")}`, [formId]);
  const meta = useMemo<FormMeta>(
    () => ({
      formId,
      fieldId,
      labelFor: (name) => labelsByName.current.get(name),
      registerLabel: (name, label) => {
        labelsByName.current.set(name, label);
      },
    }),
    [formId, fieldId],
  );

  const { isDirty, isSubmitting, errors } = form.formState;

  /** Errors in the order their fields appear on screen. */
  const orderedErrors = useCallback(
    (fieldErrors: FieldErrors): ErrorSummaryItem[] => {
      const flat = flattenErrors(fieldErrors);
      const position = (name: string) => {
        const node = document.getElementById(fieldId(name));
        const all = element.current ? [...element.current.querySelectorAll("[id]")] : [];
        return node ? all.indexOf(node) : Number.MAX_SAFE_INTEGER;
      };
      return flat
        .map((item) => ({
          ...item,
          id: fieldId(item.name),
          label: labelsByName.current.get(item.name),
        }))
        .sort((a, b) => position(a.name) - position(b.name));
    },
    [fieldId],
  );

  // Keep the summary in step while the user fixes fields.
  const errorKey = JSON.stringify(flattenErrors(errors));
  const showingSummary = summary !== null;
  useEffect(() => {
    if (!showingSummary) return;
    const next = orderedErrors(form.formState.errors);
    setSummary(next.length ? next : null);
    // errorKey captures every change to the errors.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [errorKey, showingSummary]);

  const submit = form.handleSubmit(
    async (values) => {
      setSummary(null);
      await onSubmit(values as z.output<Schema>, form);
    },
    (fieldErrors) => {
      const items = orderedErrors(fieldErrors);
      setSummary(items);
      const first = items[0];
      if (first) {
        const target = document.getElementById(first.id);
        if (target instanceof HTMLElement) target.focus();
        else form.setFocus(first.name as never);
      }
    },
  );

  const leaveGuard = useUnsavedChangesGuard(guard && isDirty && !isSubmitting, onLeave);

  return (
    <FormMetaContext.Provider value={meta}>
      <FormProvider {...form}>
        <form
          ref={element}
          id={formId}
          noValidate
          onSubmit={submit}
          className={className}
          {...aria}
        >
          {summary && summary.length ? (
            <ErrorSummary title={labels.errorSummaryTitle(summary.length)} items={summary} />
          ) : null}
          {children}
          {saveBar ? (
            <StickySaveBar
              visible={isDirty || isSubmitting}
              saving={isSubmitting}
              labels={labels}
              onSave={() => element.current?.requestSubmit()}
              onDiscard={() => {
                form.reset();
                setSummary(null);
              }}
            />
          ) : null}
        </form>
        <UnsavedChangesDialog guard={leaveGuard} labels={labels} />
      </FormProvider>
    </FormMetaContext.Provider>
  );
}

/** `{ address: { postalCode: { message } } }` → `[{ name: "address.postalCode", message }]`. */
export function flattenErrors(
  errors: FieldErrors,
  prefix = "",
): { name: string; message: string }[] {
  const items: { name: string; message: string }[] = [];
  for (const [key, value] of Object.entries(errors)) {
    if (!value || typeof value !== "object") continue;
    const name = prefix ? `${prefix}.${key}` : key;
    const message = (value as { message?: unknown }).message;
    if (typeof message === "string" && message) items.push({ name, message });
    else items.push(...flattenErrors(value as FieldErrors, name));
  }
  return items;
}
