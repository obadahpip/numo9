import { readFileSync } from "node:fs";

import { build, loadTokens, THEME_CSS, TOKENS_CSS } from "./build-tokens.mjs";
import {
  cssValue,
  cssVar,
  flatten,
  kebab,
  renderThemeCss,
  renderTokensCss,
  resolveAlias,
  themeVar,
} from "./tokens-lib.mjs";

describe("token helpers", () => {
  it("kebab-cases camelCase names and keeps scale steps", () => {
    expect(kebab("accentSubtle")).toBe("accent-subtle");
    expect(kebab("2xl")).toBe("2xl");
    expect(kebab("0-5")).toBe("0-5");
  });

  it("flattens nested groups and inherits $type", () => {
    const tokens = flatten({
      color: { $type: "color", brand: { yellow: { $value: "#FFD100" } } },
      $description: "ignored",
    });
    expect(tokens).toEqual([
      { path: ["color", "brand", "yellow"], type: "color", value: "#FFD100" },
    ]);
  });

  it("names CSS variables; semantic drops its group and 'default'", () => {
    expect(cssVar(["color", "yellow", "50"])).toBe("--n9-color-yellow-50");
    expect(cssVar(["semantic", "surface", "default"])).toBe("--n9-surface");
    expect(cssVar(["semantic", "text", "onAccent"])).toBe("--n9-text-on-accent");
  });

  it("resolves aliases and rejects unknown or circular ones", () => {
    const tokens = flatten({
      a: { $value: "#000000" },
      b: { $value: "{a}" },
      c: { $value: "{b}" },
      x: { $value: "{y}" },
      y: { $value: "{x}" },
    });
    expect(resolveAlias(tokens, "{c}")).toBe("#000000");
    expect(() => resolveAlias(tokens, "{missing}")).toThrow(/unknown token alias/);
    expect(() => resolveAlias(tokens, "{x}")).toThrow(/circular/);
  });

  it("writes composite values as CSS", () => {
    expect(
      cssValue({ path: ["f"], type: "fontFamily", value: ["Inter", "Segoe UI", "sans-serif"] }),
    ).toBe('Inter, "Segoe UI", sans-serif');
    expect(
      cssValue({
        path: ["s"],
        type: "shadow",
        value: [{ color: "#0000001A", offsetX: "0px", offsetY: "1px", blur: "2px", spread: "0px" }],
      }),
    ).toBe("0px 1px 2px 0px #0000001a");
    expect(cssValue({ path: ["e"], type: "cubicBezier", value: [0.2, 0, 0, 1] })).toBe(
      "cubic-bezier(0.2, 0, 0, 1)",
    );
    expect(cssValue({ path: ["t"], type: "color", value: "{color.brand.black}" })).toBe(
      "var(--n9-color-brand-black)",
    );
  });

  it("maps tokens to Tailwind theme namespaces", () => {
    expect(themeVar(["semantic", "surface", "default"])).toBe("--color-surface");
    expect(themeVar(["semantic", "text", "muted"])).toBe("--color-fg-muted");
    expect(themeVar(["semantic", "border", "focus"])).toBe("--color-border-focus");
    expect(themeVar(["font", "size", "sm"])).toBe("--text-sm");
    expect(themeVar(["font", "lineHeight", "sm"])).toBe("--text-sm--line-height");
    expect(themeVar(["elevation", "2"])).toBe("--shadow-elevation-2");
    expect(themeVar(["size", "touchTarget"])).toBe("--spacing-touch-target");
    expect(themeVar(["space", "4"])).toBeNull();
  });
});

describe("tokens.json", () => {
  const tokens = loadTokens();

  it("every alias resolves to a literal", () => {
    for (const token of tokens) {
      const value = resolveAlias(tokens, token.value);
      expect(String(value)).not.toMatch(/^\{/);
    }
  });

  it("every colour is a 6- or 8-digit hex value", () => {
    for (const token of tokens.filter((t) => t.type === "color")) {
      expect(resolveAlias(tokens, token.value), token.path.join(".")).toMatch(
        /^#[0-9A-F]{6}([0-9A-F]{2})?$/i,
      );
    }
  });

  it("covers colour, type, spacing, radius and elevation (A-10-T01)", () => {
    const groups = new Set(tokens.map((t) => t.path[0]));
    for (const group of ["color", "semantic", "font", "space", "radius", "elevation"]) {
      expect(groups).toContain(group);
    }
  });

  it("breakpoints are literal in the theme (media queries cannot read var())", () => {
    const theme = renderThemeCss(tokens);
    expect(theme).toContain("--breakpoint-sm: 360px;");
    expect(theme).toContain("--breakpoint-xl: 1440px;");
    expect(theme).toContain("--color-*: initial;");
  });

  it("committed CSS matches tokens.json", () => {
    expect(readFileSync(TOKENS_CSS, "utf8")).toBe(renderTokensCss(tokens));
    expect(readFileSync(THEME_CSS, "utf8")).toBe(renderThemeCss(tokens));
    expect(build({ check: true }).stale).toEqual([]);
  });
});
