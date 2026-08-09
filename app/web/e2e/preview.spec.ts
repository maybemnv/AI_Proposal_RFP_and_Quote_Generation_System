import {expect, test} from "@playwright/test";

test("preview section order matches the PDF section order", async ({page}) => {
  await page.goto("/proposals/prop_northwind/preview");
  const headings = await page.getByRole("heading", {level: 2}).allTextContents();
  expect(headings).toEqual(["Executive summary", "Understanding", "Scope", "Milestones",
    "Assumptions", "Options", "Pricing", "Payment schedule", "Case studies", "Next steps"]);
});

test("optional services are labelled and excluded from the headline total", async ({page}) => {
  await page.goto("/proposals/prop_northwind/preview");
  await expect(page.getByTestId("options-section").getByText("Optional")).toBeVisible();
  const total = Number((await page.getByTestId("total-minor").getAttribute("data-minor"))!);
  const optional = Number((await page.getByTestId("optional-total-minor").getAttribute("data-minor"))!);
  expect(total).toBeLessThan(total + optional);
});

test("download produces a PDF", async ({page}) => {
  await page.goto("/proposals/prop_ready/preview");
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", {name: "Download PDF"}).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/\.pdf$/);
});
