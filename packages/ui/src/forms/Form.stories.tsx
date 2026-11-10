import type { Meta, StoryObj } from "@storybook/react";

import { CheckboxField, SelectField, TextField } from "./Field";
import { Form } from "./Form";
import { formLabels, generalDefaults, generalSettingsSchema, provinceOptions } from "./fixtures";

/**
 * Form kit (A-10-T07): React Hook Form + Zod. Clear "Legal name" or type "12345" and submit:
 * inline errors, the error summary with links, and focus on the first error. Edit any field to
 * see the sticky save bar (Ctrl/⌘+S saves); click the link above the form to see the guard.
 */
const meta: Meta = { title: "Forms/Form kit" };
export default meta;

export const GeneralSettings: StoryObj = {
  render: () => (
    <div className="max-w-lg">
      <p className="mb-4 text-sm">
        <a className="text-fg-link underline" href="/o/maple-leaf/contacts">
          Go to Contacts (guarded)
        </a>
      </p>
      <Form
        aria-label="General settings"
        schema={generalSettingsSchema}
        defaultValues={generalDefaults}
        labels={formLabels}
        onSubmit={async () => {
          await new Promise((resolve) => setTimeout(resolve, 800));
        }}
        onLeave={() => undefined}
        className="grid gap-5"
      >
        <TextField name="legalName" label="Legal name" required hint="As registered with the CRA" />
        <SelectField name="province" label="Province" options={provinceOptions} required />
        <TextField name="postalCode" label="Postal code" required autoComplete="postal-code" />
        <CheckboxField name="newsletter" label="Send me product news" />
        <div>
          <button
            type="submit"
            className="min-h-touch-target rounded-md bg-surface-accent px-4 text-sm font-semibold text-fg-on-accent"
          >
            Save settings
          </button>
        </div>
      </Form>
    </div>
  ),
};
