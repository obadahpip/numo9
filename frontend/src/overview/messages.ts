import { defineMessages } from "@/i18n";

/** Shared overview cards (D-09-T06/T10): loading, error with retry and the support reference. */
export const m = defineMessages({
  loading: {
    id: "overview.card.loading",
    defaultMessage: "Loading {card}…",
    description: "Announced while an overview card loads; {card} is its title",
  },
  retry: { id: "overview.card.retry", defaultMessage: "Try again", description: "Button" },
  reference: {
    id: "overview.card.reference",
    defaultMessage: "Reference: {reference}",
    description: "Support reference of the failed request, under a card's error",
  },
  failed: {
    id: "overview.card.failed",
    defaultMessage: "{card} couldn't be loaded",
    description: "Error title of an overview card; {card} is its title",
  },
  offline: {
    id: "overview.card.offline",
    defaultMessage:
      "Numo9 couldn't be reached. Your connection may have dropped. Try again in a moment.",
    description: "Error body: the request never reached the server",
  },
  server: {
    id: "overview.card.server",
    defaultMessage:
      "Something went wrong on our side and nothing was changed. Try again; if it keeps failing, give support the reference below.",
    description: "Error body: the server answered 5xx",
  },
  denied: {
    id: "overview.card.denied",
    defaultMessage: "Your role doesn't include this information. Ask an administrator for access.",
    description: "Error body: the server answered 403",
  },
  other: {
    id: "overview.card.other",
    defaultMessage:
      "The request was refused. Try again; if it keeps failing, give support the reference below.",
    description: "Error body: another 4xx answer",
  },
});
