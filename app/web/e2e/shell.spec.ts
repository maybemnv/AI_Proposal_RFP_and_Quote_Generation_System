import { expect, test } from "@playwright/test";

test("shell renders navigation to every workspace route", async ({ page }) => {
  await page.goto("/");
  for (const label of ["Opportunities", "Content library", "Analytics"]) {
    await expect(page.getByRole("link", {name: label})).toBeVisible();
  }
});

test("money is formatted identically to the API", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("format-probe")).toHaveText("1,250.00 USD");
});

test("dark mode uses the selected dark tokens, not an inverted light palette", async ({ page }) => {
  await page.emulateMedia({colorScheme: "dark"});
  await page.goto("/");
  const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  expect(bg).toBe("rgb(17, 23, 28)");
});
