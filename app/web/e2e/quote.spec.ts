import {expect, test} from "./fixture";

test("optional line changes the total only when selected", async ({page}) => {
  await page.goto("/proposals/prop_northwind/quote");
  const total = page.getByTestId("total-minor");
  const before = await total.textContent();
  let recalculated = page.waitForResponse((response) =>
    response.request().method() === "POST"
      && response.url().endsWith("/v1/proposal-versions/version_northwind/quote/calculate"),
  );
  await page.getByTestId("line-optional-training").click();
  await recalculated;
  await expect(total).not.toHaveText(before!);
  recalculated = page.waitForResponse((response) =>
    response.request().method() === "POST"
      && response.url().endsWith("/v1/proposal-versions/version_northwind/quote/calculate"),
  );
  await page.getByTestId("line-optional-training").click();
  await recalculated;
  await expect(total).toHaveText(before!);
});

test("total equals subtotal minus discount plus tax", async ({page}) => {
  await page.goto("/proposals/prop_northwind/quote");
  await page.getByLabel("Discount").fill("500.00");
  await page.getByLabel("Tax").fill("120.00");
  await page.getByRole("button", {name: "Recalculate"}).click();
  const read = async (id: string) =>
    Number((await page.getByTestId(id).getAttribute("data-minor"))!);
  expect(await read("total-minor")).toBe(
    (await read("subtotal-minor")) - (await read("discount-minor")) + (await read("tax-minor")),
  );
});

test("payment installments sum to the total", async ({page}) => {
  await page.goto("/proposals/prop_northwind/quote");
  const parts = await page.getByTestId("installment").all();
  const sum = (await Promise.all(parts.map(async (part) =>
    Number((await part.getAttribute("data-minor"))!),
  ))).reduce((a, b) => a + b, 0);
  expect(sum).toBe(Number((await page.getByTestId("total-minor").getAttribute("data-minor"))!));
});

test("an over-policy discount requires quote approval and says why", async ({page}) => {
  await page.goto("/proposals/prop_northwind/quote");
  await page.getByLabel("Discount").fill("500.00");
  await page.getByRole("button", {name: "Recalculate"}).click();
  await expect(page.getByText(/review required/i)).toBeVisible();
  await expect(page.getByText(/requires quote approval/)).toBeVisible();
});

test("every line names its pricing rule version", async ({page}) => {
  await page.goto("/proposals/prop_northwind/quote");
  for (const row of await page.getByTestId("quote-line").all()) {
    await expect(row.getByTestId("rule-version")).toHaveText("2026.1");
  }
});
