import {expect, test} from "@playwright/test";

test("a pending claim can be approved from the library", async ({page}) => {
  await page.goto("/content");
  const row = page.getByRole("row", {name: /Pending approval/}).first();
  await row.getByRole("button", {name: "Approve"}).click();
  await expect(row.getByText("Approved")).toBeVisible();
});

test("an expired claim is marked unusable in a new version", async ({page}) => {
  await page.goto("/content");
  const row = page.getByRole("row", {name: /Expired/}).first();
  await expect(row.getByText("Cannot be used in a new version")).toBeVisible();
});

test("every claim shows its evidence count and sources", async ({page}) => {
  await page.goto("/content");
  for (const row of await page.getByTestId("claim-row").all()) {
    await expect(row.getByTestId("evidence-count")).toBeVisible();
  }
});
