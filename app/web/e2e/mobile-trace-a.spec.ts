import {expect, test} from "./fixture";

test("Trace A pricing controls remain visible and work on a narrow viewport", async ({page, request}) => {
  const created = await request.post("http://localhost:8106/v1/proposals", {
    data: {opportunityId: "opp_northwind", title: "Mobile Trace A quote"},
  });
  expect(created.ok()).toBeTruthy();
  const versionId = (await created.json()).version.id as string;

  await page.setViewportSize({width: 390, height: 844});
  await page.goto(`/proposals/${versionId}/quote`);

  const recalculate = page.getByRole("button", {name: "Recalculate"});
  await recalculate.scrollIntoViewIfNeeded();
  await expect(recalculate).toBeVisible();
  await expect(recalculate).toBeInViewport();
  const response = page.waitForResponse((item) =>
    item.request().method() === "POST"
      && item.url().endsWith(`/v1/proposal-versions/${versionId}/quote/calculate`),
  );
  await recalculate.click();
  expect((await response).status()).toBe(200);
  await expect(page.getByTestId("total-minor")).toBeVisible();
});
