import {expect, test} from "./fixture";

test("four KPI tiles render as figures, not charts", async ({page}) => {
  await page.goto("/analytics");
  await expect(page.getByTestId("kpi-tile")).toHaveCount(4);
  await expect(page.getByTestId("kpi-tile").first().locator("svg")).toHaveCount(0);
});

test("the single-series chart has no legend", async ({page}) => {
  await page.goto("/analytics");
  await expect(page.getByTestId("views-chart")).toBeVisible();
  await expect(page.getByTestId("chart-legend")).toHaveCount(0);
});

test("only the max and latest bars are directly labelled", async ({page}) => {
  await page.goto("/analytics");
  const bars = await page.getByTestId("bar").count();
  expect(bars).toBeGreaterThan(4);
  await expect(page.getByTestId("bar-label")).toHaveCount(2);
});

test("bars are anchored to the baseline with rounded data-ends", async ({page}) => {
  await page.goto("/analytics");
  const bar = page.getByTestId("bar").first();
  await expect(bar).toHaveAttribute("rx", "4");
  const [barBox, axisBox] = [await bar.boundingBox(), await page.getByTestId("x-axis").boundingBox()];
  expect(Math.abs(barBox!.y + barBox!.height - axisBox!.y)).toBeLessThan(2);
});

test("hovering a column shows day and count", async ({page}) => {
  await page.goto("/analytics");
  await page.getByTestId("bar-hit").first().hover();
  await expect(page.getByTestId("chart-tooltip")).toContainText(/\d+ view/);
});

test("a table view exposes the same numbers", async ({page}) => {
  await page.goto("/analytics");
  await page.getByRole("button", {name: "Table view"}).click();
  const rows = await page.getByTestId("chart-table-row").count();
  expect(rows).toBe(await page.getByTestId("bar").count());
});

test("every timeline event carries an icon and a text label", async ({page}) => {
  await page.goto("/analytics");
  for (const row of await page.getByTestId("timeline-event").all()) {
    await expect(row.getByTestId("event-icon")).toBeVisible();
    await expect(row.getByTestId("event-label")).not.toBeEmpty();
  }
});

test("the chart has exactly one value axis", async ({page}) => {
  await page.goto("/analytics");
  await expect(page.getByTestId("y-axis")).toHaveCount(1);
});
