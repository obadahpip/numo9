/**
 * Message API (S-01-T10, next-intl since A-10-T13). Message descriptors are written with
 * `defineMessages` so `formatjs extract` collects them and the eslint formatjs rules check them;
 * catalogues live in `frontend/messages/<locale>.json` (nested keys, ICU MessageFormat).
 *
 * - Components (client, and sync server components): `const fm = useFormatMessage();`
 *   then `fm(messages.title)` or `fm(messages.count, { count: 3 })`.
 * - Async server components and metadata: `const fm = await getFormatMessage()` from
 *   `@/i18n/server`.
 *
 * Rules: every user-visible string is a message; ids are dotted lower-camel keys
 * (`area.screen.item`); `defaultMessage` is the en-CA source text.
 */
import { useTranslations } from "next-intl";
import { useCallback } from "react";

export interface MessageDescriptor {
  id: string;
  defaultMessage: string;
  description?: string;
}

/** Values for ICU arguments, e.g. `{practice}` in "via {practice}". */
export type MessageValues = Record<string, string | number | Date>;

export type FormatMessage = (descriptor: MessageDescriptor, values?: MessageValues) => string;

export function defineMessages<K extends string>(
  messages: Record<K, MessageDescriptor>,
): Record<K, MessageDescriptor> {
  return messages;
}

/** Formatter for the active locale (next-intl `useTranslations`). */
export function useFormatMessage(): FormatMessage {
  const t = useTranslations();
  return useCallback<FormatMessage>(
    (descriptor, values) => t(descriptor.id as never, values as never),
    [t],
  );
}
