import {expect, test} from "@playwright/test";

test("Trace A clicks the demo path from capture through delivery", async ({page}) => {
  await page.goto("/opportunities");
  await page.getByRole("button", {name: "Import"}).click();
  await expect(page.getByRole("row", {name: /Northwind Retail Group/})).toBeVisible();
  await page.getByLabel("Outcome").selectOption("failure");
  await page.getByRole("button", {name: "Import"}).click();
  await expect(page.getByText("AUTH")).toBeVisible();

  await page.goto("/proposals/prop_northwind");
  await page.getByTestId("source-chip").first().click();
  await expect(page.getByTestId("evidence-excerpt")).toBeVisible();

  await page.goto("/proposals/prop_northwind/scope");
  await page.getByTestId("resolve-open-question").click();
  await page.getByLabel("Resolution").fill("Legacy CMS stays on v4 through Q4.");
  await page.getByRole("button", {name: "Confirm"}).click();
  await expect(page.getByText("Scope is ready for the next gate.")).toBeVisible();

  await page.goto("/proposals/prop_northwind/quote");
  const before = await page.getByTestId("total-minor").getAttribute("data-minor");
  await page.getByTestId("line-optional-training").check();
  await expect(page.getByTestId("total-minor")).not.toHaveAttribute("data-minor", before!);
  await page.getByTestId("line-optional-training").uncheck();
  await page.getByLabel("Discount").fill("9000.00");
  await page.getByRole("button", {name: "Recalculate"}).click();
  await expect(page.getByText("Review required")).toBeVisible();

  await page.goto("/proposals/prop_ready/approval?as=proposal_approver");
  await page.getByTestId("approval-proposal").getByRole("button", {name: "Approve"}).click();
  await expect(page.getByText("Locked")).toBeVisible();

  await page.goto("/proposals/prop_ready/preview");
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", {name: "Download PDF"}).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/\.pdf$/);
  await page.goto("/analytics");
  await expect(page.getByTestId("views-chart")).toBeVisible();
});
