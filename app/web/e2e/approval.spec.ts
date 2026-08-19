import {expect, test} from "./fixture";

test("submit is blocked while a flag is open and lists the flags", async ({page}) => {
  await page.goto("/proposals/prop_blocked/approval");
  await expect(page.getByRole("button", {name: "Submit for approval"})).toBeDisabled();
  await expect(page.getByText("UNRESOLVED_REQUIREMENT")).toBeVisible();
});

test("a reviewer cannot decide an approval outside their role", async ({page}) => {
  await page.goto("/proposals/prop_northwind/approval?as=content_editor");
  const quoteCard = page.getByTestId("approval-quote");
  await expect(quoteCard.getByRole("button", {name: "Approve"})).toBeDisabled();
  await expect(quoteCard.getByText("Requires quote approver")).toBeVisible();
});

test("approval failure stays visible instead of locally locking the version", async ({page}) => {
  await page.goto("/proposals/prop_ready/approval?as=proposal_approver");
  await page.getByTestId("approval-proposal").getByRole("button", {name: "Approve"}).click();
  await expect(page.getByText("approval approval-proposal was not found")).toBeVisible();
  await expect(page.getByText("Locked")).toHaveCount(0);
  await expect(page.getByTestId("approval-proposal").getByRole("button", {name: "Approve"})).toBeVisible();
});
