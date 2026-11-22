import { calculateTax } from "./calculator";

/**
 * G-01-T13 — the client calculator gives the server's numbers (backend
 * tests/test_tax_calculator.py: the same 2026 matrix, to the cent).
 */
const PROVINCES: Record<string, string[]> = {
  AB: ["5"],
  BC: ["5", "7"],
  MB: ["5", "7"],
  NB: ["15"],
  NL: ["15"],
  NS: ["14"],
  NT: ["5"],
  NU: ["5"],
  ON: ["13"],
  PE: ["15"],
  QC: ["5", "9.975"],
  SK: ["5", "6"],
  YT: ["5"],
};
const EXCLUSIVE: Record<string, [string[], string]> = {
  AB: [["5.00"], "105.00"],
  BC: [["5.00", "7.00"], "112.00"],
  MB: [["5.00", "7.00"], "112.00"],
  NB: [["15.00"], "115.00"],
  NL: [["15.00"], "115.00"],
  NS: [["14.00"], "114.00"],
  NT: [["5.00"], "105.00"],
  NU: [["5.00"], "105.00"],
  ON: [["13.00"], "113.00"],
  PE: [["15.00"], "115.00"],
  QC: [["5.00", "9.98"], "114.98"],
  SK: [["5.00", "6.00"], "111.00"],
  YT: [["5.00"], "105.00"],
};
const INCLUSIVE: Record<string, [string, string[]]> = {
  AB: ["95.24", ["4.76"]],
  BC: ["89.29", ["4.46", "6.25"]],
  MB: ["89.29", ["4.46", "6.25"]],
  NB: ["86.96", ["13.04"]],
  NL: ["86.96", ["13.04"]],
  NS: ["87.72", ["12.28"]],
  NT: ["95.24", ["4.76"]],
  NU: ["95.24", ["4.76"]],
  ON: ["88.50", ["11.50"]],
  PE: ["86.96", ["13.04"]],
  QC: ["86.97", ["4.35", "8.68"]],
  SK: ["90.09", ["4.50", "5.41"]],
  YT: ["95.24", ["4.76"]],
};

const parts = (rates: string[]) => rates.map((rate, i) => ({ key: `c${i}`, rate }));

describe.each(Object.keys(PROVINCES))("%s 2026", (prov) => {
  it("exclusive and inclusive 100.00 match the server to the cent", () => {
    const out = calculateTax(parts(PROVINCES[prov]!), "100.00");
    expect([out.components.map((c) => c.amount), out.gross]).toEqual(EXCLUSIVE[prov]);
    const back = calculateTax(parts(PROVINCES[prov]!), "100.00", { inclusive: true });
    expect([back.net, back.components.map((c) => c.amount)]).toEqual(INCLUSIVE[prov]);
    expect(back.gross).toBe("100.00");
  });
});

it("splits claimable and cost on purchases (50 % ITC on HST of 10.01; BC PST)", () => {
  const meals = calculateTax([{ key: "hst", rate: "13", claimablePct: 50 }], "10.01", {
    purchase: true,
  });
  expect([meals.tax, meals.claimable, meals.cost]).toEqual(["1.30", "0.65", "0.65"]);
  const bc = calculateTax(
    [
      { key: "gst", rate: "5", claimablePct: 100 },
      { key: "pst", rate: "7", claimablePct: 0 },
    ],
    "100.00",
    { purchase: true },
  );
  expect([bc.claimable, bc.cost]).toEqual(["5.00", "7.00"]);
});

it("handles tiny, refunds and no-tax amounts", () => {
  expect(calculateTax(parts(["13"]), "0.01", { inclusive: true })).toMatchObject({
    net: "0.01",
    tax: "0.00",
  });
  expect(calculateTax(parts(["13"]), "-113.00", { inclusive: true })).toMatchObject({
    net: "-100.00",
    tax: "-13.00",
  });
  expect(calculateTax([], "12.34").gross).toBe("12.34");
});

it("round-trips exclusive → inclusive exactly over many amounts", () => {
  for (let cents = 1; cents < 5000; cents += 37) {
    const net = (cents / 100).toFixed(2);
    for (const rates of Object.values(PROVINCES)) {
      const forward = calculateTax(parts(rates), net);
      expect(calculateTax(parts(rates), forward.gross, { inclusive: true }).net).toBe(net);
    }
  }
});
