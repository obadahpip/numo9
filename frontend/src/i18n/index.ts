/**
 * Minimal message API (S-01-T10). Message descriptors are written with `defineMessages`
 * so `formatjs extract` can collect them; catalogues live in `frontend/messages/<locale>.json`
 * (nested keys, next-intl compatible). A-10-T13 replaces the runtime with next-intl, keeping
 * the same ids and catalogues.
 *
 * Rules: every user-visible string is a message; ids are dotted lower-camel keys
 * (`area.screen.item`); `defaultMessage` is the en-CA source text.
 */
import enCA from "../../messages/en-CA.json";

export interface MessageDescriptor {
  id: string;
  defaultMessage: string;
  description?: string;
}

interface Catalog {
  [key: string]: string | Catalog;
}

export function defineMessages<K extends string>(
  messages: Record<K, MessageDescriptor>,
): Record<K, MessageDescriptor> {
  return messages;
}

function lookup(catalog: Catalog, id: string): string | undefined {
  let node: string | Catalog | undefined = catalog;
  for (const part of id.split(".")) {
    if (node === undefined || typeof node === "string") return undefined;
    node = node[part];
  }
  return typeof node === "string" ? node : undefined;
}

/** Values for simple ICU arguments, e.g. `{practice}` in "via {practice}". */
export type MessageValues = Record<string, string | number>;

const ARGUMENT = /\{([a-zA-Z][a-zA-Z0-9]*)\}/g;

/**
 * Resolve a message from the en-CA catalogue, falling back to its default message, and fill simple
 * `{name}` arguments (A-01-T14). Numbers are formatted for en-CA. Plural/select arguments arrive
 * with next-intl in A-10-T13.
 */
export function formatMessage(descriptor: MessageDescriptor, values?: MessageValues): string {
  const text = lookup(enCA as Catalog, descriptor.id) ?? descriptor.defaultMessage;
  if (values === undefined) return text;
  return text.replace(ARGUMENT, (whole, name: string) => {
    const value = values[name];
    if (value === undefined) return whole;
    return typeof value === "number" ? value.toLocaleString("en-CA") : value;
  });
}
