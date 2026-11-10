"use client";

import { useEffect, type ReactNode } from "react";
import {
  useController,
  useFormContext,
  type ControllerRenderProps,
  type FieldValues,
} from "react-hook-form";

import { Checkbox } from "../primitives/Checkbox";
import { Input, type InputProps } from "../primitives/Input";
import { Select, type SelectProps } from "../primitives/Select";
import { useFormMeta } from "./Form";

export interface FieldControlProps {
  /** id for the control (the label's `for`, the error summary's link target). */
  id: string;
  invalid: boolean;
  /** ids of the hint and the error message, for `aria-describedby`. */
  describedBy: string | undefined;
  required: boolean;
  field: ControllerRenderProps<FieldValues, string>;
}

export interface FieldProps {
  name: string;
  label: string;
  hint?: ReactNode;
  required?: boolean;
  /** Label hidden visually (still the accessible name), e.g. in a grid cell. */
  hideLabel?: boolean;
  /** Renders the control with the wiring above. */
  children: (control: FieldControlProps) => ReactNode;
  className?: string;
}

/**
 * A form field (A-10-T07): label, optional hint, the control and its inline error message, all
 * wired for assistive technology (`for`, `aria-describedby`, `aria-invalid`). Registers the label
 * so the error summary can name the field.
 */
export function Field({
  name,
  label,
  hint,
  required = false,
  hideLabel = false,
  children,
  className,
}: FieldProps) {
  const meta = useFormMeta();
  const { control } = useFormContext();
  const { field, fieldState } = useController({ name, control });
  const id = meta.fieldId(name);
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = fieldState.error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;

  useEffect(() => {
    meta.registerLabel(name, label);
  }, [meta, name, label]);

  return (
    <div className={className ?? "grid gap-1"} data-field={name}>
      <label htmlFor={id} className={hideLabel ? "sr-only" : "text-sm font-medium text-fg"}>
        {label}
        {required ? (
          <span aria-hidden="true" className="ms-0.5 text-fg-danger">
            *
          </span>
        ) : null}
      </label>
      {hint ? (
        <p id={hintId} className="text-xs text-fg-muted">
          {hint}
        </p>
      ) : null}
      {children({ id, invalid: Boolean(fieldState.error), describedBy, required, field })}
      {fieldState.error?.message ? (
        <p id={errorId} className="text-sm font-medium text-fg-danger">
          {fieldState.error.message}
        </p>
      ) : null}
    </div>
  );
}

type TextFieldProps = Omit<FieldProps, "children"> &
  Omit<InputProps, "name" | "id" | "value" | "defaultValue" | "onChange" | "onBlur" | "required">;

/** Text field: `Field` + `Input`. */
export function TextField({
  name,
  label,
  hint,
  required,
  hideLabel,
  className,
  ...input
}: TextFieldProps) {
  return (
    <Field
      name={name}
      label={label}
      hint={hint}
      required={required}
      hideLabel={hideLabel}
      className={className}
    >
      {({ id, invalid, describedBy, field }) => (
        <Input
          {...input}
          id={id}
          name={field.name}
          ref={field.ref}
          value={(field.value as string | undefined) ?? ""}
          onChange={field.onChange}
          onBlur={field.onBlur}
          invalid={invalid}
          aria-describedby={describedBy}
          aria-required={required || undefined}
        />
      )}
    </Field>
  );
}

type SelectFieldProps = Omit<FieldProps, "children"> &
  Pick<SelectProps, "options" | "placeholder" | "disabled">;

/** Select field: `Field` + `Select`. */
export function SelectField({
  name,
  label,
  hint,
  required,
  hideLabel,
  className,
  ...select
}: SelectFieldProps) {
  return (
    <Field
      name={name}
      label={label}
      hint={hint}
      required={required}
      hideLabel={hideLabel}
      className={className}
    >
      {({ id, invalid, describedBy, field }) => (
        <Select
          {...select}
          ref={field.ref}
          id={id}
          name={field.name}
          value={(field.value as string | undefined) || undefined}
          onValueChange={(value) => {
            field.onChange(value);
            field.onBlur();
          }}
          invalid={invalid}
          aria-describedby={describedBy}
        />
      )}
    </Field>
  );
}

/** Checkbox field: the box with its label on the right, error below. */
export function CheckboxField({
  name,
  label,
  hint,
}: {
  name: string;
  label: string;
  hint?: string;
}) {
  const meta = useFormMeta();
  const { control } = useFormContext();
  const { field, fieldState } = useController({ name, control });
  const id = meta.fieldId(name);
  const errorId = fieldState.error ? `${id}-error` : undefined;
  useEffect(() => {
    meta.registerLabel(name, label);
  }, [meta, name, label]);
  return (
    <div className="grid gap-1" data-field={name}>
      <Checkbox
        id={id}
        ref={field.ref}
        name={field.name}
        label={label}
        description={hint}
        checked={Boolean(field.value)}
        onCheckedChange={(checked) => field.onChange(checked === true)}
        onBlur={field.onBlur}
        invalid={Boolean(fieldState.error)}
        aria-errormessage={errorId}
      />
      {fieldState.error?.message ? (
        <p id={errorId} className="text-sm font-medium text-fg-danger">
          {fieldState.error.message}
        </p>
      ) : null}
    </div>
  );
}
