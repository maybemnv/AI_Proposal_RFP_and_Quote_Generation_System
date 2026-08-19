import {expect, test} from "./fixture";

test("importing a hubspot opportunity lands normalized", async ({page}) => {
  await page.goto("/opportunities");
  await page.getByLabel("Provider").selectOption("hubspot");
  await page.getByRole("button", {name: "Import"}).click();
  await expect(page.getByRole("row", {name: /Northwind Retail Group/}).getByText("normalized", {exact: false})).toBeVisible();
});

test("a failed import shows the adapter failure with its code", async ({page}) => {
  await page.goto("/opportunities");
  await page.getByLabel("Outcome").selectOption("failure");
  await page.getByRole("button", {name: "Import"}).click();
  await expect(page.getByText("AUTH")).toBeVisible();
  await expect(page.getByText(/token expired/i)).toBeVisible();
});

test("every claim-backed block exposes its evidence", async ({page}) => {
  await page.goto("/proposals/prop_northwind");
  const chips = page.getByTestId("source-chip");
  await expect(chips.first()).toBeVisible();
  await chips.first().click();
  await expect(page.getByTestId("evidence-excerpt")).toBeVisible();
});

test("resolving the open question clears the scope warning", async ({page}) => {
  await page.goto("/proposals/prop_northwind/scope");
  await expect(page.getByText("Open question")).toBeVisible();
  await page.getByTestId("resolve-open-question").first().click();
  await page.getByLabel("Resolution").fill("Legacy CMS stays on v4 through Q4.");
  await page.getByRole("button", {name: "Confirm"}).click();
  await expect(page.getByText("Open question")).toHaveCount(0);
});
