import {expect, test} from "./fixture";

test("submit is blocked while a flag is open and lists the flags", async ({page}) => {
  await page.goto("/proposals/prop_blocked/approval");
  await expect(page.getByRole("button", {name: "Submit for approval"})).toBeDisabled();
  await expect(page.getByText("UNRESOLVED_REQUIREMENT")).toBeVisible();
});

test("a reviewer cannot decide an approval outside their role", async ({page, request}) => {
  const apiUrl = "http://localhost:8106";
  expect((await request.post(`${apiUrl}/v1/proposal-versions/version_northwind/scope/resolve`, {
    data: {openQuestion: "req_legacy_cms", resolution: "Legacy CMS stays on v4 through Q4."},
  })).ok()).toBeTruthy();
  expect((await request.post(`${apiUrl}/v1/proposal-versions/version_northwind/quote/calculate`, {data: {
    currency: "USD", discountMinor: 0, taxMinor: 0,
    lines: [
      {id: "line-strategy", label: "Strategy days", ruleId: "rule_strategy_day", quantity: 4, optional: false, selected: true, sourceRecordIds: []},
      {id: "line-optional-training", label: "Training session", ruleId: "rule_training", quantity: 1, optional: true, selected: false, sourceRecordIds: []},
    ],
  }})).ok()).toBeTruthy();
  expect((await request.post(`${apiUrl}/v1/proposal-versions/version_northwind/generate`, {data: {
    templateId: "tmpl-consulting-v1", requestedSections: ["scope", "case_studies"],
    modelProvider: "claude", modelName: "claude-opus-5",
  }})).ok()).toBeTruthy();
  expect((await request.post(`${apiUrl}/v1/proposal-versions/version_northwind/validate`)).ok()).toBeTruthy();
  expect((await request.post(`${apiUrl}/v1/proposal-versions/version_northwind/submit`)).ok()).toBeTruthy();

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
