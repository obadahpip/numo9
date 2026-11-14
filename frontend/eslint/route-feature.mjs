/**
 * `numo9/route-feature` (U-01-T08): every route in the route registry declares the feature key
 * it needs — `feature: "accounting.journals.read"` — or `feature: CORE` when it is part of every
 * organisation (Home, Settings, audit log). The entitlement engine (U-03) gates routes from this
 * metadata (locked panel in place, never a redirect), so a route without it would escape gating.
 *
 * Checked: the object literals of the arrays assigned to the registry variables (option
 * `registries`, default `ORG_MODULES`). Each must have a `feature` property whose value is a
 * key literal `<product>.<area>.<action>` (action read, write or approve), the literal `"@core"`,
 * or a constant (an identifier such as `CORE`, resolved by TypeScript).
 */
const KEY = /^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)?\.[a-z][a-z0-9_]*\.(?:read|write|approve)$/;
const CORE = "@core";

function unwrap(node) {
  let current = node;
  while (
    current &&
    (current.type === "TSAsExpression" ||
      current.type === "TSSatisfiesExpression" ||
      current.type === "TSTypeAssertion")
  ) {
    current = current.expression;
  }
  return current;
}

function propertyName(property) {
  if (property.type !== "Property" || property.computed) return undefined;
  if (property.key.type === "Identifier") return property.key.name;
  if (property.key.type === "Literal") return String(property.key.value);
  return undefined;
}

function describe(objectNode) {
  const path = objectNode.properties.find((p) => propertyName(p) === "path");
  const value = path && unwrap(path.value);
  return value?.type === "Literal" ? String(value.value) : "(no path)";
}

export const routeFeature = {
  meta: {
    type: "problem",
    docs: {
      description: "Routes in the route registry must declare their feature key (U-01-T08).",
    },
    schema: [
      {
        type: "object",
        properties: { registries: { type: "array", items: { type: "string" } } },
        additionalProperties: false,
      },
    ],
    messages: {
      missing:
        "Route '{{path}}' declares no feature. Add `feature: \"<product>.<area>.<action>\"`, or `feature: CORE` when it is part of every organisation (U-01, docs/dev/feature-keys.md).",
      invalid:
        "Route '{{path}}' has feature '{{value}}': use a key '<product>.<area>.<action>' (read, write or approve) or CORE.",
    },
  },
  create(context) {
    const registries = new Set(context.options[0]?.registries ?? ["ORG_MODULES"]);
    return {
      VariableDeclarator(node) {
        if (node.id.type !== "Identifier" || !registries.has(node.id.name)) return;
        const array = unwrap(node.init);
        if (!array || array.type !== "ArrayExpression") return;
        for (const element of array.elements) {
          const entry = unwrap(element);
          if (!entry || entry.type !== "ObjectExpression") continue;
          const feature = entry.properties.find((p) => propertyName(p) === "feature");
          if (!feature) {
            context.report({ node: entry, messageId: "missing", data: { path: describe(entry) } });
            continue;
          }
          const value = unwrap(feature.value);
          if (value.type === "Literal") {
            const text = typeof value.value === "string" ? value.value : String(value.value);
            if (text !== CORE && !KEY.test(text)) {
              context.report({
                node: feature,
                messageId: "invalid",
                data: { path: describe(entry), value: text },
              });
            }
          } else if (value.type !== "Identifier" && value.type !== "MemberExpression") {
            context.report({
              node: feature,
              messageId: "invalid",
              data: { path: describe(entry), value: context.sourceCode.getText(value) },
            });
          }
        }
      },
    };
  },
};
