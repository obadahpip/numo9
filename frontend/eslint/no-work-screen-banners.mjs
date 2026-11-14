/**
 * `numo9/no-work-screen-banners` (A-10-T17, gap-12; Phase 0 UX principle 15).
 *
 * Xero stacks three promotional banners above the invoice editor and pushes the form below the
 * fold. In Numo9, work screens (editors, lists, settings, dashboards) carry no promotional or
 * announcement banners:
 *
 * - system notices (maintenance, trial reminders, job results) go to the notification centre —
 *   the bell in the app shell (A-07);
 * - commercial messages appear only in Settings → Subscription and in the owner-controlled,
 *   dismissible announcement slot on Home — the files listed in the `allow` option.
 *
 * Reported inside work screens:
 * 1. a component whose name ends in `Banner` or starts with Promo/Promotion/Upsell/Marketing/Ad/
 *    Advert/Announcement (`<PromoCard>`, `<UpgradeBanner>`, `<Marketing.Hero>`);
 * 2. `role="banner"` — the only page banner is the app shell's top bar (`@numo9/ui` AppShell);
 * 3. a `className` with a `banner`, `promo`, `upsell` or `marquee` class;
 * 4. a `data-banner` or `data-promo` attribute.
 */
import { routeFeature } from "./route-feature.mjs";

const COMPONENT =
  /(?:Banner$)|^(?:Promo|Promotion|Upsell|Marketing|Ad|Advert|Announcement)(?:[A-Z]|$)/;
const CLASS_TOKEN = /(?:^|[\s:])(?:[\w-]*-)?(?:banner|promo|upsell|marquee)(?:-[\w-]*)?(?=\s|$)/i;
const DATA_ATTRIBUTE = /^data-(?:banner|promo)$/i;

const MESSAGE =
  "No promotional or announcement banners in work screens (gap-12). Send system notices to the " +
  "notification centre; commercial messages belong in Settings → Subscription or the Home " +
  "announcement slot.";

/** Minimal glob → RegExp (`**`, `*`, `?`, `[` and `]` literal) for the `allow` option. */
function globToRegExp(glob) {
  let source = "";
  for (let i = 0; i < glob.length; i += 1) {
    const char = glob[i];
    if (char === "*" && glob[i + 1] === "*") {
      source += ".*";
      i += 1;
      if (glob[i + 1] === "/") i += 1;
    } else if (char === "*") {
      source += "[^/]*";
    } else if (char === "?") {
      source += "[^/]";
    } else {
      source += char.replace(/[.+^${}()|[\]\\]/g, "\\$&");
    }
  }
  return new RegExp(`(?:^|/)${source}$`);
}

/** Every segment of an element name: `<Marketing.Hero>` → ["Marketing", "Hero"]. */
function nameSegments(node) {
  if (node.type === "JSXIdentifier") return [node.name];
  if (node.type === "JSXMemberExpression") {
    return [...nameSegments(node.object), ...nameSegments(node.property)];
  }
  if (node.type === "JSXNamespacedName") return [node.namespace.name, node.name.name];
  return [];
}

function staticString(value) {
  if (!value) return null;
  if (value.type === "Literal" && typeof value.value === "string") return value.value;
  if (value.type === "JSXExpressionContainer") {
    const expression = value.expression;
    if (expression.type === "Literal" && typeof expression.value === "string") {
      return expression.value;
    }
    if (expression.type === "TemplateLiteral") {
      return expression.quasis.map((quasi) => quasi.value.cooked ?? "").join(" ");
    }
  }
  return null;
}

/** @type {import("eslint").Rule.RuleModule} */
export const noWorkScreenBanners = {
  meta: {
    type: "problem",
    docs: {
      description:
        "Forbid promotional and announcement banners inside work screens (editor and list layouts)",
    },
    schema: [
      {
        type: "object",
        properties: { allow: { type: "array", items: { type: "string" } } },
        additionalProperties: false,
      },
    ],
    messages: {
      component: `<{{name}}>: ${MESSAGE}`,
      role: `role="banner": ${MESSAGE} The only page banner is the app shell's top bar.`,
      className: `class "{{value}}": ${MESSAGE}`,
      data: `{{name}}: ${MESSAGE}`,
    },
  },
  create(context) {
    const allow = (context.options[0]?.allow ?? []).map(globToRegExp);
    const filename = context.filename.replaceAll("\\", "/");
    if (allow.some((pattern) => pattern.test(filename))) return {};

    return {
      JSXOpeningElement(node) {
        const segments = nameSegments(node.name);
        const name = segments.join(".");
        if (segments.some((segment) => COMPONENT.test(segment))) {
          context.report({ node, messageId: "component", data: { name } });
        }
        for (const attribute of node.attributes) {
          if (attribute.type !== "JSXAttribute") continue;
          const attributeName =
            attribute.name.type === "JSXNamespacedName"
              ? `${attribute.name.namespace.name}:${attribute.name.name.name}`
              : attribute.name.name;
          const value = staticString(attribute.value);
          if (attributeName === "role" && value?.trim().split(/\s+/).includes("banner")) {
            context.report({ node: attribute, messageId: "role" });
          } else if ((attributeName === "className" || attributeName === "class") && value) {
            if (CLASS_TOKEN.test(value)) {
              context.report({ node: attribute, messageId: "className", data: { value } });
            }
          } else if (DATA_ATTRIBUTE.test(attributeName)) {
            context.report({ node: attribute, messageId: "data", data: { name: attributeName } });
          }
        }
      },
    };
  },
};

/**
 * Files allowed to show commercial messages: Settings → Subscription and the Home announcement
 * slot (owner-controlled, dismissible). Nothing else may be added without a plan change.
 */
export const BANNER_ALLOWED_FILES = [
  "src/app/o/[org]/settings/subscription/**",
  "src/components/announcements/HomeAnnouncementSlot.tsx",
];

const plugin = {
  meta: { name: "eslint-plugin-numo9" },
  rules: {
    "no-work-screen-banners": noWorkScreenBanners,
    // Routes declare their feature key (U-01-T08).
    "route-feature": routeFeature,
  },
};

export default plugin;
