import type { Meta, StoryObj } from "@storybook/react";

import tokensJson from "../../tokens/tokens.json";
import { cssVar, flatten, resolveAlias, themeVar, type Token } from "../../scripts/tokens-lib.mjs";

/**
 * Foundations (A-10-T03): the brand tokens rendered from tokens/tokens.json, with the CSS variable
 * and the Tailwind utility each one produces. Screens use the semantic tokens only.
 */
const tokens = flatten(tokensJson);
const byGroup = (...prefix: string[]) =>
  tokens.filter((token) => prefix.every((part, i) => token.path[i] === part));
const literal = (token: Token) => String(resolveAlias(tokens, token.value));
const utility = (token: Token, prefix: string) =>
  `${prefix}-${(themeVar(token.path) ?? "").replace(/^--[a-z]+-/, "")}`;

function Swatch({ token, prefix }: { token: Token; prefix: string }) {
  return (
    <li className="flex items-center gap-3">
      <span
        className="size-10 shrink-0 rounded-md border border-border"
        style={{ background: `var(${cssVar(token.path)})` }}
      />
      <span className="min-w-0">
        <span className="block font-semibold">{token.path.slice(1).join(".")}</span>
        <code className="block text-xs text-fg-muted">
          {cssVar(token.path)} · {utility(token, prefix)} · {literal(token)}
        </code>
      </span>
    </li>
  );
}

function SwatchGroup({ title, list, prefix }: { title: string; list: Token[]; prefix: string }) {
  return (
    <section className="mb-8">
      <h2 className="mb-3 text-lg font-semibold">{title}</h2>
      <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {list.map((token) => (
          <Swatch key={token.path.join(".")} token={token} prefix={prefix} />
        ))}
      </ul>
    </section>
  );
}

const meta: Meta = {
  title: "Foundations/Tokens",
  parameters: { layout: "padded" },
};
export default meta;

type Story = StoryObj;

export const SemanticColours: Story = {
  render: () => (
    <div>
      <SwatchGroup title="Surfaces (bg-*)" list={byGroup("semantic", "surface")} prefix="bg" />
      <SwatchGroup title="Text (text-*)" list={byGroup("semantic", "text")} prefix="text" />
      <SwatchGroup
        title="Borders (border-*)"
        list={byGroup("semantic", "border")}
        prefix="border"
      />
    </div>
  ),
};

export const PrimitiveColours: Story = {
  render: () => (
    <div>
      {["brand", "yellow", "neutral", "red", "green", "amber", "blue"].map((palette) => (
        <SwatchGroup key={palette} title={palette} list={byGroup("color", palette)} prefix="bg" />
      ))}
    </div>
  ),
};

export const YellowBlackPairs: Story = {
  render: () => (
    <div className="grid gap-4 md:grid-cols-3">
      <div className="rounded-lg bg-surface-accent p-6 text-fg-on-accent">
        <p className="text-2xl font-bold">Numo9</p>
        <p>Black on yellow — primary button, brand mark</p>
      </div>
      <div className="rounded-lg bg-surface-inverse p-6 text-fg-inverse-accent">
        <p className="text-2xl font-bold">Numo9</p>
        <p>Yellow on black — active navigation item</p>
      </div>
      <div className="rounded-lg border border-border bg-surface p-6 text-fg-accent-strong">
        <p className="text-2xl font-bold">Numo9</p>
        <p>Dark yellow on white — yellow-hued text</p>
      </div>
    </div>
  ),
};

export const Typography: Story = {
  render: () => (
    <ul className="space-y-4">
      {byGroup("font", "size").map((token) => {
        const step = token.path[2] ?? "";
        return (
          <li key={step} className="flex items-baseline gap-6">
            <code className="w-40 shrink-0 text-xs text-fg-muted">
              text-{step} · {literal(token)}
            </code>
            <span
              style={{
                fontSize: `var(--n9-font-size-${step})`,
                lineHeight: `var(--n9-font-line-height-${step})`,
              }}
            >
              Numbers build a brighter tomorrow — $1,234.56
            </span>
          </li>
        );
      })}
    </ul>
  ),
};

export const SpacingRadiusElevation: Story = {
  render: () => (
    <div className="space-y-8">
      <section>
        <h2 className="mb-3 text-lg font-semibold">Spacing (4 px grid)</h2>
        <ul className="space-y-2">
          {byGroup("space").map((token) => (
            <li key={token.path.join(".")} className="flex items-center gap-4">
              <code className="w-28 text-xs text-fg-muted">
                space.{token.path[1]} · {literal(token)}
              </code>
              <span
                className="h-3 bg-surface-accent"
                style={{ width: `var(${cssVar(token.path)})` }}
              />
            </li>
          ))}
        </ul>
      </section>
      <section>
        <h2 className="mb-3 text-lg font-semibold">Radius</h2>
        <ul className="flex flex-wrap gap-4">
          {byGroup("radius").map((token) => (
            <li key={token.path.join(".")} className="text-center">
              <span
                className="block size-16 border-2 border-border-strong bg-surface-muted"
                style={{ borderRadius: `var(${cssVar(token.path)})` }}
              />
              <code className="text-xs text-fg-muted">rounded-{token.path[1]}</code>
            </li>
          ))}
        </ul>
      </section>
      <section>
        <h2 className="mb-3 text-lg font-semibold">Elevation</h2>
        <ul className="flex flex-wrap gap-6 bg-surface-subtle p-6">
          {byGroup("elevation").map((token) => (
            <li
              key={token.path.join(".")}
              className="flex size-28 items-center justify-center rounded-lg bg-surface"
              style={{ boxShadow: `var(${cssVar(token.path)})` }}
            >
              <code className="text-xs">shadow-elevation-{token.path[1]}</code>
            </li>
          ))}
        </ul>
      </section>
    </div>
  ),
};
