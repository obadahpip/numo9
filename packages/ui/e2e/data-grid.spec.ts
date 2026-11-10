import { expect, test, type Page } from "@playwright/test";

/**
 * A-10-T10 acceptance: 10,000 rows scroll at 60 fps (Phase 0 plan: Playwright perf). The grid is
 * scrolled one step per animation frame for 3 s; frame durations come from requestAnimationFrame.
 * Virtualisation keeps the DOM small, so the frame time stays at the display's refresh interval.
 */
const STORY = "/iframe.html?id=data-datagrid--ten-thousand-rows&viewMode=story";

async function openGrid(page: Page) {
  await page.goto(STORY);
  const grid = page.getByRole("grid", { name: "Organisations" });
  await expect(grid).toHaveAttribute("aria-rowcount", "10001");
  return grid;
}

test("10,000 rows scroll at 60 fps with a bounded DOM", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openGrid(page);

  const result = await page.evaluate(async () => {
    const scroller = document.querySelector<HTMLElement>("[data-grid-scroller]")!;
    const frames: number[] = [];
    let maxRows = 0;
    const step = 96; // px per frame ≈ fast wheel/trackpad scrolling
    await new Promise<void>((done) => {
      let last = performance.now();
      const started = last;
      const tick = (now: number) => {
        frames.push(now - last);
        last = now;
        scroller.scrollTop += step;
        maxRows = Math.max(maxRows, scroller.querySelectorAll("tr[data-row-index]").length);
        if (now - started < 3000) requestAnimationFrame(tick);
        else done();
      };
      requestAnimationFrame(tick);
    });
    frames.shift(); // first delta includes the start-up wait
    const sorted = [...frames].sort((a, b) => a - b);
    const pct = (p: number) => sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * p))]!;
    const total = frames.reduce((a, b) => a + b, 0);
    const budget = 1000 / 60 + 3; // a 60 Hz frame plus timer jitter
    return {
      frames: frames.length,
      longFrames: frames
        .map((f, i) => ({ frame: i, ms: Math.round(f) }))
        .filter(({ ms }) => ms > budget),
      onBudget: frames.filter((f) => f <= budget).length / frames.length,
      fps: (frames.length * 1000) / total,
      median: pct(0.5),
      p95: pct(0.95),
      maxRows,
      scrolledTo: scroller.scrollTop,
    };
  });

  console.log(`DataGrid 10k scroll: ${JSON.stringify(result)}`);
  expect(result.scrolledTo).toBeGreaterThan(10_000);
  expect(result.maxRows).toBeLessThan(80); // virtualised: never 10,000 rows in the DOM
  // 60 fps: the typical (median) and 95th-percentile frame fit in a 60 Hz frame, and at least
  // 95 % of all frames do (the average is not used: one GC pause would dominate it).
  expect(result.median).toBeLessThanOrEqual(1000 / 60 + 1.5);
  expect(result.p95).toBeLessThanOrEqual(1000 / 60 + 3);
  expect(result.onBudget).toBeGreaterThanOrEqual(0.95);
});

test("keyboard: End and Home reach rows that were not rendered yet; Enter opens", async ({
  page,
}) => {
  const grid = await openGrid(page);
  const firstRow = grid.locator('tr[data-row-index="0"]');
  await firstRow.focus();
  await page.keyboard.press("End");
  await expect(grid.locator('tr[data-row-index="9999"]')).toBeFocused();
  await page.keyboard.press("PageUp");
  await expect(page.locator("tr[data-row-index]:focus")).toHaveAttribute(
    "data-row-index",
    /^99\d\d$/,
  );
  await page.keyboard.press("Home");
  await expect(firstRow).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("opened")).toHaveText("Opened Maple Bakery 1 Ltd.");
});

test("sort 10,000 rows and search stay responsive", async ({ page }) => {
  const grid = await openGrid(page);
  const started = Date.now();
  await grid.getByRole("button", { name: /Receivables/ }).click();
  await expect(grid.getByRole("columnheader", { name: /Receivables/ })).toHaveAttribute(
    "aria-sort",
    "ascending",
  );
  await page.getByRole("searchbox", { name: "Search organisations" }).fill("harbour emilie");
  await expect(page.getByRole("status")).toContainText("of 10,000 organisations");
  expect(Date.now() - started).toBeLessThan(3000);
});
