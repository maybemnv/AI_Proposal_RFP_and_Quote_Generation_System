import {expect, test} from "./fixture";
import type {APIRequestContext} from "@playwright/test";
import {readFile} from "node:fs/promises";

async function lockNorthwindProposal(request: APIRequestContext) {
  const apiUrl = "http://localhost:8106";
  const quote = {
    currency: "USD", discountMinor: 0, taxMinor: 0,
    lines: [
      {id: "line-strategy", label: "Strategy days", ruleId: "rule_strategy_day", quantity: 4, optional: false, selected: true, sourceRecordIds: []},
      {id: "line-optional-training", label: "Training session", ruleId: "rule_training", quantity: 1, optional: true, selected: false, sourceRecordIds: []},
    ],
  };
  expect((await request.post(`${apiUrl}/v1/proposal-versions/version_northwind/scope/resolve`, {
    data: {openQuestion: "req_legacy_cms", resolution: "Legacy CMS stays on v4 through Q4."},
  })).ok()).toBeTruthy();
  expect((await request.post(`${apiUrl}/v1/proposal-versions/version_northwind/quote/calculate`, {data: quote})).ok()).toBeTruthy();
  expect((await request.post(`${apiUrl}/v1/proposal-versions/version_northwind/generate`, {data: {
    templateId: "tmpl-consulting-v1", requestedSections: ["scope", "case_studies"],
    modelProvider: "claude", modelName: "claude-opus-5",
  }})).ok()).toBeTruthy();
  const validated = await request.post(`${apiUrl}/v1/proposal-versions/version_northwind/validate`);
  expect((await validated.json()).flags.filter((flag: {severity: string}) => flag.severity === "blocking")).toEqual([]);
  const submitted = await request.post(`${apiUrl}/v1/proposal-versions/version_northwind/submit`);
  const approvals = (await submitted.json()).approvals as {id: string; requiredRole: string}[];
  for (const approval of approvals) {
    expect((await request.post(`${apiUrl}/v1/approvals/${approval.id}/decide`, {data: {
      decision: "approved", reviewerId: `user-${approval.requiredRole}`, reviewerRole: approval.requiredRole,
    }})).ok()).toBeTruthy();
  }
}

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

test("download is the server-rendered PDF", async ({page, request}) => {
  await lockNorthwindProposal(request);
  await page.goto("/proposals/prop_northwind/preview");
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", {name: "Download PDF"}).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/\.pdf$/);
  const path = await download.path();
  expect(path).not.toBeNull();
  const bytes = await readFile(path!);
  expect(bytes.subarray(0, 4).toString("ascii")).toBe("%PDF");
  expect(bytes.length).toBeGreaterThan(1_000);
});
