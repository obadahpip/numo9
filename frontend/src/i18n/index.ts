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

/** Resolve a message from the en-CA catalogue, falling back to its default message. */
export function formatMessage(descriptor: MessageDescriptor): string {
  return lookup(enCA as Catalog, descriptor.id) ?? descriptor.defaultMessage;
}
