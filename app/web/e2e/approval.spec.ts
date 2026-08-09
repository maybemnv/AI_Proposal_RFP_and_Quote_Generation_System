import {expect, test} from "@playwright/test";

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

test("approving the last approval locks the version", async ({page}) => {
  await page.goto("/proposals/prop_ready/approval?as=proposal_approver");
  await page.getByTestId("approval-proposal").getByRole("button", {name: "Approve"}).click();
  await expect(page.getByText("Locked")).toBeVisible();
  await expect(page.getByRole("button", {name: "Approve"})).toHaveCount(0);
});
